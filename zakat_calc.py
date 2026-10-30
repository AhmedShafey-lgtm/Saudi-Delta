# zakat_calc.py
# حاسبة الزكاة وضريبة الدخل للشركة المختلطة (سعودي / أجنبي) وفق اللائحة التنفيذية لجباية الزكاة (1445هـ)
# مبنية على القوائم المالية في المنصة، مع إمكانية تعديل أي بند وإضافة بنود يدوية.

import streamlit as st
import pandas as pd
import numpy as np

FX_CSS = """
<style>
    .zk-note { direction: rtl; text-align: right; background:#FFF7E0; border-right:4px solid #F59E0B;
               color:#7A4B00; padding:8px 12px; border-radius:6px; font-size:0.92rem; margin:6px 0; }
    .zk-fx { direction: rtl; text-align: right; font-size:0.82rem; color:#0B2A6F; background:#EAF1FF;
             border-right:3px solid #1E3A8A; padding:3px 8px; border-radius:4px; font-weight:600; margin:4px 0 8px 0; }
    .zk-title { direction: rtl; text-align: right; background: linear-gradient(90deg,#1E3A8A,#3B5FC4); color:#fff;
                padding:8px 14px; border-radius:6px; margin:16px 0 8px 0; font-weight:700; }
</style>
"""

ADD, DED, EXC = "إضافة للوعاء", "حسم من الوعاء", "غير مشمول"
PLUS, MINUS = "يضاف للربح", "يخصم من الربح"

# أرصدة المركز المالي (من التبويب الثالث): 2024، 2025، 30 سبتمبر 2026
BS = {
    "capital": [25000000, 25000000, 25000000],
    "reserve": [8833551, 8833551, 8833551],
    "retained": [132148383, 164649861, 162616261],
    "provisions": [21096296, 19909421, 16379994],
    "eosb": [26516081, 16099000, 13994264],
    "loans": [0, 10701784, 16518837],
    "deferred_rev": [32133523, 14697741, 0],
    "payables_accr": [3192368 + 14417100, 2878100 + 24830152, 1977811 + 23977533],
    "ppe": [115314870, 109582482, 112931800],
    "adv_ppe": [1759631, 2850850, 2850850],
    "inv_prop": [12180000, 13947604, 13947604],
    "afs": [15000000, 20142380, 25142380],
    "dta": [309330, 309330, 309330],
    "total_assets": [265819870, 290125340, None],
}
YEARS = ["2024", "2025", "2026 (9 أشهر حتى 30 سبتمبر)"]
DAYS = [366, 365, 273]
BOOKED = [4133419.0, 3939343.0, 0.0]
REVAL = [6287500.0, 1767604.0, 0.0]
DIVS = [39871858.0, 15000000.0, 2000000.0]


def _num(v):
    try:
        v = float(v)
        return 0.0 if np.isnan(v) else v
    except Exception:
        return 0.0


def _sum(df, col_type, types):
    if df is None or len(df) == 0:
        return 0.0
    m = df[col_type].isin(types)
    return float(pd.to_numeric(df.loc[m, "المبلغ"], errors="coerce").fillna(0).sum())


def render_zakat(ctx, build_styled_table):
    st.markdown(FX_CSS, unsafe_allow_html=True)
    st.subheader("🧮 حاسبة الزكاة وضريبة الدخل (شركة مختلطة: سعودي / أجنبي)")
    st.markdown(
        '<div class="zk-note">⚠️ الحاسبة تقديرية لأغراض التخطيط والمخصصات، وتستند إلى اللائحة التنفيذية لجباية الزكاة '
        '(قرار وزير المالية، سارية على السنوات المالية التي تبدأ من 1 يناير 2024) وإلى نظام ضريبة الدخل. '
        'تقدَّم الإقرارات الفعلية بعد مراجعة المستشار الزكوي، وتُراجع تعديلات الهيئة اللاحقة (ومنها تعديلات يونيو 2025 '
        'المتعلقة بضوابط الحد الأدنى والأعلى للوعاء) قبل الاعتماد. معالجة كل بند قابلة للتعديل أدناه.</div>',
        unsafe_allow_html=True)

    # ---------- المدخلات الأساسية ----------
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

    rate_full = 2.5
    rate = rate_full * days / 354.0 if basis.startswith("ميلادية") else rate_full
    st.markdown(f'<div class="zk-fx">معدل الزكاة المطبق = 2.5% × (عدد أيام الفترة ÷ 354) = <b>{rate:.4f}%</b> '
                f'| ضريبة الدخل على الحصة الأجنبية = 20% | حصة الأجنبي = {foreign:.1f}%</div>', unsafe_allow_html=True)
    if yi == 2:
        st.markdown('<div class="zk-note">فترة 2026 تغطي 9 أشهر، والحساب هنا تقدير للمخصص بالتناسب. '
                    'الفترات المالية الأقل من 354 يوماً لا تخضع للزكاة في نهاية النشاط وفق اللائحة، فيُحسب الاستحقاق النهائي على السنة المالية الكاملة.</div>',
                    unsafe_allow_html=True)

    # ---------- أرصدة الأرباح ----------
    ebt = [ctx["ebt_24"], ctx["ebt_25"], ctx["ebt_26_a"]][yi]
    net = [ctx["net_24"], ctx["net_25"], ctx["net_26_a"]][yi]
    cur_profit = net if yi == 2 else 0.0   # في 2024/2025 الأرباح المبقاة تشمل ربح السنة
    ca_ = [121256039, 143292694, ctx["tot_ca_26_a"]][yi]
    cl_ = [73321855, 75542928, 59000848][yi]
    assets = [265819870, 290125340, ctx["tot_assets_26_a"]][yi]
    accrued = ctx["accrued_rev_26"] if yi == 2 else 0.0

    # ---------- أولاً: تعديل صافي الربح ----------
    st.markdown('<div class="zk-title">1️⃣ تعديل صافي الربح المحاسبي إلى صافي الربح المعدل</div>', unsafe_allow_html=True)
    adj_default = pd.DataFrame([
        {"البند": "أرباح إعادة تقييم عقارات استثمارية (غير محققة)", "المبلغ": REVAL[yi], "المعالجة": MINUS, "ملاحظة": "غير محققة، تخصم من الربح"},
        {"البند": "مصروفات غير مقبولة (غرامات وجزاءات ومخالفات)", "المبلغ": 0.0, "المعالجة": PLUS, "ملاحظة": "أدخل المبلغ يدوياً"},
        {"البند": "مصروفات مع جهات مرتبطة تتجاوز سعر السوق", "المبلغ": 0.0, "المعالجة": PLUS, "ملاحظة": "تسعير المعاملات"},
        {"البند": "مصروفات ضيافة وهدايا وتبرعات غير مرخصة", "المبلغ": 0.0, "المعالجة": PLUS, "ملاحظة": ""},
        {"البند": "ديون معدومة غير مستوفية للشروط", "المبلغ": 0.0, "المعالجة": PLUS, "ملاحظة": "المادة 65"},
        {"البند": "إيراد خاضع غير مثبت (فروقات تنفيذ/فوترة)", "المبلغ": 0.0, "المعالجة": PLUS, "ملاحظة": "اختياري"},
    ])
    adj = st.data_editor(
        adj_default, num_rows="dynamic", use_container_width=True, hide_index=True, key=f"zk_adj_{yi}",
        column_config={
            "المعالجة": st.column_config.SelectboxColumn("المعالجة", options=[PLUS, MINUS, EXC], required=True),
            "المبلغ": st.column_config.NumberColumn("المبلغ", format="%.0f"),
        })
    add_back = _sum(adj, "المعالجة", [PLUS])
    deduct = _sum(adj, "المعالجة", [MINUS])
    adj_profit = ebt + add_back - deduct
    zakat_tax_booked = BOOKED[yi]
    net_book = net  # بعد الزكاة والضريبة
    diff = adj_profit - net_book

    # ---------- ثانياً: بنود الوعاء ----------
    st.markdown('<div class="zk-title">2️⃣ بنود الوعاء الزكوي (حسب القوائم المالية — قابلة للتعديل والإضافة)</div>', unsafe_allow_html=True)
    b = {k: v[yi] for k, v in BS.items()}
    rows = [
        ("رأس المال المدفوع", b["capital"], ADD, "حقوق الملكية"),
        ("الاحتياطي النظامي", b["reserve"], ADD, "حقوق الملكية"),
        ("الأرباح المبقاة", b["retained"], ADD, "حقوق الملكية"),
        ("ربح الفترة الجارية (2026)", cur_profit, ADD, "حقوق الملكية"),
        ("المخصصات (إخلاء مشاريع ومكافآت)", b["provisions"], ADD, "المادة 24: تضاف كحقوق ملكية"),
        ("التزامات المزايا المحددة (نهاية الخدمة)", b["eosb"], ADD, "التزام غير متداول، بحد الأصول المحسومة"),
        ("قروض وتسهيلات قصيرة الأجل", b["loans"], EXC, "تضاف إذا مولت أصولاً ثابتة (التزام في حكم غير المتداول)"),
        ("إيرادات مؤجلة / دفعات مقدمة من العميل", b["deferred_rev"], EXC, "التزام عقد: يضاف إن كان غير متداول"),
        ("الممتلكات والآلات والمعدات، صافي", b["ppe"], DED, "المادة 26"),
        ("دفعات مقدمة لشراء ممتلكات ومعدات", b["adv_ppe"], DED, "أصل غير متداول"),
        ("عقارات استثمارية (أرض)", b["inv_prop"], DED, "تحسم إن لم تكن للمتاجرة وبشروط"),
        ("استثمارات متاحة للبيع (صناديق)", b["afs"], DED, "المادة 45: الاستثمار في الصناديق بشروط"),
        ("أصول ضريبية مؤجلة", b["dta"], DED, "المادة 26"),
    ]
    zdf = pd.DataFrame([{"البند": r[0], "المبلغ": float(r[1]), "المعالجة": r[2], "ملاحظة": r[3]} for r in rows])
    zed = st.data_editor(
        zdf, num_rows="dynamic", use_container_width=True, hide_index=True, key=f"zk_base_{yi}",
        column_config={
            "المعالجة": st.column_config.SelectboxColumn("المعالجة", options=[ADD, DED, EXC], required=True),
            "المبلغ": st.column_config.NumberColumn("المبلغ", format="%.0f"),
        })
    # فصل الإضافات حسب النوع لتطبيق سقف الالتزامات غير المتداولة
    names = zed["البند"].astype(str)
    is_liab = names.str.contains("التزامات|قروض|مؤجلة|دفعات مقدمة من العميل", regex=True) & ~names.str.contains("ضريبية مؤجلة")
    amt = pd.to_numeric(zed["المبلغ"], errors="coerce").fillna(0)
    add_equity = float(amt[(zed["المعالجة"] == ADD) & ~is_liab].sum())
    add_liab_raw = float(amt[(zed["المعالجة"] == ADD) & is_liab].sum())
    deductions = float(amt[zed["المعالجة"] == DED].sum())
    add_liab = min(add_liab_raw, deductions)        # المادة 29/30: بحد الأصول المحسومة
    # الالتزامات المتداولة الزائدة على الأصول المتداولة (المادة 29)
    excess_cl = max(0.0, cl_ - ca_)

    # ---------- ثالثاً: الحساب ----------
    base_calc = add_equity + add_liab + excess_cl + diff - deductions
    equity_end = float(amt[(zed["البند"].isin(["رأس المال المدفوع", "الاحتياطي النظامي", "الأرباح المبقاة", "ربح الفترة الجارية (2026)"]))].sum())
    max_base = equity_end + diff                                  # المادة 28
    undeducted_assets = max(0.0, assets - deductions)
    min_alt = undeducted_assets + diff                            # المادة 27
    # تطبيق الحد الأدنى: إذا نقص الوعاء عن الربح المعدل
    base_final = base_calc
    rule = "الوعاء المحسوب كما هو"
    if base_calc < adj_profit:
        base_final = min(min_alt, adj_profit) if min_alt > 0 else adj_profit
        rule = "طُبق الحد الأدنى (المادة 27): الوعاء أقل من صافي الربح المعدل"
    if base_final > max_base and max_base > 0:
        base_final = max_base
        rule = "طُبق الحد الأعلى (المادة 28): الوعاء لا يتجاوز حقوق الملكية + فرق الربح"
    if base_final < 0 and adj_profit <= 0:
        base_final = 0.0
        rule = "وعاء سالب وبلا ربح معدل: لا وعاء زكوي (المادة 27)"
    base_final = max(base_final, 0.0)

    zakat_full = base_final * rate / 100.0
    zakat_saudi = zakat_full * saudi / 100.0

    # ---------- ضريبة الدخل على الحصة الأجنبية ----------
    st.markdown('<div class="zk-title">3️⃣ ضريبة الدخل على حصة الشريك الأجنبي ومدخلات إضافية</div>', unsafe_allow_html=True)
    t1, t2, t3 = st.columns(3)
    with t1:
        nol = st.number_input("خسائر ضريبية مرحلة (ريال)", value=0.0, min_value=0.0, step=100000.0, key=f"zk_nol_{yi}")
    with t2:
        wht = st.number_input("ضريبة الاستقطاع على توزيعات الأجنبي %", value=5.0, min_value=0.0, max_value=30.0, step=1.0, key="zk_wht")
    with t3:
        divs = st.number_input("التوزيعات المقررة/المسددة (ريال)", value=float(DIVS[yi]), min_value=0.0, step=100000.0, key=f"zk_div_{yi}")
    taxable_total = max(adj_profit, 0.0)
    nol_used = min(nol, 0.25 * taxable_total)       # حد استخدام الخسائر 25% من الربح
    taxable_foreign = max(taxable_total - nol_used, 0.0) * foreign / 100.0
    income_tax = taxable_foreign * 0.20
    wht_amt = divs * foreign / 100.0 * wht / 100.0
    total_due = zakat_saudi + income_tax
    # للمقارنة مع المثبت دفترياً
    booked = zakat_tax_booked
    diff_booked = total_due - booked

    # ---------- النتائج ----------
    st.markdown('<div class="zk-title">4️⃣ نتيجة الاحتساب</div>', unsafe_allow_html=True)
    D = ""
    spec = [
        ("section", "أ) صافي الربح المعدل", []),
        ("item", "صافي الربح المحاسبي قبل الزكاة والضريبة", [ebt]),
        ("item", "يضاف: مصروفات غير مقبولة وتعديلات", [add_back]),
        ("item", "يخصم: إيرادات غير خاضعة / غير محققة", [-deduct]),
        ("subtotal", "صافي الربح المعدل", [adj_profit]),
        ("item", "صافي الربح المحاسبي بعد الزكاة والضريبة", [net_book]),
        ("item", "فرق الربح المعدل عن الدفتري (يضاف للوعاء)", [diff]),
        ("section", "ب) الوعاء الزكوي", []),
        ("item", "حقوق الملكية والمخصصات", [add_equity]),
        ("item", f"الالتزامات غير المتداولة المضافة (بحد الأصول المحسومة: {add_liab_raw:,.0f})", [add_liab]),
        ("item", "الالتزامات المتداولة الزائدة على الأصول المتداولة", [excess_cl]),
        ("item", "فرق الربح المعدل عن الدفتري", [diff]),
        ("item", "يخصم: الأصول والاستثمارات المحسومة", [-deductions]),
        ("subtotal", "الوعاء الزكوي المحسوب", [base_calc]),
        ("item", f"الحد الأدنى للوعاء (الربح المعدل)", [max(adj_profit, 0.0)]),
        ("item", "الحد الأعلى للوعاء (حقوق الملكية + فرق الربح)", [max_base]),
        ("total", "الوعاء الزكوي المعتمد", [base_final]),
        ("section", "ج) المستحق", []),
        ("item", f"الزكاة على كامل الوعاء بمعدل {rate:.4f}%", [zakat_full]),
        ("subtotal", f"الزكاة المستحقة على الحصة السعودية ({saudi:.0f}%)", [zakat_saudi]),
        ("item", f"الربح الخاضع لضريبة الدخل بحصة الأجنبي ({foreign:.0f}%) بعد الخسائر", [taxable_foreign]),
        ("subtotal", "ضريبة الدخل 20%", [income_tax]),
        ("total", "إجمالي الزكاة والضريبة المستحقة", [total_due]),
        ("item", "المثبت دفترياً في قائمة الدخل", [booked]),
        ("subtotal", "الفرق (مخصص إضافي مطلوب + / زيادة في المخصص −)", [diff_booked]),
        ("item", "ضريبة الاستقطاع على توزيعات الأجنبي (للمعلومية، تسدد عند التوزيع)", [wht_amt]),
    ]
    st.table(build_styled_table(spec, ["البند", year]))
    st.caption(f"حالة الوعاء: {rule}")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("الوعاء الزكوي المعتمد", f"{base_final:,.0f} ريال")
    m2.metric("الزكاة (حصة سعودية)", f"{zakat_saudi:,.0f} ريال", f"المعدل {rate:.3f}%")
    m3.metric("ضريبة الدخل (حصة أجنبية)", f"{income_tax:,.0f} ريال")
    m4.metric("الفرق عن المثبت دفترياً", f"{diff_booked:,.0f} ريال", delta_color="inverse")

    eff = (total_due / adj_profit * 100) if adj_profit > 0 else float("nan")
    if not np.isnan(eff):
        st.markdown(f'<div class="zk-fx">العبء الفعلي = (الزكاة + الضريبة) ÷ صافي الربح المعدل = <b>{eff:.1f}%</b></div>', unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### مرجع الأحكام المطبقة:")
    st.markdown(f"""
    * **الوعاء (المواد 23–29):** حقوق الملكية والمخصصات + الالتزامات غير المتداولة بحد الأصول المحسومة + فرق الربح المعدل عن الدفتري − الأصول والاستثمارات المحسومة. مخصص نهاية الخدمة والإجازات يعامل كالتزام غير متداول.
    * **الحد الأدنى (المادة 27):** لا يقل الوعاء عن صافي الربح المعدل، والحد الأعلى (المادة 28) حقوق الملكية في نهاية العام مضافاً إليها فرق الربح؛ الوعاء السالب بلا ربح معدل لا زكاة عليه.
    * **المعدل (المادة 15):** 2.5% للسنة الهجرية، وللسنة الميلادية بالأيام: 2.5% ÷ 354 × عدد الأيام (≈ 2.5777% لـ 365 يوماً).
    * **الشركة المختلطة:** تُحسب الزكاة على الحصة السعودية/الخليجية ({saudi:.0f}%) من الوعاء، وضريبة الدخل 20% على الحصة الأجنبية ({foreign:.0f}%) من الربح المعدل. تُحدد النسب بحسب الملكية في نهاية العام (المادة 13). الخسائر المرحلة تخفض الربح الخاضع بحد 25%. ضريبة الاستقطاع 5% على الأرباح الموزعة للأجنبي.
    * **قروض الشركاء والقروض البنكية:** غير مشمولة افتراضياً؛ حوّل معالجتها إلى "إضافة" إذا مولت أصولاً ثابتة أو أُعيد تصنيفها كالتزام غير متداول.
    * الاستثمارات في الصناديق والعقارات الاستثمارية تُحسم بشروط (المادة 45 وما يتصل بها)، فتأكد من استيفائها قبل الاعتماد.
    """)
