# store.py
# استمرارية البيانات بين عمليات النشر: مزامنة ملفات البيانات مع مستودع GitHub خاص.
# بدون إعداد يعمل كل شيء كما هو محلياً، ومع الإعداد تُسترجع البيانات تلقائياً بعد كل إعادة نشر.

import base64
import fnmatch
import glob
import hashlib
import json
import os
import urllib.error
import urllib.request

import streamlit as st

HERE = os.path.dirname(os.path.abspath(__file__))
API = "https://api.github.com"

# أنماط ملفات البيانات التي تُحفظ وتُسترجع (لا تشمل الكود ولا الملفات المرجعية الثابتة)
PATTERNS = ["hr_*.csv", "hr_*.json", "st_*.csv", "st_*.csv.gz", "st_*.json",
            "cashflow_*.csv", "cashflow_*.json", "bank_data.json"]
SKIP = {"st_shares.csv"}          # تُزامَن أيضاً، لكن تُستثنى عند طلب عدم مشاركة الروابط
MAX_MB = 45


def cfg():
    """إعدادات المستودع من st.secrets أو من متغيرات البيئة."""
    c = {}
    try:
        s = st.secrets.get("store", {})
        c = {k: str(s.get(k, "")) for k in ("repo", "token", "branch", "folder")}
    except Exception:
        c = {}
    for k, e in (("repo", "STORE_REPO"), ("token", "STORE_TOKEN"),
                 ("branch", "STORE_BRANCH"), ("folder", "STORE_FOLDER")):
        if not c.get(k):
            c[k] = os.environ.get(e, "")
    c["branch"] = c["branch"] or "main"
    c["folder"] = (c["folder"] or "data").strip("/")
    c["on"] = bool(c["repo"] and c["token"])
    return c


def _req(url, token, method="GET", payload=None):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    r = urllib.request.Request(url, data=data, method=method)
    r.add_header("Authorization", f"Bearer {token}")
    r.add_header("Accept", "application/vnd.github+json")
    r.add_header("X-GitHub-Api-Version", "2022-11-28")
    if data:
        r.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(r, timeout=45) as resp:
        return json.loads(resp.read().decode("utf-8") or "{}")


def _files():
    out = []
    for p in PATTERNS:
        out += glob.glob(os.path.join(HERE, p))
    return sorted(set(out))


def _md5(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def _listing(c):
    """محتويات مجلد البيانات في المستودع: الاسم ← (sha, الحجم)."""
    try:
        j = _req(f"{API}/repos/{c['repo']}/contents/{c['folder']}?ref={c['branch']}", c["token"])
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {}
        raise
    return {x["name"]: (x["sha"], x.get("size", 0)) for x in j if x.get("type") == "file"}


def status():
    """حالة المزامنة لعرضها في الواجهة."""
    c = cfg()
    if not c["on"]:
        return {"on": False, "msg": "المزامنة غير مفعّلة: لم تُضبط إعدادات المستودع في Secrets."}
    s = st.session_state.get("_store_state", {})
    return {"on": True, "repo": c["repo"], "branch": c["branch"], "folder": c["folder"],
            "msg": s.get("msg", ""), "pulled": s.get("pulled", []), "pushed": s.get("pushed", [])}


def pull(force=False):
    """يُستدعى مرة عند بدء الجلسة: ينزّل ملفات البيانات المفقودة محلياً."""
    if st.session_state.get("_store_pulled") and not force:
        return
    st.session_state["_store_pulled"] = True
    c = cfg()
    if not c["on"]:
        return
    got, err, rem = [], "", {}
    try:
        rem = _listing(c)
        for name, (sha, _sz) in rem.items():
            path = os.path.join(HERE, name)
            if os.path.exists(path) and not force:
                continue
            if not any(fnmatch.fnmatch(name, p) for p in PATTERNS):
                continue
            j = _req(f"{API}/repos/{c['repo']}/git/blobs/{sha}", c["token"])
            raw = base64.b64decode(j.get("content", ""))
            with open(path, "wb") as f:
                f.write(raw)
            got.append(name)
    except Exception as e:
        err = str(e)
    # البصمة تشمل ما هو موجود في المستودع فقط، فأي ملف محلي لم يُرفع بعد يُعدّ متغيّراً ويُحفظ تلقائياً
    try:
        st.session_state["_store_md5"] = {os.path.basename(p): _md5(p) for p in _files()
                                          if os.path.basename(p) in rem}
    except Exception:
        st.session_state["_store_md5"] = {}
    st.session_state["_store_state"] = {
        "pulled": got, "pushed": [],
        "msg": (f"تعذّر الاسترجاع: {err}" if err else
                (f"استُرجع {len(got)} ملفاً من المستودع." if got else "البيانات المحلية محدّثة."))}


def snap(reset=False):
    """بصمة الملفات الحالية لمعرفة ما تغيّر خلال التشغيل."""
    cur = {os.path.basename(p): _md5(p) for p in _files()}
    if reset or "_store_md5" not in st.session_state:
        st.session_state["_store_md5"] = cur
    return cur


def push():
    """يُستدعى في نهاية كل تشغيل: يرفع ما تغيّر من ملفات البيانات فقط."""
    c = cfg()
    if not c["on"]:
        return
    try:
        cur = {os.path.basename(p): _md5(p) for p in _files()}
    except Exception:
        return
    old = st.session_state.get("_store_md5", {})
    dirty = [n for n, h in cur.items() if old.get(n) != h]
    if not dirty:
        s = st.session_state.get("_store_state", {})
        if s.get("pushed"):
            s["pushed"] = []
            st.session_state["_store_state"] = s
        return
    sent, err = [], ""
    try:
        rem = _listing(c)
        for name in dirty:
            path = os.path.join(HERE, name)
            if os.path.getsize(path) > MAX_MB * 1024 * 1024:
                continue
            with open(path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("ascii")
            body = {"message": f"data: {name}", "content": b64, "branch": c["branch"]}
            if name in rem:
                body["sha"] = rem[name][0]
            _req(f"{API}/repos/{c['repo']}/contents/{c['folder']}/{name}", c["token"], "PUT", body)
            sent.append(name)
            st.session_state["_store_md5"][name] = cur[name]
    except Exception as e:
        err = str(e)
    s = st.session_state.get("_store_state", {})
    s["pushed"] = sent
    s["msg"] = (f"تعذّر الحفظ في المستودع: {err}" if err
                else (f"حُفظ {len(sent)} ملفاً في المستودع." if sent else s.get("msg", "")))
    st.session_state["_store_state"] = s


def ui(unlocked):
    """لوحة حالة المزامنة داخل مركز البيانات."""
    c = cfg()
    st.markdown("#### ☁️ استمرارية البيانات بعد إعادة النشر")
    if not c["on"]:
        st.warning(
            "المزامنة غير مفعّلة، فالبيانات المرفوعة تضيع مع كل إعادة نشر. لتفعيلها: أنشئ مستودعاً "
            "**خاصاً** على GitHub للبيانات وحدها (غير مستودع المنصة)، ثم أضف في إعدادات Secrets:\n"
            "```toml\n[store]\nrepo = \"owner/delta-platform-data\"\ntoken = \"github_pat_...\"\n"
            "branch = \"main\"\nfolder = \"data\"\n```\n"
            "الصلاحية المطلوبة للتوكن: Contents · Read and write على ذلك المستودع وحده. "
            "لا تستخدم مستودع المنصة نفسه لأن كل حفظ سيعيد تشغيل التطبيق.")
        st.caption("حتى تُفعَّل المزامنة، استخدم زر النسخة الاحتياطية الشاملة قبل أي إعادة نشر واستعدها بعدها.")
        return
    s = status()
    n = len(_files())
    c1, c2, c3 = st.columns(3)
    c1.metric("المستودع", c["repo"].split("/")[-1])
    c2.metric("ملفات البيانات", f"{n:,}")
    c3.metric("آخر عملية", f"{len(s.get('pulled', []))} استرجاع · {len(s.get('pushed', []))} حفظ")
    if s.get("msg"):
        st.caption(s["msg"])
    if not unlocked:
        st.info("المزامنة تلقائية. أدخل كلمة السر للتحكم اليدوي.")
        return
    a, b = st.columns(2)
    if a.button("⬆️ حفظ البيانات في المستودع الآن", use_container_width=True, key="store_push"):
        st.session_state["_store_md5"] = {}
        push()
        st.success(status().get("msg", "تم."))
    if b.button("⬇️ استرجاع البيانات من المستودع (يستبدل المحلي)", use_container_width=True, key="store_pull"):
        pull(force=True)
        st.cache_data.clear()
        st.success(status().get("msg", "تم."))
        st.rerun()
