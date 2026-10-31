import streamlit as st

# استيراد ملفات المنصة المساندة مع رسالة واضحة إن كان أحدها قديماً أو غير مرفوع
try:
    import contracts_view as cv
    from tab8_dicts import (SITES_DETAILED_DB, ASSETS_BY_SITE_DB, PAYROLL_BY_SITE_26,
                            MAKKAH_OPS_DB, ASSIGN_2026_BY_SITE)
except ImportError as _imp_err:
    st.error("⚠️ ملف مساند قديم أو غير مرفوع. ارفع النسخ الحديثة من الملفات الثلاثة معاً في نفس المجلد: "
             "APP.py و contracts_view.py و tab8_dicts.py ثم أعد تشغيل التطبيق (Reboot app). "
             f"تفاصيل: {_imp_err}")
    st.stop()
import pandas as pd
import numpy as np
import plotly.express as px
import io
import importlib
import exec_summary, zakat_calc, banks
importlib.reload(exec_summary)
importlib.reload(zakat_calc)
importlib.reload(banks)

# إعدادات الصفحة الرئيسية
st.set_page_config(
    page_title="منصة التقارير المالية - شركة دلتا السعودية",
    page_icon="📊",
    layout="wide"
)

# تنسيق CSS شامل لفرض الاتجاه من اليمين إلى اليسار (RTL) وضبط محاذاة القوائم والنصوص من اليمين
st.markdown("""
<style>
    .stApp, .main, [data-testid="stSidebar"], [data-testid="stAppViewContainer"], .element-container, p, span, div, li, ul, ol {
        direction: rtl !important;
        text-align: right !important;
    }
    ul, ol {
        text-align: right !important;
        padding-right: 20px !important;
        padding-left: 0px !important;
    }
    li {
        text-align: right !important;
    }
    /* شريط التبويبات: تمرير أفقي ظاهر عند كثرة التبويبات */
    div[data-baseweb="tab-list"] {
        direction: rtl !important;
        justify-content: flex-start !important;
        flex-wrap: nowrap !important;
        overflow-x: auto !important;
        overflow-y: hidden !important;
        padding-bottom: 8px !important;
        scrollbar-width: thin;
        scrollbar-color: #1E3A8A #E5E7EB;
    }
    div[data-baseweb="tab-list"] button[role="tab"] {
        flex: 0 0 auto !important;
        white-space: nowrap !important;
    }
    div[data-baseweb="tab-list"]::-webkit-scrollbar {
        height: 8px;
    }
    div[data-baseweb="tab-list"]::-webkit-scrollbar-track {
        background: #E5E7EB;
        border-radius: 4px;
    }
    div[data-baseweb="tab-list"]::-webkit-scrollbar-thumb {
        background: #1E3A8A;
        border-radius: 4px;
    }
    /* الرسوم البيانية: اتجاه LTR داخل الرسم حتى لا تُقص وسيلة الإيضاح، والنص العربي يظهر صحيحاً */
    .js-plotly-plot, .js-plotly-plot div, .js-plotly-plot span, .js-plotly-plot text {
        direction: ltr !important;
        text-align: left !important;
    }
    div[data-testid="stHorizontalBlock"] {
        direction: rtl !important;
    }
    div[data-testid="stMetricValue"] {
        font-size: 1.6rem;
        font-weight: bold;
        color: #1E3A8A;
        text-align: right !important;
        direction: rtl !important;
    }
    div[data-testid="stMetricLabel"], div[data-testid="stMetricLabel"] * {
        font-size: 1.1rem !important;
        line-height: 1.4 !important;
        white-space: normal !important;
    }
    div[data-testid="stMetricDelta"], div[data-testid="stMetricDelta"] * {
        font-size: 1.0rem !important;
        white-space: normal !important;
    }
    div[data-testid="stMetricLabel"], div[data-testid="stMetricDelta"] {
        font-size: 1.0rem;
        font-weight: 600;
        text-align: right !important;
        direction: rtl !important;
    }
    [data-testid="stTable"], table {
        direction: rtl !important;
        width: 100% !important;
        border-collapse: collapse !important;
    }
    thead, tbody, tr {
        direction: rtl !important;
    }
    th {
        text-align: center !important;
        vertical-align: middle !important;
        direction: rtl !important;
        background-color: #1E3A8A !important;
        color: white !important;
        font-size: 1.08rem !important;
        white-space: pre-line !important;
        padding: 12px 12px !important;
        font-family: 'Segoe UI', Tahoma, sans-serif !important;
    }
    td {
        text-align: center !important;
        vertical-align: middle !important;
        direction: rtl !important;
        font-size: 1.1rem !important;
        padding: 10px 12px !important;
        font-family: 'Segoe UI', Tahoma, sans-serif !important;
    }
    td:first-child, th:first-child {
        text-align: right !important;
    }
    .stSelectbox, .stRadio, .stMultiSelect, .stNumberInput, .stFileUploader, .stMarkdown {
        direction: rtl !important;
        text-align: right !important;
    }
</style>
""", unsafe_allow_html=True)

st.title("📊 منصة التقارير المالية والإدارية التنفيذية")
st.markdown("### شركة دلتا السعودية لمشاريع الطاقة المحدودة | القوائم المالية الكاملة وموقف العقد الموحد (2021 – 2026)")
st.markdown("---")

# ==========================================
# الهيكل التنظيمي المعتمد للعقود والمناطق والمواقع الـ 22
# ==========================================
CONTRACTS_HIERARCHY = {
    "العقد الموحد بتبوك": ["تبوك", "ضباء", "الوجه", "حقل", "املج", "صيانة تبوك", "قراء عدادات تبوك"],
    "العقد الموحد بالباحة": ["الباحة", "المخواة", "القنفذة", "صيانة الباحة", "قراء عدادات الباحة"],
    "العقد الموحد عسير": ["ابها", "السراة", "محايل", "المجاردة", "صيانة عسير"],
    "العقد الموحد بمكة المكرمة": ["مكة", "خليص", "صيانة مكة", "قراء عدادات مكة", "مصنع الأعمدة الخرسانية بخليص"],
    "العقد الموحد بالرياض": ["الرياض (إجمالي العقد)"]
}

# ==========================================
# الشريط الجانبي: مركز رفع وتحديث البيانات
# ==========================================
st.sidebar.header("⚙️ مركز رفع وتحديث البيانات")

import hmac, os
def _upload_password():
    try:
        return str(st.secrets["UPLOAD_PASSWORD"]), True
    except Exception:
        pw = os.environ.get("UPLOAD_PASSWORD")
        return (pw, True) if pw else ("Delta@2026", False)

_pw_real, _pw_custom = _upload_password()
_pw_in = st.sidebar.text_input("🔒 كلمة سر مركز التحديث", type="password", key="up_pw")
UP_UNLOCKED = bool(_pw_in) and hmac.compare_digest(_pw_in.encode("utf-8"), _pw_real.encode("utf-8"))
if UP_UNLOCKED:
    st.sidebar.success("🔓 مركز التحديث مفتوح")
else:
    st.sidebar.info("🔒 المركز مقفل: أدخل كلمة السر لرفع أو تعديل البيانات (العرض متاح للجميع).")
if UP_UNLOCKED and not _pw_custom:
    st.sidebar.warning("كلمة السر الافتراضية قيد الاستخدام. عيّن UPLOAD_PASSWORD في إعدادات Secrets لتغييرها.")

uploaded_tb = st.sidebar.file_uploader("1️⃣ رفع ميزان المراجعة العام (Excel/CSV)", type=["xlsx", "csv"], key="tb_up", disabled=not UP_UNLOCKED)
uploaded_proj_pl = st.sidebar.file_uploader("2️⃣ رفع تحديث قوائم دخل المشاريع (Excel)", type=["xlsx"], key="proj_up", disabled=not UP_UNLOCKED)
uploaded_assign = st.sidebar.file_uploader("3️⃣ رفع نموذج الإسناد والتنفيذ الشهري الموحد (Excel/CSV)", type=["xlsx", "csv"], accept_multiple_files=True, key="assign_up", disabled=not UP_UNLOCKED)

st.sidebar.markdown("---")
st.sidebar.header("🎯 إعدادات التنفيذ والإيراد المؤجل (2026)")
deferred_rev_2025 = st.sidebar.number_input(
    "الإيراد المؤجل المرحل من 2025 (ريال)",
    value=14697741.0,
    step=100000.0,
    format="%.0f",
    disabled=not UP_UNLOCKED,
    key="deferred_in"
)

# ==========================================
# دالة تنسيق الجداول المحاسبية الملونة
# ==========================================
def fmt_val(val, r_type='item'):
    if val is None or val == "":
        return ""
    if isinstance(val, str):
        return val
    if r_type == 'pct':
        return f"{val:.2f}%"
    if r_type == 'mult':
        return f"{val:.2f}x"
    if r_type == 'days':
        return f"{int(round(val))} يوم"
    if val < 0:
        return f"({abs(val):,.0f})"
    return f"{val:,.0f}"

def build_styled_table(rows_spec, columns, formula_col=None):
    formatted_rows = []
    row_types = []
    for r_type, label, vals in rows_spec:
        row_types.append(r_type)
        if r_type == 'section':
            formatted_rows.append([label] + [""] * (len(columns) - 1))
        else:
            formatted_rows.append([label] + [fmt_val(v, r_type) for v in vals])
            
    df = pd.DataFrame(formatted_rows, columns=columns)
    
    def apply_row_styles(row):
        rt = row_types[row.name]
        base_rtl = 'direction: rtl; text-align: right; font-size: 1.08rem; '
        if rt == 'section':
            return [base_rtl + 'background-color: #1E3A8A; color: #FFFFFF; font-weight: bold; font-size: 1.02rem;'] * len(row)
        elif rt == 'subtotal':
            return [base_rtl + 'background-color: #DBEAFE; color: #1E3A8A; font-weight: bold; border-top: 1px solid #93C5FD; border-bottom: 1px solid #93C5FD;'] * len(row)
        elif rt in ['pct', 'mult', 'days']:
            return [base_rtl + 'background-color: #F8FAFC; color: #1E293B; font-weight: 600;'] * len(row)
        elif rt == 'total':
            return [base_rtl + 'background-color: #DCFCE7; color: #14532D; font-weight: bold; font-size: 1.04rem; border-top: 2px solid #166534; border-bottom: 2px double #166534;'] * len(row)
        else:
            return [base_rtl + 'background-color: #FFFFFF; color: #111827;'] * len(row)

    def _center(row):
        out = apply_row_styles(row)
        return [out[0]] + [(c.replace('text-align: right;', 'text-align: center; vertical-align: middle;')) for c in out[1:]]

    styler = df.style.apply(_center, axis=1)
    styler = styler.set_table_styles([
        {'selector': 'th', 'props': [('text-align', 'center'), ('vertical-align', 'middle'), ('font-size', '1.05rem'), ('white-space', 'pre-line')]},
        {'selector': 'td', 'props': [('vertical-align', 'middle'), ('padding', '8px 10px')]},
    ])
    if formula_col and formula_col in df.columns:
        def _fx(col):
            return ['direction: rtl; text-align: right; background-color: #EAF1FF; color: #0B2A6F; font-weight: 600; font-size: 0.86rem; border-right: 3px solid #1E3A8A;' if row_types[i] != 'section' else 'direction: rtl; background-color: #1E3A8A; color: #FFFFFF;' for i in range(len(col))]
        styler = styler.apply(_fx, subset=[formula_col], axis=0)
    try:
        styler = styler.hide(axis="index")
    except Exception:
        pass
    return styler

# ==========================================
# قاعدة بيانات قوائم دخل المشاريع (2021 - 2026)
# ==========================================
PROJECTS_DB = {
    "منطقة تبوك": {
        "rev_shamel": [30494576.80, 55590488.50, 58830613.91, 38962744.10, 62071999.83, 32927965.95],
        "team_2026": 39170853.0, "sub_2026": 0.0, "def_2026": 0.0,
        "other_rev": [58075.53, 64998.00, 207098.00, 879.04, 311282.35, 102776.00],
        "salaries": [15343112.19, 23814297.29, 24523939.80, 22906038.29, 24966561.27, 21154079.00],
        "direct_cost": [2354035.82, 14337400.02, 5968127.02, 5166787.56, 5456287.78, 5923938.97],
        "maint_veh": [2251752.29, 3690047.01, 4002719.58, 3738190.89, 4702331.87, 3816279.00],
        "rent_trans": [366832.00, 496068.53, 667832.03, 615626.93, 673046.43, 843738.66],
        "tools_cons": [538571.68, 927028.99, 649801.14, 515007.18, 1046998.22, 571758.00],
        "ga_exp": [270644.47, 348555.22, 280585.62, 264822.41, 366869.49, 326690.00],
        "fin_exp": [24048.34, 91805.25, 20901.00, 20900.00, 15701.77, 455.00],
        "dep_exp": [1797099.96, 2087009.30, 2151915.98, 2413237.06, 3013400.85, 2322376.52]
    },
    "منطقة الباحة": {
        "rev_shamel": [37273063.51, 47362597.64, 73947310.75, 95237586.94, 93985647.97, 64319949.49],
        "team_2026": 48216447.0, "sub_2026": 11108513.0, "def_2026": 0.0,
        "other_rev": [157497.00, 49999.00, 107498.00, -24108.35, 328618.00, 0.00],
        "salaries": [26359725.26, 34689531.70, 37254952.58, 41292294.79, 43852993.52, 33119988.46],
        "direct_cost": [2704085.36, 8454842.50, 19130893.92, 11981235.00, 13306501.24, 12465744.92],
        "maint_veh": [3646026.75, 4011953.99, 5028348.43, 5691705.78, 7270866.61, 4801148.61],
        "rent_trans": [822536.00, 1264147.84, 1182326.73, 1110965.52, 2093741.92, 1521000.00],
        "tools_cons": [720961.83, 1262212.90, 1327664.25, 1163704.89, 1467982.77, 524694.97],
        "ga_exp": [209877.98, 221190.70, 307548.34, 291707.76, 418372.90, 314910.00],
        "fin_exp": [1134.19, 157934.11, 47536.00, 47758.00, 215724.51, 0.00],
        "dep_exp": [1704005.31, 2162227.92, 3203602.81, 4363462.45, 6198856.62, 4668172.25]
    },
    "منطقة عسير": {
        "rev_shamel": [33453858.65, 56568847.84, 65533857.79, 58230974.92, 59188116.81, 19930136.36],
        "team_2026": 34935777.0, "sub_2026": 1131278.0, "def_2026": 0.0,
        "other_rev": [23470.00, 26589.00, 0.00, 0.00, 250780.88, 125998.00],
        "salaries": [9904956.62, 24380617.39, 27796352.54, 27737697.96, 30034753.73, 21024829.00],
        "direct_cost": [10511060.37, 6357213.14, 10148504.50, 9150416.93, 6786415.59, 4985460.00],
        "maint_veh": [3025903.81, 4970575.38, 5479140.87, 5675680.04, 5558807.92, 3845739.54],
        "rent_trans": [720686.09, 1516494.11, 1525491.99, 1535089.49, 1217906.84, 1290763.95],
        "tools_cons": [585691.16, 1007551.53, 1177392.06, 945045.15, 1068449.78, 739203.73],
        "ga_exp": [210044.42, 317214.32, 334565.26, 341773.41, 319980.14, 238951.00],
        "fin_exp": [43.00, 52702.64, 39373.00, 39373.00, 0.00, 389.00],
        "dep_exp": [0.00, 0.00, 1149.02, 3047.43, 6119305.93, 4110846.63]
    },
    "منطقة مكة المكرمة": {
        "rev_shamel": [37721414.63, 60079194.41, 71013929.94, 69395329.72, 64070292.50, 50675386.70],
        "team_2026": 41676603.0, "sub_2026": 12698389.0, "def_2026": 0.0,
        "other_rev": [86298.00, 608448.00, 65147.00, 94083.75, 226932.91, 15000.00],
        "salaries": [19970457.80, 26352076.37, 29919403.60, 36155601.83, 35246122.33, 23158831.97],
        "direct_cost": [4770266.96, 9603292.21, 12235744.74, 8924052.56, 14988709.96, 14106583.67],
        "maint_veh": [3380022.29, 4755034.13, 4770804.29, 5661272.76, 5905254.50, 4216447.54],
        "rent_trans": [386755.57, 521741.07, 608287.60, 613915.31, 670886.69, 861048.71],
        "tools_cons": [473110.86, 599617.40, 596710.70, 776918.33, 763036.49, 609377.77],
        "ga_exp": [316425.22, 436883.16, 287519.93, 390627.17, 435914.05, 214917.47],
        "fin_exp": [3495.02, 84094.27, 32914.00, 32913.00, 6209.84, 204.00],
        "dep_exp": [3238342.91, 2668237.32, 3087755.95, 4560909.89, 4811571.32, 3159510.73]
    },
    "الرياض": {
        "rev_shamel": [22570183.72, 27809189.54, 30535984.00, 23273304.37, 18862668.67, 11893717.47],
        "team_2026": 12000000.0, "sub_2026": 6000000.0, "def_2026": 0.0,
        "other_rev": [0.00, 178149.00, 15999.00, -11433.35, 809781.00, 0.00],
        "salaries": [5541020.12, 7226230.91, 7691894.04, 8066816.43, 9733253.23, 7828750.00],
        "direct_cost": [7010734.40, 8934468.92, 8517518.32, 10978248.47, 7665115.16, 7852975.80],
        "maint_veh": [936842.25, 1117531.74, 1232122.81, 1584657.29, 1673870.70, 1403989.84],
        "rent_trans": [634529.00, 697735.69, 729455.62, 843981.09, 631926.83, 363300.91],
        "tools_cons": [132132.46, 623667.54, 157733.44, 522180.92, 362595.22, 221919.18],
        "ga_exp": [269905.58, 267399.61, 447775.69, 358589.95, 145544.61, 172753.80],
        "fin_exp": [58.60, 26945.52, 25745.00, 25743.00, 0.00, 0.00],
        "dep_exp": [483361.87, 253612.31, 414470.31, 762451.98, 1414103.00, 1188121.73]
    },
    "الادارة (شامل مصنع الأعمدة)": {
        "rev_shamel": [11343.00, 7989.00, -19020039.00, 3699862.92, 635106.00, 14665738.00],
        "team_2026": 0.0, "sub_2026": 0.0, "def_2026": deferred_rev_2025,
        "other_rev": [2311344.63, 400356.59, 1816218.19, 7686617.95, 1667604.00, 780870.00],
        "salaries": [7450916.66, 7373959.37, 13910202.20, 11475820.96, 5505723.37, 5719061.92],
        "direct_cost": [52409.34, 63397.04, 4875.14, 2106126.00, 193541.49, 13758.67],
        "maint_veh": [200821.46, 278430.06, 696668.00, 184574.05, 48391.61, 296241.44],
        "rent_trans": [446643.74, 467074.15, 436453.15, 364321.37, 435779.26, 449459.53],
        "tools_cons": [-3952.06, 15165.87, -12365.56, 45519.30, 3613.15, 35284.36],
        "ga_exp": [1859651.87, 1028880.04, 1425228.94, 1024885.83, 781273.24, 897285.49],
        "fin_exp": [786819.07, 1289904.87, 166732.66, 343450.60, 1906362.40, 1573987.85],
        "dep_exp": [394429.39, 906217.76, 1250637.62, 1586160.84, 3982820.53, 3246937.16]
    }
}

if uploaded_proj_pl is not None:
    try:
        xls_proj = pd.ExcelFile(uploaded_proj_pl)
        for sheet in xls_proj.sheet_names:
            df_sh = pd.read_excel(uploaded_proj_pl, sheet_name=sheet)
            if "Key" in df_sh.columns:
                target_name = sheet.strip()
                if target_name not in PROJECTS_DB:
                    PROJECTS_DB[target_name] = {}
                for _, r in df_sh.iterrows():
                    k = str(r["Key"]).strip()
                    if k in ["team_2026", "sub_2026", "def_2026"]:
                        PROJECTS_DB[target_name][k] = float(r.get("2026", 0.0))
                    elif k in ["rev_shamel", "other_rev", "salaries", "direct_cost", "maint_veh", "rent_trans", "tools_cons", "ga_exp", "fin_exp", "dep_exp"]:
                        PROJECTS_DB[target_name][k] = [float(r.get(str(yr), 0.0)) for yr in [2021, 2022, 2023, 2024, 2025, 2026]]
        st.sidebar.success("✅ تم تحديث قوائم دخل المشاريع بنجاح!")
    except Exception as e:
        st.sidebar.error(f"خطأ في تحديث ملف المشاريع: {e}")

def aggregate_projects(keys_list):
    agg = {k: [0.0]*6 for k in ["rev_shamel", "other_rev", "salaries", "direct_cost", "maint_veh", "rent_trans", "tools_cons", "ga_exp", "fin_exp", "dep_exp"]}
    agg["team_2026"] = sum(PROJECTS_DB[p].get("team_2026", 0.0) for p in keys_list if p in PROJECTS_DB)
    agg["sub_2026"] = sum(PROJECTS_DB[p].get("sub_2026", 0.0) for p in keys_list if p in PROJECTS_DB)
    agg["def_2026"] = sum(PROJECTS_DB[p].get("def_2026", 0.0) for p in keys_list if p in PROJECTS_DB)
    for p in keys_list:
        if p in PROJECTS_DB:
            for k in agg:
                if isinstance(agg[k], list):
                    agg[k] = [agg[k][i] + PROJECTS_DB[p][k][i] for i in range(6)]
    return agg

base_regions = ["منطقة تبوك", "منطقة الباحة", "منطقة عسير", "منطقة مكة المكرمة", "الرياض"]
PROJECTS_DB["إجمالي المشاريع (5 مناطق)"] = aggregate_projects(base_regions)
PROJECTS_DB["إجمالي الشركة (شامل الإيراد المؤجل 2025)"] = aggregate_projects(base_regions + ["الادارة (شامل مصنع الأعمدة)"])

team_exec_total_26 = PROJECTS_DB["إجمالي الشركة (شامل الإيراد المؤجل 2025)"]["team_2026"]
sub_exec_total_26 = PROJECTS_DB["إجمالي الشركة (شامل الإيراد المؤجل 2025)"]["sub_2026"]
actual_revenue_total_26 = team_exec_total_26 + sub_exec_total_26 + deferred_rev_2025

billed_rev_26 = 194444897.0
accrued_rev_26 = actual_revenue_total_26 - billed_rev_26

cogs_24 = [136720115, 23769921, 17230919, 15724423, 3999797, 19372902, 21441044]
cogs_25 = [141071881, 27514807, 17656665, 15947310, 5319803, 24932318, 18902453]
cogs_26 = [107629784, 19154261, 12161073, 22656999, 4897447, 18314321, 14032656]

tot_cogs_24, tot_cogs_25, tot_cogs_26 = sum(cogs_24), sum(cogs_25), sum(cogs_26)
rev_24, rev_25 = 288799803.0, 298813832.0

gp_24, gp_25 = rev_24 - tot_cogs_24, rev_25 - tot_cogs_25
gp_26_b, gp_26_a = billed_rev_26 - tot_cogs_26, actual_revenue_total_26 - tot_cogs_26

ga_24, ga_25, ga_26 = 10514103.0, 10100078.0, 5270057.0
ebit_24, ebit_25 = gp_24 - ga_24, gp_25 - ga_25
ebit_26_b, ebit_26_a = gp_26_b - ga_26, gp_26_a - ga_26

dep_total_24, dep_total_25, dep_total_26 = 20959063.0, 25511647.0, 18740011.0
ebitda_24, ebitda_25 = ebit_24 + dep_total_24, ebit_25 + dep_total_25
ebitda_26_b, ebitda_26_a = ebit_26_b + dep_total_26, ebit_26_a + dep_total_26

fin_24, fin_25, fin_26 = -510137.0, -2143999.0, -1575292.0
gain_ppe_24, gain_ppe_25, gain_ppe_26 = 125419.0, 1256086.0, 3228647.0
reval_24, reval_25, reval_26 = 6287500.0, 1767604.0, 0.0
other_rev_24, other_rev_25, other_rev_26 = 2214720.0, 684782.0, 780870.0

ebt_24 = ebit_24 + fin_24 + gain_ppe_24 + reval_24 + other_rev_24
ebt_25 = ebit_25 + fin_25 + gain_ppe_25 + reval_25 + other_rev_25
ebt_26_b = ebit_26_b + fin_26 + gain_ppe_26 + reval_26 + other_rev_26
ebt_26_a = ebit_26_a + fin_26 + gain_ppe_26 + reval_26 + other_rev_26

zakat_tax_24, zakat_tax_25 = -4133419.0, -3939343.0
# الزكاة وضريبة الدخل المحتسبة من تبويب الحاسبة (تُطبق على 2026 عند تفعيل خيار الاعتماد)
ZK_APPLY = bool(st.session_state.get("zk_apply", False))
ZK_CUR = float(st.session_state.get("zk_cur_2026", 0.0)) if ZK_APPLY else 0.0
ZK_DTA = float(st.session_state.get("zk_dta_adj_2026", 0.0)) if (ZK_APPLY and st.session_state.get("zk_apply_dt", False)) else 0.0
zakat_tax_26 = -(ZK_CUR - ZK_DTA)
net_24, net_25 = ebt_24 + zakat_tax_24, ebt_25 + zakat_tax_25
net_26_b, net_26_a = ebt_26_b + zakat_tax_26, ebt_26_a + zakat_tax_26

tot_ca_26_b = 107025487.0
tot_ca_26_a = tot_ca_26_b + accrued_rev_26
tot_nca_26 = 155181964.0 + ZK_DTA
tot_assets_26_b = tot_nca_26 + tot_ca_26_b
tot_assets_26_a = tot_nca_26 + tot_ca_26_a
tot_eq_26_b = 189212339.0 + zakat_tax_26
tot_eq_26_a = 162616261.0 + 25000000.0 + 8833551.0 + net_26_a
cl_26 = 59000848.0 + ZK_CUR
liab_26 = 72995112.0 + ZK_CUR
dta_26 = 309330.0 + ZK_DTA


# ---- سياق مشترك للملخص التنفيذي وتبويب المؤشرات ----
ex_sum = exec_summary
dso_billed_26 = (53056543.0 / actual_revenue_total_26) * 273.75
dso_total_26 = ((53056543.0 + accrued_rev_26) / actual_revenue_total_26) * 273.75
dio_26 = (1285134.0 / tot_cogs_26) * 273.75
dpo_26 = (1977811.0 / tot_cogs_26) * 273.75
ccc_26 = dso_total_26 + dio_26 - dpo_26
EX_CTX = dict(
    rev_24=rev_24, rev_25=rev_25, rev_26=actual_revenue_total_26,
    tot_cogs_24=tot_cogs_24, tot_cogs_25=tot_cogs_25, tot_cogs_26=tot_cogs_26,
    cogs_24=cogs_24, cogs_25=cogs_25, cogs_26=cogs_26,
    gp_24=gp_24, gp_25=gp_25, gp_26_a=gp_26_a, ga_24=ga_24, ga_25=ga_25, ga_26=ga_26,
    ebit_24=ebit_24, ebit_25=ebit_25, ebit_26_a=ebit_26_a,
    ebitda_24=ebitda_24, ebitda_25=ebitda_25, ebitda_26_a=ebitda_26_a,
    dep_total_24=dep_total_24, dep_total_25=dep_total_25, dep_total_26=dep_total_26,
    ebt_24=ebt_24, ebt_25=ebt_25, ebt_26_a=ebt_26_a, net_24=net_24, net_25=net_25, net_26_a=net_26_a,
    fin_24=fin_24, fin_25=fin_25, fin_26=fin_26,
    tot_ca_26_a=tot_ca_26_a, tot_assets_26_a=tot_assets_26_a, tot_eq_26_a=tot_eq_26_a,
    accrued_rev_26=accrued_rev_26, deferred_rev_2025=deferred_rev_2025,
    team_exec_total_26=team_exec_total_26, sub_exec_total_26=sub_exec_total_26,
    dso_billed_26=dso_billed_26, dso_total_26=dso_total_26, dio_26=dio_26, dpo_26=dpo_26, ccc_26=ccc_26,
    PAYROLL=PAYROLL_BY_SITE_26, ASSIGN=ASSIGN_2026_BY_SITE,
    cl_26=cl_26, liab_26=liab_26, dta_26=dta_26, ZK_CUR=ZK_CUR, ZK_DTA=ZK_DTA,
    zakat_tax_24=zakat_tax_24, zakat_tax_25=zakat_tax_25, zakat_tax_26=zakat_tax_26,
    UP_UNLOCKED=UP_UNLOCKED, bs_cash_26=30649316.0, bs_loans_26=16518837.0, bs_guar_margin_26=9550682.0,
    tb_loans_30_09=16608106.86, bs_def_fin_26=89277.85, tb_guar_margin_30_09=11137440.35,
)

# ==========================================
# تقسيم شاشات المنصة (8 تبويبات متكاملة)
# ==========================================
grp_mgmt, grp_fs, grp_zk, grp_bank, grp_proj = st.tabs([
    "📈 الإدارة والمؤشرات",
    "📑 القوائم المالية",
    "🧮 الزكاة وضريبة الدخل",
    "🏦 البنوك",
    "🏗️ المشاريع والعقود",
])
with grp_mgmt:
    tab1, tab5, tab_chk = st.tabs(["📈 الملخص التنفيذي", "📉 المؤشرات المالية الشاملة (KPIs & DuPont)", "✅ فحوصات سلامة البيانات"])
with grp_fs:
    tab2, tab3, tab4, tab_eq = st.tabs(["📑 قائمة الدخل", "⚖️ المركز المالي", "💵 التدفقات النقدية", "🏛️ التغير في حقوق الملكية"])
with grp_zk:
    tab_zk = st.container()
with grp_bank:
    tab_bank = st.container()
with grp_proj:
    tab8, tab6, tab7, tab9, tab10, tab11, tab12, tab13 = st.tabs([
        "🏢 تحليل الشركة", "🏗️ قوائم دخل المشاريع (2021-2026)", "📋 الإسناد والتنفيذ والفوترة",
        "📍 عقد تبوك", "📍 عقد الباحة", "📍 عقد عسير", "📍 عقد مكة المكرمة", "📍 عقد الرياض"])

# ------------------------------------------
# التبويب الأول: الملخص التنفيذي
# ------------------------------------------
with tab1:
    ex_sum.render_exec_summary(EX_CTX)

# ------------------------------------------
# التبويب الثاني: قائمة الدخل التفصيلية
# ------------------------------------------
with tab2:
    st.subheader("📑 قائمة الربح أو الخسارة التفصيلية (شاملة تفصيل التنفيذ الفعلي والإيراد المؤجل من 2025)")
    pl_columns = [
        "البيان (بالريال السعودي)", 
        "2024\n(مدققة)", 
        "2025\n(مدققة)", 
        "30 سبتمبر 2026\n(داخلية)", 
        "30 سبتمبر 2026\n(داخلية معدلة)"
    ]
    pl_rows = [
        ("section", "أولاً: الإيرادات التشغيلية (مفصلة حسب المصدر في 2026)", []),
        ("item", "إيرادات المشاريع المفوترة (العقد الموحد والمشاريع)", [rev_24, rev_25, billed_rev_26, 0]),
        ("item", "↳ إيرادات التنفيذ الفعلي - إنتاجية فرق الشركة (2026)", [0, 0, 0, team_exec_total_26]),
        ("item", "↳ إيرادات التنفيذ الفعلي - أعمال مقاولي الباطن (2026)", [0, 0, 0, sub_exec_total_26]),
        ("item", "↳ إيرادات مؤجلة مرحلة من عام 2025 (دفعات العقد الموحد)", [0, 0, 0, deferred_rev_2025]),
        ("subtotal", "إجمالي الإيرادات التشغيلية المعتمدة", [rev_24, rev_25, billed_rev_26, actual_revenue_total_26]),
        ("section", "ثانياً: تكلفة المشاريع (حسب البنود الرئيسية السبعة)", []),
        ("item", "1. الرواتب والأجور وملحقاتها (رواتب، إقامات، إجازات، تأمين طبي، نهاية خدمة)", [-cogs_24[0], -cogs_25[0], -cogs_26[0], -cogs_26[0]]),
        ("item", "2. مصاريف صيانة وتشغيل السيارات والمعدات (محروقات، قطع غيار، كفرات، زيوت، تأمين)", [-cogs_24[1], -cogs_25[1], -cogs_26[1], -cogs_26[1]]),
        ("item", "3. تكلفة مشتريات المواد (أسفلت، خرسانة، أسمنت، بطحاء، حديد، مستهلكات)", [-cogs_24[2], -cogs_25[2], -cogs_26[2], -cogs_26[2]]),
        ("item", "4. تكلفة مقاولي الباطن - بنود المصنعيات (أسفلت، حفريات، عقد موحد)", [-cogs_24[3], -cogs_25[3], -cogs_26[3], -cogs_26[3]]),
        ("item", "5. مصاريف الإيجارات (مستودعات، سكن، مكاتب، معدات ونقليات)", [-cogs_24[4], -cogs_25[4], -cogs_26[4], -cogs_26[4]]),
        ("item", "6. مصاريف استهلاك السيارات والمعدات (حصة المشاريع من الإهلاك)", [-cogs_24[5], -cogs_25[5], -cogs_26[5], -cogs_26[5]]),
        ("item", "7. مصاريف مشاريع أخرى (تعديل مقايسات، رخص حفريات، تجهيز ومرافق المواقع)", [-cogs_24[6], -cogs_25[6], -cogs_26[6], -cogs_26[6]]),
        ("subtotal", "إجمالي تكلفة المشاريع", [-tot_cogs_24, -tot_cogs_25, -tot_cogs_26, -tot_cogs_26]),
        ("subtotal", "مجمل الربح (أو العجز) التشغيلي للمشاريع (Gross Profit)", [gp_24, gp_25, gp_26_b, gp_26_a]),
        ("pct", "نسبة هامش مجمل الربح (%)", [(gp_24/rev_24)*100, (gp_25/rev_25)*100, (gp_26_b/billed_rev_26)*100, (gp_26_a/actual_revenue_total_26)*100]),
        ("section", "ثالثاً: المصروفات الإدارية وربح التشغيل", []),
        ("item", "المصروفات العمومية والإدارية (شاملة إهلاك الإدارة ومصنع الأعمدة 3.25 مليون ريال)", [-ga_24, -ga_25, -ga_26, -ga_26]),
        ("subtotal", "ربح (خسارة) التشغيل (Operating Profit - EBIT)", [ebit_24, ebit_25, ebit_26_b, ebit_26_a]),
        ("pct", "نسبة هامش ربح التشغيل (EBIT Margin %)", [(ebit_24/rev_24)*100, (ebit_25/rev_25)*100, (ebit_26_b/billed_rev_26)*100, (ebit_26_a/actual_revenue_total_26)*100]),
        ("subtotal", "الربح التشغيلي النقدي قبل الفوائد والإهلاك والزكاة (EBITDA)", [ebitda_24, ebitda_25, ebitda_26_b, ebitda_26_a]),
        ("pct", "نسبة هامش الربح النقدي (EBITDA Margin %)", [(ebitda_24/rev_24)*100, (ebitda_25/rev_25)*100, (ebitda_26_b/billed_rev_26)*100, (ebitda_26_a/actual_revenue_total_26)*100]),
        ("section", "رابعاً: الإيرادات والمصروفات الأخرى والزكاة", []),
        ("item", "تكاليف تمويل وعمولات بنكية", [fin_24, fin_25, fin_26, fin_26]),
        ("item", "أرباح رأسمالية من بيع ممتلكات وآلات ومعدات", [gain_ppe_24, gain_ppe_25, gain_ppe_26, gain_ppe_26]),
        ("item", "أرباح إعادة تقييم عقارات استثمارية", [reval_24, reval_25, reval_26, reval_26]),
        ("item", "إيرادات أخرى (بيع مخلفات مشاريع وأخرى)", [other_rev_24, other_rev_25, other_rev_26, other_rev_26]),
        ("subtotal", "صافي الربح قبل الزكاة وضريبة الدخل (EBT)", [ebt_24, ebt_25, ebt_26_b, ebt_26_a]),
        ("item", "الزكاة الشرعية وضريبة الدخل", [zakat_tax_24, zakat_tax_25, zakat_tax_26, zakat_tax_26]),
        ("total", "صافي ربح (خسارة) الفترة (Net Profit)", [net_24, net_25, net_26_b, net_26_a]),
        ("pct", "نسبة هامش صافي الربح (Net Profit Margin %)", [(net_24/rev_24)*100, (net_25/rev_25)*100, (net_26_b/billed_rev_26)*100, (net_26_a/actual_revenue_total_26)*100])
    ]
    st.table(build_styled_table(pl_rows, pl_columns))

    st.markdown("---")
    st.markdown("### ملاحظات إدارية هامة:")
    st.markdown("""
    * **مراكز التكلفة:** تقارير الإدارة ومصنع الأعمدة الخرسانية بخليص مدرجة ضمن المصروفات العمومية واستهلاك الأصول الثابتة.
    * **حالة البيانات:** عامي 2024 و2025 (مدققة مراجعة خارجية)، بينما عام 2026 (بيانات داخلية لفترة 9 أشهر).
    """)

# ------------------------------------------
# التبويب الثالث: قائمة المركز المالي الكاملة
# ------------------------------------------
with tab3:
    st.subheader("⚖️ قائمة المركز المالي التفصيلية الكاملة (كما في 30 سبتمبر 2026 مقارنة بعامي 2025 و2024)")
    bs_columns = [
        "البيان (بالريال السعودي)", 
        "31 ديسمبر 2024\n(مدققة)", 
        "31 ديسمبر 2025\n(مدققة)", 
        "30 سبتمبر 2026\n(داخلية قبل التسوية)", 
        "30 سبتمبر 2026\n(داخلية معدلة بالتنفيذ)"
    ]
    bs_rows = [
        ("section", "أولاً: الأصول غير المتداولة (Non-Current Assets)", []),
        ("item", "الممتلكات والآلات والمعدات ومشاريع تحت التنفيذ، صافي", [115314870, 109582482, 112931800, 112931800]),
        ("item", "دفعات مقدمة لشراء ممتلكات وآلات ومعدات", [1759631, 2850850, 2850850, 2850850]),
        ("item", "عقارات استثمارية، صافي (أرض حي المصيف بالرياض)", [12180000, 13947604, 13947604, 13947604]),
        ("item", "أصول ضريبية مؤجلة", [309330, 309330, 309330 + ZK_DTA, 309330 + ZK_DTA]),
        ("item", "استثمارات متاحة للبيع (صناديق أصول وبخيت ورصانة)", [15000000, 20142380, 25142380, 25142380]),
        ("subtotal", "إجمالي الأصول غير المتداولة", [144563831, 146832646, tot_nca_26, tot_nca_26]),
        
        ("section", "ثانياً: الأصول المتداولة (Current Assets)", []),
        ("item", "النقد وما في حكمه (حسابات البنوك والصناديق النقدية)", [32470427, 31159527, 30649316, 30649316]),
        ("item", "مدينون تجاريون (عملاء مشاريع شركة الكهرباء وآخرون)", [61297501, 87231291, 53056543, 53056543]),
        ("item", "إيرادات مستحقة (أعمال منفذة غير مفوترة - WIP)", [0, 0, 0, accrued_rev_26]),
        ("item", "مصروفات مدفوعة مقدماً وأرصدة مدينة أخرى (إقامات، تأمين، سلف)", [8060444, 7949033, 8757612, 8757612]),
        ("item", "المخزون (مخزون مواد المشاريع والمستودعات)", [1204677, 1120040, 1285134, 1285134]),
        ("item", "تأمين خطابات ضمان بنكية (الراجحي، الأهلي، الأول)", [16313715, 11137440, 9550682, 9550682]),
        ("item", "المستحق من أطراف ذات علاقة", [1909275, 4695363, 3726200, 3726200]),
        ("subtotal", "إجمالي الأصول المتداولة", [121256039, 143292694, tot_ca_26_b, tot_ca_26_a]),
        ("total", "إجمالي الأصول (Total Assets)", [265819870, 290125340, tot_assets_26_b, tot_assets_26_a]),
        
        ("section", "ثالثاً: حقوق الملكية (Shareholders' Equity)", []),
        ("item", "رأس المال المدفوع", [25000000, 25000000, 25000000, 25000000]),
        ("item", "الاحتياطي النظامي", [8833551, 8833551, 8833551, 8833551]),
        ("item", "الأرباح المبقاة (بعد إقفال أرباح 2025 والتوزيعات)", [132148383, 164649861, 162616261, 162616261]),
        ("item", "صافي ربح (خسارة) الفترة الجارية (9M 2026)", [0, 0, net_26_b, net_26_a]),
        ("subtotal", "إجمالي حقوق الملكية", [165981934, 198483412, tot_eq_26_b, tot_eq_26_a]),
        
        ("section", "رابعاً: الالتزامات غير المتداولة (Non-Current Liabilities)", []),
        ("item", "التزامات المزايا المحددة للموظفين (مخصص مكافأة نهاية الخدمة)", [26516081, 16099000, 13994264, 13994264]),
        ("subtotal", "إجمالي الالتزامات غير المتداولة", [26516081, 16099000, 13994264, 13994264]),
        
        ("section", "خامساً: الالتزامات المتداولة (Current Liabilities)", []),
        ("item", "دائنون تجاريون (موردو المواد ومقاولو الباطن)", [3192368, 2878100, 1977811, 1977811]),
        ("item", "مصروفات مستحقة وأرصدة دائنة أخرى وضريبة القيمة المضافة", [14417100, 24830152, 23977533, 23977533]),
        ("item", "المخصصات (مخصص إخلاء مشاريع ومكافآت عاملين)", [21096296, 19909421, 16379994, 16379994]),
        ("item", "قروض وتسهيلات قصيرة الأجل (مرابحات مصرف الراجحي بالصافي)", [0, 10701784, 16518837, 16518837]),
        ("item", "إيرادات مؤجلة (دفعات مقدمة من شركة الكهرباء للعقد الموحد)", [32133523, 14697741, 0, 0]),
        ("item", "مخصص الزكاة الشرعية وضريبة الدخل", [2482568, 2525730, 146673 + ZK_CUR, 146673 + ZK_CUR]),
        ("subtotal", "إجمالي الالتزامات المتداولة", [73321855, 75542928, cl_26, cl_26]),
        ("subtotal", "إجمالي الالتزامات (Total Liabilities)", [99837936, 91641928, liab_26, liab_26]),
        ("total", "إجمالي حقوق الملكية والالتزامات", [265819870, 290125340, tot_assets_26_b, tot_assets_26_a])
    ]
    st.table(build_styled_table(bs_rows, bs_columns))

    st.markdown("---")
    st.markdown("### ملاحظات المركز المالي:")
    st.markdown("الأرصدة معروضة وفقاً للمعايير الدولية للتقارير المالية (IFRS) ومقاطعة مع ميزان المراجعة العام للشركة.")

# ------------------------------------------
# التبويب الرابع: قائمة التدفقات النقدية الكاملة
# ------------------------------------------
with tab4:
    st.subheader("💵 قائمة التدفقات النقدية التفصيلية الكاملة (بالطريقة غير المباشرة)")
    cf_columns = [
        "البيان (بالريال السعودي)", 
        "2024\n(مدققة)", 
        "2025\n(مدققة)", 
        "30 سبتمبر 2026\n(داخلية)"
    ]
    cf_rows = [
        ("section", "أولاً: التدفقات النقدية من الأنشطة التشغيلية", []),
        ("item", "صافي ربح الفترة قبل الزكاة وضريبة الدخل", [48144081, 38932990, ebt_26_a]),
        ("section", "التعديلات لتسوية صافي الربح قبل الزكاة إلى التدفق النقدي التشغيلي:", []),
        ("item", "الاستهلاكات (إهلاك الممتلكات والآلات والمعدات ومصنع الأعمدة)", [20959063, 25511647, 18740011]),
        ("item", "أرباح إعادة تقييم عقارات استثمارية", [-6287500, -1767604, 0]),
        ("item", "صافي حركة المخصصات (مخصص إخلاء مشاريع ومكافآت)", [996000, -1186875, -3529430]),
        ("item", "أرباح رأسمالية من بيع ممتلكات وآلات ومعدات", [-125757, -1256086, -3228647]),
        ("item", "مكون وفائدة مخصص التزامات المزايا المحددة للموظفين (نهاية الخدمة)", [3173886, 4932000, 3987416]),
        ("subtotal", "الربح التشغيلي النقدي قبل التغيرات في رأس المال العامل", [66859773, 65166072, ebt_26_a + 15969350]),
        
        ("section", "التغيرات في بنود الأصول والالتزامات التشغيلية (رأس المال العامل):", []),
        ("item", "المخزون", [-145501, 84637, -165094]),
        ("item", "مدينون تجاريون (صافي التحصيل الفعلي من ذمم العملاء)", [1878400, -25933790, 34047121]),
        ("item", "إيرادات مستحقة (الزيادة في الأعمال المنفذة غير المفوترة - WIP)", [0, 0, -accrued_rev_26]),
        ("item", "تأمين خطابات الضمان البنكية", [1180000, 5176275, 1586758]),
        ("item", "مصروفات مدفوعة مقدماً وأرصدة مدينة أخرى", [1043763, 111411, -1517836]),
        ("item", "أطراف ذات علاقة وجاري الشركاء", [1885587, -2786088, -340630]),
        ("item", "دائنون تجاريون (الموردون ومقاولو الباطن)", [1405847, -314268, -105979]),
        ("item", "مصروفات مستحقة وأرصدة دائنة أخرى وضريبة القيمة المضافة", [162355, 10413052, 466151]),
        ("item", "إيرادات مؤجلة (إطفاء الدفعات المقدمة للعقد الموحد)", [-11699186, -17435782, -14697741]),
        ("subtotal", "النقد الناتج من العمليات التشغيلية", [62571038, 34481519, 28004628]),
        ("item", "التزامات المزايا المحددة للموظفين (نهاية الخدمة) المسددة فعلياً", [-4526793, -2841250, -6092147]),
        ("item", "الزكاة الشرعية وضريبة الدخل المسددة فعلياً", [-3730305, -3896180, -2379060]),
        ("subtotal", "صافي التدفقات النقدية من الأنشطة التشغيلية (A)", [54313940, 27744089, 19533421]),
        
        ("section", "ثانياً: التدفقات النقدية من الأنشطة الاستثمارية", []),
        ("item", "مدفوعات لشراء وإضافة ممتلكات وآلات ومعدات ومستودعات قيد التأسيس", [-19915434, -21048366, -24712273]),
        ("item", "متحصلات نقدية من بيع ممتلكات وآلات ومعدات مستبعدة", [821614, 1392260, 5851603]),
        ("item", "دفعات مقدمة لشراء ممتلكات وآلات ومعدات", [-1759631, -1091219, 0]),
        ("item", "مدفوعات لشراء استثمارات متاحة للبيع (صناديق استثمارية - رصانة)", [-15000000, -5142380, -5000000]),
        ("subtotal", "صافي التدفقات النقدية المستخدمة في الأنشطة الاستثمارية (B)", [-36986383, -24756773, -23860670]),
        
        ("section", "ثالثاً: التدفقات النقدية من الأنشطة التمويلية", []),
        ("item", "توزيعات أرباح مسددة للشركاء", [-39871858, -15000000, -2000000]),
        ("item", "متحصلات من قروض ومرابحات قصيرة الأجل (مصرف الراجحي)", [0, 11899153, 21866803]),
        ("item", "المسدد من قروض قصيرة الأجل ونفقات التمويل المؤجلة", [0, -1197369, -16049759]),
        ("subtotal", "صافي التدفقات النقدية من (المستخدمة في) الأنشطة التمويلية (C)", [-39871858, -4298216, 3817044]),
        
        ("section", "رابعاً: صافي حركة النقد وأرصدة البنوك", []),
        ("subtotal", "صافي التغير (النقص) في النقد وما في حكمه خلال الفترة (A + B + C)", [-22544301, -1310900, -510205]),
        ("item", "النقد وما في حكمه في بداية الفترة", [55014728, 32470427, 31159521]),
        ("total", "النقد وما في حكمه في نهاية الفترة (Ending Cash Balance)", [32470427, 31159527, 30649316])
    ]
    st.table(build_styled_table(cf_rows, cf_columns))

    st.markdown("---")
    st.markdown("### ملاحظات التدفقات النقدية:")
    st.markdown("أعدت قائمة التدفقات النقدية وفقاً للمعايير المحاسبية المعتمدة ومطابقة للحركات الفعلية في الحسابات البنكية.")

# ------------------------------------------
# التبويب الخامس: النسب والمؤشرات المالية الشاملة
with tab_eq:
    st.subheader("🏛️ قائمة التغير في حقوق الملكية (2024 – 30 سبتمبر 2026)")
    CAP, RES = 25000000.0, 8833551.0
    ret_24_end, ret_25_end = 132148383.0, 164649861.0
    ret_26_open_adj = 162616261.0          # الأرباح المبقاة بعد التوزيعات في قائمة المركز المالي
    div_24, div_25, div_26 = 39871858.0, 15000000.0, 2000000.0
    ret_23_end = ret_24_end - net_24 + div_24            # مشتق بافتراض عدم وجود حركات أخرى
    oth_25 = ret_25_end - (ret_24_end + net_25 - div_25)  # أرباح شاملة أخرى وتسويات (بالفرق)
    oth_26 = ret_26_open_adj - (ret_25_end - div_26)      # تسويات أخرى على الرصيد الافتتاحي (بالفرق)
    ret_26_end = ret_26_open_adj + net_26_a
    eq_cols = ["البيان", "رأس المال", "الاحتياطي النظامي", "الأرباح المبقاة", "إجمالي حقوق الملكية"]
    def eq_row(t, label, ret, cap=0.0, res=0.0):
        return (t, label, [cap, res, ret, cap + res + ret])
    eq_rows = [
        ("section", "أولاً: عام 2024", []),
        ("subtotal", "الرصيد في 1 يناير 2024 (مشتق)", [CAP, RES, ret_23_end, CAP + RES + ret_23_end]),
        ("item", "صافي ربح السنة", [0, 0, net_24, net_24]),
        ("item", "توزيعات أرباح مسددة", [0, 0, -div_24, -div_24]),
        ("subtotal", "الرصيد في 31 ديسمبر 2024", [CAP, RES, ret_24_end, CAP + RES + ret_24_end]),
        ("section", "ثانياً: عام 2025", []),
        ("item", "صافي ربح السنة", [0, 0, net_25, net_25]),
        ("item", "توزيعات أرباح مسددة", [0, 0, -div_25, -div_25]),
        ("item", "أرباح شاملة أخرى وتسويات (بالفرق)", [0, 0, oth_25, oth_25]),
        ("subtotal", "الرصيد في 31 ديسمبر 2025", [CAP, RES, ret_25_end, CAP + RES + ret_25_end]),
        ("section", "ثالثاً: الفترة من 1 يناير إلى 30 سبتمبر 2026 (9 أشهر)", []),
        ("item", "توزيعات أرباح مسددة", [0, 0, -div_26, -div_26]),
        ("item", "تسويات أخرى على الأرباح المبقاة (بالفرق)", [0, 0, oth_26, oth_26]),
        ("item", "صافي ربح الفترة (معدل بالتنفيذ)", [0, 0, net_26_a, net_26_a]),
        ("total", "الرصيد في 30 سبتمبر 2026", [CAP, RES, ret_26_end, CAP + RES + ret_26_end]),
    ]
    st.table(build_styled_table(eq_rows, eq_cols if False else eq_cols))
    chk = (CAP + RES + ret_26_end) - tot_eq_26_a
    st.caption(f"مطابقة مع قائمة المركز المالي (إجمالي حقوق الملكية 2026): الفرق = {chk:,.0f}")
    tot_chg = tot_eq_26_a - (CAP + RES + ret_23_end)
    m1, m2, m3 = st.columns(3)
    m1.metric("حقوق الملكية 31 ديسمبر 2024", f"{CAP + RES + ret_24_end:,.0f} ريال")
    m2.metric("حقوق الملكية 31 ديسمبر 2025", f"{CAP + RES + ret_25_end:,.0f} ريال", f"{(ret_25_end - ret_24_end):+,.0f} عن 2024")
    m3.metric("حقوق الملكية 30 سبتمبر 2026", f"{tot_eq_26_a:,.0f} ريال", f"{tot_eq_26_a - (CAP + RES + ret_25_end):+,.0f} عن 2025")
    st.markdown("---")
    st.markdown("### ملاحظات:")
    st.markdown(f"""
    * رأس المال (25 مليون) والاحتياطي النظامي (8.83 مليون) ثابتان طوال الفترة؛ الحركة كلها في الأرباح المبقاة.
    * الرصيد الافتتاحي لـ 2024 **مشتق** من رصيد نهاية 2024 بعد خصم ربح السنة وإضافة التوزيعات، على افتراض عدم وجود حركات أخرى، ويُستبدل بالرقم المدقق متى توفر.
    * بند "أرباح شاملة أخرى وتسويات" في 2025 ({oth_25:,.0f}) ناتج بالفرق، ويرجح أنه يخص إعادة قياس التزامات نهاية الخدمة (انخفضت من 26.5 إلى 16.1 مليون)؛ يلزم تأكيده من القوائم المدققة.
    * في 2026 التوزيعات المسددة 2 مليون من قائمة التدفقات، والتسوية المتبقية ({oth_26:,.0f}) بالفرق بين رصيد الأرباح المبقاة في 2025 والرصيد المعتمد في المركز المالي.
    * ربح 2026 غير مدقق ويعتمد على إثبات الإيراد حسب التنفيذ، ولم تُحتسب زكاة عن الفترة.
    """)

# ------------------------------------------
with tab_zk:
    zakat_calc.render_zakat(EX_CTX, build_styled_table)

# ------------------------------------------
with tab_bank:
    banks.render_banks(EX_CTX, build_styled_table)

# ------------------------------------------
with tab5:
    ex_sum.render_kpis(EX_CTX, build_styled_table)

# ------------------------------------------
# التبويب السادس: قوائم دخل المشاريع (2021 - 2026)
# ------------------------------------------
with tab6:
    st.subheader("🏗️ قوائم دخل المشاريع التاريخية والتحليلية (2021 – 30 سبتمبر 2026)")
    col_opt1, col_opt2, col_opt3 = st.columns([1.2, 1.5, 0.8])
    with col_opt1:
        selected_proj = st.selectbox(
            "📍 اختر المشروع / المنطقة للاستعراض:",
            ["إجمالي الشركة (شامل الإيراد المؤجل 2025)", "إجمالي المشاريع (5 مناطق)", "منطقة تبوك", "منطقة الباحة", "منطقة عسير", "منطقة مكة المكرمة", "الرياض", "الادارة (شامل مصنع الأعمدة)"]
        )
    with col_opt2:
        rev_mode = st.selectbox(
            "⚙️ خيار عرض إيرادات عام 2026:",
            ["حسب التنفيذ الفعلي (فرق + مقاولين + مؤجل 2025)", "حسب المفوتر (المثبت بالشامل)"]
        )
    with col_opt3:
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            for reg_name in base_regions + ["الادارة (شامل مصنع الأعمدة)"]:
                reg_d = PROJECTS_DB[reg_name]
                rows_t = []
                for k_item, lbl in [
                    ("rev_shamel", "الإيراد المثبت بالشامل"), ("other_rev", "إيرادات أخرى"),
                    ("salaries", "الرواتب والأجور وملحقاتها"), ("direct_cost", "تكلفة المشتريات ومقاولي الباطن"),
                    ("maint_veh", "صيانة السيارات والمعدات"), ("rent_trans", "الإيجارات والنقليات"),
                    ("tools_cons", "العدد والأدوات والمستهلكات"), ("ga_exp", "مصاريف إدارية وعمومية"),
                    ("fin_exp", "مصاريف التمويل البنكية"), ("dep_exp", "مصاريف الإهلاك")
                ]:
                    vals = reg_d[k_item]
                    rows_t.append({"Key": k_item, "البند": lbl, "2021": vals[0], "2022": vals[1], "2023": vals[2], "2024": vals[3], "2025": vals[4], "2026": vals[5]})
                rows_t.append({"Key": "team_2026", "البند": "تنفيذ فرق الشركة 2026", "2021": 0, "2022": 0, "2023": 0, "2024": 0, "2025": 0, "2026": reg_d["team_2026"]})
                rows_t.append({"Key": "sub_2026", "البند": "تنفيذ مقاولي الباطن 2026", "2021": 0, "2022": 0, "2023": 0, "2024": 0, "2025": 0, "2026": reg_d["sub_2026"]})
                rows_t.append({"Key": "def_2026", "البند": "إيراد مؤجل من 2025", "2021": 0, "2022": 0, "2023": 0, "2024": 0, "2025": 0, "2026": reg_d["def_2026"]})
                pd.DataFrame(rows_t).to_excel(writer, sheet_name=reg_name[:30], index=False)
        st.download_button(
            label="📥 تحميل قالب تحديث المشاريع (Excel)",
            data=buf.getvalue(),
            file_name="Projects_PL_Template.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    p_data = PROJECTS_DB[selected_proj]
    use_actual_26 = (rev_mode == "حسب التنفيذ الفعلي (فرق + مقاولين + مؤجل 2025)")

    main_rev = list(p_data["rev_shamel"][:5])
    if use_actual_26:
        main_rev.append(p_data["team_2026"] + p_data["sub_2026"] + p_data["def_2026"])
    else:
        main_rev.append(p_data["rev_shamel"][5])

    other_r = p_data["other_rev"]
    tot_rev_series = [main_rev[i] + other_r[i] for i in range(6)]
    sal_s, dir_s, mnt_s = p_data["salaries"], p_data["direct_cost"], p_data["maint_veh"]
    rnt_s, tls_s, ga_s  = p_data["rent_trans"], p_data["tools_cons"], p_data["ga_exp"]
    fin_s, dep_s        = p_data["fin_exp"], p_data["dep_exp"]

    tot_exp_series = [sal_s[i] + dir_s[i] + mnt_s[i] + rnt_s[i] + tls_s[i] + ga_s[i] + fin_s[i] + dep_s[i] for i in range(6)]
    net_inc_series = [tot_rev_series[i] - tot_exp_series[i] for i in range(6)]
    margin_series = [(net_inc_series[i] / tot_rev_series[i] * 100) if tot_rev_series[i] != 0 else 0.0 for i in range(6)]

    def with_total(lst):
        return lst + [sum(lst)]

    proj_cols = [
        "البيان (وفق ترتيب النموذج المعتمد)", 
        "2021\n(مدققة)", 
        "2022\n(مدققة)", 
        "2023\n(مدققة)", 
        "2024\n(مدققة)", 
        "2025\n(مدققة)", 
        "2026 (حتى 30/9)\n(داخلية)", 
        "إجمالي الفترة"
    ]
    proj_rows = [
        ("section", f"أولاً: الإيرادات - {selected_proj}", []),
        ("item", "الإيراد المثبت بالشامل (المفوتر)", with_total(p_data["rev_shamel"])),
    ]
    if use_actual_26:
        proj_rows.extend([
            ("item", "↳ تنفيذ 2026: إنتاجية فرق الشركة", [0, 0, 0, 0, 0, p_data["team_2026"], p_data["team_2026"]]),
            ("item", "↳ تنفيذ 2026: أعمال مقاولي الباطن", [0, 0, 0, 0, 0, p_data["sub_2026"], p_data["sub_2026"]]),
            ("item", "↳ إيراد مؤجل من عام 2025", [0, 0, 0, 0, 0, p_data["def_2026"], p_data["def_2026"]]),
            ("subtotal", "الإيراد المعتمد في الحساب (شامل التنفيذ الفعلي والمؤجل)", with_total(main_rev)),
        ])
    proj_rows.extend([
        ("item", "إيرادات أخرى", with_total(other_r)),
        ("subtotal", "إجمالي الإيرادات", with_total(tot_rev_series)),
        ("section", "ثانياً: المصروفات والتكاليف (مرتبة حسب النموذج)", []),
        ("item", "1. إجمالي الرواتب والأجور وملحقاتها", with_total(sal_s)),
        ("item", "2. تكلفة المشتريات ومقاولي الباطن والغرامات", with_total(dir_s)),
        ("item", "3. صيانة السيارات والمعدات", with_total(mnt_s)),
        ("item", "4. إجمالي الإيجارات والنقليات", with_total(rnt_s)),
        ("item", "5. العدد والأدوات والمواد المستهلكة", with_total(tls_s)),
        ("item", "6. إجمالي مصاريف إدارية وعمومية", with_total(ga_s)),
        ("item", "7. مصاريف التمويل البنكية", with_total(fin_s)),
        ("item", "8. إجمالي مصاريف الإهلاك (شامل مصنع الأعمدة للإدارة)", with_total(dep_s)),
        ("subtotal", "إجمالي المصروفات", with_total(tot_exp_series)),
        ("section", "ثالثاً: صافي النتيجة والربحية", []),
        ("total", "صافي الدخل", with_total(net_inc_series)),
        ("pct", "نسبة صافي الدخل إلى إجمالي الإيرادات (%)", margin_series + [(sum(net_inc_series)/sum(tot_rev_series)*100) if sum(tot_rev_series) != 0 else 0.0])
    ])
    st.table(build_styled_table(proj_rows, proj_cols))

    st.markdown("---")
    st.markdown("### ملاحظات قائمة دخل المشاريع:")
    st.markdown("تقارير الإدارة تشمل تكاليف وإهلاك مصنع الأعمدة الخرسانية بخليص ومراكز التكلفة العامة غير الموزعة.")

# ------------------------------------------
# التبويب السابع: موقف الإسناد والتنفيذ والفوترة
# ------------------------------------------
with tab7:
    st.subheader("📋 موقف الإسناد والتنفيذ والفوترة التراكمي (وفق القالب الشهري الموحد)")
    
    # البيانات من ملخص المواقع (أكتوبر 2026) المحفوظ في tab8_dicts.py (ASSIGN_2026_BY_SITE)
    _site_order = [s_ for lst in CONTRACTS_HIERARCHY.values() for s_ in lst]
    unified_contract_rows = []
    for _site, _d in sorted(ASSIGN_2026_BY_SITE.items(),
                            key=lambda kv: _site_order.index(kv[0]) if kv[0] in _site_order else 99):
        unified_contract_rows.append({
            "العقد": _d["contract"], "المنطقة تحت العقد": _site, "حالة البيانات": "✅ ملخص المواقع (أكتوبر 2026)",
            "افتتاحي غير منفذ - إسناد (2025)": _d["open_unexec"], "افتتاحي غير منفذ - طوارئ (2025)": 0.0,
            "إسناد أوامر عمل 2026": _d["new_wo"], "إسناد طوارئ 2026": _d["new_emerg"], "إيراد فرق الصيانة": 0.0,
            "افتتاحي منفذ غير مفوتر - إسناد (2025)": _d["open_exec_unbilled"], "افتتاحي منفذ غير مفوتر - طوارئ (2025)": 0.0,
            "افتتاحي منفذ جزئي سابق (أصبح متاحاً)": _d["open_partial"],
            "تنفيذ فرق الشركة 2026": _d["team_wo"] + _d["team_partial"], "تنفيذ مقاولي الباطن 2026": _d["sub_works"],
            "تنفيذ مقاولين - عقد بنسبة %": _d["sub_pct_contract"], "تنفيذ طوارئ 2026": _d["team_emerg"],
            "تنفيذ جزئي 2026 (غير مكتمل)": _d["partial_2026"],
            "مفوتر أوامر عمل 2026": _d["billed"], "مفوتر طوارئ 2026": 0.0,
            "الغير منفذ (رصيد الإسناد المتبقي)": _d["remaining_unexec"],
        })

    df_assign = pd.DataFrame(unified_contract_rows)

    if uploaded_assign:
        loaded_dfs = []
        for f_ass in uploaded_assign:
            try:
                if f_ass.name.endswith(".csv"):
                    loaded_dfs.append(pd.read_csv(f_ass))
                else:
                    loaded_dfs.append(pd.read_excel(f_ass))
            except Exception as e:
                st.warning(f"تعذر قراءة الملف {f_ass.name}: {e}")
        if loaded_dfs:
            df_custom = pd.concat(loaded_dfs, ignore_index=True)
            req_cols = {"العقد", "المنطقة تحت العقد", "افتتاحي غير منفذ - إسناد (2025)", "افتتاحي منفذ غير مفوتر - إسناد (2025)"}
            if req_cols.issubset(set(df_custom.columns)):
                df_assign = df_custom.fillna(0.0)
                st.success("✅ تم تحديث بيانات النموذج الشهري الموحد للإسناد والتنفيذ بنجاح!")
            else:
                st.info("💡 عُرض محتوى الملف المرفق أدناه:")
                st.dataframe(df_custom, use_container_width=True)

    for _oc in ("افتتاحي منفذ جزئي سابق (أصبح متاحاً)", "تنفيذ مقاولين - عقد بنسبة %", "تنفيذ جزئي 2026 (غير مكتمل)"):
        if _oc not in df_assign.columns:
            df_assign[_oc] = 0.0

    df_assign["إجمالي افتتاحي غير منفذ (2025)"] = df_assign["افتتاحي غير منفذ - إسناد (2025)"] + df_assign["افتتاحي غير منفذ - طوارئ (2025)"]
    df_assign["إجمالي الإسناد الجديد (2026)"] = df_assign["إسناد أوامر عمل 2026"] + df_assign["إسناد طوارئ 2026"]
    df_assign["إجمالي الإسناد المتاح للتنفيذ"] = df_assign["إجمالي افتتاحي غير منفذ (2025)"] + df_assign["إجمالي الإسناد الجديد (2026)"]

    df_assign["إجمالي افتتاحي منفذ غير مفوتر (2025)"] = (df_assign["افتتاحي منفذ غير مفوتر - إسناد (2025)"] + df_assign["افتتاحي منفذ غير مفوتر - طوارئ (2025)"]
                                                        + df_assign["افتتاحي منفذ جزئي سابق (أصبح متاحاً)"])
    df_assign["تنفيذ فرق الشركة الإجمالي (عمل+جزئي+طوارئ+صيانة)"] = df_assign["تنفيذ فرق الشركة 2026"] + df_assign["تنفيذ طوارئ 2026"] + df_assign["إيراد فرق الصيانة"]
    df_assign["تنفيذ المقاولين الإجمالي (أعمال+نسبة)"] = df_assign["تنفيذ مقاولي الباطن 2026"] + df_assign["تنفيذ مقاولين - عقد بنسبة %"]
    df_assign["إجمالي التنفيذ الفعلي (2026)"] = df_assign["تنفيذ فرق الشركة الإجمالي (عمل+جزئي+طوارئ+صيانة)"] + df_assign["تنفيذ المقاولين الإجمالي (أعمال+نسبة)"]
    df_assign["إجمالي المنفذ المتاح للفوترة (تراكمي)"] = (df_assign["إجمالي افتتاحي منفذ غير مفوتر (2025)"] + df_assign["إجمالي التنفيذ الفعلي (2026)"]
                                                       - df_assign["تنفيذ جزئي 2026 (غير مكتمل)"])

    df_assign["إجمالي المفوتر (2026)"] = df_assign["مفوتر أوامر عمل 2026"] + df_assign["مفوتر طوارئ 2026"]
    df_assign["الرصيد الختامي للمنفذ غير المفوتر (WIP التراكمي)"] = df_assign["إجمالي المنفذ المتاح للفوترة (تراكمي)"] - df_assign["إجمالي المفوتر (2026)"]

    col_ctrl1, col_ctrl2, col_ctrl3 = st.columns([1.4, 1.3, 0.9])
    with col_ctrl1:
        company_view_scope = st.selectbox(
            "🔍 خيار العرض والمقارنة:",
            ["الشركة بالكامل (مقارنة العقود الخمسة)", "استعراض عقد محدد (مقارنة المناطق تحت العقد)", "استعراض جميع المناطق التفصيلية (مطابق لملف الإكسيل)"]
        )
    with col_ctrl2:
        if company_view_scope == "استعراض عقد محدد (مقارنة المناطق تحت العقد)":
            selected_contract = st.selectbox("📑 اختر العقد الموحد:", list(CONTRACTS_HIERARCHY.keys()))
        else:
            selected_contract = "إجمالي عقود الشركة"
    with col_ctrl3:
        buf_ass = io.BytesIO()
        with pd.ExcelWriter(buf_ass, engine="openpyxl") as writer:
            df_assign.to_excel(writer, sheet_name="النموذج_الشهري_الموحد", index=False)
        st.download_button(
            label="📥 تحميل قالب النموذج الشهري الموحد (Excel)",
            data=buf_ass.getvalue(),
            file_name="Unified_Monthly_Execution_Template.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    num_cols = [
        "افتتاحي غير منفذ - إسناد (2025)", "افتتاحي غير منفذ - طوارئ (2025)", "إجمالي افتتاحي غير منفذ (2025)",
        "إسناد أوامر عمل 2026", "إسناد طوارئ 2026", "إجمالي الإسناد الجديد (2026)", "إجمالي الإسناد المتاح للتنفيذ",
        "افتتاحي منفذ غير مفوتر - إسناد (2025)", "افتتاحي منفذ غير مفوتر - طوارئ (2025)", "إجمالي افتتاحي منفذ غير مفوتر (2025)",
        "تنفيذ فرق الشركة 2026", "تنفيذ مقاولي الباطن 2026", "تنفيذ طوارئ 2026", "إجمالي التنفيذ الفعلي (2026)",
        "إجمالي المنفذ المتاح للفوترة (تراكمي)", "مفوتر أوامر عمل 2026", "مفوتر طوارئ 2026", "إجمالي المفوتر (2026)",
        "الرصيد الختامي للمنفذ غير المفوتر (WIP التراكمي)", "الغير منفذ (رصيد الإسناد المتبقي)",
        "تنفيذ فرق الشركة الإجمالي (عمل+جزئي+طوارئ+صيانة)", "تنفيذ المقاولين الإجمالي (أعمال+نسبة)",
        "تنفيذ جزئي 2026 (غير مكتمل)"
    ]

    if company_view_scope == "الشركة بالكامل (مقارنة العقود الخمسة)":
        df_scope = df_assign.copy()
        grp_col = "العقد"
        df_grouped = df_scope.groupby(grp_col, as_index=False, sort=False)[num_cols].sum()
        table_title = "بيان الحركة التراكمية للإسناد والتنفيذ والفوترة للشركة بالكامل (وفق النموذج الشهري الموحد)"
    elif company_view_scope == "استعراض عقد محدد (مقارنة المناطق تحت العقد)":
        df_scope = df_assign[df_assign["العقد"] == selected_contract].copy()
        grp_col = "المنطقة تحت العقد"
        df_grouped = df_scope.groupby(grp_col, as_index=False, sort=False)[num_cols].sum()
        table_title = f"بيان الحركة التراكمية للإسناد والتنفيذ والفوترة - {selected_contract} (حسب المناطق التابعة)"
    else:
        df_grouped = df_assign.copy()
        df_grouped["الموقع والعقد"] = df_grouped["العقد"] + " - " + df_grouped["المنطقة تحت العقد"]
        grp_col = "الموقع والعقد"
        table_title = "بيان جميع المناطق والمواقع التفصيلية (وفق النموذج الموحد)"

    tot_open_unexec = df_grouped["إجمالي افتتاحي غير منفذ (2025)"].sum()
    tot_new_ass = df_grouped["إجمالي الإسناد الجديد (2026)"].sum()
    tot_avail_ass = df_grouped["إجمالي الإسناد المتاح للتنفيذ"].sum()

    tot_open_wip = df_grouped["إجمالي افتتاحي منفذ غير مفوتر (2025)"].sum()
    tot_exec_26 = df_grouped["إجمالي التنفيذ الفعلي (2026)"].sum()
    tot_avail_bill = df_grouped["إجمالي المنفذ المتاح للفوترة (تراكمي)"].sum()
    tot_bill_26 = df_grouped["إجمالي المفوتر (2026)"].sum()
    tot_end_wip = df_grouped["الرصيد الختامي للمنفذ غير المفوتر (WIP التراكمي)"].sum()
    tot_end_unexec = df_grouped["الغير منفذ (رصيد الإسناد المتبقي)"].sum()

    k1, k2, k3, k4, k5, k6 = st.columns(6)
    k1.metric("1️⃣ افتتاحي غير منفذ (25)", f"{tot_open_unexec:,.0f} ريال", f"+ إسناد 26: {tot_new_ass:,.0f}")
    k2.metric("2️⃣ إجمالي المتاح للتنفيذ", f"{tot_avail_ass:,.0f} ريال", f"المتبقي غير منفذ: {tot_end_unexec:,.0f}")
    k3.metric("3️⃣ افتتاحي غير مفوتر (25)", f"{tot_open_wip:,.0f} ريال", "مرحل منفذ لم يفوتر")
    k4.metric("4️⃣ التنفيذ الفعلي (2026)", f"{tot_exec_26:,.0f} ريال", f"متاح للفوترة: {tot_avail_bill:,.0f}")
    k5.metric("5️⃣ إجمالي المفوتر (2026)", f"{tot_bill_26:,.0f} ريال", f"نسبة الفوترة للمتاح: {(tot_bill_26/tot_avail_bill*100) if tot_avail_bill else 0:.1f}%")
    k6.metric("6️⃣ رصيد WIP الختامي", f"{tot_end_wip:,.0f} ريال", "متاح للتحويل إلى سيولة")

    ass_cols = [
        grp_col,
        "افتتاحي غير منفذ 25 (إسناد+طوارئ)",
        "إسناد جديد 26 (عمل+طوارئ)",
        "إجمالي الإسناد المتاح للتنفيذ",
        "افتتاحي منفذ غير مفوتر 25 (WIP)",
        "تنفيذ فعلي 26 (فرق+مقاولين+طوارئ)",
        "إجمالي المنفذ المتاح للفوترة",
        "إجمالي المفوتر 26 (عمل+طوارئ)",
        "رصيد WIP الختامي (غير مفوتر)",
        "رصيد الإسناد غير المنفذ"
    ]
    ass_rows = [("section", table_title, [])]
    for _, r in df_grouped.iterrows():
        ass_rows.append((
            "item", str(r[grp_col]),
            [
                r["إجمالي افتتاحي غير منفذ (2025)"],
                r["إجمالي الإسناد الجديد (2026)"],
                r["إجمالي الإسناد المتاح للتنفيذ"],
                r["إجمالي افتتاحي منفذ غير مفوتر (2025)"],
                r["إجمالي التنفيذ الفعلي (2026)"],
                r["إجمالي المنفذ المتاح للفوترة (تراكمي)"],
                r["إجمالي المفوتر (2026)"],
                r["الرصيد الختامي للمنفذ غير المفوتر (WIP التراكمي)"],
                r["الغير منفذ (رصيد الإسناد المتبقي)"]
            ]
        ))
    ass_rows.append((
        "total", f"الإجمالي التراكمي ({selected_contract})",
        [
            tot_open_unexec, tot_new_ass, tot_avail_ass,
            tot_open_wip, tot_exec_26, tot_avail_bill,
            tot_bill_26, tot_end_wip, tot_end_unexec
        ]
    ))
    st.table(build_styled_table(ass_rows, ass_cols))

    fig_ass = px.bar(
        df_grouped, x=grp_col,
        y=[
            "إجمالي الإسناد المتاح للتنفيذ",
            "إجمالي المنفذ المتاح للفوترة (تراكمي)",
            "إجمالي المفوتر (2026)",
            "الرصيد الختامي للمنفذ غير المفوتر (WIP التراكمي)",
            "الغير منفذ (رصيد الإسناد المتبقي)"
        ],
        barmode="group",
        title=f"تحليل الأرصدة التراكمية: المتاح للتنفيذ، المتاح للفوترة، المفوتر، والـ WIP الختامي ({selected_contract})",
        text_auto=',.0f'
    )
    st.plotly_chart(cv.finish_fig(fig_ass), use_container_width=True)

    split_cols = [grp_col, "تنفيذ فرق الشركة", "تنفيذ مقاولي الباطن", "إجمالي التنفيذ الفعلي", "نسبة المقاولين من التنفيذ",
                  "تنفيذ جزئي غير مكتمل (غير متاح للفوترة)"]
    split_rows = [("section", "تفصيل التنفيذ الفعلي 2026: فرق الشركة مقابل مقاولي الباطن", [])]
    _tt, _ts, _tp = 0.0, 0.0, 0.0
    for _, r in df_grouped.iterrows():
        _t = r["تنفيذ فرق الشركة الإجمالي (عمل+جزئي+طوارئ+صيانة)"]
        _s = r["تنفيذ المقاولين الإجمالي (أعمال+نسبة)"]
        _p = r["تنفيذ جزئي 2026 (غير مكتمل)"]
        _tt += _t; _ts += _s; _tp += _p
        split_rows.append(("item", str(r[grp_col]), [_t, _s, _t + _s, f"{(_s / (_t + _s) * 100) if (_t + _s) else 0:.1f}%", _p]))
    split_rows.append(("total", "الإجمالي", [_tt, _ts, _tt + _ts, f"{(_ts / (_tt + _ts) * 100) if (_tt + _ts) else 0:.1f}%", _tp]))
    st.table(build_styled_table(split_rows, split_cols))

    st.markdown("---")
    st.markdown("### ملاحظات الحركة التراكمية للإسناد والتنفيذ:")
    st.markdown("""
    * **الحركة غير المنفذة (الإسناد المتاح):** `رصيد افتتاحي غير منفذ من 2025` + `إسناد عام 2026` = **إجمالي المتاح للتنفيذ** يُخصم منه المنفذ ليعطي **رصيد الإسناد غير المنفذ بنهاية الفترة**.
    * **الحركة غير المفوتر (WIP):** `رصيد افتتاحي منفذ غير مفوتر من 2025` + `إجمالي التنفيذ الفعلي 2026` = **إجمالي المنفذ المتاح للفوترة** يُخصم منه `إجمالي المفوتر 2026` ليعطي **الرصيد الختامي للمنفذ غير المفوتر (WIP)**.
    * **التنفيذ الجزئي:** ما نُفِّذ جزئياً ولم يكتمل في 2026 يُحتسب ضمن التنفيذ لكنه لا يدخل المتاح للفوترة حتى يكتمل، وما اكتمل من تنفيذ جزئي سابق يضاف إلى الافتتاحي المتاح للفوترة.
    * **عقد بنسبة %:** تنفيذ مقاولين خارج أوامر العمل المسندة، فيدخل في التنفيذ والفوترة ولا يُخصم من رصيد الإسناد غير المنفذ.
    * **الصيانة والقراء:** المسند = المنفذ شهرياً، والفرق بين المنفذ والمفوتر يعود لاكتمال التوقيعات وتوفر الميزانية لدى العميل.
    """)

# ------------------------------------------
# التبويب الثامن: تحليل الشركة + تبويب مستقل لكل عقد
# (المنطق في contracts_view.py، والبيانات في tab8_dicts.py)
# ------------------------------------------

cv.setup(SITES_DETAILED_DB, ASSETS_BY_SITE_DB, PAYROLL_BY_SITE_26,
         PROJECTS_DB, base_regions, build_styled_table,
         site_exec=ASSIGN_2026_BY_SITE, makkah_ops=MAKKAH_OPS_DB)

with tab8:
    cv.render_company_tab()

with tab9:
    cv.render_contract_tab("العقد الموحد بتبوك", df_assign)

with tab10:
    cv.render_contract_tab("العقد الموحد بالباحة", df_assign)

with tab11:
    cv.render_contract_tab("العقد الموحد عسير", df_assign)

with tab12:
    cv.render_contract_tab("العقد الموحد بمكة المكرمة", df_assign)

with tab13:
    cv.render_contract_tab("العقد الموحد بالرياض", df_assign)

st.markdown("---")
st.markdown("🔒 **منصة دلتا السعودية للتقارير المالية** - إشراف الإدارة المالية | جميع الحقوق محفوظة © 2026")

# ------------------------------------------
# التبويب الأخير: فحوصات سلامة البيانات والتطابق بين القوائم والمصادر
# ------------------------------------------
def _pick(rows, key, col):
    for t, l, v in rows:
        if v and key in l:
            return float(v[col])
    return float("nan")

with tab_chk:
    st.subheader("✅ فحوصات سلامة البيانات والتطابق بين القوائم والمصادر")
    st.caption("تُجرى تلقائياً عند كل تحديث للبيانات. الفرق ضمن التسامح (±10 ريال) يعد مطابقاً، وما عداه يحتاج تفسيراً أو تصحيحاً.")
    CK = []
    def add_ck(group, name, a, b, tol=10.0, note="", explained=0.0, review=""):
        d = a - b
        rest = d - explained
        if abs(d) <= tol:
            st_ = "✅ مطابق"
        elif review:
            st_ = "🔵 قيد المراجعة"
        elif abs(rest) <= tol:
            st_ = "✅ مفسَّر بالكامل"
        elif abs(rest) <= max(tol * 1000, 0.02 * max(abs(a), abs(b), 1)):
            st_ = "🟡 فرق يحتاج تفسير"
        else:
            st_ = "🔴 فرق جوهري"
        CK.append({"المجموعة": group, "الفحص": name, "القيمة (أ)": a, "القيمة (ب)": b, "الفرق": d,
                   "المفسَّر": explained, "المتبقي بعد التفسير": rest, "الحالة": st_, "ملاحظة": note or review})

    for i, y in enumerate(["2024", "2025", "2026"]):
        ta = _pick(bs_rows, "إجمالي الأصول (Total Assets)", i if i < 2 else 3)
        le = _pick(bs_rows, "إجمالي حقوق الملكية والالتزامات", i if i < 2 else 3)
        add_ck("المركز المالي", f"توازن الميزانية {y}: الأصول = الالتزامات + الملكية", ta, le)
        a_ = _pick(cf_rows, "(A)", i); b_ = _pick(cf_rows, "(B)", i); c_ = _pick(cf_rows, "(C)", i)
        add_ck("التدفقات", f"صافي التغير في النقد {y} = A + B + C", a_ + b_ + c_, _pick(cf_rows, "صافي التغير (النقص)", i))
        pre = _pick(cf_rows, "الربح التشغيلي النقدي قبل", i)
        wc = sum(v[i] for t, l, v in cf_rows if v and t == "item" and (
            l in ("المخزون", "إيرادات مستحقة (الزيادة في الأعمال المنفذة غير المفوترة - WIP)", "تأمين خطابات الضمان البنكية",
                  "مصروفات مدفوعة مقدماً وأرصدة مدينة أخرى", "أطراف ذات علاقة وجاري الشركاء")
            or "مدينون تجاريون (صافي" in l or l.startswith("دائنون تجاريون")
            or l.startswith("مصروفات مستحقة وأرصدة") or l.startswith("إيرادات مؤجلة (إطفاء")))
        add_ck("التدفقات", f"التدفقات {y}: الربح قبل رأس المال العامل + التغيرات = النقد من العمليات", pre + wc, _pick(cf_rows, "النقد الناتج من العمليات", i),
               note="فرق صغير = تقريب في المدخلات")
        end_cash = _pick(cf_rows, "النقد وما في حكمه في نهاية", i)
        bs_cash = _pick(bs_rows, "النقد وما في حكمه (حسابات", i if i < 2 else 3)
        add_ck("التدفقات", f"النقد الختامي {y}: قائمة التدفقات = المركز المالي", end_cash, bs_cash)
    add_ck("التدفقات", "النقد الافتتاحي 2026 = النقد الختامي 2025", _pick(cf_rows, "النقد وما في حكمه في بداية", 2), _pick(cf_rows, "النقد وما في حكمه في نهاية", 1))
    add_ck("حقوق الملكية", "رصيد حقوق الملكية في قائمة التغير = المركز المالي (2026)", CAP + RES + ret_26_end, tot_eq_26_a)
    add_ck("الربح", "صافي الربح قبل الزكاة: قائمة الدخل = قائمة التدفقات (2026)", ebt_26_a, _pick(cf_rows, "صافي ربح الفترة قبل الزكاة", 2))

    site_exec = sum(d["total_exec"] for d in ASSIGN_2026_BY_SITE.values())
    site_team = sum(d["team_wo"] + d["team_partial"] + d["team_emerg"] for d in ASSIGN_2026_BY_SITE.values())
    site_sub = sum(d["sub_works"] + d["sub_pct_contract"] for d in ASSIGN_2026_BY_SITE.values())
    site_billed = sum(d["billed"] for d in ASSIGN_2026_BY_SITE.values())
    REV_NOTE = "سيُعتمد نهائياً في النسخة القادمة بعد مراجعة ملخص المواقع (السبت) وإنهاء نموذج الإسناد والفوترة"
    add_ck("الإيراد 2026", "التنفيذ الكلي: قوائم الدخل (فرق + مقاولين + مؤجل) مقابل ملخص المواقع", actual_revenue_total_26, site_exec, review=REV_NOTE)
    add_ck("الإيراد 2026", "تنفيذ فرق الشركة: قوائم الدخل (شامل المؤجل) مقابل ملخص المواقع", team_exec_total_26 + deferred_rev_2025, site_team, review=REV_NOTE)
    add_ck("الإيراد 2026", "تنفيذ مقاولي الباطن: قوائم الدخل مقابل ملخص المواقع", sub_exec_total_26, site_sub, review=REV_NOTE)
    add_ck("الإيراد 2026", "المفوتر: قائمة الدخل مقابل ملخص المواقع", billed_rev_26, site_billed, explained=deferred_rev_2025,
           review="مفسَّر جزئياً: الإيراد المؤجل من 2025 (يظهر في قوائم 2025). المتبقي يُراجع مع ملخص المواقع يوم السبت")
    add_ck("التكاليف 2026", "تكلفة الرواتب: قائمة الدخل مقابل ملف الرواتب بالمواقع",
           cogs_26[0], sum(v["total_comp"] for v in PAYROLL_BY_SITE_26.values()),
           review="مفسَّر نوعياً: مصاريف مرتبطة بالعمال لا تُصرف نقداً في ملف الرواتب (مخصصات إجازات ونهاية خدمة وغيرها). يحتاج حصراً بالمبلغ")
    add_ck("التكاليف 2026", "الإهلاك: قائمة الدخل مقابل سجل الأصول",
           dep_total_26, sum(v.get("dep_2026", 0) for v in ASSETS_BY_SITE_DB.values()))
    add_ck("الزكاة", "الزكاة والضريبة المثبتة في 2026 (0 = غير معتمدة بعد)", -zakat_tax_26, 0.0, tol=1.0,
           note="فعّل خيار الاعتماد في تبويب الحاسبة لتحميل المبلغ")

    BK = banks.summary()
    add_ck("البنوك", "المرابحات: جداول الأقساط (أصل + ربح القسط القادم) مقابل رصيد المرابحات في ميزان 30/9/2026",
           BK["mur_principal"] + BK["mur_next_profit"], 16608106.86, tol=10.0, note="فرق التقريب في الجدول")
    add_ck("البنوك", "المرابحات بعد خصم نفقات التمويل المؤجلة (89,278) مقابل القروض قصيرة الأجل بالمركز المالي (2026)",
           BK["mur_principal"] + BK["mur_next_profit"] - 89277.85, 16518837.0, tol=100.0,
           note="رصيد نفقات التمويل المؤجلة في ميزان 30/9 هو 347,159، بينما المركز المالي يعكس 89,278")
    add_ck("البنوك", "هامش الضمانات النقدي (ملف الضمانات) مقابل حسابات تأمين خطابات الضمان بميزان 30/9/2026",
           BK["guar_margin_live"], 11137440.35,
           review="الفرق هو هامش ضمان ساب مكة 2026 (95,462) غير مرحَّل في الميزان")
    add_ck("البنوك", "تأمين خطابات الضمان: ميزان 30/9/2026 مقابل المركز المالي (2026)", 11137440.35, 9550682.0,
           review="رقم المركز المالي 9,550,682 يساوي الرصيد الافتتاحي لحسابات التأمين في الميزان، والختامي 11,137,440. يُراجع العمود المعتمد")
    if BK["bal_rows"]:
        add_ck("البنوك", "النقد حسب الميزان (بنوك + صناديق) مقابل النقد وما في حكمه بالمركز المالي (2026)", BK["bal_total"], 30649316.0,
               review="الميزان استرشادي؛ يُعاد الفحص عند اعتماد ميزان 30/9")

    ckdf = pd.DataFrame(CK)
    n_ok = int((ckdf["الحالة"].str.startswith("✅")).sum())
    n_warn = int((ckdf["الحالة"].str.startswith("🟡") | ckdf["الحالة"].str.startswith("🔵")).sum())
    n_bad = int((ckdf["الحالة"].str.startswith("🔴")).sum())
    k1, k2, k3 = st.columns(3)
    k1.metric("فحوصات مطابقة", f"{n_ok}")
    k2.metric("قيد المراجعة / تحتاج تفسيراً", f"{n_warn}")
    k3.metric("فروق جوهرية", f"{n_bad}", delta_color="inverse")
    show = ckdf.copy()
    for c in ["القيمة (أ)", "القيمة (ب)", "الفرق", "المفسَّر", "المتبقي بعد التفسير"]:
        show[c] = show[c].map(lambda v: "—" if pd.isna(v) else (f"({abs(v):,.0f})" if v < 0 else f"{v:,.0f}"))
    def _ck_style(row):
        col = "#E8F8EE" if row["الحالة"].startswith("✅") else ("#E8F0FE" if row["الحالة"].startswith("🔵") else ("#FFF6DD" if row["الحالة"].startswith("🟡") else "#FDE8E8"))
        return [f"background-color: {col}; color: #111827;"] * len(row)
    st.table(show.style.apply(_ck_style, axis=1).hide(axis="index"))

# ------------------------------------------
# تصدير القوائم المالية إلى Excel (الشريط الجانبي)
# ------------------------------------------
def _rows_to_df(rows, cols):
    data = []
    for t, l, v in rows:
        if t == "section":
            data.append([l] + [None] * (len(cols) - 1))
        else:
            data.append([l] + [x if isinstance(x, (int, float)) else (None if x in ("", None) else x) for x in v])
    return pd.DataFrame(data, columns=[c.replace("\n", " ") for c in cols])

try:
    _buf = io.BytesIO()
    with pd.ExcelWriter(_buf, engine="openpyxl") as _xw:
        for _nm, _rows, _cols in [("قائمة الدخل", pl_rows, pl_columns), ("المركز المالي", bs_rows, bs_columns),
                                  ("التدفقات النقدية", cf_rows, cf_columns), ("حقوق الملكية", eq_rows, eq_cols),
                                  ("فحوصات الجودة", None, None)]:
            if _rows is None:
                ckdf.to_excel(_xw, sheet_name=_nm, index=False)
            else:
                _rows_to_df(_rows, _cols).to_excel(_xw, sheet_name=_nm, index=False)
        for _ws in _xw.book.worksheets:
            _ws.sheet_view.rightToLeft = True
            _ws.column_dimensions["A"].width = 70
            for _c in "BCDEFG":
                _ws.column_dimensions[_c].width = 22
            for _row in _ws.iter_rows(min_row=2):
                for _cell in _row[1:]:
                    if isinstance(_cell.value, (int, float)):
                        _cell.number_format = '#,##0;(#,##0)'
    st.sidebar.markdown("---")
    st.sidebar.download_button("📥 تصدير القوائم المالية (Excel)", data=_buf.getvalue(), file_name="Delta_Financial_Statements_2026-09-30.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
except Exception as _e:
    st.sidebar.warning(f"تعذر تجهيز ملف التصدير: {_e}")
