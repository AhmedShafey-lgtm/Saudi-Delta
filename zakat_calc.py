# zakat_calc.py
# حاسبة الزكاة وضريبة الدخل للشركة المختلطة (سعودي / أجنبي) وفق اللائحة التنفيذية لجباية الزكاة (1445هـ)
# مبنية على القوائم المالية في المنصة، مع إمكانية تعديل أي بند وإضافة بنود يدوية،
# وجداول مرجعية: حركة المخصصات، الإهلاك الضريبي، الضريبة المؤجلة، وخيار اعتماد النتيجة في القوائم.

import streamlit as st
import pandas as pd
import numpy as np

CSS = """
<style>
    .zk-note { direction: rtl; text-align: right; background:#FFF7E0; border-right:4px solid #F59E0B;
               color:#7A4B00; padding:8px 12px; border-radius:6px; font-size:0.95rem; margin:6px 0; }
    .zk-fx { direction: rtl; text-align: right; font-size:0.9rem; color:#0B2A6F; background:#EAF1FF;
             border-right:3px solid #1E3A8A; padding:4px 10px; border-radius:4px; font-weight:600; margin:4px 0 8px 0; }
    .zk-title { direction: rtl; text-align: right; background: linear-gradient(90deg,#1E3A8A,#3B5FC4); color:#fff;
                padding:9px 14px; border-radius:6px; margin:18px 0 8px 0; font-weight:700; font-size:1.1rem; }
</style>
"""

ADD, DED, EXC = "إضافة للوعاء", "حسم من الوعاء", "غير مشمول"
PLUS, MINUS = "يضاف للربح", "يخصم من الربح"

BS = {
    "capital": [25000000, 25000000, 25000000],
    "reserve": [8833551, 8833551, 8833551],
    "retained": [132148383, 164649861, 162616261],
    "provisions": [21096296, 19909421, 16379994],
    "eosb": [26516081, 16099000, 13994264],
    "loans": [0, 10701784, 16518837],
    "deferred_rev": [32133523, 14697741, 0],
    "ppe": [115314870, 109582482, 112931800],
    "adv_ppe": [1759631, 2850850, 2850850],
    "inv_prop": [12180000, 13947604, 13947604],
    "afs": [15000000, 20142380, 25142380],
    "dta": [309330, 309330, 309330],
}
YEARS = ["2024", "2025", "2026 (9 أشهر حتى 30 سبتمبر)"]
DAYS = [366, 365, 273]
REVAL = [6287500.0, 1767604.0, 0.0]
DIVS = [39871858.0, 15000000.0, 2000000.0]
CAPEX = [19915434.0, 21048366.0, 24712273.0]
PROCEEDS = [821614.0, 1392260.0, 5851603.0]
GAIN_PPE = [125419.0, 1256086.0, 3228647.0]
# حركة المخصصات (من قائمة التدفقات والمركز المالي): المكوّن، المستخدم
PROV_MOVE = {
    "prov": [(996000.0, 0.0), (0.0, 1186875.0), (0.0, 3529430.0)],
    "eosb": [(3173886.0, 4526793.0), (4932000.0, 2841250.0), (3987416.0, 6092147.0)],
}
PROV_OPEN = {"prov": [20100296.0, 21096296.0, 19909421.0], "eosb": [27868988.0, 26516081.0, 16099000.0]}


def _n(v):
    try:
        v = float(v)
        return 0.0 if np.isnan(v) else v
    except Exception:
        return 0.0


def _fmt(v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return ""
    if isinstance(v, (int, float, np.floating, np.integer)):
        return f"({abs(v):,.0f})" if v < 0 else f"{v:,.0f}"
    return str(v)


def _title(t):
    st.markdown(f'<div class="zk-title">{t}</div>', unsafe_allow_html=True)


def _show(df, tint_col=None):
    """عرض جدول منسق: خط كبير، أرقام بفواصل وأقواس للسالب، وتلوين حسب المعالجة."""
    if df is None or len(df) == 0:
        return
    shown = df.copy()
    for c in shown.columns:
        if pd.api.types.is_numeric_dtype(shown[c]) and shown[c].dtype != bool:
            shown[c] = shown[c].map(_fmt)
        elif shown[c].dtype == bool:
            shown[c] = shown[c].map(lambda x: "نعم" if x else "لا")
    colors = {ADD: "#E8F8EE", DED: "#FDE8E8", EXC: "#F1F5F9", PLUS: "#E8F8EE", MINUS: "#FDE8E8"}

    def sty(row):
        bg = colors.get(row.get(tint_col, ""), "#FFFFFF") if tint_col else "#FFFFFF"
        return [f"background-color: {bg}; color: #111827; font-size: 1.08rem;"] * len(row)

    s = shown.style.apply(sty, axis=1)
    try:
        s = s.hide(axis="index")
    except Exception:
        pass
    st.table(s)


def _sum(df, col, types, amount="المبلغ"):
    if df is None or len(df) == 0:
        return 0.0
    m = df[col].isin(types)
    return float(pd.to_numeric(df.loc[m, amount], errors="coerce").fillna(0).sum())


def _editor(df, key, extra_cfg=None):
    cfg = {"المبلغ": st.column_config.NumberColumn("المبلغ", format="%.0f", width="medium")}
    if extra_cfg:
        cfg.update(extra_cfg)
    return st.data_editor(df, num_rows="dynamic", use_container_width=True, hide_index=True, key=key, column_config=cfg)


def render_zakat(ctx, build_styled_table):
    st.markdown(CSS, unsafe_allow_html=True)
    st.subheader("🧮 حاسبة الزكاة وضريبة الدخل (شركة مختلطة: سعودي / أجنبي)")
    st.markdown(
        '<div class="zk-note">⚠️ الحاسبة تقديرية لأغراض التخطيط والمخصصات، وتستند إلى اللائحة التنفيذية لجباية الزكاة '
        '(سارية على السنوات المالية التي تبدأ من 1 يناير 2024) وإلى نظام ضريبة الدخل. '
        'تقدَّم الإقرارات الفعلية بعد مراجعة المستشار الزكوي، وتُراجع تعديلات الهيئة اللاحقة (ومنها تعديلات يونيو 2025 '
        'المتعلقة بضوابط الحد الأدنى والأعلى للوعاء) قبل الاعتماد. لتعديل أي بند أو إضافة بند جديد افتح قسم "✏️ تعديل".</div>',
        unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        year = st.selectbox("السنة / الفترة:", YEARS, index=2, key="zk_year")
    yi = YEARS.index(year)
    with c2:
        saudi = st.number_input("نسبة الملكية السعودية/الخليجية %", value=75.0, min_value=0.0, max_value=100.0, step=1.0, key="zk_saudi")
    foreign = 100.0 - saudi
    with c3:
        days = st.number_input("عدد أيام الفترة", value=DAYS[yi], min_value=1, max_value=732, step=1, key=f"zk_days_{yi}")
    with c4:
        basis = st.selectbox("تقويم السنة المالية:", ["ميلادية (بالأيام ÷ 354)", "هجرية (2.5% كاملة)"], key="zk_cal")
    rate = 2.5 * days / 354.0 if basis.startswith("ميلادية") else 2.5
    st.markdown(f'<div class="zk-fx">معدل الزكاة = 2.5% × (عدد الأيام ÷ 354) = <b>{rate:.4f}%</b> | ضريبة الدخل على الحصة الأجنبية = 20% '
                f'| الحصة الأجنبية = {foreign:.1f}%</div>', unsafe_allow_html=True)
    if yi == 2:
        st.markdown('<div class="zk-note">فترة 2026 تغطي 9 أشهر والحساب تقدير للمخصص بالتناسب؛ الفترات الأقل من 354 يوماً لا تخضع للزكاة '
                    'في نهاية النشاط، فيُحسب الاستحقاق النهائي على السنة المالية الكاملة.</div>', unsafe_allow_html=True)

    ebt = [ctx["ebt_24"], ctx["ebt_25"], ctx["ebt_26_a"]][yi]
    net_book = [ctx["net_24"], ctx["net_25"], ctx["net_26_a"]][yi]
    cur_profit = net_book if yi == 2 else 0.0
    ca_ = [121256039, 143292694, ctx["tot_ca_26_a"]][yi]
    cl_ = [73321855, 75542928, ctx["cl_26"]][yi]
    assets = [265819870, 290125340, ctx["tot_assets_26_a"]][yi]
    booked = -[ctx["zakat_tax_24"], ctx["zakat_tax_25"], ctx["zakat_tax_26"]][yi]
    dta_book = [309330.0, 309330.0, ctx["dta_26"]][yi]

    # حاويات لترتيب العرض: 1، 2، النتيجة، ثم المراجع في أسفل الصفحة
    box1, box2, box_res, box_ref = st.container(), st.container(), st.container(), st.container()

    # ---------- 1) تعديل صافي الربح ----------
    with box1:
        _title("1️⃣ تعديل صافي الربح المحاسبي إلى صافي الربح المعدل (للزكاة)")
        adj_default = pd.DataFrame([
            {"البند": "أرباح إعادة تقييم عقارات استثمارية (غير محققة)", "المبلغ": REVAL[yi], "المعالجة": MINUS, "ملاحظة": "غير محققة"},
            {"البند": "مصروفات غير مقبولة (غرامات وجزاءات ومخالفات)", "المبلغ": 0.0, "المعالجة": PLUS, "ملاحظة": "أدخل المبلغ"},
            {"البند": "مصروفات مع جهات مرتبطة تتجاوز سعر السوق", "المبلغ": 0.0, "المعالجة": PLUS, "ملاحظة": "تسعير المعاملات"},
            {"البند": "تبرعات وضيافة غير مقبولة", "المبلغ": 0.0, "المعالجة": PLUS, "ملاحظة": ""},
            {"البند": "ديون معدومة غير مستوفية للشروط", "المبلغ": 0.0, "المعالجة": PLUS, "ملاحظة": "المادة 65"},
        ])
        with st.expander("✏️ تعديل أو إضافة بنود تعديل الربح"):
            adj = _editor(adj_default, f"zk_adj_{yi}", {"المعالجة": st.column_config.SelectboxColumn("المعالجة", options=[PLUS, MINUS, EXC], required=True)})
        _show(adj, "المعالجة")
    add_back = _sum(adj, "المعالجة", [PLUS])
    deduct = _sum(adj, "المعالجة", [MINUS])
    adj_profit = ebt + add_back - deduct
    diff = adj_profit - net_book

    # ---------- 2) بنود الوعاء ----------
    b = {k: v[yi] for k, v in BS.items()}
    b["dta"] = dta_book
    with box2:
        _title("2️⃣ بنود الوعاء الزكوي (من القوائم المالية بالمنصة)")
        rows = [
            ("رأس المال المدفوع", b["capital"], ADD, "حقوق الملكية"),
            ("الاحتياطي النظامي", b["reserve"], ADD, "حقوق الملكية"),
            ("الأرباح المبقاة", b["retained"], ADD, "حقوق الملكية"),
            ("ربح الفترة الجارية (2026)", cur_profit, ADD, "حقوق الملكية"),
            ("المخصصات (إخلاء مشاريع ومكافآت)", b["provisions"], ADD, "المادة 24: تضاف كحقوق ملكية"),
            ("التزامات المزايا المحددة (نهاية الخدمة)", b["eosb"], ADD, "التزام غير متداول بحد الأصول المحسومة"),
            ("قروض وتسهيلات قصيرة الأجل", b["loans"], EXC, "تضاف إذا مولت أصولاً ثابتة"),
            ("إيرادات مؤجلة / دفعات مقدمة من العميل", b["deferred_rev"], EXC, "التزام عقد: يضاف إن كان غير متداول"),
            ("الممتلكات والآلات والمعدات، صافي", b["ppe"], DED, "المادة 26"),
            ("دفعات مقدمة لشراء ممتلكات ومعدات", b["adv_ppe"], DED, "أصل غير متداول"),
            ("عقارات استثمارية (أرض)", b["inv_prop"], DED, "تحسم إن لم تكن للمتاجرة"),
            ("استثمارات متاحة للبيع (صناديق)", b["afs"], DED, "المادة 45 بشروط"),
            ("أصول ضريبية مؤجلة", b["dta"], DED, "المادة 26"),
        ]
        zdf = pd.DataFrame([{"البند": r[0], "المبلغ": float(r[1]), "المعالجة": r[2], "ملاحظة": r[3]} for r in rows])
        with st.expander("✏️ تعديل أو إضافة بنود الوعاء"):
            zed = _editor(zdf, f"zk_base_{yi}", {"المعالجة": st.column_config.SelectboxColumn("المعالجة", options=[ADD, DED, EXC], required=True)})
        _show(zed, "المعالجة")
    names = zed["البند"].astype(str)
    is_liab = names.str.contains("التزامات|قروض|مؤجلة|دفعات مقدمة من العميل", regex=True) & ~names.str.contains("ضريبية مؤجلة")
    amt = pd.to_numeric(zed["المبلغ"], errors="coerce").fillna(0)
    add_equity = float(amt[(zed["المعالجة"] == ADD) & ~is_liab].sum())
    add_liab_raw = float(amt[(zed["المعالجة"] == ADD) & is_liab].sum())
    deductions = float(amt[zed["المعالجة"] == DED].sum())
    add_liab = min(add_liab_raw, deductions)
    excess_cl = max(0.0, cl_ - ca_)

    # ---------- المراجع (أسفل الصفحة) ----------
    with box_ref:
        st.markdown("---")
        st.markdown("## 📚 الجداول المرجعية للتعديلات")
        # ---- أ) حركة المخصصات ----
        _title("أ) حركة المخصصات (تؤثر على ربح ضريبة الدخل للشريك الأجنبي)")
        pm = pd.DataFrame([
            {"المخصص": "مخصص إخلاء مشاريع ومكافآت", "الرصيد الافتتاحي": PROV_OPEN["prov"][yi], "المكوَّن": PROV_MOVE["prov"][yi][0],
             "المستخدم": PROV_MOVE["prov"][yi][1], "الرصيد الختامي": float(BS["provisions"][yi]), "يخضع لتعديل ضريبي": True},
            {"المخصص": "مخصص نهاية الخدمة (مزايا محددة)", "الرصيد الافتتاحي": PROV_OPEN["eosb"][yi], "المكوَّن": PROV_MOVE["eosb"][yi][0],
             "المستخدم": PROV_MOVE["eosb"][yi][1], "الرصيد الختامي": float(BS["eosb"][yi]), "يخضع لتعديل ضريبي": True},
        ])
        with st.expander("✏️ تعديل حركة المخصصات"):
            pme = st.data_editor(pm, num_rows="dynamic", use_container_width=True, hide_index=True, key=f"zk_prov_{yi}",
                                 column_config={c: st.column_config.NumberColumn(c, format="%.0f") for c in
                                                ["الرصيد الافتتاحي", "المكوَّن", "المستخدم", "الرصيد الختامي"]})
        pmo = pme.copy()
        for c in ["الرصيد الافتتاحي", "المكوَّن", "المستخدم", "الرصيد الختامي"]:
            pmo[c] = pd.to_numeric(pmo[c], errors="coerce").fillna(0.0)
        pmo["تسويات أخرى (إعادة قياس بالفرق)"] = pmo["الرصيد الختامي"] - (pmo["الرصيد الافتتاحي"] + pmo["المكوَّن"] - pmo["المستخدم"])
        pmo["الأثر الضريبي على الربح"] = np.where(pmo["يخضع لتعديل ضريبي"].fillna(False).astype(bool), pmo["المكوَّن"] - pmo["المستخدم"], 0.0)
        _show(pmo)
        prov_effect = float(pmo["الأثر الضريبي على الربح"].sum())
        st.markdown('<div class="zk-fx">الأثر الضريبي = المخصص المكوَّن − المخصص المستخدم. المكوَّن لا يُخصم ضريبياً إلا عند الاستخدام؛ '
                    'فيُضاف للربح عند التكوين ويُخصم عند الصرف. التسويات الأخرى (إعادة قياس نهاية الخدمة) تُسجل في الدخل الشامل ولا أثر ضريبي لها.</div>',
                    unsafe_allow_html=True)

        # ---- ب) الإهلاك الضريبي ----
        _title("ب) جدول احتساب الإهلاك لأغراض الضريبة (طريقة الرصيد المتناقص)")
        acc_dep = [ctx["dep_total_24"], ctx["dep_total_25"], ctx["dep_total_26"]][yi]
        prior_capex = CAPEX[yi - 1] if yi > 0 else 0.0
        prior_proc = PROCEEDS[yi - 1] if yi > 0 else 0.0
        open_ppe = float(BS["ppe"][yi - 1]) if yi > 0 else float(BS["ppe"][0]) - CAPEX[0] + acc_dep + PROCEEDS[0]
        dd = pd.DataFrame([
            {"الفئة": "مباني ثابتة", "النسبة %": 5.0, "الرصيد الافتتاحي": 0.0, "النصف المؤجل من العام السابق": 0.0, "إضافات العام": 0.0, "متحصلات الاستبعاد": 0.0},
            {"الفئة": "آلات ومعدات ومركبات وبرامج", "النسبة %": 25.0, "الرصيد الافتتاحي": round(open_ppe * 0.95),
             "النصف المؤجل من العام السابق": round(0.5 * (prior_capex - prior_proc) * 0.95),
             "إضافات العام": round(CAPEX[yi] * 0.95), "متحصلات الاستبعاد": round(PROCEEDS[yi])},
            {"الفئة": "أصول أخرى (أثاث وتجهيزات)", "النسبة %": 10.0, "الرصيد الافتتاحي": round(open_ppe * 0.05),
             "النصف المؤجل من العام السابق": round(0.5 * (prior_capex - prior_proc) * 0.05),
             "إضافات العام": round(CAPEX[yi] * 0.05), "متحصلات الاستبعاد": 0.0},
        ])
        with st.expander("✏️ تعديل الأصول الضريبية (الأرصدة والنسب والإضافات)"):
            dde = st.data_editor(dd, num_rows="dynamic", use_container_width=True, hide_index=True, key=f"zk_dep_{yi}",
                                 column_config={c: st.column_config.NumberColumn(c, format="%.0f") for c in dd.columns if c != "الفئة"})
        ddo = dde.copy()
        for c in ddo.columns:
            if c != "الفئة":
                ddo[c] = pd.to_numeric(ddo[c], errors="coerce").fillna(0.0)
        factor = min(days / 365.0, 1.0)
        base_pool = ddo["الرصيد الافتتاحي"] + ddo["النصف المؤجل من العام السابق"] + 0.5 * ddo["إضافات العام"] - 0.5 * ddo["متحصلات الاستبعاد"]
        ddo["الإهلاك الضريبي"] = (base_pool.clip(lower=0) * ddo["النسبة %"] / 100.0 * factor).round(0)
        ddo["الرصيد الختامي الضريبي"] = (ddo["الرصيد الافتتاحي"] + ddo["النصف المؤجل من العام السابق"] + ddo["إضافات العام"]
                                         - ddo["متحصلات الاستبعاد"] - ddo["الإهلاك الضريبي"])
        _show(ddo)
        tax_dep = float(ddo["الإهلاك الضريبي"].sum())
        tax_wdv = float(ddo["الرصيد الختامي الضريبي"].sum())
        dep_diff = acc_dep - tax_dep
        g1, g2, g3 = st.columns(3)
        g1.metric("الإهلاك المحاسبي", f"{acc_dep:,.0f} ريال")
        g2.metric("الإهلاك الضريبي", f"{tax_dep:,.0f} ريال")
        g3.metric("الفرق (يضاف للربح الضريبي)", f"{dep_diff:,.0f} ريال")
        st.markdown('<div class="zk-fx">الإهلاك الضريبي = (الرصيد الافتتاحي + النصف المؤجل من إضافات العام السابق + 50% من إضافات العام − 50% من متحصلات الاستبعاد) × النسبة × (الأيام ÷ 365). '
                    'النسب: المباني 5%، الآلات والمعدات والمركبات والبرامج 25%، الأصول الأخرى 10%. لأغراض الزكاة يجوز الإهلاك بالقسط الثابت، '
                    'وأرصدة الجدول افتراضية تقديرية (95% آلات و5% أخرى) فعدّلها حسب سجل الأصول الضريبي.</div>', unsafe_allow_html=True)

        # ---- ج) الضريبة المؤجلة ----
        _title("ج) جدول الضريبة المؤجلة (على حصة الشريك الأجنبي)")
        dt_rate = st.number_input("معدل الضريبة المؤجلة % (20% × الحصة الأجنبية)", value=round(20.0 * foreign / 100.0, 4), min_value=0.0,
                                  max_value=20.0, step=0.5, key=f"zk_dtrate_{yi}")
        dtd = pd.DataFrame([
            {"البند": "ممتلكات وآلات ومعدات (محاسبي مقابل ضريبي)", "طبيعة البند": "أصل", "القيمة الدفترية": float(b["ppe"]), "الأساس الضريبي": round(tax_wdv)},
            {"البند": "التزامات نهاية الخدمة", "طبيعة البند": "التزام", "القيمة الدفترية": float(b["eosb"]), "الأساس الضريبي": 0.0},
            {"البند": "مخصص إخلاء مشاريع ومكافآت", "طبيعة البند": "التزام", "القيمة الدفترية": float(b["provisions"]), "الأساس الضريبي": 0.0},
            {"البند": "خسائر ضريبية مرحلة (اختياري)", "طبيعة البند": "التزام", "القيمة الدفترية": 0.0, "الأساس الضريبي": 0.0},
        ])
        with st.expander("✏️ تعديل أو إضافة بنود الضريبة المؤجلة"):
            dte = st.data_editor(dtd, num_rows="dynamic", use_container_width=True, hide_index=True, key=f"zk_dt_{yi}",
                                 column_config={"طبيعة البند": st.column_config.SelectboxColumn("طبيعة البند", options=["أصل", "التزام"], required=True),
                                                "القيمة الدفترية": st.column_config.NumberColumn("القيمة الدفترية", format="%.0f"),
                                                "الأساس الضريبي": st.column_config.NumberColumn("الأساس الضريبي", format="%.0f")})
        dto = dte.copy()
        dto["القيمة الدفترية"] = pd.to_numeric(dto["القيمة الدفترية"], errors="coerce").fillna(0.0)
        dto["الأساس الضريبي"] = pd.to_numeric(dto["الأساس الضريبي"], errors="coerce").fillna(0.0)
        dto["الفرق المؤقت"] = dto["القيمة الدفترية"] - dto["الأساس الضريبي"]
        sign = np.where(dto["طبيعة البند"] == "التزام", 1.0, -1.0)   # التزام: أصل ضريبي مؤجل، أصل: التزام ضريبي مؤجل
        dto["الضريبة المؤجلة (+ أصل / − التزام)"] = (dto["الفرق المؤقت"] * sign * dt_rate / 100.0).round(0)
        dto["النوع"] = np.where(dto["الضريبة المؤجلة (+ أصل / − التزام)"] >= 0, "أصل ضريبي مؤجل", "التزام ضريبي مؤجل")
        _show(dto)
        dt_net = float(dto["الضريبة المؤجلة (+ أصل / − التزام)"].sum())
        dta_adj = dt_net - dta_book
        h1, h2, h3 = st.columns(3)
        h1.metric("صافي الضريبة المؤجلة المحسوب", f"{dt_net:,.0f} ريال")
        h2.metric("المسجل في المركز المالي", f"{dta_book:,.0f} ريال")
        h3.metric("تسوية مطلوبة (+ دخل / − مصروف)", f"{dta_adj:,.0f} ريال")
        st.markdown('<div class="zk-fx">الضريبة المؤجلة = (القيمة الدفترية − الأساس الضريبي) × معدل الضريبة؛ للالتزامات يمثل الفرق أصلاً ضريبياً مؤجلاً، وللأصول التزاماً ضريبياً مؤجلاً. '
                    'يُعترف بالأصل المؤجل متى كان استرداده محتملاً من أرباح مستقبلية خاضعة.</div>', unsafe_allow_html=True)

    # ---------- حساب الوعاء ----------
    base_calc = add_equity + add_liab + excess_cl + diff - deductions
    eq_names = ["رأس المال المدفوع", "الاحتياطي النظامي", "الأرباح المبقاة", "ربح الفترة الجارية (2026)"]
    equity_end = float(amt[zed["البند"].isin(eq_names)].sum())
    max_base = equity_end + diff
    min_alt = max(0.0, assets - deductions) + diff
    base_final, rule = base_calc, "الوعاء المحسوب كما هو"
    if base_calc < adj_profit:
        base_final = min(min_alt, adj_profit) if min_alt > 0 else adj_profit
        rule = "طُبق الحد الأدنى (المادة 27): الوعاء أقل من صافي الربح المعدل"
    if max_base > 0 and base_final > max_base:
        base_final, rule = max_base, "طُبق الحد الأعلى (المادة 28): لا يتجاوز حقوق الملكية + فرق الربح"
    if base_final < 0 and adj_profit <= 0:
        base_final, rule = 0.0, "وعاء سالب وبلا ربح معدل: لا وعاء زكوي (المادة 27)"
    base_final = max(base_final, 0.0)
    zakat_full = base_final * rate / 100.0
    zakat_saudi = zakat_full * saudi / 100.0

    # ---------- ضريبة الدخل على الحصة الأجنبية ----------
    with box_res:
        _title("3️⃣ ضريبة الدخل على حصة الشريك الأجنبي ومدخلات إضافية")
        t1, t2, t3, t4 = st.columns(4)
        with t1:
            nol = st.number_input("خسائر ضريبية مرحلة (ريال)", value=0.0, min_value=0.0, step=100000.0, key=f"zk_nol_{yi}")
        with t2:
            wht = st.number_input("ضريبة الاستقطاع على توزيعات الأجنبي %", value=5.0, min_value=0.0, max_value=30.0, step=1.0, key="zk_wht")
        with t3:
            divs = st.number_input("التوزيعات (ريال)", value=float(DIVS[yi]), min_value=0.0, step=100000.0, key=f"zk_div_{yi}")
        with t4:
            gain_adj = st.number_input("أرباح بيع أصول تُستبعد من الربح الضريبي", value=float(GAIN_PPE[yi]), min_value=0.0, step=10000.0, key=f"zk_gain_{yi}")
        it_profit = adj_profit + prov_effect + dep_diff - gain_adj
        taxable_total = max(it_profit, 0.0)
        nol_used = min(nol, 0.25 * taxable_total)
        taxable_foreign = max(taxable_total - nol_used, 0.0) * foreign / 100.0
        income_tax = taxable_foreign * 0.20
        wht_amt = divs * foreign / 100.0 * wht / 100.0
        total_due = zakat_saudi + income_tax
        diff_booked = total_due - booked

        _title("4️⃣ نتيجة الاحتساب")
        spec = [
            ("section", "أ) صافي الربح المعدل للزكاة", []),
            ("item", "صافي الربح المحاسبي قبل الزكاة والضريبة", [ebt]),
            ("item", "يضاف: مصروفات غير مقبولة وتعديلات", [add_back]),
            ("item", "يخصم: إيرادات غير خاضعة / غير محققة", [-deduct]),
            ("subtotal", "صافي الربح المعدل (للزكاة)", [adj_profit]),
            ("item", "صافي الربح المحاسبي بعد الزكاة والضريبة", [net_book]),
            ("item", "فرق الربح المعدل عن الدفتري (يضاف للوعاء)", [diff]),
            ("section", "ب) الوعاء الزكوي", []),
            ("item", "حقوق الملكية والمخصصات", [add_equity]),
            ("item", f"الالتزامات غير المتداولة المضافة (بحد الأصول المحسومة: {add_liab_raw:,.0f})", [add_liab]),
            ("item", "الالتزامات المتداولة الزائدة على الأصول المتداولة", [excess_cl]),
            ("item", "فرق الربح المعدل عن الدفتري", [diff]),
            ("item", "يخصم: الأصول والاستثمارات المحسومة", [-deductions]),
            ("subtotal", "الوعاء الزكوي المحسوب", [base_calc]),
            ("item", "الحد الأدنى للوعاء (الربح المعدل)", [max(adj_profit, 0.0)]),
            ("item", "الحد الأعلى للوعاء (حقوق الملكية + فرق الربح)", [max_base]),
            ("total", "الوعاء الزكوي المعتمد", [base_final]),
            ("section", "ج) الربح الخاضع لضريبة الدخل (الحصة الأجنبية)", []),
            ("item", "صافي الربح المعدل (للزكاة)", [adj_profit]),
            ("item", "أثر حركة المخصصات (المكوَّن − المستخدم)", [prov_effect]),
            ("item", "فرق الإهلاك (المحاسبي − الضريبي)", [dep_diff]),
            ("item", "يستبعد: أرباح بيع الأصول", [-gain_adj]),
            ("subtotal", "الربح الضريبي قبل الخسائر المرحلة", [it_profit]),
            ("item", "يخصم: خسائر مرحلة مستخدمة (بحد 25% من الربح)", [-nol_used]),
            ("item", f"الربح الخاضع بحصة الأجنبي ({foreign:.0f}%)", [taxable_foreign]),
            ("section", "د) المستحق", []),
            ("item", f"الزكاة على كامل الوعاء بمعدل {rate:.4f}%", [zakat_full]),
            ("subtotal", f"الزكاة المستحقة على الحصة السعودية ({saudi:.0f}%)", [zakat_saudi]),
            ("subtotal", "ضريبة الدخل 20% على الحصة الأجنبية", [income_tax]),
            ("total", "إجمالي الزكاة والضريبة المستحقة", [total_due]),
            ("item", "المثبت دفترياً في قائمة الدخل", [booked]),
            ("subtotal", "الفرق (+ مخصص إضافي مطلوب / − زيادة في المخصص)", [diff_booked]),
            ("item", "ضريبة الاستقطاع على توزيعات الأجنبي (تسدد عند التوزيع)", [wht_amt]),
        ]
        st.table(build_styled_table(spec, ["البند", year]))
        st.caption(f"حالة الوعاء: {rule}")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("الوعاء الزكوي المعتمد", f"{base_final:,.0f} ريال")
        m2.metric("الزكاة (حصة سعودية)", f"{zakat_saudi:,.0f} ريال", f"المعدل {rate:.3f}%")
        m3.metric("ضريبة الدخل (حصة أجنبية)", f"{income_tax:,.0f} ريال")
        m4.metric("الفرق عن المثبت دفترياً", f"{diff_booked:,.0f} ريال", delta_color="inverse")
        if adj_profit > 0:
            st.markdown(f'<div class="zk-fx">العبء الفعلي = (الزكاة + الضريبة) ÷ صافي الربح المعدل = <b>{total_due / adj_profit * 100:.1f}%</b></div>',
                        unsafe_allow_html=True)

        # ---------- اعتماد النتيجة في القوائم ----------
        _title("5️⃣ اعتماد الزكاة والضريبة المحتسبة في القوائم المالية بالمنصة (فترة 2026)")
        a1, a2 = st.columns(2)
        with a1:
            apply_now = st.checkbox("✅ اعتماد الزكاة وضريبة الدخل (2026) في قائمة الدخل والمركز المالي والمؤشرات", value=False, key="zk_apply")
        with a2:
            apply_dt = st.checkbox("➕ تضمين تسوية الضريبة المؤجلة في الاعتماد", value=False, key="zk_apply_dt")
        if yi == 2:
            st.session_state["zk_cur_2026"] = float(total_due)
            st.session_state["zk_dta_adj_2026"] = float(dta_adj)
        used_cur, used_dta = ctx["ZK_CUR"], ctx["ZK_DTA"]
        if apply_now:
            st.markdown(f'<div class="zk-fx">معتمد حالياً في القوائم: زكاة وضريبة دخل {ctx["ZK_CUR"]:,.0f} ريال'
                        f'{" وتسوية ضريبة مؤجلة " + format(ctx["ZK_DTA"], ",.0f") + " ريال" if apply_dt else ""} (تُحمَّل كمصروف على الفترة وكمخصص في الخصوم المتداولة).</div>',
                        unsafe_allow_html=True)
        else:
            st.markdown('<div class="zk-note">الاعتماد غير مفعّل: القوائم المالية لا تتضمن زكاة أو ضريبة عن 2026. اختر السنة 2026 ثم فعّل الخيار ليجري تحميل المبلغ.</div>',
                        unsafe_allow_html=True)
        if yi == 2 and apply_now:
            want_dt = dta_adj if apply_dt else 0.0
            if abs(used_cur - total_due) > 1 or abs(used_dta - want_dt) > 1:
                st.rerun()

    st.markdown("---")
    st.markdown("### مرجع الأحكام المطبقة:")
    st.markdown(f"""
    * **الوعاء (المواد 23–29):** حقوق الملكية والمخصصات + الالتزامات غير المتداولة بحد الأصول المحسومة + فرق الربح المعدل عن الدفتري − الأصول والاستثمارات المحسومة.
    * **الحد الأدنى (المادة 27) والأعلى (المادة 28):** لا يقل الوعاء عن صافي الربح المعدل، ولا يزيد على حقوق الملكية في نهاية العام مضافاً إليها فرق الربح.
    * **المعدل (المادة 15):** 2.5% للسنة الهجرية، وللميلادية بالأيام: 2.5% ÷ 354 × عدد الأيام.
    * **الشركة المختلطة:** الزكاة على الحصة السعودية/الخليجية ({saudi:.0f}%) من الوعاء، وضريبة الدخل 20% على الحصة الأجنبية ({foreign:.0f}%) من الربح الضريبي، ويحدد توزيع الملكية في نهاية العام (المادة 13). الخسائر المرحلة بحد 25% من الربح، وضريبة الاستقطاع 5% على الأرباح الموزعة للأجنبي.
    * **ربح الزكاة وربح الضريبة:** الأول يقبل المخصصات المكوّنة والإهلاك المحاسبي (وتضاف المخصصات للوعاء)، أما ربح الضريبة فتُضاف إليه المخصصات عند تكوينها وتُخصم عند استخدامها، ويُستبدل الإهلاك المحاسبي بالضريبي.
    * **القروض والإيرادات المؤجلة:** غير مشمولة افتراضياً، وتحوّل إلى "إضافة" إذا مولت أصولاً ثابتة أو صُنفت التزاماً غير متداول.
    """)
