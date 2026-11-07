# sites.py
# تبويب تقارير المواقع: مراجعة البونص، تكلفة أوامر العمل، إنتاجية الموقع، انحرافات المواد، قاعدة أوامر العمل.
# المصادر: تقارير البونص الشهرية، حركة الأصناف، تصفية أوامر العمل، موقف أوامر العمل من الكهرباء،
#          تقرير الرواتب التفصيلي، أسعار الأصناف، أسعار بنود العقد، تقرير إنتاجية الموقع.

import io, os, re, json, datetime as dt
import numpy as np
import openpyxl
import pandas as pd
import streamlit as st

import uitable as ut

HERE = os.path.dirname(os.path.abspath(__file__))
F_BON = os.path.join(HERE, "st_bonus.csv.gz")
F_NOT = os.path.join(HERE, "st_notes.csv")
F_MOV = os.path.join(HERE, "st_moves.csv.gz")
F_SET = os.path.join(HERE, "st_settle.csv.gz")
F_WO = os.path.join(HERE, "st_wo.csv.gz")
F_PRD = os.path.join(HERE, "st_prod.csv")
F_IPR = os.path.join(HERE, "st_itemprices.csv")
F_CPR = os.path.join(HERE, "st_contractprices.csv")
F_PAY = os.path.join(HERE, "st_pay.csv.gz")
F_MAP = os.path.join(HERE, "st_map.csv")
F_CFG = os.path.join(HERE, "st_settings.json")
# جدول ربط المواد ببنود الأعمال، مفتاحه كود الشركة المعدّل (40 + كود الكتالوج + U)
F_LNK = os.path.join(HERE, "sites_matlink.csv")
# تصنيف الأصناف المعتمد من الشركة (عهدة / تشغيلية) لما لا يرد في جدول تصنيف تقرير الحركة
F_CLS = os.path.join(HERE, "st_itemclass.csv")

CSS = """
<style>
  .sv-title { direction: rtl; text-align: right; background: linear-gradient(90deg,#065F46,#0E9F6E); color:#fff;
              padding:9px 14px; border-radius:6px; margin:18px 0 8px 0; font-weight:700; font-size:1.1rem; }
  .sv-note { direction: rtl; text-align: right; background:#FFF7E0; border-right:4px solid #F59E0B; color:#7A4B00;
             padding:8px 12px; border-radius:6px; font-size:0.95rem; margin:6px 0; }
  [class*="st-key-sv_grid"] [data-testid="stDataFrame"], [class*="st-key-sv_grid"] [data-testid="stDataFrame"] * {
      direction: ltr !important; text-align: left !important; }
  [class*="st-key-sv_grid"] [data-testid="stDataFrame"] { font-size: 1.02rem !important; }
  [class*="st-key-sv_grid"] [role="columnheader"] { font-weight:700 !important; font-size:1.0rem !important; }
  [class*="st-key-sv_grid"] [role="gridcell"] { font-size: 1.0rem !important; }
  .sv-start { direction: rtl; text-align: right; background:#F8FAFC; border:1px solid #E2E8F0;
              border-right:4px solid #0E9F6E; border-radius:10px; padding:14px 18px; margin:10px 0; }
  .sv-start h4 { margin:0 0 8px 0; color:#065F46; font-size:1.08rem; }
  .sv-start ol { margin:0; padding-right:20px; line-height:2.0; color:#111827; font-size:1.0rem; }
  .sv-start .f { background:#fff; border:1px solid #E2E8F0; border-radius:6px; padding:2px 8px;
                 font-weight:600; color:#0B2A6F; }
</style>
"""

SITES = ["الرياض", "مكة", "تبوك", "عسير", "الباحة", "المخواة", "القنفذة", "حقل"]
# ربط رقم عقد الكهرباء بالموقع (العقد السابق 2021 والعقد الحالي 2026)
CONTRACT_SITE = {
    "4400014756": "الرياض", "4400014785": "مكة", "4400014802": "تبوك", "4400014962": "عسير", "4400014970": "الباحة",
    "4400023652": "الرياض", "4400023847": "مكة", "4400023494": "تبوك", "4400023564": "عسير", "4400023530": "الباحة",
}
NEW_CONTRACTS = {"4400023494", "4400023530", "4400023564", "4400023652", "4400023847"}
# مكاتب تُفصل عن عقد الباحة في التقارير
OFFICE_SPLIT = {"المخواة": "المخواة", "المخواه": "المخواة", "القنفذة": "القنفذة", "القنفذه": "القنفذة", "حقل": "حقل"}
MONTHS_AR = {"يناير": 1, "فبراير": 2, "مارس": 3, "أبريل": 4, "ابريل": 4, "مايو": 5, "يونيو": 6, "يوليو": 7,
             "أغسطس": 8, "اغسطس": 8, "سبتمبر": 9, "أكتوبر": 10, "اكتوبر": 10, "نوفمبر": 11, "ديسمبر": 12}
ISSUE, EST, RET = "صرف أمر العمل", "أمر العمل", "استلام صرف أمر العمل"
DEFAULT_CFG = {"site": "الرياض", "rd_factor": 18.0, "alloc": "نسبة البونص", "m_from": 1, "m_to": 12, "year": 2026,
               "asphalt_code": "306010001", "asphalt_pct": 40.0, "emg_pct": 45.0}


def _box(key):
    """حاوية بمفتاح لتطبيق التنسيق، مع بديل للإصدارات التي لا تدعم المفتاح."""
    try:
        return st.container(key=key)
    except TypeError:
        return st.container()


def _grid(df, key, height=430, rev=True, pin=None, key_font=1.25, rows=700):
    """جدول موحّد: رأس ثابت وعمود أساسي ثابت على اليمين وأرقام في منتصف الخلية."""
    ut.wide(df, pin, key_font=key_font, height=f"{int(height) + 60}px", max_rows=rows)


def _onboard(where=""):
    """شاشة البداية: ماذا يُرفع وبأي ترتيب، تظهر ما دامت بيانات الموقع غير محمّلة."""
    st.markdown(
        '<div class="sv-start"><h4>ابدأ من تبويب «⚙️ البيانات والإعدادات»: اختر الموقع ثم ارفع ملفاته دفعة واحدة</h4>'
        '<ol>'
        '<li><span class="f">تقارير البونص الشهرية</span> — ملف لكل شهر، ومنه تُقرأ كميات البنود المنفذة وأسعارها وملاحظات المراجع.</li>'
        '<li><span class="f">تقرير حركة الأصناف</span> — صرف المواد على أوامر العمل، ويُصحَّح تكرار التصدير آلياً.</li>'
        '<li><span class="f">تقرير تصفية أوامر العمل</span> — المقايسة والمصروف والمتبقي لكل أمر عمل وصنف.</li>'
        '<li><span class="f">موقف أوامر العمل من الكهرباء</span> — ملف لكل منطقة، ومنه حالة كل أمر وشهادات الإنجاز.</li>'
        '<li><span class="f">تقرير إنتاجية الموقع</span> — التنفيذ الشهري لفرق الشركة ومقاولي الباطن.</li>'
        '<li><span class="f">أسعار الأصناف</span> من الحسابات — لتسعير المواد التشغيلية المصروفة في مستودع الموقع.</li>'
        '<li><span class="f">تقرير الرواتب التفصيلي</span> و<span class="f">أسعار بنود العقد</span> — مرة واحدة للشركة كلها.</li>'
        '</ol>'
        '<div style="margin-top:10px;color:#475569;font-size:.95rem">'
        '<b>تُرفع مرة واحدة للشركة كلها ولا تتكرر مع كل موقع:</b> تقرير الرواتب التفصيلي (يشمل كل المواقع والشهور)، '
        'وأسعار بنود العقد (الخمسة في ملف واحد)، وموقف أوامر العمل (ملف لكل منطقة يغطي مواقعها). '
        '<b>وتُرفع لكل موقع على حدة:</b> تقارير البونص وحركة الأصناف وتصفية أوامر العمل وإنتاجية الموقع وأسعار الأصناف. '
        'البرنامج يتعرّف على نوع كل ملف من محتواه، ويستنتج شهر تقرير البونص من اسم الملف أو من أوراقه. '
        'بعد الرفع اضبط «جدول ربط بنود الأعمال بالمواد» في تبويب مراجعة البونص، فهو أساس المقارنة.</div></div>',
        unsafe_allow_html=True)
    if where:
        st.caption(where)


def _title(t):
    st.markdown(f'<div class="sv-title">{t}</div>', unsafe_allow_html=True)


def _note(t):
    st.markdown(f'<div class="sv-note">{t}</div>', unsafe_allow_html=True)


def _fmt(v, d=0):
    try:
        if v is None or (isinstance(v, float) and not np.isfinite(v)):
            return "—"
        return f"{float(v):,.{d}f}"
    except Exception:
        return "—"


def _read(path, **kw):
    try:
        if os.path.exists(path):
            return pd.read_csv(path, **kw)
    except Exception:
        pass
    return None


def _save(df, path):
    try:
        df.to_csv(path, index=False)
    except Exception:
        pass


def _norm(s):
    return re.sub(r"\s+", " ", str(s)).strip()


def _wo(v):
    """رقم أمر العمل كما ورد (تسعة أرقام للمشاريع والطوارئ، وقد يرد بثمانية)."""
    s = str(v).split(".")[0].strip()
    return s if re.fullmatch(r"\d{7,11}", s) else ""


def _woraw(v):
    """أي قيمة غير فارغة في خانة أمر العمل تُحفظ كما هي حتى لا تضيع كميات المستند."""
    s = str(v).split(".")[0].strip()
    return "" if s in ("", "nan", "None", "NaT") else s


# ---------------- التعرف على الملفات ----------------
def detect(raw, name=""):
    """يحدد نوع الملف من أسماء الأوراق ورؤوس الأعمدة."""
    try:
        wb = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
    except Exception:
        return ""
    sheets = [s.title.strip() for s in wb.worksheets]
    if any("تقرير البونص" in s for s in sheets):
        return "بونص"
    if any("حركة الاصناف" in s or "حركة الأصناف" in s or "حركة اصناف" in s or "حركة أصناف" in s for s in sheets):
        return "حركة الأصناف"
    ws = wb.worksheets[0]
    hdr = []
    for i, r in enumerate(ws.iter_rows(max_row=6, max_col=30, values_only=True)):
        hdr += [_norm(x) for x in r if x is not None]
        if i >= 5:
            break
    H = set(hdr)
    if {"موقف أمر العمل", "رقم أمر العمل"} <= H or "مـوقف أوامر عمل مقاول" in [s for s in sheets]:
        return "أوامر العمل"
    if {"المقايسة", "الصرف", "الارجاع"} <= H:
        return "تصفية"
    if {"الاسناد المتاح", "أجمالي التنفيذ"} & H or "موقف_العقود" in sheets[0]:
        return "إنتاجية"
    if {"اجمالي الراتب", "الشهر", "الموقع"} <= H:
        return "رواتب"
    if {"الصنف", "الكمية", "السعر", "الاجمالي"} <= H:
        return "أسعار الأصناف"
    if {"رقم البند", "نوع البند"} <= H or {"Item", "Line type"} <= H:
        return "أسعار العقد"
    if {"كود الصنف", "التصنيف المعتمد"} <= H:
        return "تصنيف الأصناف"
    return ""


# ---------------- المحللات ----------------
def _month_of(texts):
    """يستنتج رقم الشهر من اسم ورقة أو اسم ملف (رقم مجرد أو اسم شهر عربي)."""
    for t in texts:
        t = _norm(t)
        for k, v in MONTHS_AR.items():
            if k in t:
                return v
        m = re.search(r"(?<!\d)(1[0-2]|[1-9])(?!\d)", re.sub(r"20\d\d", " ", t))
        if m:
            return int(m.group(1))
    return 0


def parse_bonus(raw, site, fname=""):
    """تقرير البونص الشهري: صفوف أوامر العمل وأعمدة بنود الأعمال، مع ورقة ملاحظات المراجع."""
    wb = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
    sh = [s.title for s in wb.worksheets if "تقرير البونص" in s.title]
    ws = wb[sh[0]]
    rows = list(ws.iter_rows(max_col=80, values_only=True))
    h = next((i for i, r in enumerate(rows) if r and r[0] == "م" and r[1] and "امر العمل" in str(r[1])), None)
    if h is None:
        return pd.DataFrame(), pd.DataFrame()
    top, sub = rows[h], rows[h + 1]
    codes = next((r for r in rows[h: h + 8] if r and r[0] and str(r[0]).startswith("رقم البند")), [None] * 80)
    grp, cur = [None] * 80, None
    for j in range(80):
        if top[j]:
            cur = _norm(top[j])
        grp[j] = cur
    cols = {}
    for j in range(2, 76):
        nm = _norm(sub[j]) if sub[j] else ""
        s3, s4 = rows[h + 2][j], rows[h + 3][j]
        parts = [grp[j], nm]
        for s in (s3, s4):
            t = _norm(s) if s is not None else ""
            if t and not t.replace(".", "").isdigit():
                parts.append(t)
        cols[j] = (" | ".join([p for p in parts if p]), _norm(codes[j]) if codes[j] else "")
    # الشهر: من اسم ورقة حركة الأصناف داخل الملف، وإلا من اسم الملف
    mon = _month_of([s.title for s in wb.worksheets if "حركة" in s.title] + [fname])
    # صفوف الأسعار داخل التقرير نفسه: سعر البند في العقد، ثم سعره بعد نسبة الطوارئ
    def _row(pre):
        return next((i for i, r in enumerate(rows) if r[0] and str(r[0]).strip().startswith(pre)), None)
    iq, ie = _row("الاجمالي للتنفيذ"), _row("الاجمالي للطواريء")
    P = rows[iq + 1] if iq is not None and iq + 1 < len(rows) else [None] * 80
    PE = rows[ie + 1] if ie is not None and ie + 1 < len(rows) else P
    num = lambda v: float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else np.nan
    rep_total = next((num(r[12]) for r in rows if r[10] and "إجمالى الأعمال" in str(r[10])), np.nan)
    end = iq if iq is not None else len(rows)
    out = []
    for r in rows[h + 1: end]:
        w = _wo(r[1]) if r[1] is not None else ""
        if not w:
            continue
        em = len(w) < 9  # أوامر الطوارئ ترد بثمانية أرقام وتُسعَّر بسعر العقد بعد نسبة الطوارئ
        for j, (nm, cd) in cols.items():
            v = num(r[j])
            if pd.notna(v) and v:
                pr = num(PE[j]) if em else num(P[j])
                out.append((site, mon, w, "طوارئ" if em else "مشروع", nm, cd, v, pr, v * pr if pd.notna(pr) else np.nan,
                            rep_total, fname))
    B = pd.DataFrame(out, columns=["الموقع", "الشهر", "أمر العمل", "النوع", "بند الأعمال", "رمز البند", "الكمية",
                                   "سعر البند", "القيمة", "إجمالي التقرير", "المصدر"])
    N = pd.DataFrame(columns=["الموقع", "الشهر", "أمر العمل", "البند", "البونص", "الصرف", "الفرق", "الملاحظة", "رد أمين المستودع", "المصدر"])
    sn = [s.title for s in wb.worksheets if "ملاحظات البونص" in s.title]
    if sn:
        nr = [r for r in wb[sn[0]].iter_rows(min_row=2, values_only=True) if r and r[0]]
        N = pd.DataFrame([(site, mon, _wo(r[0]), r[1], r[2], r[3], r[4],
                           r[5] if len(r) > 5 else "", r[6] if len(r) > 6 else "", fname) for r in nr], columns=N.columns)
    return B, N


def parse_moves(raw, site):
    """حركة الأصناف: تُجمَّع على مستوى (المستند، التاريخ، الصنف، أمر العمل) مع تصحيح تكرار التصدير."""
    wb = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
    sh = [s.title for s in wb.worksheets if "حركة" in s.title and "صناف" in s.title]
    ws = wb[sh[0]]
    rows = list(ws.iter_rows(values_only=True))
    hdr = [_norm(c) for c in rows[0]]
    D = pd.DataFrame(rows[1:], columns=hdr)
    ren = {"رقن امر العمل": "أمر العمل", "رقم امر العمل": "أمر العمل", "نوع المعاملة": "نوع المعاملة",
           "تاريخ المعاملة": "التاريخ", "رقم المستند": "المستند", "الكمية": "الكمية", "الوحدة": "الوحدة",
           "الصنف": "الصنف", "كود الصنف": "كود الصنف"}
    D = D.rename(columns={k: v for k, v in ren.items() if k in D.columns})
    # أسطر بلا أمر عمل تبقى محسوبة ضمن المستند حتى لا تضيع كمياتها
    D["أمر العمل"] = D["أمر العمل"].map(lambda v: _woraw(v) or "بدون أمر عمل")
    D["التاريخ"] = pd.to_datetime(D["التاريخ"], errors="coerce")
    D["الكمية"] = pd.to_numeric(D["الكمية"], errors="coerce").fillna(0.0)
    D["الصنف"] = D["الصنف"].map(_norm)
    D = D.copy()
    # تصنيف المواد إن وُجدت ورقته
    cls = {}
    for s in wb.worksheets:
        if "تصنيف المواد" in s.title:
            cls = {_norm(r[0]): _norm(r[1]) for r in s.iter_rows(values_only=True) if r and r[0] and r[1]}
    D["التصنيف"] = D["الصنف"].map(cls).fillna("غير مصنف")
    # تصحيح التكرار: التصدير يكرر أسطر المستند أمام كل أمر عمل فيه
    D["أوامر المستند"] = D.groupby(["المستند", "التاريخ", "الصنف", "نوع المعاملة"])["أمر العمل"].transform("nunique")
    D["الكمية الصحيحة"] = D["الكمية"] / D["أوامر المستند"].replace(0, 1)
    D["الموقع"] = site
    D["الشهر"] = D["التاريخ"].dt.month
    D["السنة"] = D["التاريخ"].dt.year
    g = D.groupby(["الموقع", "السنة", "الشهر", "نوع المعاملة", "أمر العمل", "الصنف", "كود الصنف", "الوحدة", "التصنيف"], as_index=False).agg(
        **{"الكمية كما وردت": ("الكمية", "sum"), "الكمية": ("الكمية الصحيحة", "sum"),
           "أقصى تكرار": ("أوامر المستند", "max"), "عدد الأسطر": ("الكمية", "size")})
    return g


def parse_settle(raw, site):
    """تصفية أوامر العمل: سطر لكل أمر عمل وصنف (المقايسة والمندوب والصرف والإرجاع والمتبقي)."""
    ws = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True).worksheets[0]
    rows = list(ws.iter_rows(values_only=True))
    h = next(i for i, r in enumerate(rows) if r and any(_norm(x) == "المقايسة" for x in r if x is not None))
    hdr = [_norm(x) if x is not None else f"c{j}" for j, x in enumerate(rows[h])]
    D = pd.DataFrame(rows[h + 1:], columns=hdr)
    D = D.rename(columns={"رقم امر العمل": "أمر العمل", "التاريخ": "تاريخ الأمر", "الصنف": "الصنف",
                          "كود الصنف": "كود الصنف", "الوحدة": "الوحدة"})
    D["أمر العمل"] = D["أمر العمل"].map(_woraw)
    D = D[D["أمر العمل"] != ""].copy()
    D["تاريخ الأمر"] = pd.to_datetime(D["تاريخ الأمر"], errors="coerce")
    for c in ["المقايسة", "المندوب", "الاستلام المخزني", "الصرف", "الارجاع", "متبقي صرف", "متبقي استلام"]:
        D[c] = pd.to_numeric(D[c], errors="coerce").fillna(0.0) if c in D.columns else 0.0
    D["الصنف"] = D["الصنف"].map(_norm)
    D["صافي الصرف"] = D["الصرف"] - D["الارجاع"]
    D["فرق المقايسة"] = D["صافي الصرف"] - D["المقايسة"]
    D["الموقع"] = site
    keep = ["الموقع", "أمر العمل", "تاريخ الأمر", "الصنف", "كود الصنف", "الوحدة", "المقايسة", "المندوب",
            "الاستلام المخزني", "الصرف", "الارجاع", "صافي الصرف", "متبقي صرف", "فرق المقايسة"]
    return D[[c for c in keep if c in D.columns]].reset_index(drop=True)


def parse_wo(raw):
    """موقف أوامر العمل من الكهرباء (ملف لكل منطقة)."""
    ws = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True).worksheets[0]
    rows = list(ws.iter_rows(values_only=True))
    hdr = [_norm(x) if x is not None else f"c{j}" for j, x in enumerate(rows[0])]
    D = pd.DataFrame(rows[1:], columns=hdr)
    D["رقم أمر العمل"] = D["رقم أمر العمل"].map(_woraw)
    D = D[D["رقم أمر العمل"] != ""].copy()
    for c in ["تكلفة المواد الغير مصروفه", "تكلفة المواد المصروفه", "مبلغ شهادة الإنجاز", "تكلفة العمالة"]:
        if c in D.columns:
            D[c] = pd.to_numeric(D[c], errors="coerce")
    for c in [c for c in D.columns if c.startswith("تاريخ")]:
        D[c] = pd.to_datetime(D[c], errors="coerce", format="mixed", dayfirst=False)
    D["رقم العقد"] = D["رقم العقد"].astype(str).str.replace(".0", "", regex=False)
    D["الموقع"] = D["رقم العقد"].map(CONTRACT_SITE)
    off = D["المكتب"].astype(str) if "المكتب" in D.columns else pd.Series("", index=D.index)
    # العقود القديمة غير المعرّفة: يُستدل على الموقع من اسم المكتب
    for k, v in (("مدينةالرياض", "الرياض"), ("الرياض", "الرياض"), ("كهرباء مكة", "مكة"), ("كهرباء تبوك", "تبوك"),
                 ("كهرباء عسير", "عسير"), ("كهرباء الباحة", "الباحة"), ("بارق", "عسير"), ("سبت الجارة", "عسير")):
        D.loc[D["الموقع"].isna() & off.str.contains(k, na=False), "الموقع"] = v
    for k, v in OFFICE_SPLIT.items():
        D.loc[off.str.contains(k, na=False), "الموقع"] = v
    D["جيل العقد"] = np.where(D["رقم العقد"].isin(NEW_CONTRACTS), "العقد الحالي 2026", "العقد السابق")
    agg = {"الموقع": "first", "جيل العقد": "first", "المكتب": "first", "المنطقة": "first",
           "نوع امر العمل": "first", "موقف أمر العمل": "last", "حالة الصرف": "last",
           "تكلفة المواد المصروفه": "max", "تكلفة المواد الغير مصروفه": "max", "تكلفة العمالة": "max",
           "مبلغ شهادة الإنجاز": "sum", "تاريخ التسليم للمقاول": "min",
           "تاريخ الاستلام من المقاول": "max", "تاريخ شهادة الانجاز": "max", "تاريخ المستخلص": "max"}
    agg = {k: v for k, v in agg.items() if k in D.columns}
    if "تاريخ المستخلص" in D.columns:
        D = D.sort_values("تاريخ المستخلص")
    G = D.groupby(["رقم أمر العمل", "رقم العقد"], as_index=False).agg(agg)
    G["النوع"] = np.where(G["رقم أمر العمل"].str.startswith("42"), "طوارئ", "مشروع")
    return G


def parse_prod(raw, site):
    """تقرير إنتاجية الموقع (موقف العقود التراكمي الشهري)."""
    ws = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True).worksheets[0]
    rows = list(ws.iter_rows(max_col=30, values_only=True))
    top, sub = rows[0], rows[1]
    n = len(top)
    grp, cur = [None] * n, None
    for j in range(n):
        if top[j]:
            cur = _norm(top[j])
        grp[j] = cur
    names = {}
    for j in range(n):
        a, b = grp[j], _norm(sub[j]) if sub[j] else ""
        names[j] = (f"{a} | {b}" if a and b else (a or b or f"c{j}"))
    out = []
    for r in rows[2:]:
        k = _norm(r[0]) if r[0] else ""
        if k not in MONTHS_AR:
            continue
        rec = {"الموقع": site, "الشهر": MONTHS_AR[k]}
        for j in range(1, n):
            rec[names[j]] = pd.to_numeric(r[j], errors="coerce")
        out.append(rec)
    P = pd.DataFrame(out)
    return P.dropna(how="all", axis=1)


def parse_pay(raw):
    """تقرير الرواتب التفصيلي لكل الموظفين والشهور."""
    ws = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True).worksheets[0]
    rows = list(ws.iter_rows(values_only=True))
    hdr = [_norm(x) if x is not None else f"c{j}" for j, x in enumerate(rows[0])]
    D = pd.DataFrame(rows[1:], columns=hdr)
    D["الشهر"] = pd.to_datetime(D["الشهر"], errors="coerce")
    D = D[D["الشهر"].notna()].copy()
    num = ["اجمالي الراتب", "الراتب", "اضافي", "بدل صيانة", "بونص", "مامورية", "اخرى", "بدل انتقال", "بدل سكن",
           "التنقلات", "الاقامات", "الاجازة المستحقة", "نهاية الخدمة", "تأمين اجتماعي", "تأمين طبي شهري", "ايام الدوام"]
    for c in num:
        D[c] = pd.to_numeric(D[c], errors="coerce").fillna(0.0) if c in D.columns else 0.0
    D["الموقع"] = D["الموقع"].map(_norm) if "الموقع" in D.columns else ""
    D["الرقم الوظيفي"] = D["الرقم الوظيفي"].astype(str).str.replace(".0", "", regex=False)
    D["السنة"] = D["الشهر"].dt.year
    D["رقم الشهر"] = D["الشهر"].dt.month
    D["التكلفة الكاملة"] = D[["اجمالي الراتب", "اضافي", "بدل صيانة", "بونص", "مامورية", "اخرى", "التنقلات",
                              "الاقامات", "الاجازة المستحقة", "نهاية الخدمة", "تأمين اجتماعي", "تأمين طبي شهري"]].sum(axis=1)
    keep = ["الرقم الوظيفي", "الاسم", "المهنة", "الموقع", "السنة", "رقم الشهر", "اجمالي الراتب", "اضافي", "بدل صيانة",
            "بونص", "مامورية", "اخرى", "التنقلات", "الاقامات", "تأمين اجتماعي", "تأمين طبي شهري", "التكلفة الكاملة"]
    G = D[[c for c in keep if c in D.columns]].groupby(
        ["الموقع", "السنة", "رقم الشهر"], as_index=False).agg(
        **{"عدد العاملين": ("الرقم الوظيفي", "nunique"), "إجمالي الرواتب": ("اجمالي الراتب", "sum"),
           "مأموريات": ("مامورية", "sum"), "تنقلات": ("التنقلات", "sum"), "إقامات": ("الاقامات", "sum"),
           "تأمينات": ("تأمين اجتماعي", "sum"), "تأمين طبي": ("تأمين طبي شهري", "sum"),
           "التكلفة الكاملة": ("التكلفة الكاملة", "sum")})
    return G


def parse_item_prices(raw):
    """تقرير أسعار الأصناف من الحسابات: متوسط سعر الوحدة لكل صنف من حركة الشراء."""
    ws = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True).worksheets[0]
    rows = [r for r in ws.iter_rows(values_only=True) if r and any(x is not None for x in r)]
    h = next((i for i, r in enumerate(rows) if any(_norm(x) == "الصنف" for x in r if x is not None)), 0)
    idx = {_norm(x): j for j, x in enumerate(rows[h]) if x is not None}
    c_it, c_q, c_p, c_t = idx.get("الصنف"), idx.get("الكمية"), idx.get("السعر"), idx.get("الاجمالي")
    out = []
    for r in rows[h + 1:]:
        if c_it is None or r[c_it] is None:
            continue
        typ = _norm(r[0]) if r[0] is not None else ""
        q = pd.to_numeric(r[c_q], errors="coerce") if c_q is not None else np.nan
        t = pd.to_numeric(r[c_t], errors="coerce") if c_t is not None else np.nan
        p = pd.to_numeric(r[c_p], errors="coerce") if c_p is not None else np.nan
        out.append({"نوع الحركة": typ, "صنف الحسابات": _norm(r[c_it]), "الكمية": q, "السعر": p, "الإجمالي": t})
    D = pd.DataFrame(out)
    D = D[D["نوع الحركة"].str.contains("تكاليف|استلام|شراء", na=False)]
    G = D.groupby("صنف الحسابات", as_index=False).agg(
        **{"الكمية المستلمة": ("الكمية", "sum"), "القيمة": ("الإجمالي", "sum"),
           "أقل سعر": ("السعر", "min"), "أعلى سعر": ("السعر", "max")})
    G["متوسط السعر"] = (G["القيمة"] / G["الكمية المستلمة"]).replace([np.inf, -np.inf], np.nan)
    return G


def parse_contract_prices(raw):
    """أسعار بنود العقد الموحد للمواقع الخمسة."""
    ws = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True).worksheets[0]
    rows = list(ws.iter_rows(max_col=20, values_only=True))
    h = next((i for i, r in enumerate(rows) if r and any(_norm(x) == "Item" for x in r if x is not None)), None)
    if h is None:
        return pd.DataFrame()
    idx = {_norm(x): j for j, x in enumerate(rows[h]) if x is not None}
    ci, ct = idx.get("Item"), idx.get("Line type")
    cd = idx.get("Short Description")
    cu = idx.get("UOM")
    site_cols = {k: j for k, j in idx.items() if _norm(k) in ("الباحة", "عسير", "تبوك", "مكة", "الرياض")}
    out = []
    for r in rows[h + 1:]:
        if ci is None or r[ci] is None or (ct is not None and _norm(r[ct]) != "Breakdown"):
            continue
        rec = {"رمز البند": _norm(r[ci]), "الوصف": _norm(r[cd])[:90] if cd is not None else "",
               "الوحدة": _norm(r[cu]) if cu is not None else ""}
        for k, j in site_cols.items():
            rec[_norm(k)] = pd.to_numeric(r[j], errors="coerce")
        out.append(rec)
    D = pd.DataFrame(out).drop_duplicates("رمز البند")
    if "مكة" not in D.columns and "مكة " in D.columns:
        D = D.rename(columns={"مكة ": "مكة"})
    return D


# ---------------- الحالة ----------------
def _state():
    ss = st.session_state
    defs = {"sv_bon": (F_BON, ["الموقع", "الشهر", "أمر العمل", "بند الأعمال", "رمز البند", "الكمية"]),
            "sv_not": (F_NOT, ["الموقع", "الشهر", "أمر العمل", "البند", "البونص", "الصرف", "الفرق", "الملاحظة", "رد أمين المستودع"]),
            "sv_mov": (F_MOV, []), "sv_set": (F_SET, []), "sv_wo": (F_WO, []), "sv_prd": (F_PRD, []),
            "sv_ipr": (F_IPR, []), "sv_cpr": (F_CPR, []), "sv_pay": (F_PAY, []),
            "sv_map": (F_MAP, ["الموقع", "رمز البند", "بند الأعمال", "كود المادة", "المادة", "معامل"])}
    for k, (path, cols) in defs.items():
        if k not in ss:
            d = _read(path, dtype={"أمر العمل": str, "رمز البند": str, "كود المادة": str, "كود الصنف": str, "رقم أمر العمل": str, "رقم العقد": str})
            ss[k] = d if d is not None else pd.DataFrame(columns=cols)
    if "sv_cfg" not in ss:
        cfg = dict(DEFAULT_CFG)
        try:
            if os.path.exists(F_CFG):
                cfg.update(json.load(open(F_CFG, encoding="utf-8")))
        except Exception:
            pass
        if int(cfg.get("m_from", 1)) == 3 and int(cfg.get("m_to", 12)) == 9:
            cfg["m_from"], cfg["m_to"] = 1, 12   # النطاق القديم كان مارس–سبتمبر، والافتراضي الآن السنة كاملة
        ss["sv_cfg"] = cfg
    return [ss[k] for k in ("sv_bon", "sv_not", "sv_mov", "sv_set", "sv_wo", "sv_prd", "sv_ipr", "sv_cpr", "sv_pay", "sv_map")] + [ss["sv_cfg"]]


def _save_cfg(cfg):
    st.session_state["sv_cfg"] = cfg
    try:
        json.dump(cfg, open(F_CFG, "w", encoding="utf-8"), ensure_ascii=False)
    except Exception:
        pass


# ---------------- الحسابات ----------------
def bonus_value(bon, cpr, cfg, site):
    """قيمة المنفذ: تُؤخذ من أسعار تقرير البونص نفسه، وتُكمَّل من جدول أسعار العقد عند غيابها."""
    B = bon[bon["الموقع"] == site].copy()
    if not len(B):
        return B.assign(**{"سعر الوحدة": [], "القيمة": []})
    if "القيمة" in B.columns and B["القيمة"].notna().any():
        B["سعر الوحدة"] = B.get("سعر البند")
        miss = B["القيمة"].isna()
        if miss.any() and len(cpr) and site in cpr.columns:
            pr = cpr.drop_duplicates("رمز البند").set_index("رمز البند")[site].to_dict()
            f = np.where(B.loc[miss, "النوع"] == "طوارئ", 1.0 + float(cfg.get("emg_pct", 45.0)) / 100.0, 1.0)
            p = B.loc[miss, "رمز البند"].map(lambda c: pr.get(str(c).strip(), np.nan)).values * f
            B.loc[miss, "سعر الوحدة"] = p
            B.loc[miss, "القيمة"] = B.loc[miss, "الكمية"].values * p
        return B
    col = site if (len(cpr) and site in cpr.columns) else None
    pr = cpr.drop_duplicates("رمز البند").set_index("رمز البند")[col].to_dict() if col else {}
    asph = pr.get(str(cfg.get("asphalt_code", "306010001")))
    pct = float(cfg.get("asphalt_pct", 40.0)) / 100.0

    def price(code):
        c = str(code).strip()
        if c in pr and pd.notna(pr[c]):
            return float(pr[c])
        if "%" in c and asph:
            m = re.search(r"(\d+)\s*%", c)
            return (float(m.group(1)) / 100.0) * float(asph) if m else pct * float(asph)
        return np.nan
    B["سعر الوحدة"] = B["رمز البند"].map(price)
    B["القيمة"] = B["الكمية"] * B["سعر الوحدة"]
    return B


def _ckey(s):
    """توحيد كود الصنف للمطابقة: بلا فراغات وبحرف كبير."""
    return pd.Series(s).astype(str).str.replace(r"\s+", "", regex=True).str.upper()


@st.cache_data(show_spinner=False)
def matlink():
    """جدول ربط المواد ببنود الأعمال المستخرج من ملفي الربط، مفتاحه كود الشركة المعدّل."""
    if not os.path.exists(F_LNK):
        return pd.DataFrame()
    try:
        D = pd.read_csv(F_LNK, dtype=str).fillna("")
    except Exception:
        return pd.DataFrame()
    D["المعامل"] = pd.to_numeric(D.get("المعامل"), errors="coerce").fillna(0.0)
    D["كود المادة"] = _ckey(D["كود المادة"])
    return D


_AR_STOP = {"ال", "مقاس", "عادي", "عاده", "سم", "مم", "ملم", "حبه", "كيلو", "كجم", "من", "مع", "الي", "لون"}


def _ar(s):
    """تبسيط الاسم العربي: حذف التشكيل وتوحيد الألف والهاء والياء وإزالة الرموز."""
    s = re.sub(r"[ً-ْـ]", "", str(s or ""))
    for a, b in (("أ", "ا"), ("إ", "ا"), ("آ", "ا"), ("ة", "ه"), ("ى", "ي"), ("ؤ", "و"), ("ئ", "ي")):
        s = s.replace(a, b)
    return re.sub(r"\s+", " ", re.sub(r"[^0-9A-Za-zء-ي]+", " ", s)).strip()


def parse_item_class(raw):
    """ملف تصنيف الأصناف المعتمد: كود الصنف + الاسم + التصنيف المعتمد."""
    ws = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True).worksheets[0]
    rows = [r for r in ws.iter_rows(values_only=True) if r and any(x is not None for x in r)]
    h = next(i for i, r in enumerate(rows) if any(_norm(x) == "كود الصنف" for x in r if x is not None))
    idx = {_norm(x): j for j, x in enumerate(rows[h]) if x is not None}
    ck, cn, cc = idx.get("كود الصنف"), idx.get("الصنف"), idx.get("التصنيف المعتمد")
    out = []
    for r in rows[h + 1:]:
        if ck is None or r[ck] is None or cc is None or r[cc] is None:
            continue
        out.append({"كود الصنف": _norm(r[ck]), "الصنف": _norm(r[cn]) if cn is not None else "",
                    "التصنيف": _norm(r[cc])})
    return pd.DataFrame(out).drop_duplicates("كود الصنف")


def class_map():
    """التصنيف المعتمد مفتاحه كود الصنف."""
    if not os.path.exists(F_CLS):
        return {}
    try:
        D = pd.read_csv(F_CLS, dtype=str).fillna("")
    except Exception:
        return {}
    return dict(zip(_ckey(D["كود الصنف"]), D["التصنيف"]))


def _ar_tok(s):
    t = set()
    for w in _ar(s).split():
        w = w[2:] if (len(w) > 4 and w.startswith("ال")) else w
        if len(w) >= 2 and w not in _AR_STOP:
            t.add(w)
    return t


def _best_name(name, cands, cut=0.50):
    """أقرب اسم في قائمة أسماء الحسابات: تطابق نصي ثم تداخل كلمات."""
    a, t = _ar(name), _ar_tok(name)
    if not t:
        return None, 0.0
    best, bs = None, 0.0
    for c in cands:
        b = _ar(c)
        if b == a:
            return c, 1.0
        u = _ar_tok(c)
        if not u:
            continue
        s = len(t & u) / len(t | u)
        if min(len(a), len(b)) >= 8 and (a in b or b in a):
            s = max(s, 0.85)
        if s > bs:
            bs, best = s, c
    return (best, round(bs, 2)) if bs >= cut else (None, round(bs, 2))


def item_price_map(mov_or_set, ipr, mp, site, detail=False):
    """سعر وحدة الصرف لكل صنف تشغيلي: جدول الربط اليدوي أولاً، ثم مطابقة اسم المستودع باسم الحسابات آلياً."""
    out, rev = {}, []
    I = ipr
    if len(I) and "الموقع" in I.columns:
        own = I[I["الموقع"] == site]
        I = own if len(own) else I.drop_duplicates("صنف الحسابات", keep="last")
    pr = I.drop_duplicates("صنف الحسابات", keep="last").set_index("صنف الحسابات")["متوسط السعر"].to_dict() if len(I) else {}
    manual = set()
    if len(mp):
        M = mp[mp["الموقع"] == site] if "الموقع" in mp.columns else mp
        for _, r in M.iterrows():
            if str(r.get("نوع الربط", "")) == "بند أعمال":
                continue
            acc = r.get("المادة")
            try:
                f = float(r.get("معامل")) if pd.notna(r.get("معامل")) and float(r.get("معامل")) else 1.0
            except Exception:
                f = 1.0
            p = pr.get(acc)
            k = str(r.get("كود المادة", "")) or str(r.get("بند الأعمال", ""))
            if p is not None and pd.notna(p) and k:
                out[k] = float(p) / f
                manual.add(k)
                rev.append({"كود الصنف": k, "صنف المستودع": "", "صنف الحسابات": acc, "درجة التطابق": 1.0,
                            "سعر الحسابات": float(p), "معامل التحويل": f, "سعر وحدة الصرف": float(p) / f,
                            "المصدر": "جدول الربط اليدوي"})
    # المطابقة الآلية لما لم يرد في جدول الربط، مع استنتاج معامل التحويل من الكميات
    D = mov_or_set
    if len(D) and len(pr) and "الصنف" in D.columns:
        W = D[D["التصنيف"].astype(str).str.startswith("مواد تشغيلية")] if "التصنيف" in D.columns else D
        if "نوع المعاملة" in W.columns:
            sg = np.where(W["نوع المعاملة"] == ISSUE, 1.0, np.where(W["نوع المعاملة"] == RET, -1.0, 0.0))
            q = W.assign(**{"_q": W["الكمية"] * sg}).groupby("الصنف")["_q"].sum()
        else:
            q = W.groupby("الصنف")["صافي الصرف"].sum() if "صافي الصرف" in W.columns else pd.Series(dtype=float)
        aq = I.drop_duplicates("صنف الحسابات", keep="last").set_index("صنف الحسابات")["الكمية المستلمة"].to_dict() if len(I) else {}
        cands = list(pr)
        for _, r in W.drop_duplicates("الصنف").iterrows():
            nm = r.get("الصنف")
            k = str(r.get("كود الصنف", "")) or str(nm)
            if not k or k in manual:
                continue
            acc, s = _best_name(nm, cands)
            p = pr.get(acc) if acc else None
            qw, qa = float(q.get(nm, 0) or 0), float(aq.get(acc, 0) or 0) if acc else 0.0
            f = 1.0
            if qw > 0 and qa > 0 and qw / qa > 3:
                f = max(1.0, round(qw / qa))
            u = (float(p) / f) if (p is not None and pd.notna(p)) else np.nan
            rev.append({"كود الصنف": k, "صنف المستودع": nm, "صنف الحسابات": acc or "—", "درجة التطابق": s,
                        "كمية المستودع": qw, "كمية الحسابات": qa,
                        "سعر الحسابات": (float(p) if p is not None and pd.notna(p) else np.nan),
                        "معامل التحويل": f, "سعر وحدة الصرف": u,
                        "المصدر": ("مطابقة الاسم آلياً" if f == 1 else "مطابقة الاسم مع معامل محسوب") if acc else "بلا سعر"})
            if pd.notna(u):
                out[k] = u
    if detail:
        return out, pd.DataFrame(rev)
    return out


def ops_cost(df, qty_col, name_col, prices):
    v = df[name_col].map(lambda s: prices.get(str(s), np.nan))
    return df[qty_col] * v.fillna(0.0)


# ---------------- الأقسام ----------------
def _bonus_review(bon, notes, mov, sett, cpr, mp, cfg, site, build):
    _title("مراجعة البونص: المنفذ مقابل المصروف")
    B = bon[bon["الموقع"] == site].copy()
    if not len(B):
        _onboard("مراجعة البونص تحتاج: تقارير البونص الشهرية + حركة الأصناف + جدول الربط.")
        return
    M = mov[(mov["الموقع"] == site)] if len(mov) else pd.DataFrame()
    if not len(M):
        st.info("ارفع تقرير حركة الأصناف ليتم مقارنة البونص بالمصروف.")
    links = mp[(mp["الموقع"] == site)] if len(mp) else pd.DataFrame()
    c1, c2, c3 = st.columns(3)
    months = sorted(B["الشهر"].dropna().unique().tolist())
    msel = c1.multiselect("الأشهر", months, default=months, key="sv_bm")
    lvl = c2.radio("مستوى المقارنة", ["أمر العمل", "المستودع (شهري)"], horizontal=True, key="sv_blvl")
    only = c3.checkbox("إظهار الفروق فقط", value=True, key="sv_bonly")
    Bf = B[B["الشهر"].isin(msel)]
    if not len(links):
        _note("لم يُحدَّد بعد ربط بنود الأعمال بالمواد. افتح «جدول الربط» أدناه وحدِّد لكل بند المادة التي تُصرف عليه.")
    rows = []
    if len(links) and len(M):
        Mi = M[M["نوع المعاملة"] == ISSUE]
        Mr = M[M["نوع المعاملة"] == RET]
        for _, L in links.iterrows():
            code, mat = str(L["رمز البند"]), str(L["كود المادة"])
            if not mat or mat == "nan":
                continue
            bb = Bf[Bf["رمز البند"] == code]
            if lvl == "أمر العمل":
                b = bb.groupby("أمر العمل")["الكمية"].sum()
                s = Mi[(Mi["كود الصنف"].astype(str) == mat) & (Mi["الشهر"].isin(msel))].groupby("أمر العمل")["الكمية"].sum()
                r = Mr[(Mr["كود الصنف"].astype(str) == mat) & (Mr["الشهر"].isin(msel))].groupby("أمر العمل")["الكمية"].sum()
                T = pd.concat([b.rename("البونص"), s.rename("الصرف"), r.rename("المرتجع")], axis=1).fillna(0.0)
                T = T[(T["البونص"] != 0) | (T["الصرف"] != 0)]
                for wo, x in T.iterrows():
                    rows.append({"أمر العمل": wo, "رمز البند": code, "بند الأعمال": L.get("بند الأعمال", ""),
                                 "المادة": L.get("المادة", ""), "البونص": x["البونص"],
                                 "صافي الصرف": x["الصرف"] - x["المرتجع"]})
            else:
                for m in msel:
                    bq = bb[bb["الشهر"] == m]["الكمية"].sum()
                    sq = Mi[(Mi["كود الصنف"].astype(str) == mat) & (Mi["الشهر"] == m)]["الكمية"].sum()
                    rq = Mr[(Mr["كود الصنف"].astype(str) == mat) & (Mr["الشهر"] == m)]["الكمية"].sum()
                    rows.append({"الشهر": m, "رمز البند": code, "بند الأعمال": L.get("بند الأعمال", ""),
                                 "المادة": L.get("المادة", ""), "البونص": bq, "صافي الصرف": sq - rq})
    T = pd.DataFrame(rows)
    if len(T):
        T["الفرق"] = T["صافي الصرف"] - T["البونص"]
        T["الحالة"] = np.where(T["الفرق"] > 0, "صرف أكبر من البونص", np.where(T["الفرق"] < 0, "صرف أقل من البونص", "مطابق"))
        if "الشهر" in T.columns:
            T = T.sort_values(["رمز البند", "الشهر"])
            T["تراكمي الفرق"] = T.groupby("رمز البند")["الفرق"].cumsum()
        if len(notes):
            nn = notes[(notes["الموقع"] == site) & (notes["الشهر"].isin(msel))]
            if "أمر العمل" in T.columns:
                T["ذكر في ملاحظات المراجع"] = T["أمر العمل"].isin(set(nn["أمر العمل"]))
        V = T[T["الفرق"] != 0] if only else T
        g = T.groupby("الحالة").agg(عدد=("الفرق", "size"), صافي_الفرق=("الفرق", "sum"))
        srows = [("item", k, [str(int(r.عدد)), _fmt(r.صافي_الفرق)]) for k, r in g.iterrows()]
        srows.append(("total", "الإجمالي", [str(int(g.عدد.sum())), _fmt(g.صافي_الفرق.sum())]))
        st.table(build(srows, ["الحالة", "عدد السطور", "صافي الفرق"]))
        _grid(V, "bon", 430, pin="البند")
        st.download_button("⬇️ تنزيل المقارنة (CSV)", T.to_csv(index=False).encode("utf-8-sig"),
                           f"bonus_review_{site}.csv", "text/csv", key="sv_dl_bon")
    with st.expander("🔗 جدول ربط بنود الأعمال بالمواد", expanded=not len(links)):
        _link_editor(bon, mov, mp, site)
    with st.expander("📝 ملاحظات محاسب المراجعة على البونص"):
        nn = notes[(notes["الموقع"] == site)] if len(notes) else pd.DataFrame()
        if len(nn):
            nn = nn[nn["الشهر"].isin(msel)]
            _grid(nn, "notes", 330, pin="أمر العمل", key_font=1.1)
        else:
            st.caption("لا توجد ملاحظات محمّلة.")
    with st.expander("📋 كميات البونص كما وردت"):
        G = Bf.groupby(["رمز البند", "بند الأعمال"], as_index=False)["الكمية"].sum().sort_values("الكمية", ascending=False)
        P = bonus_value(Bf.assign(**{"الموقع": site}), cpr, cfg, site)
        if len(P):
            val = P.groupby("رمز البند")["القيمة"].sum()
            G["القيمة بأسعار العقد"] = G["رمز البند"].map(val)
        _grid(G, "bq", 330, pin="الشهر")


def _link_editor(bon, mov, mp, site):
    """تحديد المادة المقابلة لكل بند أعمال، مع اقتراح آلي من تطابق الكميات."""
    B = bon[bon["الموقع"] == site]
    items = B.groupby(["رمز البند", "بند الأعمال"], as_index=False)["الكمية"].sum().sort_values("الكمية", ascending=False)
    mats = []
    if len(mov):
        M = mov[(mov["الموقع"] == site) & (mov["نوع المعاملة"] == ISSUE)]
        mats = (M.groupby(["كود الصنف", "الصنف"])["الكمية"].sum().sort_values(ascending=False)
                .reset_index().apply(lambda r: f"{r['الصنف']} [{r['كود الصنف']}]", axis=1).tolist())
    cur = mp[mp["الموقع"] == site].set_index("رمز البند") if len(mp) else pd.DataFrame()
    E = items.copy()
    E["المادة المرتبطة"] = E["رمز البند"].map(
        lambda c: (f"{cur.loc[c, 'المادة']} [{cur.loc[c, 'كود المادة']}]" if c in cur.index else ""))
    E = E.rename(columns={"الكمية": "كمية البونص"})
    ed = st.data_editor(E[["المادة المرتبطة", "كمية البونص", "بند الأعمال", "رمز البند"]],
                        hide_index=True, use_container_width=True, height=380, key=f"sv_map_ed_{site}",
                        column_config={"المادة المرتبطة": st.column_config.SelectboxColumn(options=[""] + mats),
                                       "رمز البند": st.column_config.TextColumn(disabled=True),
                                       "بند الأعمال": st.column_config.TextColumn(disabled=True),
                                       "كمية البونص": st.column_config.NumberColumn(disabled=True, format="%.0f")})
    c1, c2 = st.columns([1, 3])
    if c1.button("💾 حفظ الربط", key="sv_map_save"):
        rows = []
        for _, r in ed.iterrows():
            v = str(r["المادة المرتبطة"] or "").strip()
            if not v:
                continue
            m = re.match(r"^(.*)\s\[(.+)\]$", v)
            rows.append({"الموقع": site, "رمز البند": str(r["رمز البند"]), "بند الأعمال": r["بند الأعمال"],
                         "كود المادة": m.group(2) if m else "", "المادة": m.group(1) if m else v, "معامل": 1.0})
        new = pd.DataFrame(rows)
        old = mp[mp["الموقع"] != site] if len(mp) else pd.DataFrame(columns=new.columns)
        out = pd.concat([old, new], ignore_index=True)
        st.session_state["sv_map"] = out
        _save(out, F_MAP)
        st.success(f"تم حفظ {len(new)} ارتباطاً.")
        st.rerun()
    c2.caption("اختر لكل بند المادة التي تُصرف عليه. البنود بلا ربط تُستثنى من المقارنة.")


def _wo_cost(bon, mov, sett, wo, pay, ipr, cpr, mp, cfg, site, build):
    _title("تكلفة أوامر العمل")
    B = bonus_value(bon, cpr, cfg, site)
    if not len(B):
        _onboard("تكلفة أوامر العمل تحتاج: تقارير البونص + حركة الأصناف + الرواتب + أسعار الأصناف.")
        return
    yr = int(cfg.get("year", 2026))
    unpriced = B[B["سعر الوحدة"].isna()]
    if len(unpriced):
        _note(f"بنود بلا سعر في جدول العقد: {unpriced['رمز البند'].nunique()} بنداً بكمية {_fmt(unpriced['الكمية'].sum())}. "
              "القيمة المنفذة أقل من الواقع بمقدارها.")
    mb = B.groupby(["أمر العمل", "الشهر"], as_index=False)["القيمة"].sum()
    tot_m = mb.groupby("الشهر")["القيمة"].sum()
    mb["حصة الشهر"] = mb["القيمة"] / mb["الشهر"].map(tot_m).replace(0, np.nan)
    # تكلفة الرواتب الشهرية للموقع
    P = pay[(pay["السنة"] == yr)] if len(pay) else pd.DataFrame()
    if len(P):
        P = P[P["الموقع"].astype(str).str.contains(site, na=False)]
        sm = P.groupby("رقم الشهر")["التكلفة الكاملة"].sum()
    else:
        sm = pd.Series(dtype=float)
    mb["رواتب الشهر"] = mb["الشهر"].map(sm)
    mb["نصيب الأمر من الرواتب"] = mb["حصة الشهر"] * mb["رواتب الشهر"]
    W = mb.groupby("أمر العمل", as_index=False).agg(
        **{"القيمة المنفذة": ("القيمة", "sum"), "نصيب الرواتب": ("نصيب الأمر من الرواتب", "sum"),
           "أشهر التنفيذ": ("الشهر", lambda s: ", ".join(str(int(x)) for x in sorted(set(s))))})
    # المواد التشغيلية من حركة الأصناف للسنة نفسها
    prices, prev = item_price_map(mov, ipr, mp, site, detail=True)
    if len(mov):
        M = mov[(mov["الموقع"] == site) & (mov["السنة"] == yr) & (mov["التصنيف"].astype(str).str.startswith("مواد تشغيلية"))].copy()
        M["سعر"] = M["كود الصنف"].astype(str).map(prices)
        if M["سعر"].isna().all():
            M["سعر"] = M["الصنف"].map(prices)
        sign = np.where(M["نوع المعاملة"] == ISSUE, 1.0, np.where(M["نوع المعاملة"] == RET, -1.0, 0.0))
        M["التكلفة"] = M["الكمية"] * M["سعر"].fillna(0.0) * sign
        oc = M.groupby("أمر العمل", as_index=False)["التكلفة"].sum().rename(columns={"التكلفة": "المواد التشغيلية"})
        W = W.merge(oc, on="أمر العمل", how="outer")
    if len(wo):
        K = wo[wo["الموقع"] == site].copy()
        if "تاريخ المستخلص" in K.columns:
            K = K.sort_values("تاريخ المستخلص")
        a = {"موقف أمر العمل": ("موقف أمر العمل", "last"), "نوع امر العمل": ("نوع امر العمل", "first"),
             "المكتب": ("المكتب", "first"), "مبلغ شهادة الإنجاز": ("مبلغ شهادة الإنجاز", "sum")}
        if "تكلفة العمالة" in K.columns:
            a["القيمة التقديرية"] = ("تكلفة العمالة", "max")
        K = K.groupby("رقم أمر العمل", as_index=False).agg(**a)
        W = W.merge(K, left_on="أمر العمل", right_on="رقم أمر العمل", how="left").drop(columns=["رقم أمر العمل"])
    W["النوع"] = W.get("النوع", pd.Series(index=W.index, dtype=object))
    W["النوع"] = np.where(W["أمر العمل"].astype(str).str.startswith("42"), "طوارئ", "مشروع")
    for c in ["القيمة المنفذة", "نصيب الرواتب", "المواد التشغيلية"]:
        if c not in W.columns:
            W[c] = 0.0
        W[c] = pd.to_numeric(W[c], errors="coerce").fillna(0.0)
    W["إجمالي التكلفة"] = W["نصيب الرواتب"] + W["المواد التشغيلية"]
    W["الهامش"] = W["القيمة المنفذة"] - W["إجمالي التكلفة"]
    W["نسبة التكلفة"] = (W["إجمالي التكلفة"] / W["القيمة المنفذة"].replace(0, np.nan)).round(2)
    g = W.groupby("النوع").agg(عدد=("أمر العمل", "size"), منفذ=("القيمة المنفذة", "sum"),
                               مواد=("المواد التشغيلية", "sum"), رواتب=("نصيب الرواتب", "sum"),
                               تكلفة=("إجمالي التكلفة", "sum"), هامش=("الهامش", "sum"))
    rows = [("item", k, [str(int(r.عدد)), _fmt(r.منفذ), _fmt(r.مواد), _fmt(r.رواتب), _fmt(r.تكلفة), _fmt(r.هامش)]) for k, r in g.iterrows()]
    rows.append(("total", "الإجمالي", [str(int(g.عدد.sum())), _fmt(g.منفذ.sum()), _fmt(g.مواد.sum()),
                                       _fmt(g.رواتب.sum()), _fmt(g.تكلفة.sum()), _fmt(g.هامش.sum())]))
    st.table(build(rows, ["النوع", "عدد الأوامر", "القيمة المنفذة", "المواد التشغيلية", "نصيب الرواتب", "إجمالي التكلفة", "الهامش"]))
    _note("توزيع الرواتب على أوامر العمل بنسبة قيمة البونص المنفذة في كل شهر. مواد العهدة من الكهرباء لا تدخل التكلفة، "
          "وحركتها معروضة في قسم «انحرافات المواد».")
    if len(prev):
        n_auto = int((prev["المصدر"] == "مطابقة الاسم آلياً").sum())
        n_no = int((prev["المصدر"] == "بلا سعر").sum())
        if n_no:
            _note(f"{n_no} صنفاً تشغيلياً بلا سعر في تقرير أسعار الأصناف، فتكلفته صفر. راجع جدول التسعير أدناه.")
        with st.expander(f"تسعير المواد التشغيلية ({n_auto} صنفاً سُعِّر بمطابقة الاسم آلياً)"):
            _grid(prev.sort_values("درجة التطابق"), "prc", 330, pin="صنف المستودع", key_font=1.15)
    # العرض: الموقع مختار من أعلى التبويب، والمكتب هو المستوى الأدنى داخله
    offs = sorted(x for x in W.get("المكتب", pd.Series(dtype=object)).dropna().unique() if str(x).strip())
    if offs:
        pick = st.selectbox("العرض داخل الموقع", ["كل المكاتب"] + offs, key="sv_woc_off")
        if pick != "كل المكاتب":
            W = W[W["المكتب"] == pick]
        o = W.groupby("المكتب").agg(عدد=("أمر العمل", "size"), منفذ=("القيمة المنفذة", "sum"),
                                    تكلفة=("إجمالي التكلفة", "sum"), هامش=("الهامش", "sum"))
        if len(o) > 1:
            rows = [("item", k, [str(int(r.عدد)), _fmt(r.منفذ), _fmt(r.تكلفة), _fmt(r.هامش)]) for k, r in o.iterrows()]
            rows.append(("total", "الإجمالي", [str(int(o.عدد.sum())), _fmt(o.منفذ.sum()), _fmt(o.تكلفة.sum()), _fmt(o.هامش.sum())]))
            st.table(build(rows, ["المكتب", "عدد الأوامر", "القيمة المنفذة", "إجمالي التكلفة", "الهامش"]))
    cols = ["أمر العمل", "القيمة التقديرية", "القيمة المنفذة", "مبلغ شهادة الإنجاز", "النوع", "موقف أمر العمل",
            "نوع امر العمل", "أشهر التنفيذ", "المواد التشغيلية", "نصيب الرواتب", "إجمالي التكلفة",
            "الهامش", "نسبة التكلفة"]
    X = W[[c for c in cols if c in W.columns]].sort_values("القيمة المنفذة", ascending=False)
    _grid(X, "woc", 430, pin="أمر العمل")
    _note("القيمة التقديرية هي تقدير الكهرباء لأمر العمل عند إصداره، والقيمة المنفذة محسوبة من بونص التنفيذ "
          "بأسعار العقد، ومبلغ شهادة الإنجاز هو المعتمد نهائياً بعد التنفيذ.")
    st.download_button("⬇️ تنزيل تكلفة أوامر العمل (CSV)", X.to_csv(index=False).encode("utf-8-sig"),
                       f"wo_cost_{site}.csv", "text/csv", key="sv_dl_woc")


def _productivity(prd, bon, mov, pay, ipr, cpr, mp, cfg, site, build):
    _title("إنتاجية الموقع مقابل التكلفة")
    P = prd[prd["الموقع"] == site] if len(prd) else pd.DataFrame()
    yr = int(cfg.get("year", 2026))
    B = bonus_value(bon, cpr, cfg, site)
    bm = B.groupby("الشهر")["القيمة"].sum() if len(B) else pd.Series(dtype=float)
    S = pay[(pay["السنة"] == yr)] if len(pay) else pd.DataFrame()
    if len(S):
        S = S[S["الموقع"].astype(str).str.contains(site, na=False)]
        sm = S.groupby("رقم الشهر").agg(n=("عدد العاملين", "sum"), c=("التكلفة الكاملة", "sum"))
    else:
        sm = pd.DataFrame()
    prices = item_price_map(mov, ipr, mp, site)
    if len(mov):
        M = mov[(mov["الموقع"] == site) & (mov["السنة"] == yr) & (mov["التصنيف"].astype(str).str.startswith("مواد تشغيلية"))].copy()
        M["سعر"] = M["كود الصنف"].astype(str).map(prices)
        if M["سعر"].isna().all():
            M["سعر"] = M["الصنف"].map(prices)
        sign = np.where(M["نوع المعاملة"] == ISSUE, 1.0, np.where(M["نوع المعاملة"] == RET, -1.0, 0.0))
        M["التكلفة"] = M["الكمية"] * M["سعر"].fillna(0.0) * sign
        om = M.groupby("الشهر")["التكلفة"].sum()
    else:
        om = pd.Series(dtype=float)
    if not len(P) and not len(B):
        _onboard("إنتاجية الموقع تحتاج: تقرير إنتاجية الموقع + تقارير البونص + الرواتب.")
        return
    pc1, pc2, pc3 = st.columns([1, 1, 3])
    m1 = int(pc1.number_input("من الشهر", 1, 12, int(cfg.get("m_from", 1)), key="sv_pm1"))
    m2 = int(pc2.number_input("إلى الشهر", 1, 12, int(cfg.get("m_to", 12)), key="sv_pm2"))
    if m2 < m1:
        m1, m2 = m2, m1
    pc3.caption("الأشهر بلا بيانات تظهر بشرطة حتى تُرفع تقاريرها.")
    c_team = next((c for c in P.columns if "تنفيذ فرق الشركة" in c and "اسناد" in c), None) if len(P) else None
    c_sub = next((c for c in P.columns if "الباطن" in c), None) if len(P) else None
    c_tot = next((c for c in P.columns if "أجمالي التنفيذ" in c or "إجمالي التنفيذ" in c), None) if len(P) else None
    rows = []
    T = {"team": 0.0, "sub": 0.0, "tot": 0.0, "bon": 0.0, "sal": 0.0, "ops": 0.0}
    for m in range(m1, m2 + 1):
        pr = P[P["الشهر"] == m] if len(P) else pd.DataFrame()
        team = float(pr[c_team].iloc[0]) if (len(pr) and c_team and pd.notna(pr[c_team].iloc[0])) else np.nan
        sub = float(pr[c_sub].iloc[0]) if (len(pr) and c_sub and pd.notna(pr[c_sub].iloc[0])) else np.nan
        tot = float(pr[c_tot].iloc[0]) if (len(pr) and c_tot and pd.notna(pr[c_tot].iloc[0])) else np.nan
        bq = float(bm.get(m, np.nan))
        sal = float(sm.c.get(m, np.nan)) if len(sm) else np.nan
        ops = float(om.get(m, np.nan))
        cost = np.nansum([sal, ops]) if (pd.notna(sal) or pd.notna(ops)) else np.nan
        marg = team - cost if (pd.notna(team) and pd.notna(cost)) else np.nan
        rows.append(("item", str(m), [_fmt(team), _fmt(sub), _fmt(tot), _fmt(bq),
                                      _fmt(bq / team if (pd.notna(bq) and team) else None, 2),
                                      _fmt(sal), _fmt(ops), _fmt(cost), _fmt(marg)]))
        for k, v in (("team", team), ("sub", sub), ("tot", tot), ("bon", bq), ("sal", sal), ("ops", ops)):
            if pd.notna(v):
                T[k] += v
    cost_t = T["sal"] + T["ops"]
    rows.append(("total", "الإجمالي", [_fmt(T["team"]), _fmt(T["sub"]), _fmt(T["tot"]), _fmt(T["bon"]),
                                       _fmt(T["bon"] / T["team"] if T["team"] else None, 2), _fmt(T["sal"]),
                                       _fmt(T["ops"]), _fmt(cost_t), _fmt(T["team"] - cost_t)]))
    st.table(build(rows, ["الشهر", "تنفيذ فرق الشركة", "مقاولو الباطن", "إجمالي التنفيذ", "المنفذ بالبونص",
                          "نسبة البونص", "تكلفة الرواتب", "المواد التشغيلية", "إجمالي التكلفة", "هامش فرق الشركة"]))
    if len(B) and "إجمالي التقرير" in B.columns:
        chk = B.groupby("الشهر")["إجمالي التقرير"].first()
        bad = [(int(m), float(chk.get(m, np.nan)), float(bm.get(m, np.nan))) for m in range(m1, m2 + 1)
               if pd.notna(chk.get(m, np.nan)) and abs(float(bm.get(m, 0)) - float(chk.get(m))) > max(1.0, 0.01 * float(chk.get(m)))]
        if bad:
            _note("أشهر لا يطابق فيها المحسوب إجمالي تقرير البونص نفسه: " +
                  "، ".join(f"شهر {m}: التقرير {_fmt(a)} والمحسوب {_fmt(b)}" for m, a, b in bad))
    if T["team"] and T["bon"] and abs(T["bon"] / T["team"] - 1) > 0.02:
        _note(f"فرق بين المنفذ من تقارير البونص وتنفيذ فرق الشركة في تقرير الموقع: {_fmt(T['team'] - T['bon'])} ريال. "
              "راجع أشهر البونص الناقصة أو المنفذ الجزئي للمشاريع الكبيرة.")
    _note("تكلفة مقاولي الباطن غير محمّلة هنا، فهامش فرق الشركة لا يشملها.")
    if len(P):
        with st.expander("تقرير الموقع كما ورد"):
            _grid(P, "prd", 330, pin=P.columns[0] if len(P.columns) else None)


def _matlink_view(X, build):
    """المواد المصروفة في الموقع مقابل جدول الربط ببنود الأعمال (مفتاحه كود الشركة المعدّل)."""
    L = matlink()
    if not len(L):
        _note("ملف جدول الربط (sites_matlink.csv) غير موجود بجانب البرنامج.")
        return
    A = X.groupby(["كود الصنف", "الصنف", "الوحدة", "التصنيف"], as_index=False).agg(
        **{"أوامر": ("أمر العمل", "nunique"), "المقايسة": ("المقايسة", "sum"),
           "صافي الصرف": ("صافي الصرف", "sum"), "الفرق": ("فرق المقايسة", "sum")})
    A["مفتاح"] = _ckey(A["كود الصنف"])
    g = L.groupby("كود المادة").agg(**{"عدد البنود المرتبطة": ("كود بند الأعمال", "nunique"),
                                       "البنود": ("بند الأعمال", lambda s: " | ".join(sorted(set(s))[:4]))})
    A = A.merge(g, left_on="مفتاح", right_index=True, how="left")
    A["عدد البنود المرتبطة"] = A["عدد البنود المرتبطة"].fillna(0).astype(int)
    A["البنود"] = A["البنود"].fillna("—")
    A["حالة الربط"] = np.where(A["عدد البنود المرتبطة"] > 0, "مرتبط ببنود محددة",
                               np.where(A["التصنيف"].astype(str).str.startswith("مواد تشغيلية"),
                                        "مادة تشغيلية (بنود الحفر والأسفلت والبلاط)", "يحتاج تأكيد الربط"))
    s = A.groupby("حالة الربط").agg(أصناف=("الصنف", "size"), صرف=("صافي الصرف", "sum"))
    rows = [("item", k, [str(int(r.أصناف)), _fmt(r.صرف)]) for k, r in s.iterrows()]
    rows.append(("total", "الإجمالي", [str(int(s.أصناف.sum())), _fmt(s.صرف.sum())]))
    st.table(build(rows, ["حالة الربط", "عدد الأصناف", "صافي الصرف"]))
    _note("جدول الربط مبني على الأسماء: اسم المادة بتكويد الشركة مقابل اسم بند الأعمال، ومفتاحه كود المادة. "
          "الأصناف التي تحتاج تأكيداً لم يُعثر لها على بند في ملفي الربط، وغالبها محولات ومفاتيح ولوحات "
          "تُصرف بتصميم المشروع لا ببند تجميعي.")
    V = A.drop(columns=["مفتاح"]).sort_values(["حالة الربط", "صافي الصرف"], ascending=[True, False])
    _grid(V, "mlk", 430, pin="الصنف", key_font=1.15)
    st.download_button("⬇️ تنزيل حالة ربط المواد بالبنود (CSV)", V.to_csv(index=False).encode("utf-8-sig"),
                       "material_item_link.csv", "text/csv", key="sv_dl_lnk")
    with st.expander("جدول الربط المعياري كاملاً (المعامل لكل وحدة بند)"):
        _grid(L, "mlk2", 380, pin="اسم المادة", key_font=1.15)


def _materials(sett, mov, site, build):
    _title("انحرافات المواد")
    S = sett[sett["الموقع"] == site] if len(sett) else pd.DataFrame()
    if not len(S):
        _onboard("انحرافات المواد تحتاج: تقرير تصفية أوامر العمل للموقع.")
        return
    c1, c2 = st.columns(2)
    kind = c1.radio("التصنيف", ["الكل", "مواد العهدة", "المواد التشغيلية"], horizontal=True, key="sv_mk")
    lvl = c2.radio("العرض", ["حسب الصنف", "حسب أمر العمل", "الربط ببنود الأعمال"], horizontal=True, key="sv_ml")
    X = S.copy()
    cls = mov.drop_duplicates("الصنف").set_index("الصنف")["التصنيف"].to_dict() if len(mov) else {}
    X["التصنيف"] = X["الصنف"].map(cls)
    cm = class_map()
    if cm:
        ov = _ckey(X["كود الصنف"]).map(cm)
        X["التصنيف"] = ov.where(ov.notna() & (ov != ""), X["التصنيف"])
        X["مصدر التصنيف"] = np.where(ov.notna() & (ov != ""), "التصنيف المعتمد",
                                     np.where(X["التصنيف"].notna(), "جدول التصنيف", "مستنتج"))
    else:
        X["مصدر التصنيف"] = np.where(X["التصنيف"].notna(), "جدول التصنيف", "مستنتج")
    # ما لم يرد في جدول التصنيف يُستنتج من نمط الكود: مواد الكهرباء تحمل كود 40…U
    sec = _ckey(X["كود الصنف"]).str.fullmatch(r"40\d{7}U").fillna(False)
    X["التصنيف"] = X["التصنيف"].fillna(pd.Series(np.where(sec, "مواد عهدة من الكهرباء",
                                                          "مواد تشغيلية توفرها الشركة"), index=X.index))
    if kind == "مواد العهدة":
        X = X[X["التصنيف"].astype(str).str.startswith("مواد عهدة")]
    elif kind == "المواد التشغيلية":
        X = X[X["التصنيف"].astype(str).str.startswith("مواد تشغيلية")]
    X["الحالة"] = np.where(X["فرق المقايسة"] > 0, "صرف زائد عن المقايسة",
                           np.where(X["فرق المقايسة"] < 0, "صرف أقل من المقايسة", "مطابق"))
    g = X.groupby("الحالة").agg(سطور=("أمر العمل", "size"), أوامر=("أمر العمل", "nunique"), فرق=("فرق المقايسة", "sum"))
    rows = [("item", k, [str(int(r.سطور)), str(int(r.أوامر)), _fmt(r.فرق)]) for k, r in g.iterrows()]
    rows.append(("total", "الإجمالي", [str(int(g.سطور.sum())), str(int(X["أمر العمل"].nunique())), _fmt(g.فرق.sum())]))
    st.table(build(rows, ["الحالة", "عدد السطور", "عدد الأوامر", "صافي الفرق"]))
    if lvl == "الربط ببنود الأعمال":
        _matlink_view(X, build)
        return
    if lvl == "حسب الصنف":
        V = X.groupby(["الصنف", "الوحدة", "التصنيف"], as_index=False).agg(
            **{"أوامر": ("أمر العمل", "nunique"), "المقايسة": ("المقايسة", "sum"), "صافي الصرف": ("صافي الصرف", "sum"),
               "الفرق": ("فرق المقايسة", "sum"), "متبقي الصرف": ("متبقي صرف", "sum")}).sort_values("الفرق")
    else:
        V = X[X["فرق المقايسة"] != 0][["أمر العمل", "الصنف", "الوحدة", "التصنيف", "المقايسة", "المندوب", "الصرف",
                                       "الارجاع", "صافي الصرف", "فرق المقايسة", "متبقي صرف", "الحالة"]].sort_values("فرق المقايسة")
    _grid(V, "mat", 430, pin="الصنف", key_font=1.15)
    st.markdown(
        '<div class="sv-note"><b>معنى الأعمدة:</b> '
        '<b>المقايسة</b> هي الكمية المعتمدة للأمر في تصميم الكهرباء، وهي السقف المسموح صرفه. '
        '<b>صافي الصرف</b> = المصروف فعلاً من المستودع ناقص المرتجع، أي ما استُهلك بالفعل. '
        '<b>متبقي الصرف</b> = المقايسة ناقص ما صُرف، أي الكمية التي ما زال من حق الأمر صرفها. '
        '<b>الفرق</b> = صافي الصرف ناقص المقايسة: موجبه صرف زائد عن المعتمد ويُحاسب عليه المقاول أو يحتاج أمر تعديل، '
        'وسالبه صرف أقل من المعتمد فإما أن التنفيذ لم يكتمل أو أن المقايسة أعلى من الواقع.</div>',
        unsafe_allow_html=True)
    st.download_button("⬇️ تنزيل انحرافات المواد (CSV)", V.to_csv(index=False).encode("utf-8-sig"),
                       f"materials_dev_{site}.csv", "text/csv", key="sv_dl_mat")
    # أصناف لم ترد في جدول تصنيف المواد، تُصدَّر ليُعتمد تصنيفها
    if "مصدر التصنيف" in X.columns:
        U = X[X["مصدر التصنيف"] == "مستنتج"].groupby(["كود الصنف", "الصنف", "الوحدة"], as_index=False).agg(
            **{"التصنيف المقترح": ("التصنيف", "first"), "صافي الصرف": ("صافي الصرف", "sum")})
        if len(U):
            U["التصنيف المعتمد"] = ""
            _note(f"{len(U)} صنفاً لم يرد في جدول تصنيف المواد المرفق بحركة الأصناف، وصُنِّف استنتاجاً من نمط الكود.")
            st.download_button("⬇️ تنزيل الأصناف غير المصنفة لاعتماد تصنيفها (CSV)",
                               U.to_csv(index=False).encode("utf-8-sig"),
                               f"unclassified_items_{site}.csv", "text/csv", key="sv_dl_unc")


def _wo_base(wo, mov, bon, site, build):
    _title("قاعدة أوامر العمل (حالة الكهرباء)")
    if not len(wo):
        _onboard("قاعدة أوامر العمل تحتاج: ملفات موقف أوامر العمل من الكهرباء (ملف لكل منطقة).")
        return
    scope = st.radio("العرض", ["كل العقود", "الموقع المختار"], horizontal=True, key="sv_wsc")
    W = wo if scope == "كل العقود" else wo[wo["الموقع"] == site]
    if not len(W):
        _note("لا توجد أوامر عمل لهذا الموقع في الملفات المرفوعة.")
        return
    if "القيمة التقديرية" not in W.columns and "تكلفة العمالة" in W.columns:
        W = W.rename(columns={"تكلفة العمالة": "القيمة التقديرية"})
    for c in ("القيمة التقديرية", "مبلغ شهادة الإنجاز"):
        if c not in W.columns:
            W[c] = np.nan
    g = W.groupby(["جيل العقد", "الموقع"], as_index=False).agg(
        **{"عدد الأوامر": ("رقم أمر العمل", "size"), "القيمة التقديرية": ("القيمة التقديرية", "sum"),
           "القيمة النهائية": ("مبلغ شهادة الإنجاز", "sum")})
    g["فرق التنفيذ عن التقدير"] = g["القيمة النهائية"] - g["القيمة التقديرية"]
    s = W.groupby("موقف أمر العمل").agg(**{"عدد": ("رقم أمر العمل", "size"),
                                           "تقديرية": ("القيمة التقديرية", "sum"),
                                           "نهائية": ("مبلغ شهادة الإنجاز", "sum")}).sort_values("عدد", ascending=False)
    rows = [("item", k, [str(int(r.عدد)), _fmt(r.تقديرية), _fmt(r.نهائية)]) for k, r in s.iterrows()]
    rows.append(("total", "الإجمالي", [str(int(s.عدد.sum())), _fmt(s.تقديرية.sum()), _fmt(s.نهائية.sum())]))
    st.table(build(rows, ["موقف أمر العمل", "عدد الأوامر", "القيمة التقديرية", "القيمة النهائية"]))
    _note("القيمة التقديرية هي تقدير الكهرباء عند إصدار الأمر، والقيمة النهائية هي مبلغ شهادة الإنجاز بعد التنفيذ. "
          "الأوامر التي لم تصدر لها شهادة إنجاز بعد تظهر بقيمة نهائية صفر.")
    _grid(g.sort_values(["جيل العقد", "القيمة التقديرية"], ascending=[True, False]), "wos", 330, pin="الموقع")
    # أوامر في المستودع ولا توجد لدى الكهرباء
    if len(mov):
        M = mov[mov["الموقع"] == site]
        miss = sorted(set(M["أمر العمل"]) - set(wo["رقم أمر العمل"]))
        em = [w for w in miss if str(w).startswith("42")]
        pr = [w for w in miss if not str(w).startswith("42")]
        c1, c2 = st.columns(2)
        c1.caption(f"أوامر طوارئ في المستودع خارج تقرير الكهرباء: {len(em):,} (التقرير لا يشمل الطوارئ)")
        c2.caption(f"أوامر مشاريع في المستودع ولا توجد في تقرير الكهرباء: {len(pr):,}")
        if pr:
            _grid(pd.DataFrame({"أمر العمل": pr}), "miss", 220, rev=False)
    with st.expander("تفاصيل أوامر العمل"):
        _grid(W, "wod", 400, pin="رقم أمر العمل")


def _data_tab(unlocked, cfg):
    _title("رفع البيانات والإعدادات")
    if not unlocked:
        _note("أدخل كلمة مرور الرفع في الشريط الجانبي لتفعيل الرفع.")
    c1, c2, c3 = st.columns(3)
    site = c1.selectbox("الموقع الذي تخصه الملفات المرفوعة", SITES, index=SITES.index(cfg.get("site", "الرياض")), key="sv_site_up")
    yr = c2.number_input("سنة التحليل", 2021, 2035, int(cfg.get("year", 2026)), key="sv_year")
    c3.number_input("معامل الرد (م3)", 1.0, 100.0, float(cfg.get("rd_factor", 18.0)), key="sv_rd")
    m1, m2 = st.columns(2)
    f1 = m1.number_input("من الشهر", 1, 12, int(cfg.get("m_from", 1)), key="sv_mf")
    f2 = m2.number_input("إلى الشهر", 1, 12, int(cfg.get("m_to", 12)), key="sv_mt")
    if st.button("💾 حفظ الإعدادات", key="sv_cfg_save"):
        cfg.update({"site": site, "year": int(yr), "rd_factor": float(st.session_state["sv_rd"]),
                    "m_from": int(f1), "m_to": int(f2)})
        _save_cfg(cfg)
        st.success("تم الحفظ.")
    ups = st.file_uploader("ارفع ملفات الموقع (بونص شهري، حركة الأصناف، تصفية أوامر العمل، موقف أوامر العمل، إنتاجية الموقع، الرواتب، أسعار الأصناف، أسعار بنود العقد)",
                           type=["xlsx", "xls"], accept_multiple_files=True, key="sv_up", disabled=not unlocked)
    if ups and unlocked and st.button("⬆️ معالجة الملفات المرفوعة", key="sv_do"):
        log = []
        bons, nots = [], []
        for f in ups:
            raw = f.read()
            kind = detect(raw, f.name)
            try:
                if kind == "بونص":
                    b, n = parse_bonus(raw, site, f.name)
                    bons.append(b)
                    nots.append(n)
                    log.append(f"✅ {f.name}: تقرير بونص — {len(b):,} سطر بند، {b['أمر العمل'].nunique()} أمر عمل، {len(n)} ملاحظة.")
                elif kind == "حركة الأصناف":
                    g = parse_moves(raw, site)
                    old = st.session_state["sv_mov"]
                    old = old[old["الموقع"] != site] if len(old) else pd.DataFrame()
                    out = pd.concat([old, g], ignore_index=True)
                    st.session_state["sv_mov"] = out
                    _save(out, F_MOV)
                    dup = int((g["أقصى تكرار"] > 1).sum())
                    log.append(f"✅ {f.name}: حركة الأصناف — {len(g):,} سطر مجمّع، صُحّح تكرار التصدير في {dup:,} سطر.")
                elif kind == "تصفية":
                    s = parse_settle(raw, site)
                    old = st.session_state["sv_set"]
                    old = old[old["الموقع"] != site] if len(old) else pd.DataFrame()
                    out = pd.concat([old, s], ignore_index=True)
                    st.session_state["sv_set"] = out
                    _save(out, F_SET)
                    log.append(f"✅ {f.name}: تصفية أوامر العمل — {len(s):,} سطر، {s['أمر العمل'].nunique():,} أمر عمل.")
                elif kind == "أوامر العمل":
                    w = parse_wo(raw)
                    old = st.session_state["sv_wo"]
                    if len(old):
                        old = old[~old["رقم أمر العمل"].isin(set(w["رقم أمر العمل"]))]
                    out = pd.concat([old, w], ignore_index=True) if len(old) else w
                    st.session_state["sv_wo"] = out
                    _save(out, F_WO)
                    log.append(f"✅ {f.name}: موقف أوامر العمل — {len(w):,} أمر عمل.")
                elif kind == "إنتاجية":
                    p = parse_prod(raw, site)
                    old = st.session_state["sv_prd"]
                    old = old[old["الموقع"] != site] if len(old) else pd.DataFrame()
                    out = pd.concat([old, p], ignore_index=True)
                    st.session_state["sv_prd"] = out
                    _save(out, F_PRD)
                    log.append(f"✅ {f.name}: إنتاجية الموقع — {len(p)} شهر.")
                elif kind == "رواتب":
                    p = parse_pay(raw)
                    st.session_state["sv_pay"] = p
                    _save(p, F_PAY)
                    log.append(f"✅ {f.name}: الرواتب — {len(p):,} سطر موقع/شهر.")
                elif kind == "أسعار الأصناف":
                    p = parse_item_prices(raw)
                    p["الموقع"] = site
                    old = st.session_state["sv_ipr"]
                    if len(old) and "الموقع" in old.columns:
                        old = old[old["الموقع"] != site]
                    elif len(old):
                        old = old.assign(**{"الموقع": ""})
                    out = pd.concat([old, p], ignore_index=True) if len(old) else p
                    st.session_state["sv_ipr"] = out
                    _save(out, F_IPR)
                    log.append(f"✅ {f.name}: أسعار الأصناف لموقع {site} — {len(p)} صنف.")
                elif kind == "تصنيف الأصناف":
                    p = parse_item_class(raw)
                    _save(p, F_CLS)
                    class_map.clear() if hasattr(class_map, "clear") else None
                    log.append(f"✅ {f.name}: تصنيف الأصناف المعتمد — {len(p):,} صنف.")
                elif kind == "أسعار العقد":
                    p = parse_contract_prices(raw)
                    st.session_state["sv_cpr"] = p
                    _save(p, F_CPR)
                    log.append(f"✅ {f.name}: أسعار بنود العقد — {len(p)} بند.")
                else:
                    log.append(f"⚠️ {f.name}: لم يتم التعرف على نوع الملف.")
            except Exception as e:
                log.append(f"❌ {f.name}: خطأ في القراءة — {e}")
        if bons:
            b = pd.concat(bons, ignore_index=True)
            old = st.session_state["sv_bon"]
            if len(old):
                old = old[~((old["الموقع"] == site) & (old["الشهر"].isin(set(b["الشهر"]))))]
            out = pd.concat([old, b], ignore_index=True) if len(old) else b
            st.session_state["sv_bon"] = out
            _save(out, F_BON)
            n = pd.concat([x for x in nots if len(x)], ignore_index=True) if any(len(x) for x in nots) else pd.DataFrame()
            if len(n):
                oldn = st.session_state["sv_not"]
                if len(oldn):
                    oldn = oldn[~((oldn["الموقع"] == site) & (oldn["الشهر"].isin(set(n["الشهر"]))))]
                outn = pd.concat([oldn, n], ignore_index=True) if len(oldn) else n
                st.session_state["sv_not"] = outn
                _save(outn, F_NOT)
        for l in log:
            st.write(l)
        st.rerun()
    st.markdown("---")
    _title("البيانات المحمّلة")
    bon, notes, mov, sett, wo, prd, ipr, cpr, pay, mp, _ = _state()
    rows = [
        ("item", "تقارير البونص", [str(len(bon)), ", ".join(str(int(x)) for x in sorted(bon["الشهر"].unique())) if len(bon) else "—"]),
        ("item", "ملاحظات المراجع", [str(len(notes)), "—"]),
        ("item", "حركة الأصناف", [str(len(mov)), ", ".join(sorted(mov["الموقع"].unique())) if len(mov) else "—"]),
        ("item", "تصفية أوامر العمل", [str(len(sett)), ", ".join(sorted(sett["الموقع"].unique())) if len(sett) else "—"]),
        ("item", "موقف أوامر العمل", [str(len(wo)), ", ".join(sorted(wo["الموقع"].dropna().unique())) if len(wo) else "—"]),
        ("item", "إنتاجية الموقع", [str(len(prd)), ", ".join(sorted(prd["الموقع"].unique())) if len(prd) else "—"]),
        ("item", "الرواتب", [str(len(pay)), "—"]),
        ("item", "أسعار الأصناف", [str(len(ipr)), "—"]),
        ("item", "أسعار بنود العقد", [str(len(cpr)), "—"]),
        ("item", "جدول الربط", [str(len(mp)), "—"]),
    ]
    st.table(_build_simple(rows, ["البيان", "عدد السطور", "التغطية"]))
    if len(bon) and (bon["الشهر"] == 0).any():
        _note("ملفات بونص لم يُعرف شهرها من اسم الملف أو من أوراقه. حدّد الشهر لكل ملف ثم احفظ.")
        U = bon[bon["الشهر"] == 0].groupby(["الموقع", "المصدر"], as_index=False).agg(
            **{"عدد الأوامر": ("أمر العمل", "nunique"), "سطور": ("الكمية", "size")})
        U["الشهر"] = 0
        ed = st.data_editor(U[["الشهر", "عدد الأوامر", "سطور", "المصدر", "الموقع"]], hide_index=True,
                            use_container_width=True, key="sv_mon_ed",
                            column_config={"الشهر": st.column_config.NumberColumn(min_value=0, max_value=12, step=1)})
        if st.button("💾 حفظ أشهر الملفات", key="sv_mon_save"):
            for _, r in ed.iterrows():
                m = int(r["الشهر"] or 0)
                if not m:
                    continue
                for k, path in (("sv_bon", F_BON), ("sv_not", F_NOT)):
                    d = st.session_state[k]
                    if len(d) and "المصدر" in d.columns:
                        d.loc[(d["المصدر"] == r["المصدر"]) & (d["الموقع"] == r["الموقع"]), "الشهر"] = m
                        st.session_state[k] = d
                        _save(d, path)
            st.success("تم التحديث.")
            st.rerun()
    with st.expander("🗑️ حذف بيانات موقع"):
        s2 = st.selectbox("الموقع", SITES, key="sv_del_site")
        if st.button("حذف بيانات هذا الموقع", key="sv_del") and unlocked:
            for k, path, col in (("sv_bon", F_BON, "الموقع"), ("sv_not", F_NOT, "الموقع"), ("sv_mov", F_MOV, "الموقع"),
                                 ("sv_set", F_SET, "الموقع"), ("sv_prd", F_PRD, "الموقع"), ("sv_map", F_MAP, "الموقع")):
                d = st.session_state[k]
                if len(d) and col in d.columns:
                    d = d[d[col] != s2]
                    st.session_state[k] = d
                    _save(d, path)
            st.success("تم الحذف.")
            st.rerun()


def _build_simple(rows, cols):
    return pd.DataFrame([[r[1]] + list(r[2]) for r in rows], columns=cols)


# ---------------- الواجهة ----------------
def render_sites(ctx, build_styled_table):
    st.markdown(CSS, unsafe_allow_html=True)
    ut.css()
    unlocked = bool(ctx.get("UP_UNLOCKED", False))
    bon, notes, mov, sett, wo, prd, ipr, cpr, pay, mp, cfg = _state()
    lock = str(ctx.get("SHARE_SITE", "") or "").strip()
    st.subheader("📍 تقارير المواقع" + (f" — {lock}" if lock else ""))
    head = st.container()
    names = ["🧾 مراجعة البونص", "💰 تكلفة أوامر العمل", "📈 إنتاجية الموقع",
             "📦 انحرافات المواد", "🗂️ قاعدة أوامر العمل"]
    if not lock:
        names.append("⚙️ البيانات والإعدادات")
    tabs = st.tabs(names)
    t_bon, t_cost, t_prod, t_mat, t_wo = tabs[:5]
    t_set = tabs[5] if len(tabs) > 5 else None
    if t_set is not None:
        with t_set:
            _data_tab(unlocked, cfg)
    bon, notes, mov, sett, wo, prd, ipr, cpr, pay, mp, cfg = _state()
    if lock:
        # جلسة مشاركة مقيّدة بموقع: تُرشَّح كل البيانات قبل العرض فلا يظهر غيره
        def _only(D):
            return D[D["الموقع"] == lock] if (len(D) and "الموقع" in D.columns) else D
        bon, notes, mov, sett, wo, prd, pay = (_only(x) for x in (bon, notes, mov, sett, wo, prd, pay))
    have = sorted(set(bon["الموقع"].unique()) | set(mov["الموقع"].unique() if len(mov) else []) |
                  set(sett["الموقع"].unique() if len(sett) else []))
    with head:
        if lock:
            site = lock
            if have and lock not in have:
                st.warning(f"لا توجد بيانات محمّلة لموقع {lock} بعد.")
        elif have:
            site = st.selectbox("📍 الموقع", have, index=have.index(cfg["site"]) if cfg.get("site") in have else 0, key="sv_site")
        else:
            site = cfg.get("site", "الرياض")
            st.warning("لا توجد بيانات محمّلة لأي موقع بعد، لذلك تظهر الأقسام فارغة. التفاصيل في كل قسم وفي تبويب «⚙️ البيانات والإعدادات».")
    with t_bon:
        _bonus_review(bon, notes, mov, sett, cpr, mp, cfg, site, build_styled_table)
    with t_cost:
        _wo_cost(bon, mov, sett, wo, pay, ipr, cpr, mp, cfg, site, build_styled_table)
    with t_prod:
        _productivity(prd, bon, mov, pay, ipr, cpr, mp, cfg, site, build_styled_table)
    with t_mat:
        _materials(sett, mov, site, build_styled_table)
    with t_wo:
        _wo_base(wo, mov, bon, site, build_styled_table)
