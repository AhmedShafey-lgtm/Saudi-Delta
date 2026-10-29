# contracts_view.py
# تبويب تحليل الشركة (التبويب الثامن) + تبويب مستقل لكل عقد من العقود الخمسة
# يعتمد على القواميس الموجودة في tab8_dicts.py وعلى PROJECTS_DB في APP.py

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

# ==========================================
# الثوابت
# ==========================================
EXP_CATEGORIES = [
    ("salaries", "1. الرواتب والأجور وملحقاتها"),
    ("maint_veh", "2. صيانة وتشغيل السيارات والمعدات"),
    ("materials", "3. تكلفة مشتريات المواد التشغيلية"),
    ("subcontractors", "4. تكلفة مقاولي الباطن"),
    ("rent_trans", "5. مصاريف الإيجارات والنقليات"),
    ("dep_exp", "6. استهلاك السيارات والمعدات والأصول"),
    ("lic_exp", "7. تكلفة إصدار التراخيص ورخص الحفريات"),
    ("penalties", "8. غرامات التأخير ومخالفات المشاريع"),
    ("camp_exp", "9. تجهيزات ومرافق السكن والمستودعات"),
    ("ga_exp", "10. مصاريف إدارية وعمومية أخرى"),
    ("fin_exp", "11. مصاريف وعمولات التمويل البنكية"),
]
YEARS_LIST = [2021, 2022, 2023, 2024, 2025, 2026]
ADMIN_SITE = "الادارة (شامل مصنع الأعمدة)"
ADMIN_CONTRACT = "الادارة ومصنع الأعمدة"

CONTRACT_ORDER = [
    "العقد الموحد بتبوك",
    "العقد الموحد بالباحة",
    "العقد الموحد عسير",
    "العقد الموحد بمكة المكرمة",
    "العقد الموحد بالرياض",
]
CONTRACT_REGION = {
    "العقد الموحد بتبوك": "منطقة تبوك",
    "العقد الموحد بالباحة": "منطقة الباحة",
    "العقد الموحد عسير": "منطقة عسير",
    "العقد الموحد بمكة المكرمة": "منطقة مكة المكرمة",
    "العقد الموحد بالرياض": "الرياض",
}
CONTRACT_KEY = {
    "العقد الموحد بتبوك": "tbk",
    "العقد الموحد بالباحة": "bha",
    "العقد الموحد عسير": "asr",
    "العقد الموحد بمكة المكرمة": "mkh",
    "العقد الموحد بالرياض": "ryd",
}
CONTRACT_NOTES = {
    "العقد الموحد بتبوك": (
        "مصروفات 2022 الإدارية والعمومية لمراكز تبوك وضباء وحقل وأملج تتضمن نحو 2.5 مليون ريال لكل مركز "
        "نتيجة تكوين مخصص خلال ذلك العام، وهو رقم صحيح لكنه استثنائي، فيرفع التكلفة ويخفض الهامش في 2022 "
        "ولا يعكس الأداء التشغيلي المعتاد."
    ),
    "العقد الموحد بمكة المكرمة": (
        "مصنع الأعمدة الخرسانية بخليص مُحمَّل ضمن الإدارة (التبويب الثامن) وليس ضمن مراكز هذا العقد."
    ),
    "العقد الموحد بالرياض": (
        "العقد يُدار من مكتب واحد، لذلك يُعرض كمركز تكلفة واحد دون مقارنات بين المراكز."
    ),
    "العقد الموحد بالباحة": (
        "بيانات «صيانة الباحة» للسنوات 2022–2026 مبنية على التقرير المحاسبي المعتمد بحساباته."
    ),
}
ACT_LABELS = {
    "construction": "الإنشاءات والتعزيزات",
    "maintenance": "الصيانة",
    "readers": "قراء العدادات",
}
METRIC_MODES = [
    "النسبة من الإيراد (%)",
    "النسبة من إجمالي التكلفة (%)",
    "القيم المالية (ريال سعودي)",
    "عرض مزدوج (% الإيراد | % التكلفة)",
]

# ==========================================
# حالة الوحدة (تُضبط مرة واحدة من APP.py)
# ==========================================
_db = {}
_ast = {}
_pay = {}
_pdb = {}
_base_regions = []
_build_table = None


def setup(sites_db, assets_db, payroll_db, projects_db, base_regions, build_table_fn):
    """تهيئة الوحدة وتوزيع إيراد التنفيذ الفعلي 2026 على المواقع."""
    global _db, _ast, _pay, _pdb, _base_regions, _build_table
    _db, _ast, _pay, _pdb = sites_db, assets_db, payroll_db, projects_db
    _base_regions = base_regions
    _build_table = build_table_fn

    # الإدارة ليس لها إيراد تشغيلي رئيسي
    _db[ADMIN_SITE]["rev_shamel"] = [0.0] * 6
    _db[ADMIN_SITE]["exec_rev_2026"] = 0.0

    # إيراد التنفيذ الفعلي المعتمد للمنطقة (فرق الشركة + مقاولو الباطن) يوزع على مواقعها بنسبة مفوترها
    for reg in base_regions:
        reg_sites = [s for s, d in _db.items() if d["region"] == reg]
        billed = sum(_db[s]["rev_shamel"][5] for s in reg_sites)
        actual = _pdb[reg]["team_2026"] + _pdb[reg]["sub_2026"]
        for s in reg_sites:
            if billed > 0:
                _db[s]["exec_rev_2026"] = _db[s]["rev_shamel"][5] * (actual / billed)
            else:
                _db[s]["exec_rev_2026"] = _db[s]["rev_shamel"][5]


# ==========================================
# دوال مساعدة
# ==========================================

def finish_fig(fig, legend_below=True):
    """ضبط الرسوم: وسيلة إيضاح أفقية أسفل الرسم بدون قص، وهوامش كافية، وخط واضح."""
    fig.update_layout(
        legend=dict(orientation="h", yanchor="top", y=-0.22, xanchor="center", x=0.5,
                    title_text="", font=dict(size=12), itemwidth=70, tracegroupgap=4),
        margin=dict(l=40, r=20, t=60, b=110),
        title=dict(x=0.5, xanchor="center", font=dict(size=15)),
        font=dict(family="Segoe UI, Tahoma, sans-serif", size=12),
        height=480,
    )
    fig.update_xaxes(title_text=None)
    return fig

def activity_of(site):
    if site == ADMIN_SITE:
        return "admin"
    if site.startswith("صيانة"):
        return "maintenance"
    if site.startswith("قراء عدادات"):
        return "readers"
    return "construction"


def sites_of_contract(contract):
    return [s for s, d in _db.items() if d["contract"] == contract]


def site_revs(site):
    d = _db[site]
    revs = [d["rev_shamel"][i] + d["other_rev"][i] for i in range(5)]
    revs.append(d["exec_rev_2026"] + d["other_rev"][5])
    return revs


def aggregate(sites, f26=1.0):
    """تجميع الإيراد والتكاليف والأصول والعمالة لقائمة مواقع. f26 معامل تسنين 2026."""
    rev = [0.0] * 6
    pl = {k: [0.0] * 6 for k, _ in EXP_CATEGORIES}
    ast = {"total_count": 0, "fully_dep_count": 0, "total_cost": 0.0, "equip_cost": 0.0,
           "dep_2026": 0.0, "nbv_total": 0.0, "nbv_equip": 0.0}
    pay = {"hc_total": 0.0, "hc_saudi": 0.0, "hc_expat": 0.0, "hc_admin": 0.0, "hc_prod": 0.0,
           "gross_sal": 0.0, "overtime": 0.0, "med_gosi": 0.0, "vac_eosb": 0.0,
           "iqama_ticket": 0.0, "total_comp": 0.0, "admin_cost": 0.0, "prod_cost": 0.0}
    for s in sites:
        if s not in _db:
            continue
        sr = site_revs(s)
        rev = [rev[i] + sr[i] for i in range(6)]
        for k, _ in EXP_CATEGORIES:
            pl[k] = [pl[k][i] + _db[s][k][i] for i in range(6)]
        for k in ast:
            ast[k] += _ast.get(s, {}).get(k, 0)
        for k in pay:
            pay[k] += _pay.get(s, {}).get(k, 0)
    if f26 != 1.0:
        rev[5] *= f26
        for k in pl:
            pl[k][5] *= f26
    cost = [sum(pl[k][i] for k, _ in EXP_CATEGORIES) for i in range(6)]
    return {"rev": rev, "pl": pl, "cost": cost, "ast": ast, "pay": pay}


def money(v):
    return f"({abs(v):,.0f})" if v < 0 else f"{v:,.0f}"


def pct(v, nd=1):
    return f"{v:.{nd}f}%"


def safe_div(a, b, mult=1.0):
    return (a / b * mult) if b else np.nan


def fmt_cell(val, rv, cv, mode):
    pr = (val / rv * 100.0) if rv > 0 else 0.0
    pc = (val / cv * 100.0) if cv > 0 else 0.0
    if mode == "القيم المالية (ريال سعودي)":
        return money(val)
    if mode == "النسبة من الإيراد (%)":
        return f"{pr:.1f}%" if rv > 0 else "—"
    if mode == "النسبة من إجمالي التكلفة (%)":
        return f"{pc:.1f}%" if cv > 0 else "—"
    return f"{pr:.1f}% | {pc:.1f}%" if (rv > 0 and cv > 0) else "—"


def year_header(y):
    return f"{y}\n({'تنفيذ فعلي 9 أشهر' if y == 2026 else 'مدققة'})"


# ==========================================
# تنسيق الجداول (أفضل/أسوأ + إجماليات)
# ==========================================
_BASE = "direction: rtl; text-align: right; background-color: #FFFFFF; color: #111827;"
_GREEN = "direction: rtl; text-align: right; background-color: #DCFCE7; color: #14532D; font-weight: bold;"
_RED = "direction: rtl; text-align: right; background-color: #FEE2E2; color: #991B1B; font-weight: bold;"
_TOTAL = "direction: rtl; text-align: right; background-color: #DBEAFE; color: #1E3A8A; font-weight: bold;"


def style_table(df_disp, raw=None, lower_better=(), higher_better=(), impact_cols=()):
    df_disp = df_disp.reset_index(drop=True)
    if raw is not None:
        raw = raw.reset_index(drop=True)

    def fn(_):
        sty = pd.DataFrame(_BASE, index=df_disp.index, columns=df_disp.columns)
        for i in df_disp.index:
            first = str(df_disp.iloc[i, 0])
            if first.startswith("إجمالي") or first.startswith("النتيجة") or first.startswith("الإجمالي"):
                sty.loc[i, :] = _TOTAL
        if raw is not None:
            for col in lower_better:
                if col in raw.columns:
                    v = pd.to_numeric(raw[col], errors="coerce").replace(0, np.nan).dropna()
                    if len(v) >= 2 and v.min() != v.max():
                        sty.loc[v.idxmin(), col] = _GREEN
                        sty.loc[v.idxmax(), col] = _RED
            for col in higher_better:
                if col in raw.columns:
                    v = pd.to_numeric(raw[col], errors="coerce").dropna()
                    if len(v) >= 2 and v.min() != v.max():
                        sty.loc[v.idxmax(), col] = _GREEN
                        sty.loc[v.idxmin(), col] = _RED
            for col in impact_cols:
                if col in raw.columns:
                    v = pd.to_numeric(raw[col], errors="coerce")
                    for i in df_disp.index:
                        x = v.iloc[i]
                        if pd.notna(x) and x <= -0.5:
                            sty.loc[i, col] = _RED
                        elif pd.notna(x) and x >= 0.5:
                            sty.loc[i, col] = _GREEN
        return sty

    styler = df_disp.style.apply(fn, axis=None)
    try:
        styler = styler.hide(axis="index")
    except Exception:
        pass
    return styler


def show_df(df_disp, **kw):
    st.table(style_table(df_disp, **kw))


def style_fig(fig, legend_rows=2):
    """وسيلة إيضاح أفقية أسفل الرسم (تمنع تداخل النصوص العربية) وهوامش مناسبة."""
    fig.update_layout(
        legend=dict(orientation="h", yanchor="top", y=-0.16, xanchor="center", x=0.5,
                    title_text="", font=dict(size=12), itemsizing="constant", tracegroupgap=2),
        margin=dict(l=10, r=10, t=55, b=40 + 28 * legend_rows),
        font=dict(family="Segoe UI, Tahoma, sans-serif", size=12),
        xaxis_title_text=None,
    )
    return fig


# ==========================================
# الجدول التاريخي لبنود التكاليف (مشترك بين الشركة والعقود)
# ==========================================
def find_anomalies(pl):
    """بنود شاذة: قيمة سنة تزيد عن 4 أضعاف وسيط باقي السنوات وتتجاوز 500 ألف."""
    out = {}
    for k, _ in EXP_CATEGORIES:
        vals = [(i, pl[k][i]) for i in range(5) if pl[k][i] > 0]
        for i, v in vals:
            others = [x for j, x in vals if j != i]
            if len(others) >= 3 and v >= 500000 and v > 4 * float(np.median(others)):
                out[(k, i)] = True
    return out


def history_rows(title, a, years, mode, flag_anomalies=False):
    rev, pl, cost = a["rev"], a["pl"], a["cost"]
    yi = [YEARS_LIST.index(y) for y in years]
    anomalies = find_anomalies(pl) if flag_anomalies else {}
    cols = ["بند الإيرادات / المصروفات"] + [year_header(y) for y in years] + ["الاتجاه (أول سنة ⬅ آخر سنة)"]
    rows = [
        ("section", f"أولاً: إيرادات الإنتاج المعتمدة - {title}", []),
        ("subtotal", "إجمالي الإيراد المعتمد", [money(rev[i]) for i in yi] + ["أساس النسبة (100%)"]),
        ("section", f"ثانياً: بنود التكاليف ({mode})", []),
    ]
    flagged = []
    for k, lbl in EXP_CATEGORIES:
        cells = []
        for i in yi:
            c = fmt_cell(pl[k][i], rev[i], cost[i], mode)
            if anomalies.get((k, i)):
                c += " ⚠️"
                flagged.append(f"{lbl.split('.')[1].strip()} ({YEARS_LIST[i]})")
            cells.append(c)
        valid = [i for i in yi if rev[i] > 0 and cost[i] > 0]
        if len(valid) >= 2:
            i0, i1 = valid[0], valid[-1]
            if mode == "النسبة من إجمالي التكلفة (%)":
                diff = pl[k][i1] / cost[i1] * 100 - pl[k][i0] / cost[i0] * 100
                lb = "من التكلفة"
            else:
                diff = pl[k][i1] / rev[i1] * 100 - pl[k][i0] / rev[i0] * 100
                lb = "من الإيراد"
            if diff > 1.0:
                trend = f"🔴 ارتفاع {lb} (+{diff:.1f}%)"
            elif diff < -1.0:
                trend = f"🟢 انخفاض/وفر {lb} ({diff:.1f}%)"
            else:
                trend = f"🟡 مستقر ({diff:+.1f}%)"
        else:
            trend = "—"
        rows.append(("item", lbl, cells + [trend]))
    rows.append(("subtotal", "إجمالي التكاليف والمصروفات",
                 [fmt_cell(cost[i], rev[i], cost[i], mode) for i in yi] + ["إجمالي التكلفة"]))
    net = []
    for i in yi:
        nv = rev[i] - cost[i]
        net.append(f"{money(nv)} ({(nv / rev[i] * 100 if rev[i] > 0 else 0):.1f}%)")
    rows.append(("total", "صافي النتيجة التشغيلية للمراكز ونسبتها للإيراد", net + ["النتيجة الصافية"]))
    return rows, cols, sorted(set(flagged))


def show_history(title, a, years, mode, flag_anomalies=False):
    rows, cols, flagged = history_rows(title, a, years, mode, flag_anomalies)
    st.table(_build_table(rows, cols))
    if flagged:
        st.caption("⚠️ بنود قيمتها في سنة محددة تفوق 4 أضعاف وسيط باقي السنوات (قد تعكس مخصصاً أو تسوية استثنائية): "
                   + "، ".join(flagged))


# ==========================================
# مصفوفة مقارنة المراكز / العقود في سنة محددة
# ==========================================
COMPARE_COLS = [
    ("salaries", "الرواتب"), ("maint_veh", "السيارات والمعدات"), ("materials", "المواد"),
    ("subcontractors", "مقاولو الباطن"), ("rent_trans", "الإيجارات"), ("dep_exp", "الاستهلاك"),
    ("lic_exp", "التراخيص"), ("penalties", "الغرامات"),
]


def comparison_df(entities, year_idx, mode, f26=1.0, total_label=None):
    """entities: قائمة (اسم، قائمة مواقع). يعيد (للعرض، خام)."""
    recs, raws = [], []
    tot_sites = []
    for name, sites in entities:
        a = aggregate(sites, f26)
        rv, cv = a["rev"][year_idx], a["cost"][year_idx]
        nv = rv - cv
        npct = (nv / rv * 100) if rv > 0 else np.nan
        rec = {"البيان": name, "عدد المراكز": str(len(sites)), "الإيراد المعتمد": money(rv),
               "إجمالي التكلفة": money(cv), "صافي النتيجة": money(nv),
               "هامش النتيجة (%)": pct(npct) if rv > 0 else "—"}
        raw = {"هامش النتيجة (%)": npct}
        for k, lbl in COMPARE_COLS:
            val = a["pl"][k][year_idx]
            rec[lbl] = fmt_cell(val, rv, cv, mode)
            if mode == "النسبة من إجمالي التكلفة (%)":
                raw[lbl] = (val / cv * 100) if cv > 0 else np.nan
            else:
                raw[lbl] = (val / rv * 100) if rv > 0 else np.nan
        recs.append(rec)
        raws.append(raw)
        tot_sites += sites
    if total_label and len(entities) > 1:
        a = aggregate(tot_sites, f26)
        rv, cv = a["rev"][year_idx], a["cost"][year_idx]
        nv = rv - cv
        rec = {"البيان": total_label, "عدد المراكز": str(len(tot_sites)), "الإيراد المعتمد": money(rv),
               "إجمالي التكلفة": money(cv), "صافي النتيجة": money(nv),
               "هامش النتيجة (%)": pct(nv / rv * 100) if rv > 0 else "—"}
        for k, lbl in COMPARE_COLS:
            rec[lbl] = fmt_cell(a["pl"][k][year_idx], rv, cv, mode)
        recs.append(rec)
        raws.append({c: np.nan for c in raws[0]})
    return pd.DataFrame(recs), pd.DataFrame(raws)


COMPARE_COST_COLS = [lbl for _, lbl in COMPARE_COLS]


# ==========================================
# مصفوفة الكفاءة 2026 (العمالة والأصول) - بدون القراء
# ==========================================
def efficiency_df(centers):
    recs, raws = [], []
    for s in centers:
        rv = site_revs(s)[5]
        d = _db[s]
        ast = _ast.get(s, {})
        pay = _pay.get(s, {})
        sal = d["salaries"][5]
        maint = d["maint_veh"][5]
        hc_p, hc_a = pay.get("hc_prod", 0.0), pay.get("hc_admin", 0.0)
        adm = pay.get("admin_cost", 0.0)
        eq = ast.get("equip_cost", 0.0)
        ppe = safe_div(rv, hc_p)
        s2p = safe_div(sal, rv, 100)
        a2p = safe_div(adm, rv, 100)
        pa = safe_div(rv, eq, 100)
        m2p = safe_div(maint, rv, 100)
        cnt, fd = ast.get("total_count", 0), ast.get("fully_dep_count", 0)
        recs.append({
            "المركز": s,
            "الإنتاج المعتمد (2026)": money(rv),
            "العمالة المنتجة": f"{hc_p:.1f}",
            "إنتاجية الفرد (ريال)": f"{ppe:,.0f}" if pd.notna(ppe) else "—",
            "الرواتب إلى الإنتاج (%)": pct(s2p) if pd.notna(s2p) else "—",
            "الطاقم الإداري (عدد / تكلفة)": f"{hc_a:.1f} ({adm:,.0f})",
            "الإدارة إلى الإنتاج (%)": pct(a2p) if pd.notna(a2p) else "—",
            "قيمة المعدات التاريخية": money(eq),
            "إنتاجية الأصول (%)": pct(pa) if pd.notna(pa) else "—",
            "صيانة المعدات إلى الإنتاج (%)": pct(m2p) if pd.notna(m2p) else "—",
            "معدات مهلكة دفترياً": f"{fd} من {cnt}" if cnt else "—",
        })
        raws.append({
            "إنتاجية الفرد (ريال)": ppe, "الرواتب إلى الإنتاج (%)": s2p,
            "الإدارة إلى الإنتاج (%)": a2p, "إنتاجية الأصول (%)": pa,
            "صيانة المعدات إلى الإنتاج (%)": m2p,
        })
    return pd.DataFrame(recs), pd.DataFrame(raws)


EFF_LOWER = ["الرواتب إلى الإنتاج (%)", "الإدارة إلى الإنتاج (%)", "صيانة المعدات إلى الإنتاج (%)"]
EFF_HIGHER = ["إنتاجية الفرد (ريال)", "إنتاجية الأصول (%)"]


def efficiency_kpis(sites):
    """بطاقات الكفاءة: تستبعد القراء (انتهى مشروعهم)."""
    eff_sites = [s for s in sites if activity_of(s) in ("construction", "maintenance")]
    a = aggregate(eff_sites)
    rv = a["rev"][5]
    return {
        "sites": eff_sites,
        "rev": rv,
        "hc_prod": a["pay"]["hc_prod"],
        "hc_admin": a["pay"]["hc_admin"],
        "admin_cost": a["pay"]["admin_cost"],
        "sal": a["pl"]["salaries"][5],
        "prod_per_person": safe_div(rv, a["pay"]["hc_prod"]),
        "sal_pct": safe_div(a["pl"]["salaries"][5], rv, 100),
        "adm_pct": safe_div(a["pay"]["admin_cost"], rv, 100),
        "asset_prod": safe_div(rv, a["ast"]["equip_cost"], 100),
        "equip_cost": a["ast"]["equip_cost"],
        "fd_pct": safe_div(a["ast"]["fully_dep_count"], a["ast"]["total_count"], 100),
        "fd": a["ast"]["fully_dep_count"],
        "cnt": a["ast"]["total_count"],
    }


def nz(v, f="{:,.0f}", suffix=""):
    return (f.format(v) + suffix) if pd.notna(v) else "—"


# ==========================================
# تبويب الشركة (التبويب الثامن)
# ==========================================
def render_company_tab():
    st.subheader("🏢 تحليل الشركة: مقارنة العقود وتغيرات الأداء وأثرها عبر السنوات")
    st.caption("نتيجة المراكز هنا = الإيراد المعتمد − تكاليف مراكز العقود (قبل تكاليف الإدارة والمصنع ومخصص الزكاة والبنود الأخرى)، "
               "ولذلك تختلف عن صافي الربح في القوائم المالية. بيانات 2026 لفترة 9 أشهر.")

    c1, c2, c3, c4 = st.columns(4)
    act_opts = {
        "كل الأنشطة (شامل القراء)": None,
        "الإنشاءات والتعزيزات فقط": "construction",
        "الصيانة فقط": "maintenance",
        "قراء العدادات فقط": "readers",
    }
    with c1:
        act_label = st.selectbox("1️⃣ نوع النشاط:", list(act_opts.keys()), key="co_act")
    with c2:
        mode = st.selectbox("2️⃣ طريقة العرض:", METRIC_MODES, key="co_mode")
    with c3:
        base_y = st.selectbox("3️⃣ سنة الأساس:", YEARS_LIST, index=4, key="co_base")
    with c4:
        cmp_y = st.selectbox("4️⃣ سنة المقارنة:", YEARS_LIST, index=5, key="co_cmp")
    c5, c6 = st.columns([2, 1])
    with c5:
        years = st.multiselect("5️⃣ السنوات المعروضة في الجداول التاريخية:", YEARS_LIST,
                               default=YEARS_LIST, key="co_years")
        years = sorted(years) if years else [2025, 2026]
    with c6:
        annual = st.checkbox("تسنين أرقام 2026 (× 12 ÷ 9) لمقارنة القيم", value=False, key="co_ann")
    f26 = 12.0 / 9.0 if annual else 1.0
    act = act_opts[act_label]

    pool = [s for s in _db if s != ADMIN_SITE and (act is None or activity_of(s) == act)]
    by_contract = {c: [s for s in pool if _db[s]["contract"] == c] for c in CONTRACT_ORDER}
    by_contract = {c: v for c, v in by_contract.items() if v}
    co = aggregate(pool, f26)
    bi, ci = YEARS_LIST.index(base_y), YEARS_LIST.index(cmp_y)

    # ---- بطاقات ----
    st.markdown(f"### ⚡ مؤشرات الشركة - {act_label} ({cmp_y} مقابل {base_y})")
    rv_b, rv_c = co["rev"][bi], co["rev"][ci]
    cv_b, cv_c = co["cost"][bi], co["cost"][ci]
    nv_b, nv_c = rv_b - cv_b, rv_c - cv_c
    mg_b = safe_div(nv_b, rv_b, 100)
    mg_c = safe_div(nv_c, rv_c, 100)
    k1, k2, k3, k4 = st.columns(4)
    k1.metric(f"الإيراد المعتمد {cmp_y}", f"{rv_c:,.0f} ريال",
              f"{safe_div(rv_c - rv_b, rv_b, 100):+.1f}% عن {base_y}" if rv_b else "—")
    k2.metric(f"تكلفة المراكز {cmp_y}", f"{cv_c:,.0f} ريال",
              f"{safe_div(cv_c - cv_b, cv_b, 100):+.1f}% عن {base_y}" if cv_b else "—", delta_color="inverse")
    k3.metric(f"نتيجة المراكز {cmp_y}", f"{nv_c:,.0f} ريال",
              f"{(nv_c - nv_b):+,.0f} عن {base_y}")
    k4.metric(f"هامش نتيجة المراكز {cmp_y}", nz(mg_c, "{:.1f}", "%"),
              f"{(mg_c - mg_b):+.1f} نقطة عن {base_y}" if pd.notna(mg_c) and pd.notna(mg_b) else "—")

    # ---- أولاً: مقارنة العقود ----
    st.markdown("---")
    st.markdown(f"### 🏛️ أولاً: مقارنة العقود الخمسة في {cmp_y} ({mode})")
    entities = [(c, v) for c, v in by_contract.items()]
    df_c, raw_c = comparison_df(entities, ci, mode, f26, total_label="إجمالي العقود")
    show_df(df_c, raw=raw_c, lower_better=COMPARE_COST_COLS, higher_better=["هامش النتيجة (%)"])
    st.caption("الأخضر = الأفضل والأحمر = الأسوأ بين العقود في كل عمود. اختلاف مزيج الأنشطة (إنشاءات/صيانة/قراء) "
               "بين العقود يؤثر على النسب، لذلك يمكن تضييق المقارنة بمرشح نوع النشاط أعلاه.")

    if act is None:
        adm = aggregate([ADMIN_SITE], f26)
        adm_cost, adm_rev = adm["cost"][ci], adm["rev"][ci]
        after = nv_c - adm_cost + adm_rev
        st.markdown(f"**تكلفة الإدارة ومصنع الأعمدة {cmp_y}:** {money(adm_cost)} ريال | "
                    f"**إيرادات الإدارة الأخرى:** {money(adm_rev)} ريال | "
                    f"**النتيجة التشغيلية بعد الإدارة:** {money(after)} ريال")

    # ---- مصفوفات السنوات ----
    rev_rows, mg_rows, mg_raw = [], [], []
    for c, v in by_contract.items():
        a = aggregate(v, f26)
        rev_rows.append({"العقد": c, **{str(y): money(a["rev"][YEARS_LIST.index(y)]) for y in years}})
        rr, rm = {"العقد": c}, {}
        for y in years:
            i = YEARS_LIST.index(y)
            m = safe_div(a["rev"][i] - a["cost"][i], a["rev"][i], 100)
            rr[str(y)] = pct(m) if pd.notna(m) else "—"
            rm[str(y)] = m
        mg_rows.append(rr)
        mg_raw.append(rm)
    tot_rev = {"العقد": "إجمالي العقود", **{str(y): money(co["rev"][YEARS_LIST.index(y)]) for y in years}}
    tot_mg = {"العقد": "إجمالي العقود"}
    for y in years:
        i = YEARS_LIST.index(y)
        m = safe_div(co["rev"][i] - co["cost"][i], co["rev"][i], 100)
        tot_mg[str(y)] = pct(m) if pd.notna(m) else "—"
    st.markdown("#### الإيراد المعتمد لكل عقد عبر السنوات")
    show_df(pd.DataFrame(rev_rows + [tot_rev]))
    st.markdown("#### هامش نتيجة المراكز (%) لكل عقد عبر السنوات")
    raw_df = pd.DataFrame(mg_raw)
    raw_df = pd.concat([raw_df, pd.DataFrame([{str(y): np.nan for y in years}])], ignore_index=True)
    show_df(pd.DataFrame(mg_rows + [tot_mg]), raw=raw_df, higher_better=[str(y) for y in years])

    ch1, ch2 = st.columns(2)
    long_rev, long_mg = [], []
    for c, v in by_contract.items():
        a = aggregate(v, f26)
        for y in years:
            i = YEARS_LIST.index(y)
            long_rev.append({"السنة": str(y), "العقد": c, "الإيراد": a["rev"][i]})
            m = safe_div(a["rev"][i] - a["cost"][i], a["rev"][i], 100)
            if pd.notna(m):
                long_mg.append({"السنة": str(y), "العقد": c, "هامش النتيجة %": round(m, 1)})
    with ch1:
        st.plotly_chart(finish_fig(px.bar(pd.DataFrame(long_rev), x="السنة", y="الإيراد", color="العقد",
                               title="الإيراد المعتمد حسب العقد")), use_container_width=True)
    with ch2:
        if long_mg:
            st.plotly_chart(finish_fig(px.line(pd.DataFrame(long_mg), x="السنة", y="هامش النتيجة %", color="العقد",
                                    markers=True, title="هامش نتيجة المراكز حسب العقد")),
                            use_container_width=True)

    # ---- ثانياً: التطور التاريخي ----
    st.markdown("---")
    st.markdown("### 📊 ثانياً: التطور التاريخي لهيكل التكاليف على مستوى الشركة")
    show_history(f"{act_label} - إجمالي مراكز العقود", co, years, mode)

    # ---- ثالثاً: تحليل أثر التغيرات ----
    st.markdown("---")
    st.markdown(f"### 🔬 ثالثاً: ما الذي تغيّر بين {base_y} و{cmp_y} وما أثره على الهامش؟")
    if base_y == cmp_y:
        st.info("اختر سنتين مختلفتين للمقارنة.")
    elif rv_b <= 0 or rv_c <= 0:
        st.info("لا يوجد إيراد في إحدى السنتين المختارتين.")
    else:
        rev_g = (rv_c / rv_b - 1) * 100
        recs, raws = [], []
        recs.append({"البند": "الإيراد المعتمد", f"{base_y}": money(rv_b), f"{cmp_y}": money(rv_c),
                     "التغير (قيمة)": money(rv_c - rv_b), "التغير %": f"{rev_g:+.1f}%",
                     f"% من الإيراد {base_y}": "100%", f"% من الإيراد {cmp_y}": "100%",
                     "الأثر على الهامش (نقطة)": "—", "نمو البند مقابل نمو الإيراد": "—", "التقييم": "—"})
        raws.append({"الأثر على الهامش (نقطة)": np.nan})
        impacts = []
        for k, lbl in EXP_CATEGORIES:
            b, c = co["pl"][k][bi], co["pl"][k][ci]
            if b == 0 and c == 0:
                continue
            pb, pc_ = b / rv_b * 100, c / rv_c * 100
            imp = -(pc_ - pb)
            g = ((c / b - 1) * 100) if b > 0 else np.nan
            gap = (g - rev_g) if pd.notna(g) else np.nan
            verdict = "🔴 ضغط على الهامش" if imp <= -0.5 else ("🟢 تحسّن" if imp >= 0.5 else "🟡 محايد")
            recs.append({"البند": lbl.split(".")[1].strip(), f"{base_y}": money(b), f"{cmp_y}": money(c),
                         "التغير (قيمة)": money(c - b),
                         "التغير %": f"{g:+.1f}%" if pd.notna(g) else "جديد",
                         f"% من الإيراد {base_y}": pct(pb), f"% من الإيراد {cmp_y}": pct(pc_),
                         "الأثر على الهامش (نقطة)": f"{imp:+.1f}",
                         "نمو البند مقابل نمو الإيراد": f"{gap:+.1f} نقطة" if pd.notna(gap) else "—",
                         "التقييم": verdict})
            raws.append({"الأثر على الهامش (نقطة)": imp})
            impacts.append((imp, lbl.split(".")[1].strip(), g))
        cg = ((cv_c / cv_b - 1) * 100) if cv_b > 0 else np.nan
        recs.append({"البند": "إجمالي التكاليف", f"{base_y}": money(cv_b), f"{cmp_y}": money(cv_c),
                     "التغير (قيمة)": money(cv_c - cv_b), "التغير %": f"{cg:+.1f}%" if pd.notna(cg) else "—",
                     f"% من الإيراد {base_y}": pct(cv_b / rv_b * 100), f"% من الإيراد {cmp_y}": pct(cv_c / rv_c * 100),
                     "الأثر على الهامش (نقطة)": f"{-(cv_c / rv_c * 100 - cv_b / rv_b * 100):+.1f}",
                     "نمو البند مقابل نمو الإيراد": f"{(cg - rev_g):+.1f} نقطة" if pd.notna(cg) else "—",
                     "التقييم": "—"})
        raws.append({"الأثر على الهامش (نقطة)": np.nan})
        dm = (mg_c - mg_b) if pd.notna(mg_c) and pd.notna(mg_b) else np.nan
        recs.append({"البند": "النتيجة التشغيلية للمراكز", f"{base_y}": money(nv_b), f"{cmp_y}": money(nv_c),
                     "التغير (قيمة)": money(nv_c - nv_b),
                     "التغير %": f"{((nv_c / nv_b - 1) * 100):+.1f}%" if nv_b > 0 else "—",
                     f"% من الإيراد {base_y}": nz(mg_b, "{:.1f}", "%"), f"% من الإيراد {cmp_y}": nz(mg_c, "{:.1f}", "%"),
                     "الأثر على الهامش (نقطة)": nz(dm, "{:+.1f}"), "نمو البند مقابل نمو الإيراد": "—",
                     "التقييم": "🟢 تحسّن" if pd.notna(dm) and dm >= 0.5 else ("🔴 تراجع" if pd.notna(dm) and dm <= -0.5 else "🟡 محايد")})
        raws.append({"الأثر على الهامش (نقطة)": dm})
        show_df(pd.DataFrame(recs), raw=pd.DataFrame(raws), impact_cols=["الأثر على الهامش (نقطة)"])
        st.caption("الأثر على الهامش = (نسبة البند من الإيراد في سنة الأساس − نسبتها في سنة المقارنة)، فالقيمة السالبة تعني أن البند "
                   "نما أسرع من الإيراد وأكل جزءاً من الهامش، والموجبة تعني وفراً نسبياً. عمود «نمو البند مقابل نمو الإيراد» "
                   "يقيس فجوة نمو البند عن نمو الإيراد ويلتقط أثر التضخم وزيادة الأسعار.")
        if cmp_y == 2026 and not annual:
            st.caption("⚠️ 2026 تغطي 9 أشهر: نسب البنود من الإيراد قابلة للمقارنة، أما القيم والنمو فتحتاج تفعيل خيار التسنين.")

        # أثر العقود على التغير
        st.markdown(f"#### مساهمة كل عقد في تغير الإيراد والنتيجة ({base_y} ⬅ {cmp_y})")
        crecs, graw = [], []
        for c, v in by_contract.items():
            a = aggregate(v, f26)
            rb, rc = a["rev"][bi], a["rev"][ci]
            nb, nc = rb - a["cost"][bi], rc - a["cost"][ci]
            mb, mc = safe_div(nb, rb, 100), safe_div(nc, rc, 100)
            crecs.append({"العقد": c, f"إيراد {base_y}": money(rb), f"إيراد {cmp_y}": money(rc),
                          "تغير الإيراد": money(rc - rb), f"نتيجة {base_y}": money(nb), f"نتيجة {cmp_y}": money(nc),
                          "تغير النتيجة": money(nc - nb),
                          "تغير الهامش (نقطة)": nz(mc - mb, "{:+.1f}") if pd.notna(mc) and pd.notna(mb) else "—"})
            graw.append({"تغير الهامش (نقطة)": (mc - mb) if pd.notna(mc) and pd.notna(mb) else np.nan})
        crecs.append({"العقد": "إجمالي العقود", f"إيراد {base_y}": money(rv_b), f"إيراد {cmp_y}": money(rv_c),
                      "تغير الإيراد": money(rv_c - rv_b), f"نتيجة {base_y}": money(nv_b), f"نتيجة {cmp_y}": money(nv_c),
                      "تغير النتيجة": money(nv_c - nv_b),
                      "تغير الهامش (نقطة)": nz(dm, "{:+.1f}")})
        graw.append({"تغير الهامش (نقطة)": np.nan})
        show_df(pd.DataFrame(crecs), raw=pd.DataFrame(graw), impact_cols=["تغير الهامش (نقطة)"])

        # ملاحظات مولدة
        press = sorted([x for x in impacts if x[0] <= -0.5])[:3]
        gain = sorted([x for x in impacts if x[0] >= 0.5], reverse=True)[:3]
        st.markdown("#### أبرز الملاحظات")
        lines = [f"- الإيراد المعتمد تغيّر بنسبة **{rev_g:+.1f}%** والتكاليف الإجمالية بنسبة "
                 f"**{cg:+.1f}%**، فتغير هامش نتيجة المراكز من **{nz(mg_b, '{:.1f}', '%')}** إلى **{nz(mg_c, '{:.1f}', '%')}**."]
        if press:
            lines.append("- أكثر البنود ضغطاً على الهامش: " + "، ".join(f"{n} ({i:+.1f} نقطة)" for i, n, _ in press) + ".")
        if gain:
            lines.append("- أكثر البنود تحسناً: " + "، ".join(f"{n} ({i:+.1f} نقطة)" for i, n, _ in gain) + ".")
        valid_m = [(c, safe_div(aggregate(v, f26)["rev"][ci] - aggregate(v, f26)["cost"][ci],
                                aggregate(v, f26)["rev"][ci], 100)) for c, v in by_contract.items()]
        valid_m = [(c, m) for c, m in valid_m if pd.notna(m)]
        if len(valid_m) >= 2:
            best = max(valid_m, key=lambda x: x[1])
            worst = min(valid_m, key=lambda x: x[1])
            lines.append(f"- في {cmp_y}: أعلى هامش للمراكز في **{best[0]}** ({best[1]:.1f}%) وأدناه في **{worst[0]}** ({worst[1]:.1f}%).")
        st.markdown("\n".join(lines))

    # ---- رابعاً: الكفاءة 2026 ----
    st.markdown("---")
    st.markdown("### 🚀 رابعاً: كفاءة العمالة والأصول لكل عقد (2026 - 9 أشهر)")
    st.caption("تُستبعد مراكز قراء العدادات من مقارنات الكفاءة لانتهاء المشروع، وتُقارَن الإنشاءات بالإنشاءات والصيانة بالصيانة.")
    for key in ("construction", "maintenance"):
        centers = [s for s in pool if activity_of(s) == key]
        if not centers:
            continue
        st.markdown(f"**{ACT_LABELS[key]}**")
        eff_entities = []
        for c in CONTRACT_ORDER:
            cs = [s for s in centers if _db[s]["contract"] == c]
            if cs:
                eff_entities.append((c, cs))
        recs, raws = [], []
        for c, cs in eff_entities:
            k = efficiency_kpis(cs)
            recs.append({
                "العقد": c, "الإنتاج المعتمد (2026)": money(k["rev"]), "العمالة المنتجة": f"{k['hc_prod']:.1f}",
                "إنتاجية الفرد (ريال)": nz(k["prod_per_person"]), "الرواتب إلى الإنتاج (%)": nz(k["sal_pct"], "{:.1f}", "%"),
                "الإدارة إلى الإنتاج (%)": nz(k["adm_pct"], "{:.1f}", "%"),
                "قيمة المعدات التاريخية": money(k["equip_cost"]), "إنتاجية الأصول (%)": nz(k["asset_prod"], "{:.1f}", "%"),
                "معدات مهلكة دفترياً": f"{k['fd']} من {k['cnt']} ({nz(k['fd_pct'], '{:.0f}', '%')})" if k["cnt"] else "—",
            })
            raws.append({"إنتاجية الفرد (ريال)": k["prod_per_person"], "الرواتب إلى الإنتاج (%)": k["sal_pct"],
                         "الإدارة إلى الإنتاج (%)": k["adm_pct"], "إنتاجية الأصول (%)": k["asset_prod"]})
        show_df(pd.DataFrame(recs), raw=pd.DataFrame(raws),
                lower_better=["الرواتب إلى الإنتاج (%)", "الإدارة إلى الإنتاج (%)"],
                higher_better=["إنتاجية الفرد (ريال)", "إنتاجية الأصول (%)"])

    # ---- الإدارة ----
    st.markdown("---")
    st.markdown("### 🏭 خامساً: الإدارة ومصنع الأعمدة (مركز تكلفة مركزي)")
    adm = aggregate([ADMIN_SITE], f26)
    adm_rows = [("section", "تكاليف الإدارة ومصنع الأعمدة (لا تدخل ضمن أي عقد)", [])]
    cols = ["البند"] + [year_header(y) for y in years]
    yi = [YEARS_LIST.index(y) for y in years]
    adm_rows.append(("item", "إيرادات أخرى", [adm["rev"][i] for i in yi]))
    for k, lbl in EXP_CATEGORIES:
        vals = [adm["pl"][k][i] for i in yi]
        if any(vals):
            adm_rows.append(("item", lbl, vals))
    adm_rows.append(("subtotal", "إجمالي تكلفة الإدارة والمصنع", [adm["cost"][i] for i in yi]))
    st.table(_build_table(adm_rows, cols))

    st.markdown("---")
    st.markdown("### ملاحظات منهجية:")
    st.markdown("""
    * **الإيراد المعتمد 2026:** هو إيراد التنفيذ الفعلي (فرق الشركة + مقاولو الباطن) بعد المراجعة، موزعاً على مراكز كل منطقة، وعلى هذا الأساس تُحسب نسب 2026.
    * **نتيجة المراكز:** لا تشمل تكاليف الإدارة والمصنع (قسم خامساً) ولا الزكاة وإيرادات إعادة التقييم، لذلك فهي مؤشر أداء تشغيلي للمراكز وليست الربح المحاسبي.
    * **مقارنات الكفاءة:** تقتصر على الإنشاءات والصيانة، ولا تشمل قراء العدادات.
    """)


# ==========================================
# موقف الإسناد للعقد (من نموذج التبويب السابع)
# ==========================================
def assignment_section(contract, df_assign):
    st.markdown("### 📋 موقف الإسناد والتنفيذ والفوترة")
    needed = ["إجمالي افتتاحي غير منفذ (2025)", "إجمالي الإسناد الجديد (2026)", "إجمالي الإسناد المتاح للتنفيذ",
              "إجمالي افتتاحي منفذ غير مفوتر (2025)", "إجمالي التنفيذ الفعلي (2026)",
              "إجمالي المنفذ المتاح للفوترة (تراكمي)", "إجمالي المفوتر (2026)",
              "الرصيد الختامي للمنفذ غير المفوتر (WIP التراكمي)", "الغير منفذ (رصيد الإسناد المتبقي)"]
    if df_assign is None or "العقد" not in df_assign.columns or any(c not in df_assign.columns for c in needed):
        st.info("بيانات موقف الإسناد غير متاحة (تُقرأ من نموذج التبويب السابع).")
        return
    d = df_assign[df_assign["العقد"] == contract].copy()
    if d.empty:
        st.info("لا توجد صفوف لهذا العقد في نموذج الإسناد.")
        return
    pending = 0
    if "حالة البيانات" in d.columns:
        pending = int(d["حالة البيانات"].astype(str).str.contains("بانتظار").sum())
    tot = {c: float(d[c].sum()) for c in needed}
    avail, ex, bill = tot[needed[2]], tot[needed[4]], tot[needed[6]]
    avail_b = tot[needed[5]]
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("إجمالي الإسناد المتاح للتنفيذ", f"{avail:,.0f} ريال", f"الرصيد غير المنفذ: {tot[needed[8]]:,.0f}")
    m2.metric("التنفيذ الفعلي 2026", f"{ex:,.0f} ريال", f"{safe_div(ex, avail, 100):.1f}% من المتاح" if avail else "—")
    m3.metric("المفوتر 2026", f"{bill:,.0f} ريال", f"{safe_div(bill, avail_b, 100):.1f}% من المتاح للفوترة" if avail_b else "—")
    m4.metric("رصيد WIP الختامي", f"{tot[needed[7]]:,.0f} ريال", "منفذ غير مفوتر")
    cols = ["المنطقة تحت العقد", "افتتاحي غير منفذ 25", "إسناد جديد 26", "إجمالي المتاح للتنفيذ",
            "افتتاحي منفذ غير مفوتر 25", "تنفيذ فعلي 26", "المتاح للفوترة", "المفوتر 26",
            "WIP الختامي", "رصيد الإسناد غير المنفذ"]
    rows = [("section", f"{contract} - حسب المنطقة", [])]
    for _, r in d.iterrows():
        label = str(r["المنطقة تحت العقد"])
        if "حالة البيانات" in d.columns and "بانتظار" in str(r["حالة البيانات"]):
            label += " ⏳"
        rows.append(("item", label, [r[c] for c in needed]))
    rows.append(("total", "الإجمالي", [tot[c] for c in needed]))
    st.table(_build_table(rows, cols))
    if pending:
        st.caption(f"⏳ {pending} من المناطق بانتظار إرفاق ملفاتها التفصيلية في نموذج الإسناد، وتظهر أرقامها أصفاراً حتى ذلك الحين.")
    fig = px.bar(d, x="المنطقة تحت العقد",
                 y=[needed[2], needed[5], needed[6], needed[7], needed[8]],
                 barmode="group", title=f"أرصدة الإسناد والتنفيذ والفوترة - {contract}")
    st.plotly_chart(finish_fig(fig), use_container_width=True)


# ==========================================
# مطابقة مراكز العقد مع قائمة دخل المنطقة
# ==========================================
def reconciliation(contract):
    region = CONTRACT_REGION[contract]
    if region not in _pdb:
        return
    p = _pdb[region]
    sites = sites_of_contract(contract)
    a = aggregate(sites)
    cost_keys = ["salaries", "direct_cost", "maint_veh", "rent_trans", "tools_cons", "ga_exp", "fin_exp", "dep_exp"]
    recs = []
    for i, y in enumerate(YEARS_LIST):
        if i < 5:
            reg_rev = p["rev_shamel"][i] + p["other_rev"][i]
        else:
            reg_rev = p["team_2026"] + p["sub_2026"] + p["other_rev"][5]
        reg_cost = sum(p[k][i] for k in cost_keys)
        d_rev = a["rev"][i] - reg_rev
        d_cost = a["cost"][i] - reg_cost
        tol = max(100000.0, 0.01 * max(reg_rev, 1.0))
        status = "🟢 مطابق" if abs(d_rev) <= tol and abs(d_cost) <= tol else "🔴 فرق يحتاج مراجعة"
        recs.append({"السنة": str(y), "إيراد المراكز": money(a["rev"][i]), "إيراد قائمة المنطقة": money(reg_rev),
                     "فرق الإيراد": money(d_rev), "تكلفة المراكز": money(a["cost"][i]),
                     "تكلفة قائمة المنطقة": money(reg_cost), "فرق التكلفة": money(d_cost), "الحالة": status})
    with st.expander("🧮 مطابقة مجموع المراكز مع قائمة دخل المنطقة (فحص جودة البيانات)"):
        st.table(pd.DataFrame(recs).style.hide(axis="index") if hasattr(pd.DataFrame, "style") else pd.DataFrame(recs))
        st.caption("الفروق تعني أن بيانات المراكز التفصيلية لا تغطي كل ما في قائمة دخل المنطقة في تلك السنة "
                   "(مثلاً مراكز غير مرفوعة أو بنود مسجلة على مستوى المنطقة فقط).")


# ==========================================
# تبويب العقد
# ==========================================
def render_contract_tab(contract, df_assign=None):
    key = CONTRACT_KEY[contract]
    sites = sites_of_contract(contract)
    groups = {}
    for act in ("construction", "maintenance", "readers"):
        g = [s for s in sites if activity_of(s) == act]
        if g:
            groups[act] = g

    st.subheader(f"📍 {contract} - تحليل شامل للعقد ومراكز التكلفة")
    st.caption("مراكز التكلفة: " + " | ".join(f"{ACT_LABELS[a]}: {'، '.join(g)}" for a, g in groups.items()))
    if contract in CONTRACT_NOTES:
        st.info(CONTRACT_NOTES[contract])

    # ---- المرشحات ----
    scope_opts = ["العقد بالكامل"]
    if len(sites) > 1:
        if len(groups) > 1:
            scope_opts += [f"مجموعة: {ACT_LABELS[a]}" for a in groups]
        scope_opts += sites
    f1, f2, f3, f4 = st.columns([1.4, 1.2, 1.6, 1.0])
    with f1:
        scope = st.selectbox("1️⃣ نطاق الاستعراض:", scope_opts, key=f"{key}_scope")
    with f2:
        mode = st.selectbox("2️⃣ طريقة العرض:", METRIC_MODES, key=f"{key}_mode")
    with f3:
        years = st.multiselect("3️⃣ السنوات المعروضة:", YEARS_LIST, default=YEARS_LIST, key=f"{key}_years")
        years = sorted(years) if years else [2025, 2026]
    with f4:
        comp_year = st.selectbox("4️⃣ سنة المقارنة بين المراكز:", YEARS_LIST, index=5, key=f"{key}_cy")
    cyi = YEARS_LIST.index(comp_year)

    if scope == "العقد بالكامل":
        target = sites
    elif scope.startswith("مجموعة: "):
        lbl = scope.replace("مجموعة: ", "")
        target = next(g for a, g in groups.items() if ACT_LABELS[a] == lbl)
    else:
        target = [scope]
    title = contract if scope == "العقد بالكامل" else scope
    a = aggregate(target)

    # ---- بطاقات 2026 ----
    st.markdown(f"### ⚡ ملخص 2026 (9 أشهر) - **{title}**")
    rv26, cv26 = a["rev"][5], a["cost"][5]
    nv26 = rv26 - cv26
    rv25, cv25 = a["rev"][4], a["cost"][4]
    mg26 = safe_div(nv26, rv26, 100)
    mg25 = safe_div(rv25 - cv25, rv25, 100)
    k1, k2, k3 = st.columns(3)
    k1.metric("الإيراد المعتمد 2026", f"{rv26:,.0f} ريال",
              f"2025 (12 شهراً): {rv25:,.0f}")
    k2.metric("تكلفة المراكز 2026", f"{cv26:,.0f} ريال", f"2025 (12 شهراً): {cv25:,.0f}")
    k3.metric("هامش نتيجة المراكز 2026", nz(mg26, "{:.1f}", "%"),
              f"{(mg26 - mg25):+.1f} نقطة عن 2025" if pd.notna(mg26) and pd.notna(mg25) else "—")
    ek = efficiency_kpis(target)
    if ek["sites"]:
        e1, e2, e3, e4, e5 = st.columns(5)
        e1.metric("إنتاجية الفرد المنتج", f"{nz(ek['prod_per_person'])} ريال", f"المنتجون: {ek['hc_prod']:.1f}")
        e2.metric("الرواتب إلى الإنتاج", nz(ek["sal_pct"], "{:.1f}", "%"), f"{ek['sal']:,.0f} ريال")
        e3.metric("إدارة الموقع إلى الإنتاج", nz(ek["adm_pct"], "{:.1f}", "%"),
                  f"كادر إداري: {ek['hc_admin']:.1f}")
        e4.metric("إنتاجية الأصول", nz(ek["asset_prod"], "{:.1f}", "%"), f"أصول: {ek['equip_cost']:,.0f}")
        e5.metric("معدات مهلكة دفترياً", nz(ek["fd_pct"], "{:.0f}", "%"), f"{ek['fd']} من {ek['cnt']}")
        if len(ek["sites"]) < len(target):
            st.caption("مؤشرات الكفاءة تستثني قراء العدادات لانتهاء المشروع.")
    else:
        st.caption("مراكز هذا النطاق (قراء العدادات) لا تُقارن كفاءتها بعد انتهاء المشروع.")

    # ---- أولاً: التاريخي ----
    st.markdown("---")
    st.markdown(f"### 📊 أولاً: التطور التاريخي للإيراد والتكاليف - **{title}**")
    show_history(title, a, years, mode, flag_anomalies=True)

    # ---- ثانياً: مقارنة المراكز ----
    st.markdown("---")
    st.markdown(f"### 🏛️ ثانياً: مقارنة مراكز التكلفة داخل العقد في {comp_year} ({mode})")
    if len(sites) == 1:
        st.info("هذا العقد مركز تكلفة واحد، فلا توجد مقارنة بين مراكز. التفاصيل في الجدول التاريخي أعلاه.")
    else:
        if len(groups) > 1:
            gents = [(ACT_LABELS[act], g) for act, g in groups.items()]
            st.markdown("**ملخص المجموعات (تباين مزيج الأنشطة داخل العقد)**")
            dfg, rawg = comparison_df(gents, cyi, mode, total_label="إجمالي العقد")
            show_df(dfg, raw=rawg)
        for act, g in groups.items():
            st.markdown(f"**{ACT_LABELS[act]}**")
            if len(g) < 2:
                st.caption(f"مركز واحد ({g[0]}) فلا توجد مقارنة داخل هذه المجموعة.")
                continue
            dfc, rawc = comparison_df([(s, [s]) for s in g], cyi, mode, total_label="إجمالي المجموعة")
            show_df(dfc, raw=rawc, lower_better=COMPARE_COST_COLS, higher_better=["هامش النتيجة (%)"])
        st.caption("الأخضر = الأفضل والأحمر = الأسوأ داخل نفس المجموعة وفي نفس العمود فقط (إنشاءات مع إنشاءات، وصيانة مع صيانة).")

    # ---- ثالثاً: عبر السنوات ----
    st.markdown("---")
    st.markdown("### 📈 ثالثاً: الإيراد وهامش النتيجة لكل مركز عبر السنوات")
    if len(sites) > 1:
        rev_recs, mg_recs, long_rev, long_mg = [], [], [], []
        for s in sites:
            sa = aggregate([s])
            rr, mm = {"المركز": s}, {"المركز": s}
            for y in years:
                i = YEARS_LIST.index(y)
                rr[str(y)] = money(sa["rev"][i]) if sa["rev"][i] != 0 else "—"
                m = safe_div(sa["rev"][i] - sa["cost"][i], sa["rev"][i], 100) if sa["rev"][i] > 0 else np.nan
                mm[str(y)] = pct(m) if pd.notna(m) else "—"
                long_rev.append({"السنة": str(y), "المركز": s, "الإيراد": sa["rev"][i]})
                if pd.notna(m):
                    long_mg.append({"السنة": str(y), "المركز": s, "هامش النتيجة %": round(m, 1)})
            rev_recs.append(rr)
            mg_recs.append(mm)
        tr = {"المركز": "إجمالي العقد"}
        tm = {"المركز": "إجمالي العقد"}
        ta = aggregate(sites)
        for y in years:
            i = YEARS_LIST.index(y)
            tr[str(y)] = money(ta["rev"][i])
            m = safe_div(ta["rev"][i] - ta["cost"][i], ta["rev"][i], 100)
            tm[str(y)] = pct(m) if pd.notna(m) else "—"
        t1, t2 = st.columns(2)
        with t1:
            st.markdown("**الإيراد المعتمد**")
            show_df(pd.DataFrame(rev_recs + [tr]))
        with t2:
            st.markdown("**هامش نتيجة المراكز (%)**")
            show_df(pd.DataFrame(mg_recs + [tm]))
        g1, g2 = st.columns(2)
        with g1:
            st.plotly_chart(finish_fig(px.bar(pd.DataFrame(long_rev), x="السنة", y="الإيراد", color="المركز",
                                   title="الإيراد المعتمد حسب المركز")), use_container_width=True)
        with g2:
            if long_mg:
                st.plotly_chart(finish_fig(px.line(pd.DataFrame(long_mg), x="السنة", y="هامش النتيجة %", color="المركز",
                                        markers=True, title="هامش نتيجة المراكز")), use_container_width=True)
    else:
        st.caption("مركز واحد: راجع الجدول التاريخي أعلاه.")

    # ---- رابعاً: الكفاءة ----
    st.markdown("---")
    st.markdown("### 🚀 رابعاً: كفاءة العمالة والأصول بين المراكز (2026 - 9 أشهر)")
    shown = False
    for act in ("construction", "maintenance"):
        g = groups.get(act, [])
        if not g:
            continue
        st.markdown(f"**{ACT_LABELS[act]}**")
        dfe, rawe = efficiency_df(g)
        if len(g) >= 2:
            show_df(dfe, raw=rawe, lower_better=EFF_LOWER, higher_better=EFF_HIGHER)
        else:
            show_df(dfe)
        shown = True
    if "readers" in groups:
        st.caption("قراء العدادات مستبعدون من الكفاءة لانتهاء المشروع (أغسطس وسبتمبر 2026).")
    if not shown:
        st.info("لا توجد مراكز إنشاءات أو صيانة في هذا العقد.")

    # ---- خامساً: الإسناد ----
    st.markdown("---")
    assignment_section(contract, df_assign)

    # ---- مطابقة ----
    st.markdown("---")
    reconciliation(contract)
