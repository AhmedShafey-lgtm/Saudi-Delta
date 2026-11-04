# hr.py
# تبويب الموارد البشرية: ملخص العمالة والسعودة، استعراض العاملين، العلاوات، المخصصات، نهاية الخدمة.
# المصادر: ملف بيانات الموظفين (الحالة، المهنة، الموقع، تواريخ التعيين والعقد وآخر إجازة) وتفاصيل الرواتب الشهرية.

import io, os, re, json, hashlib, datetime as dt
import numpy as np
import openpyxl
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
              padding:11px 16px; border-radius:8px; margin:20px 0 10px 0; font-weight:700; font-size:1.18rem;
              letter-spacing:.2px; }
  .hr-sub { direction: rtl; text-align: right; color:#1E3A8A; border-right:4px solid #3B5FC4;
            background:#EEF2FB; padding:7px 13px; border-radius:6px; margin:16px 0 6px 0;
            font-weight:700; font-size:1.04rem; }
  .hr-sub .tag { float:left; font-weight:700; font-size:.92rem; padding:1px 10px; border-radius:999px; }
  .hr-sub .ok { background:#DCFCE7; color:#14532D; } .hr-sub .no { background:#FEE2E2; color:#991B1B; }
  .hr-sub .na { background:#E2E8F0; color:#475569; }
  .hr-note { direction: rtl; text-align: right; background:#FFF7E0; border-right:4px solid #F59E0B; color:#7A4B00;
             padding:9px 13px; border-radius:6px; font-size:1.0rem; line-height:1.75; margin:7px 0; }
  /* بطاقات المؤشرات: رقم كبير واضح بدل خط الميتريك الصغير */
  .hr-kpis { display:flex; flex-wrap:wrap; gap:10px; margin:8px 0 14px 0; }
  .hr-kpi { flex:1 1 170px; min-width:158px; background:#F8FAFC; border:1px solid #E2E8F0;
            border-top:3px solid #1E3A8A; border-radius:9px; padding:11px 13px; }
  .hr-kpi .lbl { color:#475569; font-size:.88rem; font-weight:600; line-height:1.5; }
  .hr-kpi .val { color:#1E3A8A; font-size:1.55rem; font-weight:800; line-height:1.3; margin-top:2px;
                 font-variant-numeric: tabular-nums; }
  .hr-kpi .sub { color:#64748B; font-size:.82rem; margin-top:2px; }
  .hr-kpi.ok   { border-top-color:#0E9F6E; } .hr-kpi.ok .val   { color:#0E7C57; }
  .hr-kpi.bad  { border-top-color:#B91C1C; } .hr-kpi.bad .val  { color:#B91C1C; }
  .hr-kpi.gold { border-top-color:#C9A227; } .hr-kpi.gold .val { color:#8A6D12; }
  /* الجداول: خط أكبر وصفوف أوضح */
  [class*="st-key-hr_grid"] [data-testid="stDataFrame"], [class*="st-key-hr_grid"] [data-testid="stDataFrame"] * {
      direction: ltr !important; text-align: left !important; }
  [class*="st-key-hr_grid"] [data-testid="stDataFrame"] { font-size: 1.02rem !important; }
  [class*="st-key-hr_grid"] [role="columnheader"] { font-weight: 700 !important; font-size: 1.0rem !important; }
  [class*="st-key-hr_grid"] [role="gridcell"] { font-size: 1.0rem !important; }
</style>
"""


def _sub(text, tag="", tone="na"):
    """عنوان فرعي خفيف للمجموعات مع وسم حالة على اليسار."""
    t = f'<span class="tag {tone}">{tag}</span>' if tag else ""
    st.markdown(f'<div class="hr-sub">{t}{text}</div>', unsafe_allow_html=True)


def _box(key):
    """حاوية بمفتاح لتطبيق التنسيق، مع بديل للإصدارات التي لا تدعم المفتاح."""
    try:
        return st.container(key=key)
    except TypeError:
        return st.container()


def _kpis(items):
    """بطاقات مؤشرات: (العنوان، القيمة، سطر فرعي، النغمة: '' أو ok أو bad أو gold)."""
    h = '<div class="hr-kpis">'
    for it in items:
        lbl, val = it[0], it[1]
        sub = it[2] if len(it) > 2 else ""
        tone = it[3] if len(it) > 3 else ""
        h += f'<div class="hr-kpi {tone}"><div class="lbl">{lbl}</div><div class="val">{val}</div><div class="sub">{sub}</div></div>'
    st.markdown(h + "</div>", unsafe_allow_html=True)

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
ACT_DEFAULTS = {"val_date": "2026-12-31", "dr": 5.30, "dr_open": 5.30, "si": 2.0, "open_net": 16099000.0, "open_adv": 16387297.0, "extra_pay": 0.0}
ACTIVE = ["يعمل", "نشط"]
ON_LEAVE = ["مجاز"]
EMP_COLS = ["الرقم الوظيفي", "الاسم", "المهنة", "الموقع", "الحالة", "تاريخ التعيين", "بداية العقد", "نهاية العقد", "اخر اجازة", "اخر تذكرة", "تاريخ الميلاد", "الرقم", "الجنسية"]
EOSB_FILE = os.path.join(HERE, "hr_eosb.csv")
EOSB_COLS = ["الكود", "الاسم", "حتى 2024", "2025", "2026", "الحالة"]
LSA_FILE = os.path.join(HERE, "hr_leave_sa.csv")
LSA_COLS = ["الرقم الوظيفي", "الاسم", "رصيد أيام", "ملاحظات"]
LPR_FILE = os.path.join(HERE, "hr_leave_prog.csv")
LPR_COLS = ["الرقم الوظيفي", "بداية", "نهاية", "أيام"]
SAL_FILE = os.path.join(HERE, "hr_salary.csv")
SAL_COLS = ["الرقم الوظيفي", "الاسم", "الموقع", "المهنة", "الفئة", "الأساسي", "البدلات", "الإجمالي", "تاريخ آخر زيادة", "مبلغ آخر زيادة"]
PROP_FILE = os.path.join(HERE, "hr_inc_prop.csv")
PAY_COLS = ["الرقم الوظيفي", "ym", "الراتب", "اجمالي الراتب", "تأمين اجتماعي", "تأمين طبي شهري", "التنقلات", "الاقامات", "بدل سكن", "بدل انتقال", "المهنة", "الموقع"]


# ---------------- التحميل والتخزين ----------------
def _norm_cols(df):
    df.columns = [re.sub(r"\s+", " ", str(c)).strip() for c in df.columns]
    return df


def _sniff_leave(raw):
    """يتعرف على ملفي الإجازات: رصيد أيام السعوديين، وتقرير إجازات البرنامج (Employee Vacation Report)."""
    try:
        wb = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
        ws = wb.worksheets[0]
        txt = " ".join(str(v) for r in ws.iter_rows(min_row=1, max_row=12, values_only=True) for v in r if v is not None)
        wb.close()
    except Exception:
        return None
    if "Employee Vacation Report" in txt:
        return "إجازات_برنامج"
    if "المتبقي المعتمد" in txt and "الرصيد الحالي" in txt:
        return "إجازات_سعوديين"
    return None


def parse_leave_sa(raw):
    """رصيد إجازات السعوديين بالأيام (ورقة البيان المجمع): الرقم، الاسم، الرصيد الحالي (أيام)، الملاحظات."""
    df = pd.read_excel(io.BytesIO(raw), sheet_name=0, header=None)
    hi = next(i for i in range(min(15, len(df))) if "الرصيد الحالي" in [str(x).strip() for x in df.iloc[i].tolist()])
    df.columns = [re.sub(r"\s+", " ", str(c)).strip() for c in df.iloc[hi].tolist()]
    df = df.iloc[hi + 1:]
    df = df[pd.to_numeric(df["الرقم"], errors="coerce").notna()].copy()
    df["الرقم الوظيفي"] = pd.to_numeric(df["الرقم"]).astype("int64").astype(str)
    df["رصيد أيام"] = pd.to_numeric(df["الرصيد الحالي"], errors="coerce")  # #VALUE! تبقى فارغة وتُعرض كملاحظة جودة
    df["الاسم"] = df["الاسم"].fillna("").astype(str).str.strip()
    df["ملاحظات"] = df["ملاحظات"].fillna("").astype(str).str.strip() if "ملاحظات" in df.columns else ""
    return df[LSA_COLS].drop_duplicates("الرقم الوظيفي", keep="last").reset_index(drop=True)


def parse_leave_prog(raw):
    """تقرير إجازات البرنامج: يستخرج الإجازات الفعلية المنتهية (بداية ونهاية فعلية وأيام) لكل موظف."""
    import datetime as _dt
    wb = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
    cur, recs = None, []
    for r in wb.worksheets[0].iter_rows(values_only=True):
        r = list(r) + [None] * 20
        if r[0] == "Employee Code :":
            cur = str(r[3]).strip()
        elif cur and isinstance(r[0], _dt.datetime) and isinstance(r[5], _dt.datetime) and isinstance(r[8], _dt.datetime):
            recs.append((cur, r[5], r[8], r[13]))
    wb.close()
    d = pd.DataFrame(recs, columns=LPR_COLS)
    d["أيام"] = pd.to_numeric(d["أيام"], errors="coerce").fillna((d["نهاية"] - d["بداية"]).dt.days + 1)
    d = d.drop_duplicates(["الرقم الوظيفي", "بداية", "نهاية"], keep="last")
    return d.reset_index(drop=True)


def parse_salary_snapshot(raw):
    """كشف الرواتب الحالية المسترجع: الأساسي/البدلات/الإجمالي وآخر زيادة وتاريخها لكل موظف مع الموقع والمهنة والفئة."""
    df = pd.read_excel(io.BytesIO(raw), sheet_name=0)
    df.columns = [re.sub(r"\s+", " ", str(c)).strip() for c in df.columns]
    cols = list(df.columns)
    def col(name, pos):
        return name if name in cols else (cols[pos] if len(cols) > pos else None)
    c_id = cols[-1]
    c_nm = cols[-2]
    out = pd.DataFrame({
        "الرقم الوظيفي": pd.to_numeric(df[c_id], errors="coerce").map(lambda v: "" if pd.isna(v) else str(int(v))),
        "الاسم": df[c_nm].fillna("").astype(str).str.strip(),
        "الموقع": df[col("الموقع", 5)].fillna("").astype(str).str.strip(),
        "المهنة": df[col("المهنة", 6)].fillna("").astype(str).str.strip(),
        "الفئة": df[cols[7]].fillna("").astype(str).str.strip(),
        "الأساسي": pd.to_numeric(df["الاساسي"], errors="coerce"),
        "البدلات": pd.to_numeric(df["البدلات"], errors="coerce"),
        "الإجمالي": pd.to_numeric(df["الاجمالي"], errors="coerce"),
        "تاريخ آخر زيادة": pd.to_datetime(df["اخر زيادة"], errors="coerce"),
        "مبلغ آخر زيادة": pd.to_numeric(df["مبلغ اخر زيادة"], errors="coerce"),
    })
    out = out[out["الرقم الوظيفي"] != ""].drop_duplicates("الرقم الوظيفي", keep="last")
    return out[SAL_COLS].reset_index(drop=True)


def parse_proposed(raw):
    """ملف زيادات مقترحة: إما برقم الموظف (الرقم الوظيفي/الكود) أو بقاعدة (المهنة أو الموقع/العقد)، وبمبلغ شهري (الزيادة) أو نسبة % من الراتب الأساسي."""
    raw_df = pd.read_excel(io.BytesIO(raw), sheet_name=0, header=None)
    id_names = ("الرقم الوظيفي", "رقم الموظف", "الكود")
    hi = next((i for i in range(min(15, len(raw_df))) if any(str(x).strip() in id_names for x in raw_df.iloc[i].tolist())), None)
    if hi is None:
        df = _norm_cols(pd.read_excel(io.BytesIO(raw), sheet_name=0))
    else:
        df = raw_df.iloc[hi + 1:].copy()
        df.columns = [re.sub(r"\s+", " ", str(c)).strip() for c in raw_df.iloc[hi].tolist()]
        cid0 = next(c for c in df.columns if c in id_names)
        df = df[pd.to_numeric(df[cid0], errors="coerce").notna()].reset_index(drop=True)
    def pick(*names):
        for n in names:
            for c in df.columns:
                if n in c:
                    return c
        return None
    cid = pick("الرقم الوظيفي", "الكود", "رقم الموظف", "الرقم")
    camt = pick("مقترح الزيادة", "مبلغ الزيادة", "الزيادة المقترحة", "الزيادة", "المبلغ")
    cpct = pick("النسبة", "نسبة")
    cprof = pick("المهنة")
    csite = pick("الموقع", "العقد")
    if camt is None and cpct is None:
        raise ValueError("لم أجد عمود مبلغ الزيادة أو النسبة")
    if cid is None and cprof is None and csite is None:
        raise ValueError("لم أجد عمود الرقم الوظيفي أو المهنة أو الموقع")
    out = pd.DataFrame({
        "الرقم الوظيفي": (pd.to_numeric(df[cid], errors="coerce").map(lambda v: "" if pd.isna(v) else str(int(v)))) if cid else "",
        "الزيادة": pd.to_numeric(df[camt], errors="coerce") if camt else np.nan,
        "النسبة": pd.to_numeric(df[cpct], errors="coerce") if cpct else np.nan,
        "المهنة": df[cprof].fillna("").astype(str).str.strip() if cprof and cprof != cid else "",
        "الموقع": df[csite].fillna("").astype(str).str.strip() if csite and csite != cid else ""})
    return out[(out["الزيادة"].fillna(0) != 0) | (out["النسبة"].fillna(0) != 0)].reset_index(drop=True)


def resolve_proposed(P, A):
    """يحوّل الملف المقترح إلى مبلغ شهري لكل موظف (الرقم الوظيفي → مبلغ). قاعدة الموظف بالرقم تغلب قاعدة المهنة/الموقع."""
    res = pd.Series(0.0, index=A["الرقم الوظيفي"].values)
    if not len(P):
        return res
    base = A.set_index("الرقم الوظيفي")["الراتب الأساسي"].fillna(0)
    def amt(r, ids):
        if pd.notna(r["الزيادة"]) and r["الزيادة"] != 0:
            return pd.Series(float(r["الزيادة"]), index=ids)
        return base.reindex(ids).fillna(0) * float(r["النسبة"] or 0) / 100.0
    for _, r in P[P["الرقم الوظيفي"].astype(str).str.len() == 0].iterrows():
        m = pd.Series(True, index=A.index)
        if r["المهنة"]:
            m &= A["المهنة"].astype(str).str.contains(re.escape(r["المهنة"]), regex=True)
        if r["الموقع"]:
            m &= A["الموقع"].astype(str).str.contains(re.escape(r["الموقع"]), regex=True) | A["العقد"].astype(str).str.contains(re.escape(r["الموقع"]), regex=True)
        ids = A.loc[m, "الرقم الوظيفي"].values
        res.loc[ids] = amt(r, ids).values
    for _, r in P[P["الرقم الوظيفي"].astype(str).str.len() > 0].iterrows():
        i = str(r["الرقم الوظيفي"])
        if i in res.index:
            res.loc[i] = float(amt(r, [i]).iloc[0])
    return res


def foreign_hc_by_month(cf):
    """عدد العمالة الأجنبية لكل عقد في كل شهر (من تفاصيل الرواتب)، أو العدد الحالي إن لم تتوفر الرواتب. يُستخدم لتوزيع الإقامات والتأشيرات.
    يعيد DataFrame فهرسه الشهر (أو '*' للعدد الحالي) وأعمدته العقود."""
    emp, pay, _, sett = _state()
    if not len(emp):
        return None
    key = (len(emp), len(pay), len(st.session_state.get("hr_sal", [])), str(pay["ym"].max()) if len(pay) else "")
    ch = st.session_state.get("_hr_fhc")
    if ch and ch[0] == key:
        return ch[1]
    V = build_view(emp, pay, sett, cf, st.session_state.get("hr_sal"))
    nat = V.set_index("الرقم الوظيفي")["الجنسية"]
    if len(pay):
        P = pay[["الرقم الوظيفي", "ym", "الموقع"]].copy()
        P = P[P["الرقم الوظيفي"].map(nat) == "أجنبي"]
        P["العقد"] = P["الموقع"].map(lambda x: contract_of_site(x, cf))
        out = P.groupby(["ym", "العقد"])["الرقم الوظيفي"].nunique().unstack(fill_value=0)
    else:
        A = V[V["نشط"] & (V["الجنسية"] == "أجنبي")]
        out = pd.DataFrame([A.groupby("العقد").size()], index=["*"]).fillna(0)
    st.session_state["_hr_fhc"] = (key, out)
    return out


def leave_days(A, sett, lsa, lpr, today, sa_date):
    """أيام الإجازة المستحقة لكل موظف:
    - سعودي له رصيد في ملف الأرصدة: الرصيد بالأيام (السالب = صفر) + استحقاق ما بعد تاريخ الرصيد.
    - غير ذلك (الأجانب وغيرهم): الاستحقاق من تاريخ آخر إجازة فعلية (تقرير البرنامج أو الملف الرئيسي) أو من التعيين إن لم توجد."""
    D = A[["الرقم الوظيفي", "الاسم", "الجنسية", "تاريخ التعيين", "اخر اجازة"]].copy()
    yrs = ((today - D["تاريخ التعيين"]).dt.days / 365.25).clip(lower=0).fillna(0)
    D["سنوي"] = np.where(yrs >= 5, sett["leave_days_ge5"], sett["leave_days_lt5"])
    if len(lpr):
        D["آخر إجازة (برنامج)"] = D["الرقم الوظيفي"].map(lpr.groupby("الرقم الوظيفي")["نهاية"].max())
    else:
        D["آخر إجازة (برنامج)"] = pd.NaT
    D["آخر إجازة معتمدة"] = D[["آخر إجازة (برنامج)", "اخر اجازة"]].max(axis=1)
    D["بداية الاحتساب"] = D["آخر إجازة معتمدة"].where(D["آخر إجازة معتمدة"].notna(), D["تاريخ التعيين"])
    D["بداية الاحتساب"] = D[["بداية الاحتساب", "تاريخ التعيين"]].max(axis=1)
    if len(lsa):
        D["رصيد الملف"] = D["الرقم الوظيفي"].map(lsa.set_index("الرقم الوظيفي")["رصيد أيام"])
        has = D["رصيد الملف"].notna()
    else:
        D["رصيد الملف"] = np.nan
        has = pd.Series(False, index=D.index)
    sa_ts = pd.Timestamp(sa_date)
    post = ((today - sa_ts).days / 365.25) * D["سنوي"] if today > sa_ts else 0.0
    d_file = D["رصيد الملف"].clip(lower=0).fillna(0) + post
    d_calc = ((today - D["بداية الاحتساب"]).dt.days.clip(lower=0).fillna(0) / 365.25) * D["سنوي"]
    D["أيام الإجازة المستحقة"] = np.where(has, d_file, d_calc)
    D["مصدر الاحتساب"] = np.where(has, "رصيد الملف (سعوديون)", np.where(D["آخر إجازة (برنامج)"].notna(), "آخر إجازة من البرنامج", np.where(D["اخر اجازة"].notna(), "آخر إجازة من الملف الرئيسي", "من تاريخ التعيين")))
    return D


def detect(raw):
    """يعيد 'موظفين' أو 'رواتب' أو None بحسب رؤوس الأعمدة."""
    k = _sniff_leave(raw)
    if k:
        return k
    try:
        h = pd.read_excel(io.BytesIO(raw), sheet_name=0, nrows=1)
        hc = {re.sub(r"\s+", " ", str(c)).strip() for c in h.columns}
        if {"مبلغ اخر زيادة", "الاساسي", "الاجمالي"} <= hc:
            return "رواتب_حالية"
    except Exception:
        pass
    for sh in ("Report", 0):
        try:
            df = _norm_cols(pd.read_excel(io.BytesIO(raw), sheet_name=sh, nrows=3))
        except Exception:
            continue
        c = set(df.columns)
        if {"الحالة", "تاريخ التعيين", "اخر اجازة"} <= c:
            return "موظفين"
        if {"اجمالي الراتب", "الشهر"} <= c:
            return "رواتب"
        if {"الكود", "حتى 2024", "2025"} <= c:
            return "مدفوعات"
    return None


def parse_master(raw):
    try:
        df = _norm_cols(pd.read_excel(io.BytesIO(raw), sheet_name="Report"))
    except Exception:
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
    for c in ["الاسم", "المهنة", "الموقع", "الحالة", "الجنسية"]:
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


def parse_eosb(raw):
    df = _norm_cols(pd.read_excel(io.BytesIO(raw), sheet_name="Report"))
    df = df[df["الكود"].notna()].copy()
    df["الكود"] = pd.to_numeric(df["الكود"], errors="coerce")
    df = df[df["الكود"].notna()]
    df["الكود"] = df["الكود"].astype("int64").astype(str)
    for c in ["حتى 2024", "2025", "2026"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0) if c in df.columns else 0.0
    for c in ["الاسم", "الحالة"]:
        df[c] = df[c].fillna("").astype(str).str.strip() if c in df.columns else ""
    return df[EOSB_COLS].drop_duplicates("الكود", keep="last").reset_index(drop=True)


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
            if "الجنسية" not in e.columns:
                e["الجنسية"] = ""
            e = e.fillna({"الرقم": "", "الاسم": "", "المهنة": "", "الموقع": "", "الحالة": "", "الجنسية": ""})
        ss["hr_emp"] = e if e is not None else pd.DataFrame(columns=EMP_COLS)
    if "hr_pay" not in ss:
        p = _read_csv(PAY_FILE, dtype={"الرقم الوظيفي": str})
        ss["hr_pay"] = p if p is not None else pd.DataFrame(columns=PAY_COLS)
    if "hr_eosb" not in ss:
        x = _read_csv(EOSB_FILE, dtype={"الكود": str})
        ss["hr_eosb"] = x if x is not None else pd.DataFrame(columns=EOSB_COLS)
    if "hr_lsa" not in ss:
        x = _read_csv(LSA_FILE, dtype={"الرقم الوظيفي": str})
        ss["hr_lsa"] = x.fillna({"ملاحظات": "", "الاسم": ""}) if x is not None else pd.DataFrame(columns=LSA_COLS)
    if "hr_lpr" not in ss:
        x = _read_csv(LPR_FILE, dtype={"الرقم الوظيفي": str})
        if x is not None:
            x["بداية"] = pd.to_datetime(x["بداية"], errors="coerce"); x["نهاية"] = pd.to_datetime(x["نهاية"], errors="coerce")
        ss["hr_lpr"] = x if x is not None else pd.DataFrame(columns=LPR_COLS)
    if "hr_inc" not in ss:
        i = _read_csv(INC_FILE, dtype={"الرقم الوظيفي": str})
        ss["hr_inc"] = i if i is not None else pd.DataFrame(columns=["الرقم الوظيفي", "الزيادة"])
    if "hr_sal" not in ss:
        x = _read_csv(SAL_FILE, dtype={"الرقم الوظيفي": str})
        if x is not None:
            x["تاريخ آخر زيادة"] = pd.to_datetime(x["تاريخ آخر زيادة"], errors="coerce")
        ss["hr_sal"] = x if x is not None else pd.DataFrame(columns=SAL_COLS)
    if "hr_prop" not in ss:
        x = _read_csv(PROP_FILE, dtype={"الرقم الوظيفي": str})
        ss["hr_prop"] = x if x is not None else pd.DataFrame(columns=["الرقم الوظيفي", "الزيادة", "النسبة", "المهنة", "الموقع"])
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


def build_view(emp, pay, sett, cf, sal=None):
    """جدول العاملين الحاليين (يعمل/نشط/مجاز) مع الجنسية والمجموعة والعقد وآخر راتب."""
    E = emp.copy()
    iq = pay.groupby("الرقم الوظيفي")["الاقامات"].apply(lambda s: bool((s.fillna(0) > 0).any())) if len(pay) else pd.Series(dtype=bool)
    idn = E["الرقم"].astype(str).str[:1]
    nat = np.where(idn == "1", "سعودي", np.where(idn == "2", "أجنبي", ""))
    iqf = E["الرقم الوظيفي"].map(iq)
    iqf = iqf.where(iqf.notna(), False).astype(bool)
    nat = np.where((nat == "") & iqf, "أجنبي", nat)
    ctry = E["الجنسية"].astype(str).str.strip()
    E["الدولة"] = ctry
    nat = np.where(ctry != "", np.where(ctry.str.contains("سعود"), "سعودي", "أجنبي"), nat)
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
    E["الفئة"] = ""
    if sal is not None and len(sal):
        S_ = sal.drop_duplicates("الرقم الوظيفي", keep="last").set_index("الرقم الوظيفي")
        has = E["الرقم الوظيفي"].isin(S_.index)
        for dst, src in [("الراتب الأساسي", "الأساسي"), ("إجمالي الراتب", "الإجمالي"), ("مبلغ آخر زيادة", "مبلغ آخر زيادة")]:
            v_ = E["الرقم الوظيفي"].map(S_[src])
            E[dst] = np.where(has & v_.notna(), v_, E[dst])
        ld = pd.to_datetime(E["الرقم الوظيفي"].map(S_["تاريخ آخر زيادة"]), errors="coerce").dt.strftime("%Y-%m")
        E["تاريخ آخر زيادة"] = np.where(has, ld, E["تاريخ آخر زيادة"])
        E["الفئة"] = E["الرقم الوظيفي"].map(S_["الفئة"]).fillna("")
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
    fbar = st.container()
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
    V = build_view(emp, pay, sett, cf, st.session_state.get("hr_sal"))
    A_full = V[V["نشط"]].copy()
    with fbar:
        psel = st.multiselect("🔎 المهنة (فلتر ثابت يُطبَّق على كل أقسام الموارد البشرية عدا الاكتواري)", sorted(A_full["المهنة"].dropna().unique().tolist()),
                              key="hr_g_prof", placeholder="كل المهن")
        if not len(pay):
            st.warning("لا توجد تفاصيل رواتب محمّلة حالياً، لذا تظهر الرواتب والتأمينات والإقامات صفراً. أعد رفع ملف تفاصيل الرواتب الشهرية من «البيانات والإعدادات» "
                       "(الملفات المحفوظة قد تضيع عند إعادة تشغيل الاستضافة).")
    if psel:
        V = V[V["المهنة"].isin(psel)].copy()
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
        st.session_state["hr_unlocked"] = unlocked
        _actuarial(A_full, sett, st.session_state["hr_eosb"], build_styled_table)
    with t_sug:
        _suggested(V, A, pay, ym, sett, build_styled_table)


def _data_tab(unlocked, emp, pay, sett):
    _title("رفع البيانات")
    st.markdown('<div class="hr-note">ارفع ملف بيانات الموظفين (الحالة، المهنة، الموقع، تاريخ التعيين، العقد، آخر إجازة، الجنسية، تاريخ الميلاد) وملف تفاصيل الرواتب الشهرية وكشف دفعات نهاية الخدمة. '
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
                elif kind == "مدفوعات":
                    d = parse_eosb(raw)
                    st.session_state["hr_eosb"] = d
                    d.to_csv(EOSB_FILE, index=False, encoding="utf-8-sig")
                    st.success(f"{f.name}: دفعات نهاية الخدمة: {len(d)} موظفاً، 2026: {d['2026'].sum():,.0f}.")
                elif kind == "رواتب_حالية":
                    d = parse_salary_snapshot(raw)
                    st.session_state["hr_sal"] = d
                    d.to_csv(SAL_FILE, index=False, encoding="utf-8-sig")
                    st.success(f"{f.name}: كشف الرواتب الحالية: {len(d):,} موظفاً، إجمالي الرواتب {d['الإجمالي'].sum():,.0f}.")
                elif kind == "إجازات_سعوديين":
                    d = parse_leave_sa(raw)
                    st.session_state["hr_lsa"] = d
                    d.to_csv(LSA_FILE, index=False, encoding="utf-8-sig")
                    st.success(f"{f.name}: أرصدة إجازات السعوديين: {len(d)} موظفاً، إجمالي الأيام {d['رصيد أيام'].clip(lower=0).sum():,.0f}.")
                elif kind == "إجازات_برنامج":
                    d = parse_leave_prog(raw)
                    st.session_state["hr_lpr"] = d
                    d.to_csv(LPR_FILE, index=False, encoding="utf-8-sig")
                    st.success(f"{f.name}: إجازات البرنامج: {len(d):,} إجازة فعلية لـ {d['الرقم الوظيفي'].nunique():,} موظفاً حتى {d['نهاية'].max():%Y-%m-%d}.")
                elif kind == "رواتب":
                    d = parse_payroll(raw)
                    st.session_state["hr_pay"] = d
                    d.to_csv(PAY_FILE, index=False, encoding="utf-8-sig")
                    st.success(f"{f.name}: الرواتب: {len(d)} سطراً من {d['ym'].min()} إلى {d['ym'].max()}.")
                else:
                    st.warning(f"{f.name}: لم يُتعرَّف على نوع الملف (يلزم رأس أعمدة بيانات الموظفين أو تفاصيل الرواتب أو كشف دفعات نهاية الخدمة).")
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
    with _box("hr_grid_ref"):
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
    _backup_ui(unlocked)


# ---------------- النسخة الاحتياطية الشاملة ----------------
BK_FILES = {  # اسم داخل الأرشيف ← (مسار الملف على القرص، مفتاح الجلسة، هل هو مُدخَل يدوياً)
    "hr/increases.csv": (INC_FILE, "hr_inc", True),
    "hr/settings.json": (SET_FILE, "hr_set", True),
    "hr/proposed.csv": (PROP_FILE, "hr_prop", True),
    "hr/data/employees.csv": (EMP_FILE, "hr_emp", False),
    "hr/data/payroll.csv": (PAY_FILE, "hr_pay", False),
    "hr/data/eosb_paid.csv": (EOSB_FILE, "hr_eosb", False),
    "hr/data/leave_saudi.csv": (LSA_FILE, "hr_lsa", False),
    "hr/data/leave_program.csv": (LPR_FILE, "hr_lpr", False),
    "hr/data/salary_snapshot.csv": (SAL_FILE, "hr_sal", False),
    # التدفقات النقدية: التعديلات اليدوية على تصنيف السطور
    "cashflow/overrides.csv": (os.path.join(HERE, "cashflow_overrides.csv"), "cf_ovr", True),
    "cashflow/contractors.csv": (os.path.join(HERE, "cashflow_subs.csv"), "cf_subs", True),
    "cashflow/exp_overrides.csv": (os.path.join(HERE, "cashflow_exp_overrides.csv"), "cf_exovr", True),
    # تقارير المواقع
    "sites/map.csv": (os.path.join(HERE, "st_map.csv"), "sv_map", True),
    "sites/settings.json": (os.path.join(HERE, "st_settings.json"), "sv_cfg", True),
    "sites/data/bonus.csv.gz": (os.path.join(HERE, "st_bonus.csv.gz"), "sv_bon", False),
    "sites/data/notes.csv": (os.path.join(HERE, "st_notes.csv"), "sv_not", False),
    "sites/data/moves.csv.gz": (os.path.join(HERE, "st_moves.csv.gz"), "sv_mov", False),
    "sites/data/settle.csv.gz": (os.path.join(HERE, "st_settle.csv.gz"), "sv_set", False),
    "sites/data/work_orders.csv.gz": (os.path.join(HERE, "st_wo.csv.gz"), "sv_wo", False),
    "sites/data/productivity.csv": (os.path.join(HERE, "st_prod.csv"), "sv_prd", False),
    "sites/data/payroll_sites.csv.gz": (os.path.join(HERE, "st_pay.csv.gz"), "sv_pay", False),
    "sites/data/item_prices.csv": (os.path.join(HERE, "st_itemprices.csv"), "sv_ipr", False),
    "sites/data/contract_prices.csv": (os.path.join(HERE, "st_contractprices.csv"), "sv_cpr", False),
}


def make_backup(include_data=True):
    include_data = bool(include_data)
    """أرشيف ZIP واحد: العلاوات المعتمدة والمقترحة وإعدادات الموارد البشرية وبيانات البنوك، وملفات الموارد البشرية المرفوعة اختيارياً."""
    import zipfile
    ss = st.session_state
    buf = io.BytesIO()
    parts = []
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, (path, key, manual) in BK_FILES.items():
            if not manual and not include_data:
                continue
            obj = ss.get(key)
            if isinstance(obj, dict):
                z.writestr(name, json.dumps(obj, ensure_ascii=False)); parts.append(name)
            elif name.endswith(".gz"):
                # الملفات المضغوطة تُنسخ من القرص كما هي
                if os.path.exists(path):
                    z.write(path, name); parts.append(name)
            elif obj is not None and len(obj):
                z.writestr(name, obj.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")); parts.append(name)
            elif os.path.exists(path):
                z.write(path, name); parts.append(name)
        try:
            import banks as _bk
            if "bk_cur" in ss:
                _bk._save(ss["bk_cur"])
            if os.path.exists(_bk.DATA_FILE):
                z.write(_bk.DATA_FILE, "banks/bank_data.json"); parts.append("banks/bank_data.json")
        except Exception:
            pass
        z.writestr("manifest.json", json.dumps({"created": dt.datetime.now().isoformat(timespec="seconds"), "parts": parts, "include_data": bool(include_data)}, ensure_ascii=False))
    return buf.getvalue(), parts


def restore_backup(raw):
    """يستعيد الأرشيف إلى ملفات التطبيق ثم يفرّغ ذاكرة الجلسة لتُعاد قراءتها. يعيد قائمة ما استُعيد."""
    import zipfile
    z = zipfile.ZipFile(io.BytesIO(raw))
    names = set(z.namelist())
    if "manifest.json" not in names:
        raise ValueError("ليس ملف نسخة احتياطية صالحاً")
    ss = st.session_state
    done = []
    for name, (path, key, _) in BK_FILES.items():
        if name in names:
            with open(path, "wb") as f:
                f.write(z.read(name))
            ss.pop(key, None)
            done.append(name)
    if "banks/bank_data.json" in names:
        import banks as _bk
        with open(_bk.DATA_FILE, "wb") as f:
            f.write(z.read("banks/bank_data.json"))
        for k in ("bk_base", "bk_cur", "bk_ver"):
            ss.pop(k, None)
        done.append("banks/bank_data.json")
    ss.pop("_hr_fhc", None)
    ss.pop("hr_hashes", None)
    ss.pop("sv_cfg", None)
    for k in ("cf_ovr", "cf_ovr_ver", "cf_subs", "cf_exovr"):
        ss.pop(k, None)
    return done


def _backup_ui(unlocked):
    _title("النسخة الاحتياطية الشاملة")
    st.markdown('<div class="hr-note">ملف واحد يجمع: العلاوات المعتمدة والمقترحة، وإعدادات الموارد البشرية (التوطين والنطاق وقواعد المهن وفرضيات الاكتواري)، وبيانات البنوك، '
                'وملفات الموارد البشرية المرفوعة اختيارياً. احفظه بعد أي تعديل، واستعده بخطوة واحدة بعد كل إعادة تشغيل للاستضافة. '
                'والتعديلات اليدوية على تصنيف سطور التدفقات النقدية وقائمة المقاولين، '
                'وملفات تقارير المواقع (البونص وحركة الأصناف والتصفية وأوامر العمل والإنتاجية وجدول الربط). '
                'التدفقات النقدية لها نسخها الاحتياطية الخاصة بها.</div>', unsafe_allow_html=True)
    if not unlocked:
        st.info("🔒 النسخ والاستعادة مقفلان. أدخل كلمة السر في الشريط الجانبي.")
        return
    inc_data = st.checkbox("تضمين ملفات الموارد البشرية المرفوعة (الموظفين، الرواتب، الدفعات، الإجازات، كشف الرواتب)", value=True, key="hr_bk_data")
    data, parts = make_backup(inc_data)
    st.download_button(f"⬇️ نسخة احتياطية شاملة ({len(parts)} ملفاً، {len(data) / 1024:,.0f} KB)", data=data,
                       file_name=f"delta_backup_{dt.date.today():%Y%m%d}.zip", mime="application/zip", key="hr_bk_dl")
    up = st.file_uploader("استعادة من نسخة احتياطية (ZIP)", type=["zip"], key="hr_bk_up")
    if up is not None:
        h = hashlib.md5(up.getvalue()).hexdigest()
        if st.session_state.get("hr_bk_done") != h:
            ok = False
            try:
                done = restore_backup(up.getvalue())
                st.session_state["hr_bk_done"] = h
                st.session_state["hr_bk_msg"] = f"تمت الاستعادة: {len(done)} ملفاً."
                ok = True
            except Exception as e:
                st.error(f"تعذرت الاستعادة: {e}")
            if ok:
                st.rerun()
    if st.session_state.get("hr_bk_msg"):
        st.success(st.session_state.pop("hr_bk_msg"))


def _summary(A, pay, sett, ym, build):
    n_all = len(A)
    sa = int((A["الجنسية"] == "سعودي").sum())
    fo = int((A["الجنسية"] == "أجنبي").sum())
    un = n_all - sa - fo
    _title("الملخص العام للعمالة")
    mm = pay[pay["ym"] == ym] if ym else pay.iloc[0:0]
    full = [m for m in sorted(pay["ym"].unique()) if m.startswith(ym[:4]) and m <= ym and pay[pay["ym"] == m]["الرقم الوظيفي"].nunique() > 0.8 * len(mm["الرقم الوظيفي"].unique())] if ym else []
    iq_avg = float(np.mean([pay[pay["ym"] == m]["الاقامات"].sum() for m in full])) if full else 0.0
    on_job = int((A["الموقف"] == "على رأس العمل").sum())
    on_lv = int((A["الموقف"] == "في إجازة").sum())
    _kpis([
        ("إجمالي العمالة", f"{n_all:,}", f"على رأس العمل {on_job:,} · في إجازة {on_lv:,}"),
        ("سعوديون", f"{sa:,}", f"أجانب {fo:,}" + (f" · غير محدد {un:,}" if un else ""), "ok"),
        ("نسبة السعودة", _pct(sa, n_all), f"النطاق: {sett['band']}", "gold"),
        (f"إجمالي الرواتب ({ym or '—'})", _fmt(mm["اجمالي الراتب"].sum()), "شهر الرواتب المكتمل الأخير"),
    ])
    _kpis([
        ("التأمينات الاجتماعية", _fmt(mm["تأمين اجتماعي"].sum()), "شهرياً"),
        ("التأمين الطبي", _fmt(mm["تأمين طبي شهري"].sum()), "شهرياً"),
        ("متوسط الإقامات الشهرية", _fmt(iq_avg), f"متوسط {len(full)} أشهر مكتملة"),
        ("تكلفة العمالة الشهرية", _fmt(mm["اجمالي الراتب"].sum() + mm["تأمين اجتماعي"].sum() + mm["تأمين طبي شهري"].sum() + iq_avg),
         "رواتب + تأمينات + متوسط إقامات", "gold"),
    ])
    st.caption(f"الجنسية تُستنتج من رقم الهوية/الإقامة (يبدأ بـ1 سعودي و2 أجنبي)، وعند غيابه من وجود رسم إقامة في الرواتب؛ غير المحدد: {un}. "
               f"للمطابقة: شهادة التأمينات {sett['gosi_date']}: سعوديون {sett['gosi_saudi']:,} وأجانب {sett['gosi_foreign']:,} "
               f"(مقابل {sa:,} و{fo:,} في ملف الموظفين).")
    for g in GROUPS:
        G = A[A["المجموعة"] == g]
        if not len(G):
            continue
        tot = len(G)
        s = int((G["الجنسية"] == "سعودي").sum())
        f = int((G["الجنسية"] == "أجنبي").sum())
        rq = float(sett["req"].get(g, 0.0))
        need = int(np.ceil(tot * rq / 100.0 - 1e-9))
        cur = s / tot * 100 if tot else 0
        stat = "—" if rq == 0 else ("ملتزم" if s >= need else f"عجز {need - s}")
        _sub(f"مجموعة: {g} — {tot:,} موظفاً، السعودة {cur:.1f}%" + (f" والمطلوب {rq:.0f}%" if rq else ""),
             stat if rq else "لا نسبة مطلوبة", ("ok" if (rq and s >= need) else ("no" if rq else "na")))
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
    with _box("hr_grid_sum"):
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
    with _box("hr_grid_emp"):
        st.dataframe(T.style.format({"الراتب الأساسي": "{:,.0f}", "إجمالي الراتب": "{:,.0f}"}), hide_index=True, use_container_width=True, height=480)
    st.download_button("⬇️ تنزيل القائمة (CSV)", data=D.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig"), file_name="hr_employees.csv", mime="text/csv", key="hr_dl")


def _impact(D, d, sett, today):
    """أثر الزيادة الشهرية d (Series بنفس فهرس D): نقدي 12 شهراً، مخصص الإجازة، مخصص نهاية الخدمة (من التعيين حتى نهاية العقد)."""
    yrs = ((today - D["تاريخ التعيين"]).dt.days / 365.25).fillna(0)
    ann = np.where(yrs >= 5, sett["leave_days_ge5"], sett["leave_days_lt5"])
    end = D["نهاية العقد"].fillna(today)
    T_ = ((end - D["تاريخ التعيين"]).dt.days / 365.25).clip(lower=0).fillna(0)
    out = pd.DataFrame(index=D.index)
    out["أثر نقدي 12 شهراً"] = d * 12
    out["أثر على مخصص الإجازة"] = d / 30 * ann
    out["أثر على مخصص نهاية الخدمة"] = d * T_.map(eosb_factor)
    out["إجمالي الأثر على المخصصات"] = out["أثر على مخصص الإجازة"] + out["أثر على مخصص نهاية الخدمة"]
    out["إجمالي الأثر"] = out["أثر نقدي 12 شهراً"] + out["إجمالي الأثر على المخصصات"]
    return out, ann


def _save_inc(df):
    st.session_state["hr_inc"] = df
    try:
        df.to_csv(INC_FILE, index=False, encoding="utf-8-sig")
    except Exception:
        pass


def _increases(A, unlocked, ym):
    _title("تقرير العلاوات")
    st.markdown('<div class="hr-note">يحفظ العلاوات المعتمدة ويحسب أثرها: نقدياً لمدة 12 شهراً، وعلى مخصص الإجازة (دورة 12 شهراً من تاريخ آخر إجازة)، وعلى مخصص نهاية الخدمة '
                '(من تاريخ التعيين حتى نهاية العقد: نصف شهر عن كل سنة من الخمس الأولى وشهر عن كل سنة بعدها). '
                'تاريخ ومبلغ آخر زيادة يُستخرجان من تغيّر الراتب الأساسي في تفاصيل الرواتب الشهرية المرفوعة (يناير 2025 فما بعد).</div>', unsafe_allow_html=True)
    sett = st.session_state["hr_set"]
    today = pd.Timestamp(dt.date.today())
    # ---- زيادات مقترحة من ملف
    prop = st.session_state.get("hr_prop", pd.DataFrame())
    with st.expander(f"📥 زيادات مقترحة من ملف Excel (المحمّل: {len(prop):,} سطراً)", expanded=False):
        st.caption("أعمدة الملف: الرقم الوظيفي (أو المهنة/الموقع لقاعدة عامة) + «الزيادة» (مبلغ شهري) أو «النسبة» (% من الراتب الأساسي). قاعدة الرقم الوظيفي تغلب قاعدة المهنة/الموقع.")
        f = st.file_uploader("ملف الزيادات المقترحة", type=["xlsx"], key="hr_prop_up", disabled=not unlocked)
        if f is not None and unlocked:
            h = hashlib.md5(f.getvalue()).hexdigest()
            if st.session_state.get("hr_prop_hash") != h:
                try:
                    P = parse_proposed(f.getvalue())
                    st.session_state["hr_prop"] = P
                    st.session_state["hr_prop_hash"] = h
                    P.to_csv(PROP_FILE, index=False, encoding="utf-8-sig")
                    st.success(f"تم تحميل {len(P):,} سطراً من الزيادات المقترحة.")
                    prop = P
                except Exception as e:
                    st.error(f"تعذرت قراءة الملف: {e}")
        if len(prop) and unlocked and st.button("اعتماد المقترحة كزيادات معتمدة (تستبدل المعتمدة الحالية للمشمولين)", key="hr_prop_adopt"):
            r = resolve_proposed(prop, A)
            r = r[r != 0]
            cur = st.session_state["hr_inc"]
            cur = cur[~cur["الرقم الوظيفي"].isin(r.index)]
            _save_inc(pd.concat([cur, pd.DataFrame({"الرقم الوظيفي": r.index, "الزيادة": r.values})], ignore_index=True))
            st.rerun()
    scen = st.radio("السيناريو المعروض", ["المعتمدة", "المقترحة (من الملف)", "المعتمدة + المقترحة"], horizontal=True, key="hr_inc_scen")
    inc = st.session_state["hr_inc"].drop_duplicates("الرقم الوظيفي", keep="last").set_index("الرقم الوظيفي")["الزيادة"]
    appr = A["الرقم الوظيفي"].map(inc).fillna(0.0).astype(float)
    propv = A["الرقم الوظيفي"].map(resolve_proposed(prop, A)).fillna(0.0).astype(float) if len(prop) else pd.Series(0.0, index=A.index)
    A = A.copy()
    A["الزيادة المعتمدة"] = {"المعتمدة": appr, "المقترحة (من الملف)": propv, "المعتمدة + المقترحة": appr + propv}[scen].values
    imp_all, _ = _impact(A, A["الزيادة المعتمدة"], sett, today)
    # ---- أثر على مستوى الشركة والعقود
    Gc = pd.concat([A[["العقد", "الزيادة المعتمدة"]], imp_all], axis=1)
    G = Gc.groupby("العقد").agg(**{"المستفيدون": ("الزيادة المعتمدة", lambda x: int((x > 0).sum())), "الزيادة الشهرية": ("الزيادة المعتمدة", "sum"),
                                  "أثر نقدي 12 شهراً": ("أثر نقدي 12 شهراً", "sum"), "أثر المخصصات": ("إجمالي الأثر على المخصصات", "sum"), "إجمالي الأثر": ("إجمالي الأثر", "sum")})
    G = G.sort_values("إجمالي الأثر", ascending=False)
    G.loc["الإجمالي (الشركة)"] = G.sum()
    Gt = G.reset_index()
    Gt = Gt[list(Gt.columns[1:][::-1]) + [Gt.columns[0]]]
    st.markdown("**الأثر على مستوى العقد / الشركة**")
    with _box("hr_grid_incg"):
        st.dataframe(Gt.style.format({c: "{:,.0f}" for c in Gt.columns if c != "العقد"}), hide_index=True, use_container_width=True, height=min(380, 38 + 35 * len(Gt)))
    # ---- تفصيل الموظفين
    st.markdown("**تصفية العمالة (تصنيف رئيسي: العقد، ثم تصنيفات فرعية)**")
    DIMS = {"المهنة": "المهنة", "مركز التكلفة / الموقع": "الموقع", "الجنسية": "الجنسية", "المجموعة الرئيسية": "المجموعة", "الفئة": "الفئة"}
    DIMS = {k: v for k, v in DIMS.items() if v in A.columns and (v != "الفئة" or A["الفئة"].astype(str).str.strip().ne("").any())}
    D = A
    c0, c1, c2, c3, c4 = st.columns([2, 2, 2, 2, 2])
    lv1 = c0.selectbox("العقد (التصنيف الرئيسي)", ["الكل"] + sorted(A["العقد"].dropna().unique().tolist()), key="hr_inc_l1")
    if lv1 != "الكل":
        D = D[D["العقد"] == lv1]
    picks = []
    for i, (cc_, vc_, nm_) in enumerate([(c1, c2, "فرعي أول"), (c3, c4, "فرعي ثانٍ")], start=2):
        used = {d for d, _ in picks}
        dim = cc_.selectbox(f"التصنيف الفرعي ({nm_})", ["بدون"] + [k for k in DIMS if k not in used], key=f"hr_inc_d{i}")
        if dim == "بدون":
            break
        col_ = DIMS[dim]
        vals = ["الكل"] + sorted(D[col_].dropna().astype(str).unique().tolist())
        v_ = vc_.selectbox(f"{dim}", vals, key=f"hr_inc_v{i}")
        picks.append((dim, v_))
        if v_ != "الكل":
            D = D[D[col_].astype(str) == v_]
    by, val = lv1, "|".join(f"{d}={v}" for d, v in picks)
    D = D.copy()
    D["المدة من آخر إجازة (شهر)"] = ((today - D["اخر اجازة"]).dt.days / 30.44).round(1)
    imp, ann = _impact(D, D["الزيادة المعتمدة"], sett, today)
    D["إجازة مستحقة منذ آخر إجازة (يوم)"] = (D["المدة من آخر إجازة (شهر)"].clip(lower=0).fillna(0) / 12 * ann).round(1)
    D = pd.concat([D, imp], axis=1)
    d = D["الزيادة المعتمدة"]
    _kpis([("إجمالي الزيادة الشهرية", _fmt(d.sum()), f"{int((d > 0).sum()):,} موظفاً"),
           ("الأثر النقدي 12 شهراً", _fmt(D["أثر نقدي 12 شهراً"].sum()), "رواتب سنة كاملة"),
           ("أثر مخصص الإجازة", _fmt(D["أثر على مخصص الإجازة"].sum()), "غير نقدي"),
           ("أثر مخصص نهاية الخدمة", _fmt(D["أثر على مخصص نهاية الخدمة"].sum()), "غير نقدي"),
           ("إجمالي الأثر", _fmt(D["إجمالي الأثر"].sum()), "نقدي وغير نقدي", "gold")])
    D = D.sort_values(["المهنة", "الاسم"]).reset_index(drop=True)
    D["تاريخ التعيين"] = D["تاريخ التعيين"].dt.strftime("%Y-%m-%d")
    cols = ["الاسم", "المهنة", "تاريخ التعيين", "الراتب الأساسي", "تاريخ آخر زيادة", "مبلغ آخر زيادة", "المدة من آخر إجازة (شهر)", "إجازة مستحقة منذ آخر إجازة (يوم)",
            "الزيادة المعتمدة", "أثر نقدي 12 شهراً", "أثر على مخصص الإجازة", "أثر على مخصص نهاية الخدمة", "إجمالي الأثر"]
    T = D[cols].copy()
    money = ["الراتب الأساسي", "مبلغ آخر زيادة", "الزيادة المعتمدة", "أثر نقدي 12 شهراً", "أثر على مخصص الإجازة", "أثر على مخصص نهاية الخدمة", "إجمالي الأثر"]
    fm = {c: "{:,.0f}" for c in money}
    fm.update({"المدة من آخر إجازة (شهر)": "{:.1f}", "إجازة مستحقة منذ آخر إجازة (يوم)": "{:.1f}"})
    Tr = T[list(T.columns[::-1])]
    editable = unlocked and scen == "المعتمدة"
    ed = None
    with _box("hr_grid_inc"):
        if editable:
            st.caption("اكتب مبلغ الزيادة الشهرية أمام الموظف في عمود «الزيادة المعتمدة» ثم اضغط حفظ. (باقي الأعمدة للعرض ولا تتحدّث إلا بعد الحفظ.)")
            cfg = {c: st.column_config.NumberColumn(c, format="%,.0f") for c in money}
            ed = st.data_editor(Tr, hide_index=True, use_container_width=True, height=520, key=f"hr_inc_ed_{by}_{val}_{len(st.session_state['hr_inc'])}",
                                disabled=[c for c in Tr.columns if c != "الزيادة المعتمدة"], column_config=cfg, num_rows="fixed")
        else:
            st.dataframe(Tr.style.format(fm, na_rep=""), hide_index=True, use_container_width=True, height=520)
    if not unlocked:
        st.caption("🔒 لاعتماد العلاوات أدخل كلمة السر في الشريط الجانبي.")
        return
    if scen != "المعتمدة":
        st.caption("الاعتماد والتعديل اليدوي متاحان في سيناريو «المعتمدة» فقط؛ استخدم زر «اعتماد المقترحة» أعلاه لنقل المقترحة إلى المعتمدة.")
        return
    ids_all = D["الرقم الوظيفي"].tolist()
    if ed is not None and st.button("💾 حفظ الزيادات المدخلة في الجدول", key="hr_inc_save"):
        newv = pd.to_numeric(ed["الزيادة المعتمدة"].reset_index(drop=True), errors="coerce").fillna(0.0)
        cur = st.session_state["hr_inc"]
        cur = cur[~cur["الرقم الوظيفي"].isin(ids_all)]
        add = pd.DataFrame({"الرقم الوظيفي": ids_all, "الزيادة": newv.values})
        add = add[add["الزيادة"] != 0]
        _save_inc(pd.concat([cur, add], ignore_index=True))
        st.rerun()
    st.caption(f"أو طبّق مبلغاً أو نسبة على كل المعروضين حالياً ({len(ids_all):,} موظفاً حسب المهنة/الموقع المختار أعلاه). صفر يلغي العلاوة.")
    m1, m2, m3 = st.columns([2, 2, 2])
    mode = m1.radio("طريقة الإدخال", ["مبلغ شهري", "نسبة من الراتب الأساسي"], horizontal=True, key="hr_inc_mode")
    amt = m2.number_input("القيمة", min_value=0.0, value=0.0, step=100.0 if mode == "مبلغ شهري" else 1.0, key="hr_inc_amt")
    if m3.button(f"تطبيق على كل المعروضين ({len(ids_all):,})", disabled=not ids_all, key="hr_inc_apply"):
        cur = st.session_state["hr_inc"]
        cur = cur[~cur["الرقم الوظيفي"].isin(ids_all)]
        base = A.set_index("الرقم الوظيفي")["الراتب الأساسي"]
        rows = [[i, (amt if mode == "مبلغ شهري" else float(base.get(i, 0) or 0) * amt / 100.0)] for i in ids_all]
        new = pd.concat([cur, pd.DataFrame(rows, columns=["الرقم الوظيفي", "الزيادة"])], ignore_index=True)
        _save_inc(new[new["الزيادة"].fillna(0) != 0])
        st.rerun()
    st.download_button("⬇️ نسخة احتياطية من العلاوات المعتمدة (CSV)", data=st.session_state["hr_inc"].to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig"),
                       file_name="hr_increases_backup.csv", mime="text/csv", key="hr_inc_bk")


def _provisions(A, sett, build):
    _title("المخصصات المستحقة على الشركة (تقدير أولي)")
    st.markdown('<div class="hr-note">مخصص الإجازة = الأيام المستحقة × الأجر اليومي (إجمالي الراتب ÷ 30)؛ للسعوديين من رصيد الأيام المرفوع، ولغيرهم من تاريخ آخر إجازة فعلية، '
                'ومخصص نهاية الخدمة = وفق المادة 84 من نظام العمل (نصف شهر لكل سنة من الخمس الأولى وشهر بعدها) على الراتب الأساسي حتى اليوم. '
                'ستُقارن لاحقاً بأرصدة المخصصات في ميزان المراجعة.</div>', unsafe_allow_html=True)
    today = pd.Timestamp(dt.date.today())
    lsa, lpr = st.session_state.get("hr_lsa", pd.DataFrame(columns=LSA_COLS)), st.session_state.get("hr_lpr", pd.DataFrame(columns=LPR_COLS))
    c1, c2 = st.columns([1, 3])
    sa_date = c1.date_input("تاريخ رصيد إجازات السعوديين", value=dt.date(2026, 6, 30), key="hr_sa_date",
                            help="الرصيد في الملف محتسب حتى هذا التاريخ؛ يُضاف عليه استحقاق المدة بعده حتى اليوم.")
    c2.caption(f"السعوديون: رصيد الأيام من الملف ({len(lsa):,} موظفاً) × الأجر اليومي. غيرهم: استحقاق من تاريخ آخر إجازة فعلية (تقرير البرنامج: {len(lpr):,} إجازة) حتى اليوم. "
               "الرصيد السالب يُحتسب صفراً ويُعرض في قائمة الجودة.")
    D = A.copy()
    yrs = ((today - D["تاريخ التعيين"]).dt.days / 365.25).clip(lower=0).fillna(0)
    L = leave_days(D, sett, lsa, lpr, today, sa_date).set_index("الرقم الوظيفي")
    D["أيام الإجازة"] = D["الرقم الوظيفي"].map(L["أيام الإجازة المستحقة"]).fillna(0)
    D["مصدر الاحتساب"] = D["الرقم الوظيفي"].map(L["مصدر الاحتساب"])
    sal = D["إجمالي الراتب"].fillna(0)
    D["مخصص الإجازة"] = D["أيام الإجازة"] * sal / 30
    basic = D["الراتب الأساسي"].fillna(0)
    D["مخصص نهاية الخدمة (إجمالي)"] = yrs.map(eosb_factor) * basic
    eo = st.session_state.get("hr_eosb", pd.DataFrame(columns=EOSB_COLS))
    paid = (eo.set_index("الكود")[["حتى 2024", "2025", "2026"]].sum(axis=1)) if len(eo) else pd.Series(dtype=float)
    D["الدفعات المسددة"] = D["الرقم الوظيفي"].map(paid).fillna(0.0)
    D["مخصص نهاية الخدمة"] = D["مخصص نهاية الخدمة (إجمالي)"] - D["الدفعات المسددة"]
    # الاستحقاق الفعلي لو غادر الموظف عند نهاية عقده الحالي (قانوني، بلا اكتواري)، صافياً بعد الدفعات المسددة
    end = D["نهاية العقد"].where(D["نهاية العقد"] >= today, today).fillna(today)
    yrs_end = ((end - D["تاريخ التعيين"]).dt.days / 365.25).clip(lower=0).fillna(0)
    D["استحقاق نهاية العقد (إجمالي)"] = yrs_end.map(eosb_factor) * basic
    D["استحقاق نهاية العقد (صافي)"] = D["استحقاق نهاية العقد (إجمالي)"] - D["الدفعات المسددة"]
    D["الإجمالي"] = D["مخصص الإجازة"] + D["مخصص نهاية الخدمة"]
    if not len(eo):
        st.warning("كشف دفعات نهاية الخدمة غير محمّل، فالصافي يساوي الإجمالي (الدفعات المسددة صفر). ارفعه من «البيانات والإعدادات».")
    by = st.radio("التجميع", ["حسب العقد", "حسب المجموعة الرئيسية", "حسب الجنسية"], horizontal=True, key="hr_prov_by")
    col = {"حسب العقد": "العقد", "حسب المجموعة الرئيسية": "المجموعة", "حسب الجنسية": "الجنسية"}[by]
    G = D.groupby(col).agg(n=("الاسم", "size"), dd=("أيام الإجازة", "sum"), l=("مخصص الإجازة", "sum"), eg=("مخصص نهاية الخدمة (إجمالي)", "sum"), pd_=("الدفعات المسددة", "sum"),
                           e=("مخصص نهاية الخدمة", "sum"), t=("الإجمالي", "sum")).sort_values("t", ascending=False)
    rows = [("item", k, [str(int(r.n)), _fmt(r.dd), _fmt(r.l), _fmt(r.eg), _fmt(r.pd_), _fmt(r.e), _fmt(r.t)]) for k, r in G.iterrows()]
    rows.append(("total", "الإجمالي", [str(int(G.n.sum())), _fmt(G.dd.sum()), _fmt(G.l.sum()), _fmt(G.eg.sum()), _fmt(G.pd_.sum()), _fmt(G.e.sum()), _fmt(G.t.sum())]))
    st.table(build(rows, [col, "العدد", "أيام الإجازة", "مخصص الإجازة", "نهاية الخدمة (إجمالي)", "يخصم: الدفعات المسددة", "مخصص نهاية الخدمة (صافي)", "الإجمالي (إجازة + صافي)"]))
    st.caption("الصافي = المستحق قانونياً حتى اليوم − دفعات نهاية الخدمة المسددة للموظف (حتى 2024 + 2025 + 2026).")
    src = D.groupby("مصدر الاحتساب").agg(n=("الاسم", "size"), d=("أيام الإجازة", "sum"), v=("مخصص الإجازة", "sum")).sort_values("v", ascending=False)
    st.caption(" · ".join(f"{k}: {int(r.n):,} موظفاً / {_fmt(r.v)}" for k, r in src.iterrows()))
    with st.expander("قائمة الجودة والتفاصيل لكل موظف"):
        sa_ids = set(A.loc[A["الجنسية"] == "سعودي", "الرقم الوظيفي"])
        neg = lsa[(lsa["رصيد أيام"] < 0) & lsa["الرقم الوظيفي"].isin(set(D["الرقم الوظيفي"]))]
        bad = lsa[lsa["رصيد أيام"].isna() & lsa["الرقم الوظيفي"].isin(set(D["الرقم الوظيفي"]))]
        miss = A[A["الرقم الوظيفي"].isin(sa_ids - set(lsa["الرقم الوظيفي"]))]
        st.caption(f"رصيد سالب (سلف إجازة): {len(neg):,} · رصيد غير صالح (#VALUE!): {len(bad):,} · سعوديون على رأس العمل غير موجودين في ملف الأرصدة: {len(miss):,}")
        T = D[["الرقم الوظيفي", "الاسم", "الجنسية", "العقد", "إجمالي الراتب", "مصدر الاحتساب", "أيام الإجازة", "مخصص الإجازة", "مخصص نهاية الخدمة (إجمالي)", "الدفعات المسددة", "مخصص نهاية الخدمة", "استحقاق نهاية العقد (صافي)"]].copy()
        T["رصيد الملف"] = T["الرقم الوظيفي"].map(L["رصيد الملف"])
        T["آخر إجازة معتمدة"] = pd.to_datetime(T["الرقم الوظيفي"].map(L["آخر إجازة معتمدة"]), errors="coerce").dt.strftime("%Y-%m-%d")
        st.download_button("⬇️ تنزيل مخصص الإجازات لكل موظف (CSV)", data=T.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig"),
                           file_name="leave_provision.csv", mime="text/csv", key="hr_lv_dl")
        flag = pd.concat([neg.assign(السبب="رصيد سالب"), bad.assign(السبب="قيمة غير صالحة في الملف")])[["الرقم الوظيفي", "الاسم", "رصيد أيام", "السبب"]]
        if len(flag):
            with _box("hr_grid_flag"):
                st.dataframe(flag, hide_index=True, use_container_width=True)
        if len(miss):
            with _box("hr_grid_miss"):
                st.dataframe(miss[["الرقم الوظيفي", "الاسم", "المهنة"]], hide_index=True, use_container_width=True)


def _act_settings(sett):
    return {**ACT_DEFAULTS, **sett.get("act", {})}


def _actuarial(A, sett, eosb, build):
    import actuary as ac
    _title("نهاية الخدمة الاكتواري (IAS 19) — طريقة وحدة الائتمان المتوقعة")
    st.markdown('<div class="hr-note">النموذج مُعايَر على تقرير المكتب الاكتواري 31/12/2025 ومطابق له موظفاً موظفاً: التزام 2025 الإجمالي 32.45 مليون مقابل 32.49 مليون للمكتب (فرق -0.1%)، '
                'وحركة الفائدة والقياس مطابقة لأرقام التقرير. جدول الوفيات السعودي غير متاح رقمياً فاستُعيض عنه بدالة وفيات معايَرة؛ ويبقى هذا تقديراً داخلياً يُعتمد بعد مراجعة المكتب الاكتواري '
                'ولا يغني عن تقريره السنوي.</div>', unsafe_allow_html=True)
    unlocked = bool(st.session_state.get("hr_unlocked", False))
    a = _act_settings(sett)
    c1, c2, c3, c4 = st.columns(4)
    vd = c1.date_input("تاريخ التقييم", value=dt.date.fromisoformat(a["val_date"]), key="act_vd", disabled=not unlocked)
    dr = c2.number_input("معدل الخصم %", value=float(a["dr"]), step=0.05, format="%.2f", key="act_dr", disabled=not unlocked)
    si = c3.number_input("نمو الرواتب %", value=float(a["si"]), step=0.1, format="%.2f", key="act_si", disabled=not unlocked)
    dro = c4.number_input("معدل الخصم في بداية السنة %", value=float(a["dr_open"]), step=0.05, format="%.2f", key="act_dro", disabled=not unlocked)
    c5, c6, c7 = st.columns(3)
    open_net = c5.number_input("صافي التزام 31/12/2025 (الدفاتر)", value=float(a["open_net"]), step=1000.0, format="%.0f", key="act_on", disabled=not unlocked)
    open_adv = c6.number_input("رصيد الدفعات المقدمة 31/12/2025", value=float(a["open_adv"]), step=1000.0, format="%.0f", key="act_oa", disabled=not unlocked)
    extra = c7.number_input("دفعات متوقعة حتى نهاية السنة (غير مشمولة بالكشف)", value=float(a["extra_pay"]), step=1000.0, format="%.0f", key="act_ex", disabled=not unlocked)
    basis = st.radio("رصيد الدفعات المقدمة للمستمرين في 2026", ["من كشف الدفعات الجديد (التراكمي للمستمرين)", "رصيد 2025 المعتمد + دفعات 2026 − دفعات من غادروا"], horizontal=True, key="act_basis",
                     help="المعتمد مؤقتاً: التقرير الجديد، لحين انتهاء المراجعة المحاسبية لأرصدة 264 موظفاً (حتى 2024 = صفر)")
    new = {**a, "val_date": vd.isoformat(), "dr": dr, "si": si, "dr_open": dro, "open_net": open_net, "open_adv": open_adv, "extra_pay": extra}
    if unlocked and new != a:
        s2 = {**st.session_state["hr_set"], "act": new}
        st.session_state["hr_set"] = s2
        _save_settings(s2)
    a = new
    a["turn"] = ac.DEFAULT["turn"]; a["ret"] = ac.DEFAULT["ret"]; a["qa"] = ac.DEFAULT["qa"]; a["qb"] = ac.DEFAULT["qb"]
    vdt = pd.Timestamp(vd)
    D = A.copy()
    D = D[D["تاريخ التعيين"].notna() & (D["تاريخ التعيين"] <= vdt)].copy()
    D["yos"] = ((vdt - D["تاريخ التعيين"]).dt.days / 365.25).clip(lower=0)
    D["age"] = (vdt - D["تاريخ الميلاد"]).dt.days / 365.25
    miss_dob = int(D["age"].isna().sum())
    D["age"] = D["age"].fillna(D["age"].median() if D["age"].notna().any() else 36.0)
    D["sal_m"] = pd.to_numeric(D["إجمالي الراتب"], errors="coerce")
    miss_sal = int((D["sal_m"].isna() | (D["sal_m"] <= 0)).sum())
    D["sal_m"] = D["sal_m"].where(D["sal_m"] > 0, D["الراتب الأساسي"])
    D["sal_m"] = D["sal_m"].fillna(D["sal_m"].median() if D["sal_m"].notna().any() else 0.0)
    if not len(D):
        st.info("لا موظفون ببيانات كافية.")
        return
    if miss_sal >= len(D):
        st.error("لا توجد رواتب محمّلة، لذا لا يمكن احتساب الالتزام (تظهر الأرقام صفراً). ارفع «كشف الرواتب الحالية» أو «تفاصيل الرواتب الشهرية» من تبويب «البيانات والإعدادات» "
                 "ثم عُد إلى هنا. الملفات المحفوظة قد تضيع عند إعادة تشغيل الاستضافة.")
        return
    if miss_sal > 0:
        st.warning(f"{miss_sal:,} موظفاً بلا راتب في البيانات المحمّلة، احتُسب لهم متوسط الرواتب.")
    if not len(eosb):
        st.warning("كشف دفعات نهاية الخدمة غير محمّل، لذا الدفعات المقدمة للمستمرين ومدفوعات 2026 صفر. ارفعه من «البيانات والإعدادات».")
    dbo, e1, psc = ac.run(D, a)
    D["DBO"], D["منافع متوقعة"], D["تكلفة خدمة متوقعة"] = dbo, e1, psc
    gross = float(dbo.sum())
    # الدفعات المقدمة والمدفوعات
    ids = set(D["الرقم الوظيفي"])
    if len(eosb):
        E = eosb.copy()
        act = E[E["الكود"].isin(ids)]
        adv_cum = float((act["حتى 2024"] + act["2025"] + act["2026"]).sum())
        adv_26 = float(act["2026"].sum())
        left = E[~E["الكود"].isin(ids) & (E["2026"] > 0)]
        exit_26 = float(left["2026"].sum())
        left_adv = float((left["حتى 2024"] + left["2025"]).sum())
    else:
        adv_cum = adv_26 = exit_26 = left_adv = 0.0
    pay_total = adv_26 + exit_26 + extra
    adv_close = adv_cum if basis.startswith("من كشف") else open_adv + adv_26 - left_adv
    net = gross - adv_close
    sc = float(psc.sum()) / (1 + dr / 100)
    interest, remeas = ac.movement(open_net, sc, dro, pay_total, net)
    dbo_old, _, _ = ac.run(D, a, dr=dro)
    fin = float(dbo_old.sum() - gross)  # ربح عند ارتفاع الخصم
    exp_adj = -remeas - fin
    _kpis([("الالتزام الإجمالي (DBO)", _fmt(gross), "القيمة الحالية للمنافع"),
           ("الدفعات المقدمة للمستمرين", _fmt(adv_close), "تُخصم من الالتزام"),
           ("صافي الالتزام", _fmt(net), "المثبت في المركز المالي", "gold"),
           ("عدد الموظفين", f"{len(D):,}", "ضمن التقييم")])
    fmtn = lambda v: _fmt(-v) if v > 0 else f"({_fmt(abs(v))})" if v < 0 else "0"  # التزام سالب كما في التقرير
    _title("قائمة المركز المالي والأرباح والخسائر")
    rows = [("item", "القيمة الحالية للالتزام (DBO) الإجمالي", [fmtn(gross)]),
            ("item", "يخصم: دفعات مقدمة للمستمرين", [_fmt(adv_close)]),
            ("total", "صافي الالتزام في 31/12/%d" % vd.year, [fmtn(net)]),
            ("item", "تكلفة الخدمة الحالية", [fmtn(sc)]),
            ("item", "صافي الفائدة", [fmtn(interest)]),
            ("subtotal", "تكلفة المنافع المحددة (قائمة الربح أو الخسارة)", [fmtn(sc + interest)]),
            ("item", "الأرباح والخسائر الاكتوارية (الدخل الشامل الآخر)", [_fmt(-remeas) if -remeas >= 0 else f"({_fmt(remeas)})"])]
    st.table(build(rows, ["البند", "ريال"]))
    _title("حركة صافي الالتزام")
    rows = [("item", "الرصيد الافتتاحي (31/12/%d)" % (vd.year - 1), [fmtn(open_net)]),
            ("item", "تكلفة الخدمة", [fmtn(sc)]),
            ("item", "صافي الفائدة", [fmtn(interest)]),
            ("item", "المنافع المدفوعة (خروج %s + دفعات مقدمة %s)" % (_fmt(exit_26 + extra), _fmt(adv_26)), [_fmt(pay_total)]),
            ("item", "القياس: أرباح وخسائر اكتوارية", [_fmt(-remeas) if -remeas >= 0 else f"({_fmt(remeas)})"]),
            ("total", "الرصيد الختامي (31/12/%d)" % vd.year, [fmtn(net)])]
    st.table(build(rows, ["البند", "ريال"]))
    st.caption(f"تفصيل القياس: أثر تغيير الافتراضات المالية {_fmt(fin) if fin >= 0 else '(' + _fmt(-fin) + ')'}، وتسويات الخبرة {_fmt(exp_adj) if exp_adj >= 0 else '(' + _fmt(-exp_adj) + ')'} "
               "(ربح موجب). الفائدة = معدل بداية السنة × (الرصيد الافتتاحي + تكلفة الخدمة − نصف المدفوعات) كما في تقرير 2025.")
    _title("تحليل الحساسية")
    sens = [("الأصل", {}), ("معدل الخصم +1%", dict(dr=dr + 1)), ("معدل الخصم −1%", dict(dr=dr - 1)),
            ("نمو الرواتب +1%", dict(si=si + 1)), ("نمو الرواتب −1%", dict(si=max(si - 1, 0))), ("معدل الترك +1%", dict(shift=0.01)), ("معدل الترك −1%", dict(shift=-0.01))]
    rows = []
    for lab, kw in sens:
        d2, _, _ = ac.run(D, a, **kw)
        rows.append(("item" if kw else "subtotal", lab, [_fmt(d2.sum() - adv_close), _fmt(d2.sum() - gross) if kw else ""]))
    st.table(build(rows, ["الحالة", "صافي الالتزام", "الفرق عن الأصل"]))
    _title("إسقاط السنة التالية")
    e1t = float(e1.sum())
    sc_n = float(psc.sum())
    int_n = dr / 100 * (net + sc_n - 0.5 * e1t)
    rows = [("item", "صافي الالتزام الحالي", [_fmt(net)]), ("item", "تكلفة الخدمة المتوقعة", [_fmt(sc_n)]),
            ("item", "تكلفة الفائدة المتوقعة", [_fmt(int_n)]), ("item", "المنافع المتوقعة خلال السنة", [f"({_fmt(e1t)})"]),
            ("total", "الصافي المتوقع نهاية السنة التالية", [_fmt(net + sc_n + int_n - e1t)])]
    st.table(build(rows, ["البند", "ريال"]))
    _title("جودة البيانات والمطابقة")
    bad = []
    if miss_dob:
        bad.append(f"{miss_dob} موظفاً بلا تاريخ ميلاد (فُرض متوسط العمر)")
    if miss_sal:
        bad.append(f"{miss_sal} موظفاً بلا راتب في كشوف الرواتب (استُخدم الأساسي أو المتوسط)")
    if not len(eosb):
        bad.append("لم يُرفع كشف دفعات نهاية الخدمة؛ الدفعات والدفعات المقدمة = صفر")
    st.caption("؛ ".join(bad) if bad else "البيانات مكتملة.")
    if len(eosb):
        old_active_2025 = float(eosb[eosb["الكود"].isin(ids)][["حتى 2024", "2025"]].sum().sum())
        st.caption(f"مطابقة رصيد الدفعات المقدمة: الكشف الجديد يعطي للمستمرين حتى 2025: {_fmt(old_active_2025)} مقابل الرصيد المعتمد في تقرير 2025: {_fmt(open_adv)} "
                   f"(فرق {_fmt(open_adv - old_active_2025)}) — يؤثر مباشرة على صافي الالتزام ويحتاج مراجعة قبل الاعتماد. استخدم الخيار الثاني أعلاه لو الكشف ناقص تاريخياً.")
    T = D[["الرقم الوظيفي", "الاسم", "تاريخ الميلاد", "تاريخ التعيين", "sal_m", "age", "yos", "DBO", "منافع متوقعة", "تكلفة خدمة متوقعة"]].copy()
    T.columns = ["رقم الموظف", "الاسم", "تاريخ الميلاد", "تاريخ التعيين", "الراتب الشهري", "العمر", "سنوات الخدمة", "الالتزام", "منافع متوقعة", "تكلفة خدمة متوقعة"]
    T = T.sort_values("الالتزام", ascending=False)
    for c in ["تاريخ الميلاد", "تاريخ التعيين"]:
        T[c] = T[c].dt.strftime("%Y-%m-%d")
    buf = io.BytesIO()
    try:
        T.to_excel(buf, index=False, sheet_name="Results")
        st.download_button("⬇️ تنزيل الالتزام لكل موظف (Excel)", data=buf.getvalue(), file_name=f"Per_Employee_Liability_{vd.year}.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="act_dl")
    except Exception:
        st.download_button("⬇️ تنزيل الالتزام لكل موظف (CSV)", data=T.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig"), file_name=f"Per_Employee_Liability_{vd.year}.csv", mime="text/csv", key="act_dl")
    with st.expander("أكبر 50 موظفاً من حيث الالتزام"):
        with _box("hr_grid_act"):
            Tt = T.head(50)
            Tt = Tt[list(Tt.columns[::-1])]
            st.dataframe(Tt.style.format({"الراتب الشهري": "{:,.0f}", "العمر": "{:.1f}", "سنوات الخدمة": "{:.1f}", "الالتزام": "{:,.0f}", "منافع متوقعة": "{:,.0f}", "تكلفة خدمة متوقعة": "{:,.0f}"}),
                         hide_index=True, use_container_width=True)
    st.caption("الفرضيات الثابتة (من تقرير 2025): التقاعد عند 60، معدل ترك الخدمة حسب سنوات الخدمة (0–5: 25%، 6–10: 15%، 11–19: 10%، 20+: 1%)، "
               "الاستقالة تستحق: أقل من سنتين لا شيء، 2–5 ثلث، 5–10 ثلثان، 10+ كاملاً. نظام العمل المادة 84.")


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
    late = D[(D["الموقف"] == "على رأس العمل") & (D["أشهر منذ آخر إجازة"] >= 23)].sort_values("أشهر منذ آخر إجازة", ascending=False)
    ends = D[(D["نهاية العقد"] <= today + pd.Timedelta(days=90))].sort_values("نهاية العقد")
    c1, c2 = st.columns(2)
    c1.caption(f"على رأس العمل ولم يأخذوا إجازة منذ 23 شهراً فأكثر: {len(late):,}")
    c2.caption(f"عقود منتهية أو تنتهي خلال 90 يوماً: {len(ends):,}")
    for T, cols, key in [(late, ["الاسم", "المهنة", "العقد", "أشهر منذ آخر إجازة"], "late"), (ends, ["الاسم", "المهنة", "العقد", "نهاية العقد"], "ends")]:
        X = T[cols].copy()
        if "نهاية العقد" in X.columns:
            X["نهاية العقد"] = X["نهاية العقد"].dt.strftime("%Y-%m-%d")
        X = X[list(X.columns[::-1])].head(200)
        with _box("hr_grid_" + key):
            st.dataframe(X, hide_index=True, use_container_width=True, height=300)
