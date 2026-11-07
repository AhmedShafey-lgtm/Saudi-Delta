# teams.py
# تبويب فرق العمل: من بيان بونص الفرق الشهري لكل موقع — الفرق وأنواعها ومراقبوها وأفرادها وإنتاجيتها.

import io
import os
import re

import numpy as np
import openpyxl
import pandas as pd
import streamlit as st

import uitable as ut

HERE = os.path.dirname(os.path.abspath(__file__))
F_TEAMS = os.path.join(HERE, "hr_teams.csv")
F_TEXTRA = os.path.join(HERE, "hr_teams_extra.csv")
T_COLS = ["الموقع", "الشهر", "الفرقة", "مفتاح الفرقة", "النوع", "رقم الفرقة", "المراقب",
          "الاسم", "المهنة", "البونص", "بونص الفرقة", "أجور التنفيذ"]
X_COLS = ["الموقع", "الشهر", "البند", "البونص", "بونص الفرقة", "أجور التنفيذ"]

CENTRES = ["ابها", "السراة", "محايل", "المجاردة", "صيانة عسير", "الباحة", "المخواة", "القنفذة",
           "صيانة الباحة", "قراء عدادات الباحة", "تبوك", "ضباء", "الوجه", "حقل", "املج",
           "صيانة تبوك", "قراء عدادات تبوك", "مكة", "خليص", "صيانة مكة", "قراء عدادات مكة",
           "الرياض"]
AR_MONTHS = {"يناير": 1, "فبراير": 2, "مارس": 3, "ابريل": 4, "مايو": 5, "يونيو": 6, "يوليو": 7,
             "اغسطس": 8, "سبتمبر": 9, "اكتوبر": 10, "نوفمبر": 11, "ديسمبر": 12}
MONTH_AR = {v: k for k, v in AR_MONTHS.items()}
# صفوف تجميعية لا تمثل أفراداً
SKIP = ("الاجمال", "اجمالي", "عمال الشركه", "مقاولين الباطن", "مقاول باطن", "الورشه",
        "طوارئ", "طواري", "تقدير", "الانتاجيه")
TYPES = [("ارض", "أرضية"), ("هوائ", "هوائية"), ("عداد", "عدادات"), ("جوينتر", "جوينترية"),
         ("جونتر", "جوينترية"), ("فرم", "فرم"), ("صرف", "صرف ومستودع"), ("فحص", "فحص"),
         ("ترقيم", "ترقيم"), ("اتصال", "اتصالات"), ("اسفلت", "أسفلت"), ("سفلت", "أسفلت"),
         ("مدني", "مدنية"), ("خرسان", "مدنية")]

CSS = """
<style>
  .tm-note { direction: rtl; background: #F8FAFC; border-right: 4px solid #2563EB; padding: 10px 14px;
             border-radius: 8px; color: #334155; font-size: .98rem; margin: 8px 0 12px; }
  .tm-warn { direction: rtl; background: #FEF3C7; border-right: 4px solid #D97706; padding: 10px 14px;
             border-radius: 8px; color: #78350F; font-size: .98rem; margin: 8px 0 12px; }
</style>
"""


def _note(t, warn=False):
    st.markdown(f'<div class="{"tm-warn" if warn else "tm-note"}">{t}</div>', unsafe_allow_html=True)


def _n(s):
    s = re.sub(r"[ً-ْـ]", "", str(s or ""))
    for a, b in (("أ", "ا"), ("إ", "ا"), ("آ", "ا"), ("ة", "ه"), ("ى", "ي")):
        s = s.replace(a, b)
    return re.sub(r"\s+", " ", s).strip()


def _num(v):
    if v is None or isinstance(v, str) and not v.strip():
        return np.nan
    try:
        return float(v)
    except Exception:
        return np.nan


def team_type(name):
    t = _n(name)
    for k, lbl in TYPES:
        if k in t:
            return lbl
    return "أخرى"


def team_no(name):
    m = re.search(r"\d+", _n(name))
    return m.group(0) if m else ""


_STOP_W = {"فرقه", "فرقة", "رقم", "طوارئ", "طواري", "طوارى"}


def _words(name):
    t = re.sub(r"\d+", " ", _n(name))
    return [w for w in t.split() if w not in _STOP_W]


def _rest(name):
    """كلمات اسم الفرقة بعد حذف كلمة «فرقة» ورقمها وكلمات نوعها."""
    return [w for w in _words(name) if not any(k in w for k, _ in TYPES)]


def team_key(name):
    """مفتاح موحّد للفرقة: النوع + الرقم، فلا تتفرّق «هوائى2» عن «هوائى 2»."""
    ty, no = team_type(name), team_no(name)
    if no:
        return f"{ty} {no}"
    return (ty + " " + " ".join(_rest(name))).strip()


def _watcher(name, members):
    """المراقب: من مهنته مراقب داخل الفرقة، وإلا ما تبقّى من اسم الفرقة إن كان اسماً معقولاً."""
    m = [x for x in members if "مراقب" in _n(x[1])]
    if m:
        return m[0][0]
    s = " ".join(_rest(name)).strip()
    return s if len(s) >= 3 else ""


def parse_teams(raw):
    """بيان بونص الفرق: يعيد (الأفراد، البنود التجميعية، الشهر، اسم الورقة)."""
    wb = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
    for sn in wb.sheetnames:
        rows = [list(r) for r in wb[sn].iter_rows(values_only=True)]
        hdr = None
        for i, r in enumerate(rows[:14]):
            t = [_n(x) for x in r]
            if "الاسم" in t and any(x.startswith("بونص") for x in t):
                hdr = i
                break
        if hdr is None:
            continue
        H = {_n(v): j for j, v in enumerate(rows[hdr]) if v is not None}
        w = max(len(r) for r in rows) if rows else 0
        cnt = {j: sum(1 for r in rows if j < len(r) and r[j] and "فرق" in _n(r[j])) for j in range(w)}
        jteam = max(cnt, key=cnt.get) if cnt and max(cnt.values()) > 1 else None
        ym = ""
        for r in rows[:hdr + 1]:
            for v in r:
                m = re.search(r"شهر\s+(\S+)\s+(\d{4})", str(v or ""))
                if m and AR_MONTHS.get(_n(m.group(1))):
                    ym = f"{m.group(2)}-{AR_MONTHS[_n(m.group(1))]:02d}"
        g = lambda r, k: (r[H[k]] if k in H and H[k] < len(r) else None)
        rec, extra, team = [], [], ""
        for r in rows[hdr + 1:]:
            if jteam is not None and jteam < len(r) and r[jteam] and "فرق" in _n(r[jteam]):
                team = str(r[jteam]).strip()
            nm = str(g(r, "الاسم") or "").strip()
            job = str(g(r, "المهنه") or "").strip()
            if not nm and not job:
                continue
            b, tb = _num(g(r, "البونص")), _num(g(r, "بونص الفرقه"))
            wg = _num(g(r, "اجور التنفيذ الفعليه"))
            if any(k in _n(nm) or k in _n(job) for k in SKIP):
                extra.append({"البند": nm or job, "البونص": b, "بونص الفرقة": tb, "أجور التنفيذ": wg})
                team = ""          # صف تجميعي يفصل بين المجموعات فلا يُورَّث انتماؤها
                continue
            rec.append({"الفرقة": team, "الاسم": nm, "المهنة": job,
                        "البونص": b, "بونص الفرقة": tb, "أجور التنفيذ": wg})
        M = pd.DataFrame(rec)
        if len(M):
            M["مفتاح الفرقة"] = M["الفرقة"].map(lambda x: team_key(x) if x else "بلا فرقة")
            M["النوع"] = M["الفرقة"].map(lambda x: team_type(x) if x else "غير محدد")
            M["رقم الفرقة"] = M["الفرقة"].map(team_no)
            w_ = {k: _watcher(k, list(zip(v["الاسم"], v["المهنة"])))
                  for k, v in M.groupby("الفرقة")}
            M["المراقب"] = M["الفرقة"].map(w_).fillna("")
            M["الشهر"] = ym
        X = pd.DataFrame(extra)
        if len(X):
            X["الشهر"] = ym
        return M, X, ym, sn
    return pd.DataFrame(), pd.DataFrame(), "", ""


# ---------------- التخزين ----------------
def _read(path, cols):
    if not os.path.exists(path):
        return pd.DataFrame(columns=cols)
    try:
        D = pd.read_csv(path, dtype={"رقم الفرقة": str})
    except Exception:
        return pd.DataFrame(columns=cols)
    for c in cols:
        if c not in D.columns:
            D[c] = np.nan
    D = D[cols]
    num = {"البونص", "بونص الفرقة", "أجور التنفيذ"}
    for c in cols:
        if c in num:
            D[c] = pd.to_numeric(D[c], errors="coerce")
        else:
            D[c] = D[c].fillna("").astype(str)
    return D


def _state():
    ss = st.session_state
    if "tm_m" not in ss:
        ss["tm_m"] = _read(F_TEAMS, T_COLS)
    if "tm_x" not in ss:
        ss["tm_x"] = _read(F_TEXTRA, X_COLS)
    return ss["tm_m"], ss["tm_x"]


def _store(M, X):
    st.session_state["tm_m"], st.session_state["tm_x"] = M, X
    try:
        M.to_csv(F_TEAMS, index=False, encoding="utf-8-sig")
        X.to_csv(F_TEXTRA, index=False, encoding="utf-8-sig")
        return True, ""
    except Exception as e:
        return False, str(e)


def _merge(old, new, keys):
    """يستبدل بيانات نفس الموقع والشهر ويبقي الباقي."""
    if not len(new):
        return old
    if len(old):
        k = set(map(tuple, new[keys].drop_duplicates().values))
        old = old[~old[keys].apply(tuple, axis=1).isin(k)]
    return pd.concat([old, new], ignore_index=True)


# ---------------- الواجهة ----------------
def _upload(unlocked):
    st.markdown("#### رفع بيان بونص الفرق")
    _note("ارفع ملف «بونص الفرق» لكل موقع وشهر. تُقرأ الفرقة من عمود اسم الفرقة ويُنسب إليها كل من يليها "
          "حتى الفرقة التالية، ويُستنتج نوعها ورقمها ومراقبها آلياً. رفع الشهر نفسه مرة أخرى يستبدل بياناته.")
    if not unlocked:
        _note("أدخل كلمة سر مركز التحديث في الشريط الجانبي لتفعيل الرفع.", True)
        return
    c1, c2 = st.columns([1, 2])
    site = c1.selectbox("الموقع", CENTRES, key="tm_site")
    up = c2.file_uploader("ملفات بونص الفرق (Excel)", type=["xlsx", "xlsm"],
                          accept_multiple_files=True, key="tm_up")
    if not up:
        return
    M, X = _state()
    log = []
    for f in up:
        try:
            m, x, ym, sn = parse_teams(f.read())
        except Exception as e:
            log.append(("e", f"{f.name}: تعذّرت القراءة — {e}"))
            continue
        if not len(m):
            log.append(("e", f"{f.name}: لم يُعثر على ورقة بونص الفرق (يلزم عمودا «الاسم» و«البونص»)."))
            continue
        if not ym:
            log.append(("e", f"{f.name}: لم يتبيّن الشهر من عنوان الورقة (المتوقع «بونص شهر أكتوبر 2026»)."))
            continue
        m["الموقع"], x["الموقع"] = site, site
        for c in T_COLS:
            if c not in m.columns:
                m[c] = np.nan
        M = _merge(M, m[T_COLS], ["الموقع", "الشهر"])
        X = _merge(X, x[X_COLS] if len(x) else pd.DataFrame(columns=X_COLS), ["الموقع", "الشهر"])
        nt = m["مفتاح الفرقة"].nunique()
        log.append(("s", f"{f.name}: {site} — شهر {ym}: {nt} فرقة و{len(m)} فرداً."))
    ok, err = _store(M, X)
    for k, t in log:
        (st.success if k == "s" else st.error)(t)
    if not ok:
        st.error(f"تعذّر الحفظ: {err}")


def _teams_table(M, build):
    G = M.groupby(["الموقع", "الشهر", "مفتاح الفرقة"], as_index=False).agg(
        **{"الفرقة": ("الفرقة", "first"), "النوع": ("النوع", "first"), "المراقب": ("المراقب", "first"),
           "عدد الأفراد": ("الاسم", "nunique"), "بونص الأفراد": ("البونص", "sum"),
           "بونص الفرقة": ("بونص الفرقة", "sum"), "أجور التنفيذ": ("أجور التنفيذ", "sum")})
    G["الإنتاجية للفرد"] = np.where(G["عدد الأفراد"] > 0, G["أجور التنفيذ"] / G["عدد الأفراد"], 0)
    G["البونص للفرد"] = np.where(G["عدد الأفراد"] > 0, G["بونص الأفراد"] / G["عدد الأفراد"], 0)
    return G


def _overview(M, X, build):
    G = _teams_table(M, build)
    s = G.groupby("النوع").agg(**{"الفرق": ("مفتاح الفرقة", "nunique"), "الأفراد": ("عدد الأفراد", "sum"),
                                  "بونص الأفراد": ("بونص الأفراد", "sum"),
                                  "أجور التنفيذ": ("أجور التنفيذ", "sum")}).sort_values("الأفراد", ascending=False)
    f = lambda v: f"{v:,.0f}"
    rows = [("item", k, [f(r.الفرق), f(r.الأفراد), f(r["بونص الأفراد"]), f(r["أجور التنفيذ"])])
            for k, r in s.iterrows()]
    rows.append(("total", "الإجمالي", [f(s.الفرق.sum()), f(s.الأفراد.sum()),
                                       f(s["بونص الأفراد"].sum()), f(s["أجور التنفيذ"].sum())]))
    st.table(build(rows, ["نوع الفرقة", "عدد الفرق", "عدد الأفراد", "بونص الأفراد", "أجور التنفيذ"]))
    _note("أجور التنفيذ الفعلية مسجّلة في الملف على مستوى المجموعة لا على كل فرقة، فتظهر مجمّعة أمام "
          "الفرقة التي وردت عندها. الإنتاجية للفرد تُقرأ على هذا الأساس.")
    if len(X):
        Y = X.groupby("البند", as_index=False).agg(**{"بونص الفرقة": ("بونص الفرقة", "sum"),
                                                      "أجور التنفيذ": ("أجور التنفيذ", "sum")})
        with st.expander("بنود خارج الفرق (طوارئ، عمال الشركة، مقاولو الباطن)"):
            ut.wide(Y, "البند", key_font=1.1, height="26vh")


def _teams_view(M, build):
    G = _teams_table(M, build)
    c1, c2 = st.columns(2)
    ty = c1.multiselect("نوع الفرقة", sorted(G["النوع"].unique()), key="tm_ty")
    if ty:
        G = G[G["النوع"].isin(ty)]
    srt = c2.radio("الترتيب", ["عدد الأفراد", "أجور التنفيذ", "بونص الأفراد", "الإنتاجية للفرد"],
                   horizontal=True, key="tm_sort")
    V = G.sort_values(srt, ascending=False)[
        ["الفرقة", "النوع", "المراقب", "الموقع", "الشهر", "عدد الأفراد", "بونص الأفراد",
         "البونص للفرد", "بونص الفرقة", "أجور التنفيذ", "الإنتاجية للفرد"]]
    ut.wide(V, "الفرقة", key_font=1.2, height="52vh")
    st.download_button("⬇️ تنزيل بيان الفرق (CSV)", V.to_csv(index=False).encode("utf-8-sig"),
                       "teams.csv", "text/csv", key="tm_dl_t")


def _members_view(M):
    c1, c2 = st.columns(2)
    teams = sorted(M["الفرقة"].replace("", "بلا فرقة").unique())
    pick = c1.selectbox("الفرقة", ["الكل"] + teams, key="tm_pick")
    q = c2.text_input("بحث بالاسم أو المهنة", key="tm_q")
    V = M.copy()
    V["الفرقة"] = V["الفرقة"].replace("", "بلا فرقة")
    if pick != "الكل":
        V = V[V["الفرقة"] == pick]
    if q.strip():
        k = _n(q)
        V = V[V["الاسم"].map(lambda x: k in _n(x)) | V["المهنة"].map(lambda x: k in _n(x))]
    V = V[["الاسم", "المهنة", "الفرقة", "النوع", "المراقب", "الموقع", "الشهر", "البونص"]]
    st.caption(f"{len(V):,} فرداً")
    ut.wide(V.sort_values(["الفرقة", "البونص"], ascending=[True, False]), "الاسم",
            key_font=1.3, height="56vh")
    st.download_button("⬇️ تنزيل أفراد الفرق (CSV)", V.to_csv(index=False).encode("utf-8-sig"),
                       "team_members.csv", "text/csv", key="tm_dl_m")


def _trend(M, build):
    if M["الشهر"].nunique() < 2:
        _note("ارفع شهراً آخر على الأقل لتظهر مقارنة تطور الفرق عبر الشهور.")
        return
    P = M.groupby(["الشهر", "مفتاح الفرقة"], as_index=False).agg(
        **{"الأفراد": ("الاسم", "nunique"), "البونص": ("البونص", "sum"),
           "أجور التنفيذ": ("أجور التنفيذ", "sum")})
    for metric in ("الأفراد", "البونص", "أجور التنفيذ"):
        T = P.pivot_table(index="مفتاح الفرقة", columns="الشهر", values=metric,
                          aggfunc="sum").fillna(0).reset_index()
        st.markdown(f"**{metric} لكل فرقة عبر الشهور**")
        ut.wide(T, "مفتاح الفرقة", key_font=1.15, height="34vh")


def _link_hr(M, emp):
    """ربط أفراد الفرق بملف الموظفين بمطابقة الاسم."""
    if emp is None or not len(emp):
        _note("ارفع ملف بيانات الموظفين في «البيانات والإعدادات» ليُربط أفراد الفرق بأرقامهم الوظيفية.", True)
        return
    E = emp.copy()
    E["_k"] = E["الاسم"].map(_n)
    E = E.drop_duplicates("_k")
    V = M.drop_duplicates(["الاسم", "الفرقة"]).copy()
    V["_k"] = V["الاسم"].map(_n)
    V = V.merge(E[["_k", "الرقم الوظيفي", "الموقع", "المهنة"]].rename(
        columns={"الموقع": "موقع الموظفين", "المهنة": "مهنة الموظفين"}), on="_k", how="left")
    hit = int(V["الرقم الوظيفي"].notna().sum())
    _note(f"طوبق {hit:,} من {len(V):,} فرداً مع ملف الموظفين بالاسم. غير المطابق إما مختلف كتابة الاسم "
          "أو غير مُدرج في ملف الموظفين.")
    V = V[["الاسم", "الرقم الوظيفي", "الفرقة", "النوع", "المراقب", "المهنة", "مهنة الموظفين",
           "الموقع", "موقع الموظفين", "البونص"]]
    ut.wide(V.sort_values("الرقم الوظيفي", na_position="first"), "الاسم", key_font=1.3, height="52vh")
    st.download_button("⬇️ تنزيل الربط مع الموارد البشرية (CSV)",
                       V.to_csv(index=False).encode("utf-8-sig"), "teams_hr_link.csv",
                       "text/csv", key="tm_dl_l")


def render_teams(ctx, build, emp=None):
    st.markdown(CSS, unsafe_allow_html=True)
    ut.css()
    unlocked = bool(ctx.get("UP_UNLOCKED", False))
    M, X = _state()
    st.subheader("🧑‍🏭 فرق العمل")
    if not len(M):
        _note("لا توجد بيانات فرق بعد. ارفع ملف «بونص الفرق» من القسم أدناه — ملف لكل موقع وشهر.")
        _upload(unlocked)
        return
    c1, c2 = st.columns(2)
    sites = sorted(M["الموقع"].dropna().unique())
    months = sorted(M["الشهر"].dropna().unique())
    ssel = c1.multiselect("الموقع", sites, default=sites, key="tm_fs")
    msel = c2.multiselect("الشهر", months, default=months[-1:], key="tm_fm")
    V = M[M["الموقع"].isin(ssel or sites) & M["الشهر"].isin(msel or months)]
    XV = X[X["الموقع"].isin(ssel or sites) & X["الشهر"].isin(msel or months)] if len(X) else X
    if not len(V):
        _note("لا توجد بيانات للاختيار الحالي.", True)
        return
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("عدد الفرق", f"{V['مفتاح الفرقة'].nunique():,}")
    k2.metric("أفراد الفرق", f"{V['الاسم'].nunique():,}")
    k3.metric("بونص الأفراد", f"{V['البونص'].sum():,.0f}")
    k4.metric("أجور التنفيذ", f"{V['أجور التنفيذ'].sum():,.0f}")
    t = st.tabs(["📋 الفرق", "👥 الأفراد", "📊 نظرة عامة", "📈 التطور الشهري",
                 "🔗 الربط بالموارد البشرية", "⬆️ رفع البيانات"])
    with t[0]:
        _teams_view(V, build)
    with t[1]:
        _members_view(V)
    with t[2]:
        _overview(V, XV, build)
    with t[3]:
        _trend(M, build)
    with t[4]:
        _link_hr(V, emp)
    with t[5]:
        _upload(unlocked)
