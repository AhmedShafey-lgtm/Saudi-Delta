# share.py
# مشاركة تبويب واحد من المنصة برابط مستقل: رمز في الرابط + رمز سري اختياري + تاريخ انتهاء،
# والجلسة المشتركة للعرض فقط ولا ترى بقية التبويبات ولا مركز رفع البيانات.

import datetime as dt
import hashlib
import hmac
import os
import secrets

import pandas as pd
import streamlit as st

HERE = os.path.dirname(os.path.abspath(__file__))
FILE = os.path.join(HERE, "st_shares.csv")
COLS = ["الرمز", "الوصف", "التبويب", "الموقع", "ينتهي في", "رمز سري", "فعّال", "أنشئ في", "آخر فتح", "عدد مرات الفتح"]

# التبويبات القابلة للمشاركة: المفتاح ← الاسم المعروض
TAB_LABELS = {
    "deck": "🎞️ العرض التقديمي",
    "exec": "📈 الملخص التنفيذي",
    "kpis": "📉 المؤشرات المالية الشاملة",
    "company": "🏢 تحليل الشركة",
    "zakat": "🧮 الزكاة وضريبة الدخل",
    "banks": "🏦 البنوك والتسهيلات",
    "cashflow": "💧 التدفقات النقدية الفعلية الشهرية",
    "sites": "📍 تقارير المواقع",
    "hr": "👷 الموارد البشرية",
}
SITES = ["الكل", "الرياض", "مكة", "تبوك", "عسير", "الباحة"]

CSS = """
<style>
  [data-testid="stSidebar"], [data-testid="collapsedControl"] { display: none !important; }
  .sh-bar { direction: rtl; background: linear-gradient(90deg,#0B2A6F,#1E3A8A); color: #fff;
            border-radius: 10px; padding: 10px 16px; margin-bottom: 10px; display: flex;
            justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;
            font-family: 'Segoe UI', Tahoma, sans-serif; }
  .sh-bar b { font-size: 1.05rem; }
  .sh-bar span { font-size: .85rem; opacity: .85; }
  .sh-lock { direction: rtl; max-width: 420px; margin: 12vh auto; text-align: center;
             font-family: 'Segoe UI', Tahoma, sans-serif; }
</style>
"""


def _hash(token, pin):
    return hashlib.sha256(f"{token}|{pin}".encode("utf-8")).hexdigest() if str(pin).strip() else ""


def load():
    if not os.path.exists(FILE):
        return pd.DataFrame(columns=COLS)
    try:
        D = pd.read_csv(FILE, dtype=str).fillna("")
    except Exception:
        return pd.DataFrame(columns=COLS)
    for c in COLS:
        if c not in D.columns:
            D[c] = ""
    return D[COLS]


def save(D):
    try:
        D.to_csv(FILE, index=False, encoding="utf-8-sig")
        return True, ""
    except Exception as e:
        return False, str(e)


def _token():
    return secrets.token_urlsafe(9).replace("-", "a").replace("_", "b")


def _param():
    try:
        v = st.query_params.get("k")
    except Exception:
        try:
            v = st.experimental_get_query_params().get("k", [None])[0]
        except Exception:
            v = None
    return str(v).strip() if v else ""


def active():
    """صف المشاركة الفعّال إن كان الرابط يحمل رمزاً صالحاً، وإلا None."""
    k = _param()
    if not k:
        return None
    D = load()
    if not len(D):
        return None
    R = D[D["الرمز"].astype(str).str.strip() == k]
    if not len(R):
        return {"_خطأ": "رابط غير معروف."}
    r = R.iloc[0].to_dict()
    if str(r.get("فعّال", "")).strip() not in ("1", "True", "نعم", "true"):
        return {"_خطأ": "تم إيقاف هذا الرابط."}
    d = str(r.get("ينتهي في", "")).strip()
    if d:
        try:
            if dt.date.fromisoformat(d) < dt.date.today():
                return {"_خطأ": f"انتهت صلاحية هذا الرابط في {d}."}
        except Exception:
            pass
    return r


def _touch(token):
    D = load()
    m = D["الرمز"].astype(str).str.strip() == token
    if not m.any():
        return
    D.loc[m, "آخر فتح"] = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    try:
        n = int(float(D.loc[m, "عدد مرات الفتح"].iloc[0] or 0))
    except Exception:
        n = 0
    D.loc[m, "عدد مرات الفتح"] = str(n + 1)
    save(D)


def _stop(msg):
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown(f'<div class="sh-lock"><h3>🔒 الرابط غير متاح</h3><p>{msg}</p>'
                '<p style="color:#64748B">راجع الإدارة المالية لإصدار رابط جديد.</p></div>',
                unsafe_allow_html=True)
    st.stop()


def gate(share, renderers, ctx, build, cv=None):
    """يعرض التبويب المشارَك وحده ثم يوقف تنفيذ بقية الصفحة."""
    st.markdown(CSS, unsafe_allow_html=True)
    if share.get("_خطأ"):
        _stop(share["_خطأ"])
    tab = str(share.get("التبويب", "")).strip()
    if tab not in renderers:
        _stop("التبويب المرتبط بهذا الرابط غير متاح في هذه النسخة.")
    # الرمز السري إن وُجد
    h = str(share.get("رمز سري", "")).strip()
    if h:
        ok_key = "sh_ok_" + str(share["الرمز"])
        if not st.session_state.get(ok_key):
            st.markdown('<div class="sh-lock"><h3>🔒 رابط محمي</h3>'
                        '<p>أدخل الرمز السري للاطلاع على التقرير.</p></div>', unsafe_allow_html=True)
            c = st.columns([1, 2, 1])[1]
            pin = c.text_input("الرمز السري", type="password", key="sh_pin")
            if pin:
                if hmac.compare_digest(_hash(share["الرمز"], pin), h):
                    st.session_state[ok_key] = True
                    st.rerun()
                else:
                    c.error("رمز غير صحيح.")
            st.stop()
    exp = str(share.get("ينتهي في", "")).strip()
    st.markdown(
        f'<div class="sh-bar"><b>{TAB_LABELS.get(tab, tab)} — شركة دلتا السعودية</b>'
        f'<span>{share.get("الوصف", "")}'
        + (f" · صالح حتى {exp}" if exp else "")
        + ' · عرض فقط</span></div>', unsafe_allow_html=True)
    C = dict(ctx)
    C["UP_UNLOCKED"] = False
    C["SHARE_SITE"] = str(share.get("الموقع", "") or "").strip()
    try:
        _touch(str(share["الرمز"]))
    except Exception:
        pass
    renderers[tab](C, build, cv)
    st.markdown("---")
    st.caption("منصة دلتا السعودية للتقارير المالية — رابط مشاركة محدود الصلاحية، إشراف الإدارة المالية.")
    st.stop()


def admin(unlocked):
    """إدارة روابط المشاركة داخل مركز التحديث."""
    st.markdown("#### 🔗 روابط مشاركة التبويبات")
    if not unlocked:
        st.info("أدخل كلمة سر مركز التحديث لإدارة روابط المشاركة.")
        return
    D = load()
    base = ""
    try:
        base = str(st.context.url).split("?")[0]
    except Exception:
        base = ""
    base = st.text_input("رابط المنصة (يُستخدم لتكوين الروابط)", value=base, key="sh_base",
                         placeholder="https://your-app.streamlit.app")
    with st.form("sh_new", clear_on_submit=True):
        c1, c2 = st.columns(2)
        lbl = c1.text_input("الوصف (لمن هذا الرابط)", placeholder="مدير موقع الرياض")
        tab = c2.selectbox("التبويب المشارَك", list(TAB_LABELS), format_func=lambda k: TAB_LABELS[k])
        c3, c4, c5 = st.columns(3)
        site = c3.selectbox("الموقع (لتقارير المواقع)", SITES)
        exp = c4.date_input("ينتهي في", value=dt.date.today() + dt.timedelta(days=30))
        pin = c5.text_input("رمز سري (اختياري)", max_chars=12)
        if st.form_submit_button("➕ إصدار رابط", use_container_width=True):
            t = _token()
            row = {"الرمز": t, "الوصف": lbl or TAB_LABELS[tab], "التبويب": tab,
                   "الموقع": "" if site == "الكل" else site, "ينتهي في": exp.isoformat(),
                   "رمز سري": _hash(t, pin), "فعّال": "1",
                   "أنشئ في": dt.date.today().isoformat(), "آخر فتح": "", "عدد مرات الفتح": "0"}
            D = pd.concat([D, pd.DataFrame([row])], ignore_index=True)
            ok, err = save(D)
            st.success(f"تم إصدار الرابط: {base}?k={t}" if ok else f"تعذّر الحفظ: {err}")
    if not len(D):
        st.caption("لا توجد روابط مشاركة بعد.")
        return
    V = D.copy()
    V["الرابط"] = (base + "?k=") + V["الرمز"].astype(str)
    V["التبويب"] = V["التبويب"].map(lambda k: TAB_LABELS.get(k, k))
    V["محمي برمز"] = V["رمز سري"].map(lambda h: "نعم" if str(h).strip() else "لا")
    V["فعّال"] = V["فعّال"].map(lambda v: str(v).strip() in ("1", "True", "نعم", "true"))
    show = ["فعّال", "الوصف", "التبويب", "الموقع", "ينتهي في", "محمي برمز", "عدد مرات الفتح", "آخر فتح", "الرابط"]
    ed = st.data_editor(V[show], hide_index=True, use_container_width=True, num_rows="fixed",
                        disabled=[c for c in show if c != "فعّال"], key="sh_ed")
    c1, c2 = st.columns(2)
    if c1.button("💾 حفظ حالة التفعيل", use_container_width=True):
        D["فعّال"] = ["1" if bool(v) else "0" for v in ed["فعّال"]]
        ok, err = save(D)
        st.success("تم الحفظ.") if ok else st.error(f"تعذّر الحفظ: {err}")
    dead = [i for i, v in enumerate(ed["فعّال"]) if not bool(v)]
    if dead and c2.button(f"🗑️ حذف الروابط الموقوفة ({len(dead)})", use_container_width=True):
        ok, err = save(D.drop(D.index[dead]).reset_index(drop=True))
        st.success("تم الحذف.") if ok else st.error(f"تعذّر الحذف: {err}")
    st.caption("الرابط نفسه هو كلمة السر: من يملكه يرى هذا التبويب فقط وبصلاحية عرض لا تعديل. "
               "أضف رمزاً سرياً للروابط الحساسة، وأوقف أي رابط فور انتهاء الحاجة إليه.")
