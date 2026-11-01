# hr.py
# تبويب الموارد البشرية: ملخص العمالة والسعودة، استعراض العاملين، العلاوات، المخصصات، نهاية الخدمة.
# المصادر: ملف بيانات الموظفين (الحالة، المهنة، الموقع، تواريخ التعيين والعقد وآخر إجازة) وتفاصيل الرواتب الشهرية.

import io, os, re, json, hashlib, datetime as dt
import numpy as np
import pandas as pd
import streamlit as st

HERE = os.path.dirname(os.path.abspath(__file__))
EMP_FILE = os.path.join(HERE, "hr_emp.csv")
PAY_FILE = os.path.join(HERE, "hr_pay.csv")
INC_FILE = os.path.join(HERE, "hr_increases.csv")
SET_FILE = os.path.join(HERE, "hr_settings.json")

CSS = """
<style>
  .hr-title { direction: rtl; text-align: right; background: linear-gradient(90deg,#1E3A8A,#3B5FC4); color:#fff;
              padding:9px 14px; border-radius:6px; margin:18px 0 8px 0; font-weight:700; font-size:1.1rem; }
  .hr-note { direction: rtl; text-align: right; background:#FFF7E0; border-right:4px solid #F59E0B; color:#7A4B00;
             padding:8px 12px; border-radius:6px; font-size:0.95rem; margin:6px 0; }
  [class*="st-key-hr_grid"] [data-testid="stDataFrame"], [class*="st-key-hr_grid"] [data-testid="stDataFrame"] * {
      direction: ltr !important; text-align: left !important; }
</style>
"""

GROUPS = ["مهندسون", "محاسبون", "فنيون", "عمالة", "إداريون ومهن أخرى"]
# قواعد تصنيف المهنة إلى مجموعة رئيسية (أول قاعدة تنطبق)
DEFAULT_PROF_RULES = [
    ["مهندس", "مهندسون"],
    ["محاسب", "محاسبون"],
    ["مدير", "إداريون ومهن أخرى"], ["الشئون القانونية", "إداريون ومهن أخرى"], ["الموارد البشرية", "إداريون ومهن أخرى"],
    ["مندوب", "إداريون ومهن أخرى"], ["IT", "إداريون ومهن أخرى"], ["معقب", "إداريون ومهن أخرى"],
    ["مستقبل بلاغات", "إداريون ومهن أخرى"], ["مدخل بيانات", "إداريون ومهن أخرى"], ["امين", "إداريون ومهن أخرى"],
    ["موزع فواتير", "إداريون ومهن أخرى"], ["مسئول مستخلصات", "إداريون ومهن أخرى"], ["منسق", "إداريون ومهن أخرى"],
    ["سكرتير", "إداريون ومهن أخرى"], ["عامل بوفيه", "عمالة"],
    ["فني", "فنيون"], ["كهربائ", "فنيون"], ["كهرباء", "فنيون"], ["ميكانيك", "فنيون"], ["مساح", "فنيون"], ["رسام", "فنيون"],
    ["لحام", "فنيون"], ["جونتيري", "فنيون"], ["لين مان", "فنيون"], ["مسئول فرقة", "فنيون"], ["مراقب", "فنيون"],
    ["مشرف", "فنيون"], ["سمكري", "فنيون"], ["فاحص", "فنيون"], ["مسئول امن", "فنيون"],
]
# نسب التوطين المطلوبة (من صفحة «استعراض تفاصيل توطين المهن» في منصة قوى لمنشأة المقاولات) قابلة للتعديل
DEFAULT_REQ = {"مهندسون": 30.0, "محاسبون": 50.0, "فنيون": 30.0, "عمالة": 0.0, "إداريون ومهن أخرى": 0.0}
PORTAL_REF = [
    ["المهن الهندسية", 30, "ملتزمة"], ["وظائف هندسة الاتصالات وتقنية المعلومات", 25, "ملتزمة"],
    ["وظائف الدعم الفني والوظائف الفنية للاتصالات", 25, "ملتزمة"], ["المهن المحاسبية", 50, "غير ملتزمة"],
    ["مهن التسويق", 60, "ملتزمة"], ["المهن الإدارية المساندة", 100, "ملتزمة"], ["مهن المبيعات", 60, "ملتزمة"],
    ["مهن المشتريات", 70, "ملتزمة"], ["المهن الفنية الهندسية", 30, "ملتزمة"], ["مهن خدمة العملاء", 100, "ملتزمة"],
]
BANDS = ["غير محدد", "بلاتيني", "أخضر مرتفع", "أخضر متوسط", "أخضر منخفض", "أصفر", "أحمر"]
DEFAULT_SET = {"req": DEFAULT_REQ, "band": "غير محدد", "gosi_saudi": 402, "gosi_foreign": 1727, "gosi_date": "13/10/2026",
               "leave_days_lt5": 21, "leave_days_ge5": 30, "prof_rules": DEFAULT_PROF_RULES}
ACTIVE = ["يعمل", "نشط"]
ON_LEAVE = ["مجاز"]
EMP_COLS = ["الرقم الوظيفي", "الاسم", "المهنة", "الموقع", "الحالة", "تاريخ التعيين", "بداية العقد", "نهاية العقد", "اخر اجازة", "اخر تذكرة", "تاريخ الميلاد", "الرقم"]
PAY_COLS = ["الرقم الوظيفي", "ym", "الراتب", "اجمالي الراتب", "تأمين اجتماعي", "تأمين طبي شهري", "التنقلات", "الاقامات", "بدل سكن", "بدل انتقال", "المهنة", "الموقع"]


# ---------------- التحميل والتخزين ----------------
def _norm_cols(df):
    df.columns = [re.sub(r"\s+", " ", str(c)).strip() for c in df.columns]
    return df


def detect(raw):
    """يعيد 'موظفين' أو 'رواتب' أو None بحسب رؤوس الأعمدة."""
    try:
        df = _norm_cols(pd.read_excel(io.BytesIO(raw), nrows=3))
    except Exception:
        return None
    c = set(df.columns)
    if {"الحالة", "تاريخ التعيين", "اخر اجازة"} <= c:
        return "موظفين"
    if {"اجمالي الراتب", "الشهر"} <= c:
        return "رواتب"
    return None


def parse_master(raw):
    df = _norm_cols(pd.read_excel(io.BytesIO(raw)))
    for c in EMP_COLS:
        if c not in df.columns:
            df[c] = np.nan
    df = df[EMP_COLS].copy()
    df = df[df["الرقم الوظيفي"].notna()]
    df["الرقم الوظيفي"] = df["الرقم الوظيفي"].astype("int64").astype(str)
    for c in ["تاريخ التعيين", "بداية العقد", "نهاية العقد", "اخر اجازة", "اخر تذكرة", "تاريخ الميلاد"]:
        df[c] = pd.to_datetime(df[c], errors="coerce")
    df["الرقم"] = df["الرقم"].map(lambda v: "" if pd.isna(v) else str(int(float(v))))
    for c in ["الاسم", "المهنة", "الموقع", "الحالة"]:
        df[c] = df[c].fillna("").astype(str).str.strip()
    # الحالة: «مجاز» الأحدث يغلب عند التكرار
    return df.drop_duplicates("الرقم الوظيفي", keep="last").reset_index(drop=True)


def parse_payroll(raw):
    df = _norm_cols(pd.read_excel(io.BytesIO(raw), sheet_name=0))
    df["الشهر"] = pd.to_datetime(df["الشهر"], errors="coerce")
    df = df[df["الشهر"].notna() & df["الرقم الوظيفي"].notna()].copy()
    df["الرقم الوظيفي"] = df["الرقم الوظيفي"].astype("int64").astype(str)
    df["ym"] = df["الشهر"].dt.strftime("%Y-%m")
    for c in PAY_COLS:
        if c not in df.columns:
            df[c] = np.nan
    num = ["الراتب", "اجمالي الراتب", "تأمين اجتماعي", "تأمين طبي شهري", "التنقلات", "الاقامات", "بدل سكن", "بدل انتقال"]
    for c in num:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    for c in ["المهنة", "الموقع"]:
        df[c] = df[c].fillna("").astype(str).str.strip()
    return df[PAY_COLS].reset_index(drop=True)


def _read_csv(path, **kw):
    try:
        if os.path.exists(path):
            return pd.read_csv(path, encoding="utf-8-sig", **kw)
    except Exception:
        pass
    return None


def _load_settings():
    try:
        if os.path.exists(SET_FILE):
            j = json.load(open(SET_FILE, encoding="utf-8"))
            s = {**DEFAULT_SET, **j}
            s["req"] = {**DEFAULT_REQ, **j.get("req", {})}
            return s
    except Exception:
        pass
    return json.loads(json.dumps(DEFAULT_SET))


def _save_settings(s):
    try:
        json.dump(s, open(SET_FILE, "w", encoding="utf-8"), ensure_ascii=False)
    except Exception:
        pass


def _state():
    ss = st.session_state
    if "hr_emp" not in ss:
        e = _read_csv(EMP_FILE, dtype={"الرقم الوظيفي": str, "الرقم": str})
        if e is not None:
            for c in ["تاريخ التعيين", "بداية العقد", "نهاية العقد", "اخر اجازة", "اخر تذكرة", "تاريخ الميلاد"]:
                e[c] = pd.to_datetime(e[c], errors="coerce")
            e = e.fillna({"الرقم": "", "الاسم": "", "المهنة": "", "الموقع": "", "الحالة": ""})
        ss["hr_emp"] = e if e is not None else pd.DataFrame(columns=EMP_COLS)
    if "hr_pay" not in ss:
        p = _read_csv(PAY_FILE, dtype={"الرقم الوظيفي": str})
        ss["hr_pay"] = p if p is not None else pd.DataFrame(columns=PAY_COLS)
    if "hr_inc" not in ss:
        i = _read_csv(INC_FILE, dtype={"الرقم الوظيفي": str})
        ss["hr_inc"] = i if i is not None else pd.DataFrame(columns=["الرقم الوظيفي", "الزيادة"])
    if "hr_set" not in ss:
        ss["hr_set"] = _load_settings()
    return ss["hr_emp"], ss["hr_pay"], ss["hr_inc"], ss["hr_set"]


# ---------------- التصنيف والمشتقات ----------------
def prof_group(prof, rules):
    p = str(prof)
    for pat, g in rules:
        if str(pat) in p:
            return g
    return "عمالة"


def contract_of_site(text, cf):
    t = str(text)
    if "الادار" in t:
        return "الإدارة"
    return cf.contract_of(t)


def build_view(emp, pay, sett, cf):
    """جدول العاملين الحاليين (يعمل/نشط/مجاز) مع الجنسية والمجموعة والعقد وآخر راتب."""
    E = emp.copy()
    iq = pay.groupby("الرقم الوظيفي")["الاقامات"].apply(lambda s: bool((s.fillna(0) > 0).any())) if len(pay) else pd.Series(dtype=bool)
    idn = E["الرقم"].astype(str).str[:1]
    nat = np.where(idn == "1", "سعودي", np.where(idn == "2", "أجنبي", ""))
    iqf = E["الرقم الوظيفي"].map(iq)
    iqf = iqf.where(iqf.notna(), False).astype(bool)
    nat = np.where((nat == "") & iqf, "أجنبي", nat)
    E["الجنسية"] = np.where(nat == "", "غير محدد", nat)
    E["المجموعة"] = E["المهنة"].map(lambda p: prof_group(p, sett["prof_rules"]))
    sites = {s: contract_of_site(s, cf) for s in E["الموقع"].unique()}
    E["العقد"] = E["الموقع"].map(sites)
    E["نشط"] = E["الحالة"].isin(ACTIVE + ON_LEAVE)
    E["الموقف"] = np.where(E["الحالة"].isin(ON_LEAVE), "في إجازة", np.where(E["الحالة"].isin(ACTIVE), "على رأس العمل", E["الحالة"]))
    if len(pay):
        P = pay.sort_values(["الرقم الوظيفي", "ym"])
        last = P.groupby("الرقم الوظيفي").tail(1).set_index("الرقم الوظيفي")
        E["الراتب الأساسي"] = E["الرقم الوظيفي"].map(last["الراتب"])
        E["إجمالي الراتب"] = E["الرقم الوظيفي"].map(last["اجمالي الراتب"])
        chg = P.assign(d=P.groupby("الرقم الوظيفي")["الراتب"].diff())
        chg = chg[chg["d"].fillna(0).abs() > 0.5].groupby("الرقم الوظيفي").tail(1).set_index("الرقم الوظيفي")
        E["تاريخ آخر زيادة"] = E["الرقم الوظيفي"].map(chg["ym"])
        E["مبلغ آخر زيادة"] = E["الرقم الوظيفي"].map(chg["d"])
    else:
        for c in ["الراتب الأساسي", "إجمالي الراتب", "مبلغ آخر زيادة"]:
            E[c] = np.nan
        E["تاريخ آخر زيادة"] = None
    return E


def good_month(pay):
    """آخر شهر رواتب مكتمل (عدد موظفيه ≥ 80% من الشهر السابق)."""
    if not len(pay):
        return None
    n = pay.groupby("ym")["الرقم الوظيفي"].nunique().sort_index()
    ms = list(n.index)
    for i in range(len(ms) - 1, 0, -1):
        if n.iloc[i] >= 0.8 * n.iloc[i - 1]:
            return ms[i]
    return ms[-1]


def eosb_factor(years):
    y = max(float(years), 0.0)
    return 0.5 * min(y, 5.0) + max(y - 5.0, 0.0)


def _fmt(n):
    return "" if pd.isna(n) else f"{n:,.0f}"


def _pct(a, b):
    return f"{(a / b * 100):.1f}%" if b else "—"


def _tbl(build, rows, cols):
    st.table(build(rows, cols))


def _title(t):
    st.markdown(f'<div class="hr-title">{t}</div>', unsafe_allow_html=True)


# ---------------- الواجهة ----------------
def render_hr(ctx, build_styled_table):
    import cashflow as cf
    st.markdown(CSS, unsafe_allow_html=True)
    unlocked = bool(ctx.get("UP_UNLOCKED", False))
    emp, pay, inc, sett = _state()
    st.subheader("👷 الموارد البشرية")
    tabs = st.tabs(["📊 الملخص والسعودة", "👥 استعراض العاملين", "💰 العلاوات", "📌 المخصصات المستحقة", "📐 نهاية الخدمة الاكتواري", "🧾 تقارير مقترحة", "⚙️ البيانات والإعدادات"])
    t_sum, t_emp, t_inc, t_prov, t_act, t_sug, t_set = tabs
    with t_set:
        _data_tab(unlocked, emp, pay, sett)
    emp, pay, inc, sett = _state()
    if not len(emp):
        for t in (t_sum, t_emp, t_inc, t_prov, t_act, t_sug):
            with t:
                st.info("ارفع ملف بيانات الموظفين وتفاصيل الرواتب من تبويب «البيانات والإعدادات» لتظهر التقارير.")
        return
    V = build_view(emp, pay, sett, cf)
    A = V[V["نشط"]].copy()
    ym = good_month(pay)
    with t_sum:
        _summary(A, pay, sett, ym, build_styled_table)
    with t_emp:
        _browse(V)
    with t_inc:
        _increases(A, unlocked, ym)
    with t_prov:
        _provisions(A, sett, build_styled_table)
    with t_act:
        _actuarial(A, sett)
    with t_sug:
        _suggested(V, A, pay, ym, sett, build_styled_table)


def _data_tab(unlocked, emp, pay, sett):
    _title("رفع البيانات")
    st.markdown('<div class="hr-note">ارفع ملف بيانات الموظفين (الحالة، المهنة، الموقع، تاريخ التعيين، العقد، آخر إجازة، الرقم) وملف تفاصيل الرواتب الشهرية. '
                'يُتعرَّف على نوع الملف تلقائياً من رؤوس الأعمدة، ويُحفظ بجوار التطبيق (قد يضيع على الاستضافة المؤقتة فأعد الرفع عند الحاجة).</div>', unsafe_allow_html=True)
    up = st.file_uploader("ملفات الموارد البشرية (Excel)", type=["xlsx"], accept_multiple_files=True, key="hr_up", disabled=not unlocked)
    if not unlocked:
        st.info("🔒 الرفع وتعديل الإعدادات مقفلان. أدخل كلمة السر في الشريط الجانبي.")
    if up and unlocked:
        done = st.session_state.setdefault("hr_hashes", set())
        for f in up:
            raw = f.getvalue()
            h = hashlib.md5(raw).hexdigest()
            if h in done:
                continue
            try:
                kind = detect(raw)
                if kind == "موظفين":
                    d = parse_master(raw)
                    st.session_state["hr_emp"] = d
                    d.to_csv(EMP_FILE, index=False, encoding="utf-8-sig")
                    st.success(f"{f.name}: بيانات الموظفين: {len(d)} موظفاً.")
                elif kind == "رواتب":
                    d = parse_payroll(raw)
                    st.session_state["hr_pay"] = d
                    d.to_csv(PAY_FILE, index=False, encoding="utf-8-sig")
                    st.success(f"{f.name}: الرواتب: {len(d)} سطراً من {d['ym'].min()} إلى {d['ym'].max()}.")
                else:
                    st.warning(f"{f.name}: لم يُتعرَّف على نوع الملف (يلزم رأس أعمدة بيانات الموظفين أو تفاصيل الرواتب).")
                    continue
                done.add(h)
            except Exception as e:
                st.error(f"تعذرت قراءة {f.name}: {e}")
    emp, pay, _, sett = _state()
    if len(emp):
        st.caption(f"المحمّل: {len(emp)} موظفاً في الملف الرئيسي، ورواتب {pay['ym'].nunique() if len(pay) else 0} شهراً.")
    _title("الإعدادات")
    st.caption("نسب التوطين المطلوبة لكل مجموعة (حسب صفحة توطين المهن في منصة قوى لمنشأة المقاولات؛ المحاسبون «غير ملتزمة» بالتوطين حالياً حسب المنصة فتُعرض نسبتهم للمتابعة فقط):")
    req = pd.DataFrame({"المجموعة": GROUPS, "النسبة المطلوبة %": [sett["req"].get(g, 0.0) for g in GROUPS]})
    r2 = st.data_editor(req, hide_index=True, use_container_width=True, disabled=(not unlocked) or ["المجموعة"], key="hr_req_ed", num_rows="fixed")
    c1, c2, c3 = st.columns(3)
    band = c1.selectbox("النطاق الحالي (من منصة قوى)", BANDS, index=BANDS.index(sett["band"]) if sett["band"] in BANDS else 0, disabled=not unlocked, key="hr_band")
    gs = c2.number_input("سعوديون حسب شهادة التأمينات", value=int(sett["gosi_saudi"]), step=1, disabled=not unlocked, key="hr_gs")
    gf = c3.number_input("غير سعوديين حسب شهادة التأمينات", value=int(sett["gosi_foreign"]), step=1, disabled=not unlocked, key="hr_gf")
    c4, c5 = st.columns(2)
    l1 = c4.number_input("أيام الإجازة السنوية (خدمة أقل من 5 سنوات)", value=int(sett["leave_days_lt5"]), step=1, disabled=not unlocked, key="hr_l1")
    l2 = c5.number_input("أيام الإجازة السنوية (خدمة 5 سنوات فأكثر)", value=int(sett["leave_days_ge5"]), step=1, disabled=not unlocked, key="hr_l2")
    if unlocked:
        new = {**sett, "req": {g: float(v) for g, v in zip(r2["المجموعة"], r2["النسبة المطلوبة %"])}, "band": band,
               "gosi_saudi": int(gs), "gosi_foreign": int(gf), "leave_days_lt5": int(l1), "leave_days_ge5": int(l2)}
        if new != sett:
            st.session_state["hr_set"] = new
            _save_settings(new)
    st.caption("مرجع: نسب التوطين المطلوبة حسب منصة قوى")
    ref = pd.DataFrame(PORTAL_REF, columns=["المجموعة المهنية", "النسبة المطلوبة %", "الالتزام بالتوطين"])
    st.dataframe(ref, hide_index=True, use_container_width=True)
    with st.expander("قواعد تصنيف المهنة إلى مجموعة رئيسية (أول قاعدة تنطبق، وما لا ينطبق يُصنَّف عمالة)"):
        rr = pd.DataFrame(sett["prof_rules"], columns=["جزء من المهنة", "المجموعة"])
        r3 = st.data_editor(rr, num_rows="dynamic", use_container_width=True, hide_index=True, disabled=not unlocked, key="hr_rules_ed",
                            column_config={"المجموعة": st.column_config.SelectboxColumn("المجموعة", options=GROUPS)})
        if unlocked:
            rl = [[str(a), str(b)] for a, b in r3.values.tolist() if str(a).strip() and str(b) in GROUPS]
            if rl != sett["prof_rules"]:
                s2 = {**st.session_state["hr_set"], "prof_rules": rl}
                st.session_state["hr_set"] = s2
                _save_settings(s2)
    st.caption("بعد تعديل الإعدادات تتحدث التقارير عند أول تفاعل تالٍ.")


def _summary(A, pay, sett, ym, build):
    n_all = len(A)
    sa = int((A["الجنسية"] == "سعودي").sum())
    fo = int((A["الجنسية"] == "أجنبي").sum())
    un = n_all - sa - fo
    _title("الملخص العام للعمالة")
    c = st.columns(4)
    c[0].metric("إجمالي العمالة", f"{n_all:,}")
    c[1].metric("سعوديون", f"{sa:,}")
    c[2].metric("أجانب", f"{fo:,}")
    c[3].metric("نسبة السعودة", _pct(sa, n_all))
    c = st.columns(4)
    c[0].metric("النطاق", sett["band"])
    mm = pay[pay["ym"] == ym] if ym else pay.iloc[0:0]
    c[1].metric(f"إجمالي الرواتب الشهرية ({ym or '—'})", _fmt(mm["اجمالي الراتب"].sum()))
    c[2].metric("التأمينات الاجتماعية الشهرية", _fmt(mm["تأمين اجتماعي"].sum()))
    full = [m for m in sorted(pay["ym"].unique()) if m.startswith(ym[:4]) and m <= ym and pay[pay["ym"] == m]["الرقم الوظيفي"].nunique() > 0.8 * len(mm["الرقم الوظيفي"].unique())] if ym else []
    iq_avg = float(np.mean([pay[pay["ym"] == m]["الاقامات"].sum() for m in full])) if full else 0.0
    c[3].metric(f"متوسط الإقامات الشهرية (متوسط {len(full)} أشهر)", _fmt(iq_avg))
    c = st.columns(3)
    c[0].metric("التأمين الطبي الشهري", _fmt(mm["تأمين طبي شهري"].sum()))
    c[1].metric("على رأس العمل", f"{int((A['الموقف'] == 'على رأس العمل').sum()):,}")
    c[2].metric("في إجازة", f"{int((A['الموقف'] == 'في إجازة').sum()):,}")
    st.caption(f"الجنسية تُستنتج من رقم الهوية/الإقامة (يبدأ بـ1 سعودي و2 أجنبي)، وعند غيابه من وجود رسم إقامة في الرواتب؛ غير المحدد: {un}. "
               f"للمطابقة: شهادة التأمينات {sett['gosi_date']}: سعوديون {sett['gosi_saudi']:,} وأجانب {sett['gosi_foreign']:,} "
               f"(مقابل {sa:,} و{fo:,} في ملف الموظفين).")
    for g in GROUPS:
        G = A[A["المجموعة"] == g]
        if not len(G):
            continue
        _title(f"مجموعة: {g}")
        tot = len(G)
        s = int((G["الجنسية"] == "سعودي").sum())
        f = int((G["الجنسية"] == "أجنبي").sum())
        rq = float(sett["req"].get(g, 0.0))
        need = int(np.ceil(tot * rq / 100.0 - 1e-9))
        cur = s / tot * 100 if tot else 0
        stat = "—" if rq == 0 else ("ملتزم" if s >= need else f"عجز {need - s}")
        c1, c2 = st.columns(2)
        with c1:
            st.caption("التصنيف: أجنبي وسعودي ونسبة التوطين")
            rows = [("item", "الإجمالي", [str(tot)]), ("item", "سعوديون", [str(s)]), ("item", "أجانب", [str(f)]),
                    ("item", "النسبة المطلوبة", [f"{rq:.0f}%"]), ("item", "النسبة الحالية", [f"{cur:.1f}%"]),
                    ("item", "العدد المطلوب من السعوديين", [str(need)]), ("total", "الموقف", [stat])]
            st.table(build(rows, ["البند", "القيمة"]))
        with c2:
            st.caption("الموقف: على رأس العمل وفي إجازة")
            rows = []
            for lab, mask in [("الإجمالي", None), ("سعوديون", G["الجنسية"] == "سعودي"), ("أجانب", G["الجنسية"] == "أجنبي")]:
                D = G if mask is None else G[mask]
                w = int((D["الموقف"] == "على رأس العمل").sum())
                l = int((D["الموقف"] == "في إجازة").sum())
                rows.append(("item" if mask is not None else "subtotal", lab, [str(w), str(l), _pct(l, w + l)]))
            st.table(build(rows, ["الفئة", "على رأس العمل", "في إجازة", "نسبة الإجازة"]))


def _browse(V):
    _title("استعراض العاملين بالشركة")
    st.markdown('<div class="hr-note">سيُضاف لاحقاً تقرير الاسترجاع الذي ستُرفقه ببياناته المطلوبة؛ الجدول الحالي من ملف الموظفين والرواتب.</div>', unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    by = c1.selectbox("الاستعراض حسب", ["المهنة", "الجنسية", "المجموعة الرئيسية", "العقد"], key="hr_by")
    stat = c4.multiselect("الموقف", ["على رأس العمل", "في إجازة", "مستقيل"], default=["على رأس العمل", "في إجازة"], key="hr_stat")
    D = V[V["الموقف"].isin(stat)] if stat else V
    col = {"المهنة": "المهنة", "الجنسية": "الجنسية", "المجموعة الرئيسية": "المجموعة", "العقد": "العقد"}[by]
    G = D.groupby(col).agg(**{"العدد": ("الاسم", "size"), "سعوديون": ("الجنسية", lambda s: int((s == "سعودي").sum())),
                              "أجانب": ("الجنسية", lambda s: int((s == "أجنبي").sum())), "إجمالي الرواتب": ("إجمالي الراتب", "sum")})
    G = G.sort_values("العدد", ascending=False)
    val = c2.selectbox("اختر القيمة", ["الكل"] + list(G.index), key="hr_val")
    q = c3.text_input("بحث بالاسم", key="hr_q").strip()
    Gt = G.reset_index()
    Gt = Gt[list(Gt.columns[1:][::-1]) + [Gt.columns[0]]]
    with st.container(key="hr_grid_sum"):
        st.dataframe(Gt.style.format({"العدد": "{:,.0f}", "سعوديون": "{:,.0f}", "أجانب": "{:,.0f}", "إجمالي الرواتب": "{:,.0f}"}), hide_index=True, use_container_width=True,
                     height=min(380, 38 + 35 * len(Gt)))
    if val != "الكل":
        D = D[D[col] == val]
    if q:
        D = D[D["الاسم"].str.contains(re.escape(q), case=False, regex=True)]
    T = D[["الاسم", "الرقم الوظيفي", "المهنة", "المجموعة", "الجنسية", "العقد", "الموقع", "الموقف", "تاريخ التعيين", "نهاية العقد", "اخر اجازة", "الراتب الأساسي", "إجمالي الراتب"]].copy()
    for c in ["تاريخ التعيين", "نهاية العقد", "اخر اجازة"]:
        T[c] = T[c].dt.strftime("%Y-%m-%d")
    st.caption(f"{len(T):,} موظفاً")
    T = T[list(T.columns[::-1])]
    with st.container(key="hr_grid_emp"):
        st.dataframe(T.style.format({"الراتب الأساسي": "{:,.0f}", "إجمالي الراتب": "{:,.0f}"}), hide_index=True, use_container_width=True, height=480)
    st.download_button("⬇️ تنزيل القائمة (CSV)", data=D.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig"), file_name="hr_employees.csv", mime="text/csv", key="hr_dl")


def _increases(A, unlocked, ym):
    _title("تقرير العلاوات")
    st.markdown('<div class="hr-note">يحفظ العلاوات المعتمدة ويحسب أثرها: نقدياً لمدة 12 شهراً، وعلى مخصص الإجازة (دورة 12 شهراً من تاريخ آخر إجازة)، وعلى مخصص نهاية الخدمة '
                '(من تاريخ التعيين حتى نهاية العقد: نصف شهر عن كل سنة من الخمس الأولى وشهر عن كل سنة بعدها). تُضاف الزيادة إلى الأساس المستخدم في المخصصات.</div>', unsafe_allow_html=True)
    sett = st.session_state["hr_set"]
    c1, c2 = st.columns(2)
    by = c1.selectbox("عرض العمالة حسب", ["المهنة", "الموقع"], key="hr_inc_by")
    col = "المهنة" if by == "المهنة" else "الموقع"
    vals = ["الكل"] + sorted(A[col].dropna().unique().tolist())
    val = c2.selectbox("القيمة", vals, key="hr_inc_val")
    today = pd.Timestamp(dt.date.today())
    D = A.copy() if val == "الكل" else A[A[col] == val].copy()
    inc = st.session_state["hr_inc"].drop_duplicates("الرقم الوظيفي", keep="last").set_index("الرقم الوظيفي")["الزيادة"]
    D["الزيادة المعتمدة"] = D["الرقم الوظيفي"].map(inc).fillna(0.0).astype(float)
    D["المدة من آخر إجازة (شهر)"] = ((today - D["اخر اجازة"]).dt.days / 30.44).round(1)
    yrs = ((today - D["تاريخ التعيين"]).dt.days / 365.25).fillna(0)
    ann = np.where(yrs >= 5, sett["leave_days_ge5"], sett["leave_days_lt5"])
    D["إجازة مستحقة منذ آخر إجازة (يوم)"] = (D["المدة من آخر إجازة (شهر)"].clip(lower=0).fillna(0) / 12 * ann).round(1)
    end = D["نهاية العقد"].fillna(today)
    T_ = ((end - D["تاريخ التعيين"]).dt.days / 365.25).clip(lower=0).fillna(0)
    d = D["الزيادة المعتمدة"]
    D["أثر نقدي 12 شهراً"] = d * 12
    D["أثر على مخصص الإجازة"] = d / 30 * ann
    D["أثر على مخصص نهاية الخدمة"] = d * T_.map(eosb_factor)
    D["إجمالي الأثر على المخصصات"] = D["أثر على مخصص الإجازة"] + D["أثر على مخصص نهاية الخدمة"]
    D["إجمالي الأثر"] = D["أثر نقدي 12 شهراً"] + D["إجمالي الأثر على المخصصات"]
    cc = st.columns(5)
    cc[0].metric("إجمالي الزيادة الشهرية", _fmt(d.sum()))
    cc[1].metric("الأثر النقدي 12 شهراً", _fmt(D["أثر نقدي 12 شهراً"].sum()))
    cc[2].metric("أثر مخصص الإجازة", _fmt(D["أثر على مخصص الإجازة"].sum()))
    cc[3].metric("أثر مخصص نهاية الخدمة", _fmt(D["أثر على مخصص نهاية الخدمة"].sum()))
    cc[4].metric("إجمالي الأثر", _fmt(D["إجمالي الأثر"].sum()))
    D = D.sort_values(["الزيادة المعتمدة", "إجمالي الراتب"], ascending=False)
    D["تاريخ التعيين"] = D["تاريخ التعيين"].dt.strftime("%Y-%m-%d")
    cols = ["الاسم", "المهنة", "تاريخ التعيين", "الراتب الأساسي", "تاريخ آخر زيادة", "مبلغ آخر زيادة", "المدة من آخر إجازة (شهر)", "إجازة مستحقة منذ آخر إجازة (يوم)",
            "الزيادة المعتمدة", "أثر نقدي 12 شهراً", "أثر على مخصص الإجازة", "أثر على مخصص نهاية الخدمة", "إجمالي الأثر"]
    T = D[cols].reset_index(drop=True)
    fm = {c: "{:,.0f}" for c in ["الراتب الأساسي", "مبلغ آخر زيادة", "الزيادة المعتمدة", "أثر نقدي 12 شهراً", "أثر على مخصص الإجازة", "أثر على مخصص نهاية الخدمة", "إجمالي الأثر"]}
    fm.update({"المدة من آخر إجازة (شهر)": "{:.1f}", "إجازة مستحقة منذ آخر إجازة (يوم)": "{:.1f}"})
    Tr = T[list(T.columns[::-1])]
    sel = []
    with st.container(key="hr_grid_inc"):
        try:
            ev = st.dataframe(Tr.style.format(fm, na_rep=""), hide_index=True, use_container_width=True, height=520,
                              on_select="rerun" if unlocked else "ignore", selection_mode="multi-row", key=f"hr_inc_df_{by}_{val}")
            sel = list(ev.selection.rows) if unlocked else []
        except TypeError:
            st.dataframe(Tr.style.format(fm, na_rep=""), hide_index=True, use_container_width=True, height=520)
    if not unlocked:
        st.caption("🔒 لاعتماد العلاوات أدخل كلمة السر في الشريط الجانبي.")
        return
    st.caption("حدّد موظفاً أو أكثر بالمربعات على يمين الجدول، ثم أدخل مبلغ العلاوة الشهرية (أو نسبة من الراتب الأساسي) واضغط اعتماد. صفر يلغي العلاوة.")
    ids = [D.iloc[i]["الرقم الوظيفي"] for i in sel if i < len(D)]
    m1, m2, m3 = st.columns([2, 2, 2])
    mode = m1.radio("طريقة الإدخال", ["مبلغ شهري", "نسبة من الراتب الأساسي"], horizontal=True, key="hr_inc_mode")
    amt = m2.number_input("القيمة", min_value=0.0, value=0.0, step=100.0 if mode == "مبلغ شهري" else 1.0, key="hr_inc_amt")
    if m3.button(f"اعتماد للمحدد ({len(ids)})", disabled=not ids, key="hr_inc_apply"):
        cur = st.session_state["hr_inc"]
        cur = cur[~cur["الرقم الوظيفي"].isin(ids)]
        base = A.set_index("الرقم الوظيفي")["الراتب الأساسي"]
        rows = [[i, (amt if mode == "مبلغ شهري" else float(base.get(i, 0) or 0) * amt / 100.0)] for i in ids]
        new = pd.concat([cur, pd.DataFrame(rows, columns=["الرقم الوظيفي", "الزيادة"])], ignore_index=True)
        new = new[new["الزيادة"].fillna(0) != 0]
        st.session_state["hr_inc"] = new
        try:
            new.to_csv(INC_FILE, index=False, encoding="utf-8-sig")
        except Exception:
            pass
        st.rerun()
    st.download_button("⬇️ نسخة احتياطية من العلاوات المعتمدة (CSV)", data=st.session_state["hr_inc"].to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig"),
                       file_name="hr_increases_backup.csv", mime="text/csv", key="hr_inc_bk")


def _provisions(A, sett, build):
    _title("المخصصات المستحقة على الشركة (تقدير أولي)")
    st.markdown('<div class="hr-note">تقدير أولي من بيانات الموظفين والرواتب بانتظار التقرير التفصيلي: مخصص الإجازة = الأيام المستحقة منذ آخر إجازة × الأجر اليومي (إجمالي الراتب ÷ 30)، '
                'ومخصص نهاية الخدمة = وفق المادة 84 من نظام العمل (نصف شهر لكل سنة من الخمس الأولى وشهر بعدها) على الراتب الأساسي حتى اليوم. '
                'ستُقارن لاحقاً بأرصدة المخصصات في ميزان المراجعة.</div>', unsafe_allow_html=True)
    today = pd.Timestamp(dt.date.today())
    D = A.copy()
    yrs = ((today - D["تاريخ التعيين"]).dt.days / 365.25).clip(lower=0).fillna(0)
    ann = np.where(yrs >= 5, sett["leave_days_ge5"], sett["leave_days_lt5"])
    m = ((today - D["اخر اجازة"]).dt.days / 30.44).clip(lower=0).fillna(0)
    days = m / 12 * ann
    sal = D["إجمالي الراتب"].fillna(0)
    D["مخصص الإجازة"] = days * sal / 30
    D["مخصص نهاية الخدمة"] = yrs.map(eosb_factor) * D["الراتب الأساسي"].fillna(0)
    D["الإجمالي"] = D["مخصص الإجازة"] + D["مخصص نهاية الخدمة"]
    by = st.radio("التجميع", ["حسب العقد", "حسب المجموعة الرئيسية"], horizontal=True, key="hr_prov_by")
    col = "العقد" if by == "حسب العقد" else "المجموعة"
    G = D.groupby(col).agg(n=("الاسم", "size"), l=("مخصص الإجازة", "sum"), e=("مخصص نهاية الخدمة", "sum"), t=("الإجمالي", "sum")).sort_values("t", ascending=False)
    rows = [("item", k, [str(int(r.n)), _fmt(r.l), _fmt(r.e), _fmt(r.t)]) for k, r in G.iterrows()]
    rows.append(("total", "الإجمالي", [str(int(G.n.sum())), _fmt(G.l.sum()), _fmt(G.e.sum()), _fmt(G.t.sum())]))
    st.table(build(rows, [col, "العدد", "مخصص الإجازة", "مخصص نهاية الخدمة", "الإجمالي"]))


def _actuarial(A, sett):
    _title("نهاية الخدمة الاكتواري (IAS 19)")
    st.markdown('<div class="hr-note">سيُبنى هذا التقرير عند رفع بيانات العمالة ودفعات نهاية الخدمة المسددة. الحساب الاكتواري يتطلب: تاريخ الميلاد والتعيين وتاريخ نهاية الخدمة المتوقع، '
                'تاريخ الرواتب والزيادات، فرضيات الخصم ونمو الرواتب ومعدل ترك الخدمة وسن التقاعد، ودفعات نهاية الخدمة المسددة فعلاً لمطابقة الحركة (أرباح وخسائر اكتوارية).</div>', unsafe_allow_html=True)
    today = pd.Timestamp(dt.date.today())
    yrs = ((today - A["تاريخ التعيين"]).dt.days / 365.25).clip(lower=0).fillna(0)
    liab = float((yrs.map(eosb_factor) * A["الراتب الأساسي"].fillna(0)).sum())
    st.metric("الالتزام الفوري لنهاية الخدمة وفق نظام العمل (غير مخصوم)", _fmt(liab))
    age_ok = int(A["تاريخ الميلاد"].notna().sum())
    st.caption(f"الموظفون ببيانات ميلاد: {age_ok:,} من {len(A):,}، وبتاريخ تعيين: {int(A['تاريخ التعيين'].notna().sum()):,}.")


def _suggested(V, A, pay, ym, sett, build):
    _title("تقارير مقترحة")
    st.caption("1) تكلفة العمالة الشهرية حسب العقد · 2) حركة العمالة الشهرية (عدد الرواتب) · 3) استحقاق الإجازات والتذاكر وانتهاء العقود")
    # 1
    st.markdown("**تكلفة العمالة حسب العقد (آخر شهر رواتب مكتمل: %s)**" % (ym or "—"))
    if ym:
        P = pay[pay["ym"] == ym].copy()
        cf_ = __import__("cashflow")
        P["العقد"] = P["الموقع"].map(lambda s: contract_of_site(s, cf_))
        G = P.groupby("العقد").agg(n=("الرقم الوظيفي", "nunique"), sal=("اجمالي الراتب", "sum"), ins=("تأمين اجتماعي", "sum"), med=("تأمين طبي شهري", "sum"), iq=("الاقامات", "sum")).sort_values("sal", ascending=False)
        rows = [("item", k, [str(int(r.n)), _fmt(r.sal), _fmt(r.ins), _fmt(r.med), _fmt(r.iq), _fmt(r.sal + r.ins + r.med + r.iq)]) for k, r in G.iterrows()]
        rows.append(("total", "الإجمالي", [str(int(G.n.sum())), _fmt(G.sal.sum()), _fmt(G.ins.sum()), _fmt(G.med.sum()), _fmt(G.iq.sum()), _fmt((G.sal + G.ins + G.med + G.iq).sum())]))
        st.table(build(rows, ["العقد", "العدد", "الرواتب", "التأمينات", "التأمين الطبي", "الإقامات", "إجمالي التكلفة"]))
    # 2
    st.markdown("**حركة العمالة الشهرية (من ملف الرواتب)**")
    n = pay.groupby("ym").agg(n=("الرقم الوظيفي", "nunique"), sal=("اجمالي الراتب", "sum")).sort_index()
    rows = [("item", m, [str(int(r.n)), _fmt(r.sal)]) for m, r in n.iterrows()]
    st.table(build(rows, ["الشهر", "عدد الموظفين", "إجمالي الرواتب"]))
    # 3
    st.markdown("**استحقاقات تحتاج متابعة**")
    today = pd.Timestamp(dt.date.today())
    D = A.copy()
    D["أشهر منذ آخر إجازة"] = ((today - D["اخر اجازة"]).dt.days / 30.44).round(1)
    late = D[(D["الموقف"] == "على رأس العمل") & (D["أشهر منذ آخر إجازة"] >= 11)].sort_values("أشهر منذ آخر إجازة", ascending=False)
    ends = D[(D["نهاية العقد"] <= today + pd.Timedelta(days=90))].sort_values("نهاية العقد")
    c1, c2 = st.columns(2)
    c1.caption(f"على رأس العمل ولم يأخذوا إجازة منذ 11 شهراً فأكثر: {len(late):,}")
    c2.caption(f"عقود منتهية أو تنتهي خلال 90 يوماً: {len(ends):,}")
    for T, cols, key in [(late, ["الاسم", "المهنة", "العقد", "أشهر منذ آخر إجازة"], "late"), (ends, ["الاسم", "المهنة", "العقد", "نهاية العقد"], "ends")]:
        X = T[cols].copy()
        if "نهاية العقد" in X.columns:
            X["نهاية العقد"] = X["نهاية العقد"].dt.strftime("%Y-%m-%d")
        X = X[list(X.columns[::-1])].head(200)
        with st.container(key="hr_grid_" + key):
            st.dataframe(X, hide_index=True, use_container_width=True, height=300)
