# exec_summary.py
# التبويب الأول (الملخص التنفيذي) والتبويب الخامس (المؤشرات المالية) مع معادلات الاحتساب
# تُغذّى الوحدة بأرقام القوائم المالية من APP.py عبر قاموس ctx

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

import contracts_view as cv

ANN = 12.0 / 9.0          # معامل تسنين 9 أشهر إلى 12 شهراً
PRO = 9.0 / 12.0          # حصة 9 أشهر من السنة الكاملة

FX_CSS = """
<style>
    .fx {
        direction: rtl; text-align: right; font-size: 0.80rem; line-height: 1.35;
        color: #0B2A6F; background: #EAF1FF; border-right: 3px solid #1E3A8A;
        padding: 3px 8px; margin: -6px 0 10px 0; border-radius: 4px; font-weight: 600;
    }
    .sect-title {
        direction: rtl; text-align: right; background: linear-gradient(90deg, #1E3A8A, #3B5FC4);
        color: #FFFFFF; padding: 8px 14px; border-radius: 6px; margin: 18px 0 10px 0;
        font-weight: 700; font-size: 1.05rem;
    }
    .basis-note {
        direction: rtl; text-align: right; background: #FFF7E0; border-right: 4px solid #F59E0B;
        color: #7A4B00; padding: 8px 12px; border-radius: 6px; font-size: 0.92rem; margin-bottom: 8px;
    }
    .alert-ok   { direction: rtl; text-align: right; background:#E8F8EE; border-right:4px solid #16A34A; color:#14532D; padding:6px 10px; border-radius:5px; margin:4px 0; }
    .alert-warn { direction: rtl; text-align: right; background:#FFF6DD; border-right:4px solid #F59E0B; color:#7A4B00; padding:6px 10px; border-radius:5px; margin:4px 0; }
    .alert-bad  { direction: rtl; text-align: right; background:#FDE8E8; border-right:4px solid #DC2626; color:#7F1D1D; padding:6px 10px; border-radius:5px; margin:4px 0; }
</style>
"""

# ==========================================
# أرصدة المركز المالي والتدفقات (من التبويبين الثالث والرابع)
# الترتيب: 2024، 2025، 30 سبتمبر 2026 (معدلة بالتنفيذ)
# ==========================================
BS_STATIC = {
    "ppe": [115314870, 109582482, 112931800],
    "cash": [32470427, 31159527, 30649316],
    "recv": [61297501, 87231291, 53056543],
    "prepaid": [8060444, 7949033, 8757612],
    "inventory": [1204677, 1120040, 1285134],
    "ca": [121256039, 143292694, None],        # 2026 يُمرَّر من APP
    "assets": [265819870, 290125340, None],
    "equity": [165981934, 198483412, None],
    "cl": [73321855, 75542928, 59000848],
    "liab": [99837936, 91641928, 72995112],
    "debt": [0, 10701784, 16518837],
    "payables": [3192368, 2878100, 1977811],
    "afs": [15000000, 20142380, 25142380],
}
CF_STATIC = {
    "ocf": [54313940, 27744089, 19533421],
    "inv": [-36986383, -24756773, -23860670],
    "fin": [-39871858, -4298216, 3817044],
    "capex": [-19915434, -21048366, -24712273],
    "sale": [821614, 1392260, 5851603],
    "div": [-39871858, -15000000, -2000000],
}


def _div(a, b, mult=1.0):
    try:
        if b in (0, None) or a is None or (isinstance(b, float) and np.isnan(b)):
            return np.nan
        return a / b * mult
    except Exception:
        return np.nan


def _fmt(v, kind="num"):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    if kind == "pct":
        return f"{v:.1f}%"
    if kind == "mult":
        return f"{v:.2f}x"
    if kind == "days":
        return f"{int(round(v))} يوم"
    if kind == "money_m":
        return f"{v / 1e6:,.2f} مليون"
    return f"({abs(v):,.0f})" if v < 0 else f"{v:,.0f}"


def _delta_pct(new, old):
    r = _div(new - old, abs(old), 100) if old else np.nan
    return r


def _status(kind, v):
    """تقييم إرشادي سريع: 🟢 جيد، 🟡 يحتاج متابعة، 🔴 تنبيه."""
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    rules = {
        "gm": (15, 10), "ebitda": (18, 12), "net": (10, 5), "roe": (15, 8),
        "cr": (1.5, 1.0), "qr": (1.0, 0.8), "cash_ratio": (0.5, 0.2),
        "dso": (-90, -120), "ccc": (-90, -120), "de": (-60, -100), "conv": (80, 50),
        "cov": (5, 2), "ocf_capex": (1.0, 0.7),
    }
    hi, mid = rules.get(kind, (None, None))
    if hi is None:
        return "—"
    if hi < 0:       # الأقل أفضل
        return "🟢" if v <= -hi else ("🟡" if v <= -mid else "🔴")
    return "🟢" if v >= hi else ("🟡" if v >= mid else "🔴")


def _card(col, label, value, delta=None, formula=None, inverse=False, show_fx=True):
    col.metric(label, value, delta, delta_color="inverse" if inverse else "normal")
    if formula and show_fx:
        col.markdown(f'<div class="fx">{formula}</div>', unsafe_allow_html=True)


def _section(title):
    st.markdown(f'<div class="sect-title">{title}</div>', unsafe_allow_html=True)


# ==========================================
# حساب كل المؤشرات في قاموس واحد
# ==========================================
def compute(ctx):
    rev = [ctx["rev_24"], ctx["rev_25"], ctx["rev_26"]]
    cogs = [ctx["tot_cogs_24"], ctx["tot_cogs_25"], ctx["tot_cogs_26"]]
    gp = [ctx["gp_24"], ctx["gp_25"], ctx["gp_26_a"]]
    ga = [ctx["ga_24"], ctx["ga_25"], ctx["ga_26"]]
    ebit = [ctx["ebit_24"], ctx["ebit_25"], ctx["ebit_26_a"]]
    ebitda = [ctx["ebitda_24"], ctx["ebitda_25"], ctx["ebitda_26_a"]]
    dep = [ctx["dep_total_24"], ctx["dep_total_25"], ctx["dep_total_26"]]
    ebt = [ctx["ebt_24"], ctx["ebt_25"], ctx["ebt_26_a"]]
    net = [ctx["net_24"], ctx["net_25"], ctx["net_26_a"]]
    fin = [ctx["fin_24"], ctx["fin_25"], ctx["fin_26"]]

    bs = {k: list(v) for k, v in BS_STATIC.items()}
    bs["ca"][2] = ctx["tot_ca_26_a"]
    bs["assets"][2] = ctx["tot_assets_26_a"]
    bs["equity"][2] = ctx["tot_eq_26_a"]
    cf = {k: list(v) for k, v in CF_STATIC.items()}
    accrued = [0.0, 0.0, ctx["accrued_rev_26"]]

    # ملاحظة: 2026 فترة 9 أشهر. نسنّن التدفقات عند حساب العوائد ومعدلات الدوران فقط.
    f = [1.0, 1.0, ANN]
    M = {"rev": rev, "cogs": cogs, "gp": gp, "ga": ga, "ebit": ebit, "ebitda": ebitda, "dep": dep,
         "ebt": ebt, "net": net, "fin": fin, "bs": bs, "cf": cf, "accrued": accrued, "f": f}

    r = {}
    r["gm"] = [_div(gp[i], rev[i], 100) for i in range(3)]
    r["ebitda_m"] = [_div(ebitda[i], rev[i], 100) for i in range(3)]
    r["ebit_m"] = [_div(ebit[i], rev[i], 100) for i in range(3)]
    r["ebt_m"] = [_div(ebt[i], rev[i], 100) for i in range(3)]
    r["net_m"] = [_div(net[i], rev[i], 100) for i in range(3)]
    r["ga_pct"] = [_div(ga[i], rev[i], 100) for i in range(3)]
    r["int_cov"] = [_div(ebit[i], abs(fin[i])) for i in range(3)]
    r["roe"] = [_div(net[i] * f[i], bs["equity"][i], 100) for i in range(3)]
    r["roa"] = [_div(net[i] * f[i], bs["assets"][i], 100) for i in range(3)]
    r["nwc"] = [bs["ca"][i] - bs["cl"][i] for i in range(3)]
    r["cr"] = [_div(bs["ca"][i], bs["cl"][i]) for i in range(3)]
    r["qr"] = [_div(bs["ca"][i] - bs["inventory"][i] - bs["prepaid"][i], bs["cl"][i]) for i in range(3)]
    r["cash_ratio"] = [_div(bs["cash"][i], bs["cl"][i]) for i in range(3)]
    r["cash_afs_ratio"] = [_div(bs["cash"][i] + bs["afs"][i], bs["cl"][i], 100) for i in range(3)]
    r["conv"] = [_div(cf["ocf"][i], ebitda[i], 100) for i in range(3)]
    r["fcf"] = [cf["ocf"][i] + cf["capex"][i] + cf["sale"][i] for i in range(3)]
    r["de"] = [_div(bs["liab"][i], bs["equity"][i], 100) for i in range(3)]
    r["debt_assets"] = [_div(bs["liab"][i], bs["assets"][i], 100) for i in range(3)]
    r["bank_eq"] = [_div(bs["debt"][i], bs["equity"][i], 100) for i in range(3)]
    r["debt_ebitda"] = [_div(bs["debt"][i], ebitda[i] * f[i]) for i in range(3)]
    r["net_cash"] = [bs["cash"][i] - bs["debt"][i] for i in range(3)]
    r["net_debt_ebitda"] = [_div(bs["debt"][i] - bs["cash"][i], ebitda[i] * f[i]) for i in range(3)]
    # النمو (2025 مقابل 2024، و2026 المسنّن مقابل 2025)
    r["g_rev"] = [np.nan, _delta_pct(rev[1], rev[0]), _delta_pct(rev[2] * ANN, rev[1])]
    r["g_ebitda"] = [np.nan, _delta_pct(ebitda[1], ebitda[0]), _delta_pct(ebitda[2] * ANN, ebitda[1])]
    r["g_net"] = [np.nan, _delta_pct(net[1], net[0]), _delta_pct(net[2] * ANN, net[1])]
    # التدفق والاستثمار
    r["ocf_m"] = [_div(cf["ocf"][i], rev[i], 100) for i in range(3)]
    r["capex_rev"] = [_div(-cf["capex"][i], rev[i], 100) for i in range(3)]
    r["capex_dep"] = [_div(-cf["capex"][i], dep[i]) for i in range(3)]
    r["ocf_capex"] = [_div(cf["ocf"][i], -cf["capex"][i]) for i in range(3)]
    r["fa_turn"] = [_div(rev[i] * f[i], bs["ppe"][i]) for i in range(3)]
    r["fa_assets"] = [_div(bs["ppe"][i], bs["assets"][i], 100) for i in range(3)]
    r["eq_assets"] = [_div(bs["equity"][i], bs["assets"][i], 100) for i in range(3)]
    r["payout"] = [_div(-cf["div"][i], net[i], 100) for i in range(3)]
    r["nwc_rev"] = [_div(r["nwc"][i], rev[i] * f[i], 100) for i in range(3)]
    r["accrued_rev"] = [_div(accrued[i], rev[i], 100) for i in range(3)]
    # الدوران
    r["asset_turn"] = [_div(rev[i] * f[i], bs["assets"][i]) for i in range(3)]
    r["eq_mult"] = [_div(bs["assets"][i], bs["equity"][i]) for i in range(3)]
    M["r"] = r

    # ---- العمالة (2026 فقط) ----
    pay = ctx["PAYROLL"]
    hc = sum(v["hc_total"] for v in pay.values())
    hc_sa = sum(v["hc_saudi"] for v in pay.values())
    M["hc"] = hc
    M["hc_saudi_pct"] = _div(hc_sa, hc, 100)
    M["rev_per_head"] = _div(rev[2] * ANN, hc)
    M["sal_per_head"] = _div(cogs_item(ctx, 0) * ANN, hc)

    # ---- الإسناد والتنفيذ والفوترة (من ملخص المواقع) ----
    A = ctx["ASSIGN"]
    ex = sum(d["total_exec"] for d in A.values())
    bl = sum(d["billed"] for d in A.values())
    rem = sum(d["remaining_unexec"] for d in A.values())
    avail_ex = sum(d["open_unexec"] + d["new_wo"] + d["new_emerg"] for d in A.values())
    pct_ctr = sum(d["sub_pct_contract"] for d in A.values())
    wip = sum(d["avail_billing"] for d in A.values())
    M["ops"] = {
        "exec": ex, "billed": bl, "remaining": rem, "avail_exec": avail_ex, "wip": wip,
        "bill_pct": _div(bl, ex, 100),
        "exec_vs_assign": _div(ex - pct_ctr, avail_ex, 100),
        "backlog_months": _div(rem, ex / 9.0) if ex else np.nan,
        "wip_months": _div(wip, ex / 9.0) if ex else np.nan,
    }
    return M


def cogs_item(ctx, i):
    return ctx["cogs_26"][i]


# ==========================================
# الملخص التنفيذي
# ==========================================
def render_exec_summary(ctx):
    M = compute(ctx)
    r, bs, cf = M["r"], M["bs"], M["cf"]
    st.markdown(FX_CSS, unsafe_allow_html=True)
    st.subheader("🌟 الملخص التنفيذي للإدارة والملاك (حتى 30 سبتمبر 2026)")

    # ---------- خيارات العرض ----------
    o1, o2, o3 = st.columns([1.6, 1.0, 1.0])
    with o1:
        basis = st.selectbox(
            "🔀 أساس عرض ومقارنة 2026 (فترة 9 أشهر فقط):",
            ["9 أشهر الفعلية مقابل 9/12 من السنوات السابقة", "تسنين 2026 إلى 12 شهراً (× 12 ÷ 9)"],
            key="ex_basis")
    with o2:
        show_fx = st.checkbox("🧮 إظهار معادلات الاحتساب", value=True, key="ex_fx")
    with o3:
        show_charts = st.checkbox("📊 إظهار الرسوم البيانية", value=True, key="ex_charts")
    annual = basis.startswith("تسنين")

    if annual:
        k = [1.0, 1.0, ANN]
        lab = ["2024", "2025", "2026 (مسنّن)"]
        cmp_txt = "عن 2025 (2026 مسنّن)"
        st.markdown('<div class="basis-note">⚠️ أرقام 2026 في الحقول التدفقية (الإيراد والربح والتدفقات) مُسنّنة إلى 12 شهراً '
                    'لمقارنتها بالسنوات الكاملة. أرصدة المركز المالي (النقد والأصول والالتزامات) كما هي في 30 سبتمبر دون تسنين.</div>',
                    unsafe_allow_html=True)
    else:
        k = [PRO, PRO, 1.0]
        lab = ["2024 (9/12)", "2025 (9/12)", "2026 (9 أشهر)"]
        cmp_txt = "عن 9/12 من 2025"
        st.markdown('<div class="basis-note">⚠️ 2026 تغطي 9 أشهر فقط. لذلك تُقارن بـ 9/12 من أرقام 2025 (نسبة وتناسب)، '
                    'والنسب والهوامش لا تتأثر بقصر الفترة. أرصدة المركز المالي بتاريخ 30 سبتمبر مقابل 31 ديسمبر.</div>',
                    unsafe_allow_html=True)

    def flow(key, i):
        return M[key][i] * k[i]

    def chg(key):
        return _delta_pct(flow(key, 2), flow(key, 1))

    def dtxt(v):
        return f"{v:+.1f}% {cmp_txt}" if pd.notna(v) else None

    # ---------- 1) الأداء ----------
    _section("1️⃣ الأداء التشغيلي والربحية")
    a1, a2, a3, a4 = st.columns(4)
    _card(a1, "إجمالي الإيراد المعتمد", f"{flow('rev', 2):,.0f} ريال", dtxt(chg("rev")),
          "الإيراد = التنفيذ الفعلي (فرق + مقاولين) + المؤجل المرحّل", show_fx=show_fx)
    _card(a2, "مجمل الربح", f"{flow('gp', 2):,.0f} ريال", f"هامش {r['gm'][2]:.1f}% (2025: {r['gm'][1]:.1f}%)",
          "مجمل الربح = الإيراد − تكلفة المشاريع", show_fx=show_fx)
    _card(a3, "الربح النقدي EBITDA", f"{flow('ebitda', 2):,.0f} ريال", f"هامش {r['ebitda_m'][2]:.1f}% (2025: {r['ebitda_m'][1]:.1f}%)",
          "EBITDA = ربح التشغيل + الإهلاك", show_fx=show_fx)
    _card(a4, "صافي الربح", f"{flow('net', 2):,.0f} ريال", f"هامش {r['net_m'][2]:.1f}% (2025: {r['net_m'][1]:.1f}%)",
          "صافي الربح = ربح التشغيل ± التمويل والأرباح الأخرى − الزكاة", show_fx=show_fx)

    b1, b2, b3, b4 = st.columns(4)
    _card(b1, "تكلفة المشاريع", f"{flow('cogs', 2):,.0f} ريال", dtxt(chg("cogs")),
          "تكلفة المشاريع = مجموع بنود التكلفة السبعة", inverse=True, show_fx=show_fx)
    _card(b2, "ربح التشغيل EBIT", f"{flow('ebit', 2):,.0f} ريال", f"هامش {r['ebit_m'][2]:.1f}%",
          "EBIT = مجمل الربح − المصروفات العمومية والإدارية", show_fx=show_fx)
    _card(b3, "المصروفات العمومية والإدارية", f"{flow('ga', 2):,.0f} ريال", f"{r['ga_pct'][2]:.2f}% من الإيراد",
          "نسبة G&A = المصروفات الإدارية ÷ الإيراد × 100", inverse=True, show_fx=show_fx)
    _card(b4, "العائد السنوي على حقوق الملكية ROE", f"{r['roe'][2]:.1f}%", f"2025: {r['roe'][1]:.1f}%",
          "ROE = (صافي الربح × 12÷9) ÷ حقوق الملكية × 100", show_fx=show_fx)

    # ---------- 2) السيولة ----------
    _section("2️⃣ السيولة والتدفقات النقدية والمركز المالي")
    c1, c2, c3, c4 = st.columns(4)
    _card(c1, "النقد وما في حكمه", f"{bs['cash'][2]:,.0f} ريال",
          f"{bs['cash'][2] - bs['cash'][1]:+,.0f} عن 31 ديسمبر 2025",
          "النقد = أرصدة البنوك والصناديق النقدية", show_fx=show_fx)
    _card(c2, "نسبة التداول", f"{r['cr'][2]:.2f}x", f"2025: {r['cr'][1]:.2f}x  |  المعيار الآمن > 1.5x",
          "نسبة التداول = الأصول المتداولة ÷ الخصوم المتداولة", show_fx=show_fx)
    _card(c3, "صافي رأس المال العامل", f"{r['nwc'][2]:,.0f} ريال", f"2025: {r['nwc'][1]:,.0f}",
          "رأس المال العامل = الأصول المتداولة − الخصوم المتداولة", show_fx=show_fx)
    _card(c4, "صافي المركز النقدي (بعد القروض)", f"{r['net_cash'][2]:,.0f} ريال", f"القروض: {bs['debt'][2]:,.0f}",
          "صافي المركز النقدي = النقد − القروض البنكية قصيرة الأجل", show_fx=show_fx)

    d1, d2, d3, d4 = st.columns(4)
    _card(d1, "التدفق النقدي التشغيلي (9 أشهر)", f"{cf['ocf'][2]:,.0f} ريال", f"2025 كامل: {cf['ocf'][1]:,.0f}",
          "صافي التدفق من الأنشطة التشغيلية (قائمة التدفقات)", show_fx=show_fx)
    _card(d2, "تحويل EBITDA إلى نقد", f"{r['conv'][2]:.1f}%", f"2025: {r['conv'][1]:.1f}%",
          "التحويل = التدفق التشغيلي ÷ EBITDA × 100", show_fx=show_fx)
    _card(d3, "التدفق النقدي الحر", f"{r['fcf'][2]:,.0f} ريال", f"2025: {r['fcf'][1]:,.0f}",
          "الحر = التشغيلي − الإنفاق الرأسمالي + متحصلات بيع الأصول", show_fx=show_fx)
    _card(d4, "الإنفاق الرأسمالي (9 أشهر)", f"{-cf['capex'][2]:,.0f} ريال", f"{r['capex_dep'][2]:.2f}x من الإهلاك",
          "نسبة إعادة الاستثمار = الإنفاق الرأسمالي ÷ الإهلاك", show_fx=show_fx)

    e1, e2, e3, e4 = st.columns(4)
    _card(e1, "إجمالي الأصول", f"{bs['assets'][2]:,.0f} ريال", f"{bs['assets'][2] - bs['assets'][1]:+,.0f} عن 2025",
          "الأصول = غير المتداولة + المتداولة (شاملة الإيراد المستحق)", show_fx=show_fx)
    _card(e2, "حقوق الملكية", f"{bs['equity'][2]:,.0f} ريال", f"{r['eq_assets'][2]:.1f}% من الأصول",
          "نسبة الملكية = حقوق الملكية ÷ إجمالي الأصول × 100", show_fx=show_fx)
    _card(e3, "إجمالي الالتزامات إلى الملكية", f"{r['de'][2]:.1f}%", f"2025: {r['de'][1]:.1f}%",
          "= إجمالي الالتزامات ÷ حقوق الملكية × 100", inverse=True, show_fx=show_fx)
    _card(e4, "الإيراد المستحق (WIP) من الإيراد", f"{r['accrued_rev'][2]:.1f}%", f"{ctx['accrued_rev_26']:,.0f} ريال",
          "= المنفذ غير المفوتر في 2026 ÷ إيراد 2026 × 100", inverse=True, show_fx=show_fx)

    # ---------- 3) التشغيل ----------
    _section("3️⃣ التنفيذ والفوترة والعمالة")
    O = M["ops"]
    g1, g2, g3, g4 = st.columns(4)
    _card(g1, "التنفيذ الفعلي 2026 (ملخص المواقع)", f"{O['exec']:,.0f} ريال", f"المفوتر: {O['billed']:,.0f}",
          "التنفيذ = فرق الشركة + مقاولو الباطن + عقد بنسبة %", show_fx=show_fx)
    _card(g2, "نسبة الفوترة من التنفيذ", f"{O['bill_pct']:.1f}%", f"المنفذ المتاح للفوترة: {O['wip']:,.0f}",
          "نسبة الفوترة = المفوتر ÷ التنفيذ × 100", show_fx=show_fx)
    _card(g3, "المتبقي من الإسناد (غير منفذ)", f"{O['remaining']:,.0f} ريال", f"يكفي {O['backlog_months']:.1f} شهر بمعدل التنفيذ الحالي",
          "الأشهر = المتبقي ÷ (تنفيذ 2026 ÷ 9 أشهر)", show_fx=show_fx)
    _card(g4, "المنفذ غير المفوتر بالأشهر", f"{O['wip_months']:.1f} شهر", "مدة إنتاج بمعدل التنفيذ الحالي",
          "= المنفذ المتاح للفوترة ÷ (تنفيذ 2026 ÷ 9)", inverse=True, show_fx=show_fx)
    h1, h2, h3, h4 = st.columns(4)
    _card(h1, "عدد العمالة (متوسط 2026)", f"{M['hc']:,.0f}", f"نسبة السعودة {M['hc_saudi_pct']:.1f}%",
          "السعودة = العمالة السعودية ÷ إجمالي العمالة × 100", show_fx=show_fx)
    _card(h2, "إيراد الفرد (سنوي)", f"{M['rev_per_head']:,.0f} ريال", "الإيراد المسنّن ÷ عدد العمالة",
          "= (الإيراد × 12÷9) ÷ عدد العمالة", show_fx=show_fx)
    _card(h3, "تكلفة الرواتب للفرد (سنوي)", f"{M['sal_per_head']:,.0f} ريال", f"{_div(cogs_item(ctx, 0), ctx['rev_26'], 100):.1f}% من الإيراد",
          "= (تكلفة الرواتب × 12÷9) ÷ عدد العمالة", inverse=True, show_fx=show_fx)
    _card(h4, "دورة التحول النقدي", f"{ctx['ccc_26']:.0f} يوم", f"التحصيل الشامل {ctx['dso_total_26']:.0f} يوم",
          "CCC = أيام التحصيل + أيام المخزون − أيام السداد", inverse=True, show_fx=show_fx)

    # ---------- جدول مقارنة السنوات ----------
    _section("4️⃣ مقارنة الأداء عبر السنوات")
    rows = []
    for key, name, kind in [("rev", "الإيراد المعتمد", "n"), ("cogs", "تكلفة المشاريع", "n"), ("gp", "مجمل الربح", "n"),
                            ("ga", "المصروفات العمومية والإدارية", "n"), ("ebitda", "EBITDA", "n"), ("ebit", "ربح التشغيل EBIT", "n"),
                            ("net", "صافي الربح", "n")]:
        v = [M[key][i] for i in range(3)]
        rows.append({
            "البند": name, "2024 (مدققة)": _fmt(v[0]), "2025 (مدققة)": _fmt(v[1]),
            "2026 (9 أشهر)": _fmt(v[2]), "2026 (مسنّن 12 شهراً)": _fmt(v[2] * ANN),
            "التغير عن 2025 (مسنّن)": f"{_delta_pct(v[2] * ANN, v[1]):+.1f}%" if v[1] else "—",
            "الاحتساب": {"rev": "تنفيذ الفرق + المقاولين + المؤجل", "cogs": "مجموع بنود التكلفة السبعة",
                         "gp": "الإيراد − تكلفة المشاريع", "ga": "حسب قائمة الدخل", "ebitda": "ربح التشغيل + الإهلاك",
                         "ebit": "مجمل الربح − المصروفات الإدارية", "net": "EBT − الزكاة والضريبة"}[key],
        })
    df = pd.DataFrame(rows)
    if not show_fx:
        df = df.drop(columns=["الاحتساب"])
    st.table(_styled_formula_df(df, "الاحتساب" if show_fx else None))
    st.caption("التغير مبني على تسنين 2026 (× 12 ÷ 9) لمقارنة عادلة مع سنة كاملة؛ وقد لا يعكس الموسمية (فترات الذروة في الربع الأخير).")

    # ---------- أهم المؤشرات ----------
    _section("5️⃣ أهم المؤشرات والنسب مع معادلات الاحتساب")
    head = [
        ("هامش مجمل الربح %", r["gm"], "pct", "gm", "(الإيراد − تكلفة المشاريع) ÷ الإيراد × 100"),
        ("هامش EBITDA %", r["ebitda_m"], "pct", "ebitda", "EBITDA ÷ الإيراد × 100"),
        ("هامش صافي الربح %", r["net_m"], "pct", "net", "صافي الربح ÷ الإيراد × 100"),
        ("العائد على حقوق الملكية ROE %", r["roe"], "pct", "roe", "(صافي الربح السنوي) ÷ حقوق الملكية × 100"),
        ("نسبة التداول", r["cr"], "mult", "cr", "الأصول المتداولة ÷ الخصوم المتداولة"),
        ("نسبة السيولة السريعة", r["qr"], "mult", "qr", "(الأصول المتداولة − المخزون − المقدمات) ÷ الخصوم المتداولة"),
        ("نسبة النقدية", r["cash_ratio"], "mult", "cash_ratio", "النقد ÷ الخصوم المتداولة"),
        ("تحويل EBITDA إلى نقد %", r["conv"], "pct", "conv", "التدفق التشغيلي ÷ EBITDA × 100"),
        ("الالتزامات إلى الملكية %", r["de"], "pct", "de", "إجمالي الالتزامات ÷ حقوق الملكية × 100"),
        ("تغطية الفوائد", r["int_cov"], "mult", "cov", "ربح التشغيل ÷ تكاليف التمويل"),
        ("تغطية التشغيلي للإنفاق الرأسمالي", r["ocf_capex"], "mult", "ocf_capex", "التدفق التشغيلي ÷ الإنفاق الرأسمالي"),
        ("نمو الإيراد %", r["g_rev"], "pct", None, "(إيراد السنة ÷ إيراد السنة السابقة − 1) × 100، و2026 مسنّن"),
        ("نمو صافي الربح %", r["g_net"], "pct", None, "(صافي ربح السنة ÷ السنة السابقة − 1) × 100، و2026 مسنّن"),
    ]
    hrows = []
    for name, v, kind, st_key, fx in head:
        hrows.append({
            "المؤشر": name, "2024": _fmt(v[0], kind), "2025": _fmt(v[1], kind), "2026 (9 أشهر / مسنّن)": _fmt(v[2], kind),
            "الحالة": _status(st_key, v[2]) if st_key else "—", "معادلة الاحتساب": fx,
        })
    dfh = pd.DataFrame(hrows)
    if not show_fx:
        dfh = dfh.drop(columns=["معادلة الاحتساب"])
    st.table(_styled_formula_df(dfh, "معادلة الاحتساب" if show_fx else None))
    st.caption("🟢 جيد  |  🟡 يحتاج متابعة  |  🔴 تنبيه. الحدود إرشادية عامة وليست معايير تعاقدية.")

    # ---------- تنبيهات ----------
    _section("6️⃣ ملاحظات وتنبيهات للإدارة")
    alerts = []

    def add(level, txt):
        alerts.append((level, txt))

    rg = r["g_rev"][2]
    add("ok" if rg >= 0 else "warn",
        f"الإيراد المسنّن 2026 {'أعلى' if rg >= 0 else 'أقل'} من 2025 بنسبة {abs(rg):.1f}% "
        f"(الإيراد 9 أشهر {ctx['rev_26']:,.0f} ريال).")
    dm = r["net_m"][2] - r["net_m"][1]
    add("ok" if dm >= 0 else "warn", f"هامش صافي الربح {r['net_m'][2]:.1f}% مقابل {r['net_m'][1]:.1f}% في 2025 ({dm:+.1f} نقطة).")
    if r["conv"][2] < 60:
        add("bad" if r["conv"][2] < 40 else "warn",
            f"تحويل EBITDA إلى نقد {r['conv'][2]:.0f}% فقط، فجزء كبير من الأرباح محتجز في ذمم وأعمال منفذة غير مفوترة.")
    if O["bill_pct"] < 85:
        add("warn", f"المفوتر {O['bill_pct']:.1f}% من التنفيذ، والمنفذ غير المفوتر {O['wip']:,.0f} ريال "
                    f"(نحو {O['wip_months']:.1f} شهر إنتاج)، فالتحصيل يتوقف على التوقيعات والميزانية لدى العميل.")
    if ctx["dso_total_26"] > 100:
        add("warn", f"فترة التحصيل الشاملة {ctx['dso_total_26']:.0f} يوماً، وهي أعلى من 90 يوماً المرجعية.")
    if r["cr"][2] >= 1.5:
        add("ok", f"السيولة جيدة: نسبة التداول {r['cr'][2]:.2f}x، وصافي المركز النقدي {r['net_cash'][2]:,.0f} ريال.")
    else:
        add("warn", f"نسبة التداول {r['cr'][2]:.2f}x أقل من المعيار الآمن 1.5x.")
    if r["capex_dep"][2] > 1.2:
        add("warn", f"الإنفاق الرأسمالي {r['capex_dep'][2]:.2f} ضعف الإهلاك، ويستهلك {_div(-cf['capex'][2], cf['ocf'][2], 100):.0f}% من التدفق التشغيلي.")
    if bs["debt"][2] > bs["debt"][1]:
        add("warn", f"القروض قصيرة الأجل ارتفعت من {bs['debt'][1]:,.0f} إلى {bs['debt'][2]:,.0f} ريال.")
    for lvl, txt in alerts:
        st.markdown(f'<div class="alert-{lvl}">{"✅" if lvl == "ok" else ("⚠️" if lvl == "warn" else "🔴")} {txt}</div>',
                    unsafe_allow_html=True)

    # ---------- الرسوم ----------
    if show_charts:
        _section("7️⃣ الرسوم البيانية")
        opts = ["الإيراد والربحية", "هوامش الربحية", "التدفقات النقدية", "هيكل تكلفة المشاريع", "مزيج إنتاج 2026", "العقود الخمسة 2026"]
        chosen = st.multiselect("اختر الرسوم المطلوب عرضها:", opts, default=opts, key="ex_chart_sel")
        _charts(ctx, M, k, lab, chosen)

    st.markdown("---")
    st.markdown("### الملاحظات المنهجية وآلية الاحتساب:")
    st.markdown("""
    * **فترة 2026:** تغطي 9 أشهر حتى 30 سبتمبر، فتُعرض الأرقام إما فعلية مقابل 9/12 من 2025، أو مسنّنة (× 12 ÷ 9). النسب والهوامش لا تحتاج تسنيناً، أما العوائد ومعدلات الدوران فتُسنّن دائماً.
    * **قاعدة الإيرادات والفوترة:** تُثبت إيرادات عقود الصيانة والعقد الموحد وفقاً للإنتاجية الفعلية ومستخلصات الأعمال المعتمدة من الشركة السعودية للطاقة.
    * **تكاليف العمالة:** تشمل الرواتب والبدلات والتأمين الطبي وحصة التأمينات الاجتماعية ومخصصات الإجازات ونهاية الخدمة ورسوم الإقامات والتذاكر.
    * **قراء العدادات:** توقفت أعمالهم خلال أغسطس وسبتمبر 2026 بناءً على توجيهات الشركة السعودية للطاقة.
    * **مصدر التنفيذ والفوترة:** ملخص المواقع (أكتوبر 2026)، وقد يختلف عن إيراد التنفيذ المسجل في قوائم دخل المشاريع.
    """)


def _styled_formula_df(df, formula_col):
    """جدول بسيط RTL مع عمود المعادلة بلون أزرق غامق مميز."""
    df = df.reset_index(drop=True)
    first = df.columns[0]

    def fn(_):
        sty = pd.DataFrame("direction: rtl; text-align: center; vertical-align: middle; font-size: 1.05rem; background-color: #FFFFFF; color: #111827;",
                           index=df.index, columns=df.columns)
        if formula_col and formula_col in df.columns:
            sty[formula_col] = ("direction: rtl; text-align: right; background-color: #EAF1FF; color: #0B2A6F; "
                                "font-weight: 600; font-size: 0.88rem; border-right: 3px solid #1E3A8A;")
        return sty

    s = df.style.apply(fn, axis=None)
    s = s.set_table_styles([{'selector': 'th', 'props': [('text-align', 'center'), ('font-size', '1.05rem')]},
                            {'selector': 'td', 'props': [('padding', '8px 10px')]}])
    s = s.set_properties(subset=[first], **{'text-align': 'right'})
    try:
        s = s.hide(axis="index")
    except Exception:
        pass
    return s


def _charts(ctx, M, k, lab, chosen):
    r, cf = M["r"], M["cf"]

    def show(fig):
        st.plotly_chart(cv.finish_fig(fig), use_container_width=True)

    if "الإيراد والربحية" in chosen:
        rows = []
        for i in range(3):
            for key, nm in (("rev", "الإيراد"), ("ebitda", "EBITDA"), ("net", "صافي الربح")):
                rows.append({"السنة": lab[i], "البند": nm, "القيمة": M[key][i] * k[i]})
        show(px.bar(pd.DataFrame(rows), x="السنة", y="القيمة", color="البند", barmode="group",
                    title="الإيراد وEBITDA وصافي الربح"))
    if "هوامش الربحية" in chosen:
        rows = []
        for i, y in enumerate(["2024", "2025", "2026 (9 أشهر)"]):
            for key, nm in (("gm", "مجمل الربح"), ("ebitda_m", "EBITDA"), ("ebit_m", "التشغيل"), ("net_m", "صافي الربح")):
                rows.append({"السنة": y, "الهامش": nm, "النسبة %": round(r[key][i], 2)})
        show(px.line(pd.DataFrame(rows), x="السنة", y="النسبة %", color="الهامش", markers=True,
                     title="هوامش الربحية % من الإيراد"))
    if "التدفقات النقدية" in chosen:
        rows = []
        for i, y in enumerate(["2024", "2025", "2026 (9 أشهر)"]):
            for key, nm in (("ocf", "تشغيلية"), ("inv", "استثمارية"), ("fin", "تمويلية")):
                rows.append({"السنة": y, "النشاط": nm, "القيمة": cf[key][i]})
        show(px.bar(pd.DataFrame(rows), x="السنة", y="القيمة", color="النشاط", barmode="group",
                    title="التدفقات النقدية حسب النشاط"))
    if "هيكل تكلفة المشاريع" in chosen:
        names = ["الرواتب", "السيارات والمعدات", "المواد", "مقاولو الباطن", "الإيجارات", "الاستهلاك", "أخرى"]
        cg = [ctx["cogs_24"], ctx["cogs_25"], ctx["cogs_26"]]
        rows = []
        for i, y in enumerate(["2024", "2025", "2026 (9 أشهر)"]):
            for j, nm in enumerate(names):
                rows.append({"السنة": y, "البند": nm, "% من الإيراد": round(cg[i][j] / M["rev"][i] * 100, 2)})
        show(px.bar(pd.DataFrame(rows), x="السنة", y="% من الإيراد", color="البند", barmode="stack",
                    title="هيكل تكلفة المشاريع (% من الإيراد)"))
    if "مزيج إنتاج 2026" in chosen:
        mix = pd.DataFrame({"المصدر": ["فرق الشركة", "مقاولو الباطن", "مؤجل من 2025"],
                            "القيمة": [ctx["team_exec_total_26"], ctx["sub_exec_total_26"], ctx["deferred_rev_2025"]]})
        show(px.pie(mix, names="المصدر", values="القيمة", title="مزيج إيراد 2026 حسب المصدر", hole=0.45))
    if "العقود الخمسة 2026" in chosen:
        rows = []
        for c in cv.CONTRACT_ORDER:
            a = cv.aggregate(cv.sites_of_contract(c))
            short = c.replace("العقد الموحد ", "")
            rows.append({"العقد": short, "البند": "الإيراد", "القيمة": a["rev"][5]})
            rows.append({"العقد": short, "البند": "التكلفة", "القيمة": a["cost"][5]})
            rows.append({"العقد": short, "البند": "نتيجة المراكز", "القيمة": a["rev"][5] - a["cost"][5]})
        show(px.bar(pd.DataFrame(rows), x="العقد", y="القيمة", color="البند", barmode="group",
                    title="الإيراد والتكلفة ونتيجة المراكز لكل عقد (2026 - 9 أشهر)"))


# ==========================================
# تبويب المؤشرات الشاملة مع المعادلات
# ==========================================
def render_kpis(ctx, build_styled_table):
    M = compute(ctx)
    r, bs, cf = M["r"], M["bs"], M["cf"]
    st.markdown(FX_CSS, unsafe_allow_html=True)
    st.subheader("📉 منظومة النسب والمؤشرات المالية الشاملة (للإدارة المالية والتنفيذية والملاك والمستثمرين)")
    show_fx = st.checkbox("🧮 إظهار عمود معادلة الاحتساب بجانب كل مؤشر", value=True, key="kpi_fx")

    cols = ["المؤشر المالي والتشغيلي", "2023\n(مدققة)", "2024\n(مدققة)", "2025\n(مدققة)", "30 سبتمبر 2026\n(داخلية معدلة)"]
    if show_fx:
        cols.append("معادلة الاحتساب")
    D = "—"

    def row(t, label, vals, fx=""):
        v = list(vals)
        if show_fx:
            v.append(fx)
        return (t, label, v)

    def y4(hist, cur):
        return [hist[0], hist[1], hist[2], cur]

    ann_note = "× 12÷9"
    rows = [
        ("section", "أولاً: مؤشرات الربحية والكفاءة التشغيلية (Profitability & Operating Margins)", []),
        row("pct", "1. هامش مجمل الربح للمشاريع (Gross Profit Margin %)", y4([15.45, 17.50, 15.89], r["gm"][2]), "(الإيراد − تكلفة المشاريع) ÷ الإيراد × 100"),
        row("pct", "2. هامش الربح النقدي (EBITDA Margin %)", y4([17.83, 21.12, 21.04], r["ebitda_m"][2]), "(ربح التشغيل + الإهلاك) ÷ الإيراد × 100"),
        row("pct", "3. هامش الربح التشغيلي (EBIT %)", y4([12.33, 13.86, 12.51], r["ebit_m"][2]), "(مجمل الربح − المصروفات الإدارية) ÷ الإيراد × 100"),
        row("pct", "4. هامش الربح قبل الزكاة (EBT %)", y4([13.19, 16.67, 13.03], r["ebt_m"][2]), "صافي الربح قبل الزكاة ÷ الإيراد × 100"),
        row("pct", "5. هامش صافي الربح النهائي (Net Profit Margin %)", y4([11.63, 15.24, 11.71], r["net_m"][2]), "صافي الربح ÷ الإيراد × 100"),
        row("pct", "6. المصروفات العمومية والإدارية إلى الإيرادات (G&A %)", y4([3.11, 3.64, 3.38], r["ga_pct"][2]), "المصروفات العمومية والإدارية ÷ الإيراد × 100"),
        row("mult", "7. تغطية الأرباح التشغيلية لتكاليف التمويل (Interest Coverage)", y4([103.90, 78.46, 17.43], r["int_cov"][2]), "ربح التشغيل EBIT ÷ تكاليف التمويل"),

        ("section", "ثانياً: العائد للملاك وتحليل ديوبونت (Investor Returns & DuPont)", []),
        row("pct", "8. العائد على حقوق الملكية (ROE %)", y4([19.73, 26.52, 17.63], r["roe"][2]), f"(صافي الربح {ann_note}) ÷ حقوق الملكية × 100"),
        row("pct", "9. العائد على إجمالي الأصول (ROA %)", y4([11.99, 16.56, 12.06], r["roa"][2]), f"(صافي الربح {ann_note}) ÷ إجمالي الأصول × 100"),
        row("pct", "10. العائد على رأس المال المستثمر (ROIC %)", y4([31.20, 29.98, 20.94],
            _div(M["ebit"][2] * ANN, bs["equity"][2] + bs["debt"][2] - bs["cash"][2], 100)),
            f"(EBIT {ann_note}) ÷ (حقوق الملكية + القروض − النقد) × 100"),
        row("pct", "11. العائد على رأس المال العامل طويل الأجل (ROCE %)", y4([19.85, 20.80, 17.42],
            _div(M["ebit"][2] * ANN, bs["assets"][2] - bs["cl"][2], 100)), f"(EBIT {ann_note}) ÷ (إجمالي الأصول − الخصوم المتداولة) × 100"),
        row("pct", "12. العائد على رأس المال المدفوع (25 مليون ريال %)", y4([130.65, 176.04, 139.97],
            _div(M["net"][2] * ANN, 25000000.0, 100)), f"(صافي الربح {ann_note}) ÷ رأس المال المدفوع × 100"),
        row("pct", "13. [DuPont-1] هامش صافي الربح %", y4([11.63, 15.24, 11.71], r["net_m"][2]), "صافي الربح ÷ الإيراد × 100"),
        row("mult", "14. [DuPont-2] معدل دوران إجمالي الأصول", y4([1.03, 1.09, 1.03], r["asset_turn"][2]), f"(الإيراد {ann_note}) ÷ إجمالي الأصول"),
        row("mult", "15. [DuPont-3] مضاعف حقوق الملكية", y4([1.65, 1.60, 1.46], r["eq_mult"][2]), "إجمالي الأصول ÷ حقوق الملكية"),

        ("section", "ثالثاً: السيولة وجودة التدفقات النقدية (Liquidity & Cash Flow Quality)", []),
        row("subtotal", "16. صافي رأس المال العامل (ريال)", y4([66805303, 47934184, 67749766], r["nwc"][2]), "الأصول المتداولة − الخصوم المتداولة"),
        row("mult", "17. نسبة التداول (Current Ratio) [المعيار الآمن > 1.5x]", y4([1.81, 1.65, 1.90], r["cr"][2]), "الأصول المتداولة ÷ الخصوم المتداولة"),
        row("pct", "18. نسبة التداول كمؤشر مئوي (%)", y4([180.60, 165.38, 189.68], r["cr"][2] * 100), "(الأصول المتداولة ÷ الخصوم المتداولة) × 100"),
        row("mult", "19. نسبة السيولة السريعة (Quick Ratio)", y4([1.56, 1.31, 1.59], r["qr"][2]), "(الأصول المتداولة − المخزون − المدفوعات المقدمة) ÷ الخصوم المتداولة"),
        row("pct", "20. النقدية + الصناديق الاستثمارية إلى الالتزامات المتداولة %", y4([66.40, 64.74, 67.91], r["cash_afs_ratio"][2]), "(النقد + الاستثمارات المتاحة للبيع) ÷ الخصوم المتداولة × 100"),
        row("pct", "21. تحويل EBITDA إلى تدفق تشغيلي فعلي (Cash Conversion %)", y4([148.40, 89.08, 44.12], r["conv"][2]), "صافي التدفق التشغيلي ÷ EBITDA × 100"),
        row("subtotal", "22. التدفق النقدي التشغيلي الحر (ريال)", y4([42110000, 33460120, 6996764], r["fcf"][2]), "التدفق التشغيلي − الإنفاق الرأسمالي + متحصلات بيع الأصول"),

        ("section", "رابعاً: الرفع المالي والملاءة (Leverage & Solvency)", []),
        row("pct", "23. إجمالي الالتزامات إلى حقوق الملكية %", y4([64.59, 60.15, 46.17], r["de"][2]), "إجمالي الالتزامات ÷ حقوق الملكية × 100"),
        row("pct", "24. إجمالي الالتزامات إلى إجمالي الأصول %", y4([39.24, 37.56, 31.59], r["debt_assets"][2]), "إجمالي الالتزامات ÷ إجمالي الأصول × 100"),
        row("pct", "25. القروض البنكية إلى حقوق الملكية %", y4([0.00, 0.00, 5.39], r["bank_eq"][2]), "القروض قصيرة الأجل ÷ حقوق الملكية × 100"),
        row("mult", "26. القروض البنكية إلى EBITDA السنوي", y4([0.00, 0.00, 0.17], r["debt_ebitda"][2]), f"القروض ÷ (EBITDA {ann_note})"),
        row("subtotal", "27. صافي المركز النقدي بعد القروض (ريال)", y4([55014728, 32470427, 20457743], r["net_cash"][2]), "النقد − القروض البنكية"),

        ("section", "خامساً: كفاءة التحصيل والدورة النقدية (Working Capital & Collection Days)", []),
        row("days", "28. فترة تحصيل الذمم المفوترة (Billed DSO)", y4([82, 77, 107], ctx["dso_billed_26"]), "(المدينون التجاريون ÷ الإيراد) × 273.75 يوماً"),
        row("days", "29. فترة التحصيل الشاملة مع الإيراد المستحق (Total DSO)", y4([82, 77, 107], ctx["dso_total_26"]), "((المدينون + الإيراد المستحق) ÷ الإيراد) × 273.75"),
        row("days", "30. فترة الاحتفاظ بالمخزون (DIO)", y4([2, 2, 2], ctx["dio_26"]), "(المخزون ÷ تكلفة المشاريع) × 273.75"),
        row("days", "31. فترة سداد الموردين ومقاولي الباطن (DPO)", y4([3, 5, 4], ctx["dpo_26"]), "(الدائنون التجاريون ÷ تكلفة المشاريع) × 273.75"),
        row("total", "32. دورة التحول النقدي (Cash Conversion Cycle)", [81, 74, 104, int(round(ctx["ccc_26"]))], "DSO الشامل + DIO − DPO"),

        ("section", "سادساً: هيكل تكلفة المشاريع منسوبة للإيرادات (Cost Structure %)", []),
        row("pct", "33. الرواتب والأجور وملحقاتها إلى الإيرادات %", y4([47.20, 47.34, 47.21], _div(ctx["cogs_26"][0], ctx["rev_26"], 100)), "تكلفة الرواتب ÷ الإيراد × 100"),
        row("pct", "34. مقاولو الباطن والمواد المباشرة إلى الإيرادات %", y4([13.80, 11.41, 11.25], _div(ctx["cogs_26"][2] + ctx["cogs_26"][3], ctx["rev_26"], 100)), "(تكلفة المواد + مقاولي الباطن) ÷ الإيراد × 100"),
        row("pct", "35. صيانة وتشغيل وإهلاك الأسطول والمعدات إلى الإيرادات %", y4([11.50, 14.94, 17.55], _div(ctx["cogs_26"][1] + ctx["cogs_26"][5], ctx["rev_26"], 100)), "(صيانة السيارات والمعدات + الاستهلاك) ÷ الإيراد × 100"),

        ("section", "سابعاً: النمو (Growth) - 2026 مسنّن إلى 12 شهراً", []),
        row("pct", "36. نمو الإيراد %", [D, D, r["g_rev"][1], r["g_rev"][2]], "(إيراد السنة ÷ إيراد السنة السابقة − 1) × 100"),
        row("pct", "37. نمو الربح النقدي EBITDA %", [D, D, r["g_ebitda"][1], r["g_ebitda"][2]], "(EBITDA السنة ÷ EBITDA السابقة − 1) × 100"),
        row("pct", "38. نمو صافي الربح %", [D, D, r["g_net"][1], r["g_net"][2]], "(صافي ربح السنة ÷ صافي الربح السابق − 1) × 100"),

        ("section", "ثامناً: الاستثمار والتدفق النقدي وهيكل الأصول (Capex & Asset Structure)", []),
        row("pct", "39. هامش التدفق النقدي التشغيلي %", [D] + r["ocf_m"], "صافي التدفق التشغيلي ÷ الإيراد × 100"),
        row("pct", "40. الإنفاق الرأسمالي إلى الإيراد %", [D] + r["capex_rev"], "الإنفاق الرأسمالي ÷ الإيراد × 100"),
        row("mult", "41. الإنفاق الرأسمالي إلى الإهلاك (إعادة الاستثمار)", [D] + r["capex_dep"], "الإنفاق الرأسمالي ÷ مصروف الإهلاك"),
        row("mult", "42. تغطية التدفق التشغيلي للإنفاق الرأسمالي", [D] + r["ocf_capex"], "صافي التدفق التشغيلي ÷ الإنفاق الرأسمالي"),
        row("mult", "43. نسبة النقدية (Cash Ratio)", [D] + r["cash_ratio"], "النقد وما في حكمه ÷ الخصوم المتداولة"),
        row("mult", "44. دوران الأصول الثابتة", [D] + r["fa_turn"], f"(الإيراد {ann_note}) ÷ الممتلكات والآلات والمعدات"),
        row("pct", "45. الأصول الثابتة إلى إجمالي الأصول %", [D] + r["fa_assets"], "الممتلكات والآلات والمعدات ÷ إجمالي الأصول × 100"),
        row("pct", "46. حقوق الملكية إلى إجمالي الأصول %", [D] + r["eq_assets"], "حقوق الملكية ÷ إجمالي الأصول × 100"),
        row("pct", "47. رأس المال العامل إلى الإيراد %", [D] + r["nwc_rev"], f"رأس المال العامل ÷ (الإيراد {ann_note}) × 100"),
        row("pct", "48. التوزيعات المسددة إلى صافي الربح %", [D] + r["payout"], "توزيعات الأرباح المسددة ÷ صافي الربح × 100"),
        row("mult", "49. صافي الدين إلى EBITDA (سالب = صافي نقد)", [D] + r["net_debt_ebitda"], f"(القروض − النقد) ÷ (EBITDA {ann_note})"),
        row("pct", "50. الإيراد المستحق (WIP) إلى الإيراد %", [D] + r["accrued_rev"], "الإيراد المستحق غير المفوتر ÷ الإيراد × 100"),
    ]

    O = M["ops"]
    rows += [
        ("section", "تاسعاً: التنفيذ والفوترة والعمالة 2026 (ملخص المواقع - أكتوبر 2026)", []),
        row("pct", "51. نسبة الفوترة من التنفيذ %", [D, D, D, O["bill_pct"]], "المفوتر ÷ إجمالي التنفيذ × 100"),
        row("pct", "52. تنفيذ المتاح من الإسناد %", [D, D, D, O["exec_vs_assign"]], "(التنفيذ − عقد بنسبة %) ÷ (افتتاحي غير منفذ + إسناد جديد) × 100"),
        row("mult", "53. تغطية الأعمال المتبقية (أشهر)", [D, D, D, O["backlog_months"]], "المتبقي غير المنفذ ÷ (تنفيذ 2026 ÷ 9 أشهر)"),
        row("mult", "54. المنفذ غير المفوتر بالأشهر", [D, D, D, O["wip_months"]], "المنفذ المتاح للفوترة ÷ (تنفيذ 2026 ÷ 9 أشهر)"),
        row("subtotal", "55. عدد العمالة (متوسط 2026)", [D, D, D, f"{M['hc']:,.0f}"], "مجموع عمالة المواقع"),
        row("pct", "56. نسبة السعودة %", [D, D, D, M["hc_saudi_pct"]], "العمالة السعودية ÷ إجمالي العمالة × 100"),
        row("subtotal", "57. إيراد الفرد السنوي (ريال)", [D, D, D, M["rev_per_head"]], f"(الإيراد {ann_note}) ÷ عدد العمالة"),
        row("subtotal", "58. تكلفة الرواتب للفرد السنوية (ريال)", [D, D, D, M["sal_per_head"]], f"(تكلفة الرواتب {ann_note}) ÷ عدد العمالة"),
    ]

    # تحويل مؤشرات الأعوام الثلاثة إلى صيغ نصية آمنة (nan إلى —)
    clean = []
    for item in rows:
        t, lbl, vals = item
        vals = [("—" if (isinstance(x, float) and np.isnan(x)) else x) for x in vals]
        # الأرقام الخام للأعوام الأولى تحولت من مؤشرات r (قائمة من 3)، نضمن عدد الأعمدة
        clean.append((t, lbl, vals))
    # القيم المضافة بصيغة [D]+list(3) تنتج 4 قيم صحيحة
    st.table(build_styled_table(clean, cols, formula_col="معادلة الاحتساب" if show_fx else None))

    st.markdown("---")
    st.markdown("### ملاحظات منهجية المؤشرات:")
    st.markdown("""
    * سُنّنت العوائد ومعدلات الدوران والنمو لعام 2026 (× 12 ÷ 9) لتوحيد أساس المقارنة مع السنوات الكاملة، أما الهوامش والنسب بين بنود القائمة نفسها فلا تتأثر بقصر الفترة.
    * مؤشرات 2023 وما قبلها لبعض البنود مدخلة من التقارير المدققة، والمؤشرات المضافة (36 إلى 58) تُحسب من قوائم 2024 و2025 و2026 فقط.
    * المؤشرات 51 إلى 58 من ملخص المواقع (أكتوبر 2026) وتخص 2026 وحدها.
    """)
