# banks.py
# تبويب البنوك: أرصدة البنوك، التسهيلات (إجمالي/مستخدم/متاح)، الضمانات القائمة، المرابحات القائمة (قصيرة/طويلة الأجل)
# المصادر: اتفاقية تجديد وتعديل تسهيلات الراجحي (3/2/2026)، خطاب عرض ساب (10/9/2026)،
# جداول أقساط المرابحات (الراجحي)، بيانات الضمانات (الراجحي 31/3/2026، الأهلي 31/12/2025، ساب).

import io
import os
import json
import hashlib
import datetime as dt

import numpy as np
import pandas as pd
import streamlit as st

CSS = """
<style>
    .bk-note { direction: rtl; text-align: right; background:#FFF7E0; border-right:4px solid #F59E0B;
               color:#7A4B00; padding:8px 12px; border-radius:6px; font-size:0.95rem; margin:6px 0; }
    .bk-fx { direction: rtl; text-align: right; font-size:0.9rem; color:#0B2A6F; background:#EAF1FF;
             border-right:3px solid #1E3A8A; padding:4px 10px; border-radius:4px; font-weight:600; margin:4px 0 8px 0; }
    .bk-title { direction: rtl; text-align: right; background: linear-gradient(90deg,#1E3A8A,#3B5FC4); color:#fff;
                padding:9px 14px; border-radius:6px; margin:18px 0 8px 0; font-weight:700; font-size:1.1rem; }
</style>
"""

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bank_data.json")
DEFAULT_ASOF = dt.date(2026, 9, 30)   # تاريخ المركز المالي للفحوصات والأرصدة
TODAY = dt.date.today()                  # تاريخ احتساب المستخدم من التسهيلات (يشمل تمويل 27/10/2026)
RAJHI, SAB, AHLI = "مصرف الراجحي", "البنك السعودي الأول (ساب)", "البنك الأهلي"
ARAB, RIYAD, INMA, SAIB = "البنك العربي", "بنك الرياض", "مصرف الإنماء", "البنك السعودي للاستثمار"
CASHB = "صناديق وعهد نقدية (غير بنكية)"
BANKS = [RAJHI, SAB, AHLI, ARAB, RIYAD, INMA, SAIB, CASHB, "أخرى"]
COST_COLS = ["البند", RAJHI, SAB, AHLI]
ST_OK, ST_CANCEL = "قائم", "ملغي"
MST_ACTIVE, MST_PLANNED, MST_CLOSED = "قائم", "مخطط (غير مسحوب)", "مسدد بالكامل"

BAL_COLS = ["البنك", "رقم الحساب / IBAN", "نوع الحساب", "العملة", "الرصيد (ريال)", "تاريخ الرصيد", "ملاحظات"]
GUAR_COLS = ["البنك", "البيان", "رقم العقد", "رقم الضمان", "مبلغ الضمان", "الغطاء النقدي (الهامش)",
             "تاريخ الإصدار", "تاريخ الانتهاء", "حالة السجل", "ملاحظات"]
FAC_COLS = ["البنك", "الرمز", "التسهيل", "السقف", "النوع"]
MST_COLS = ["التمويل", "الوصف", "التسهيل", "تاريخ التمويل", "أصل التمويل", "الحالة"]
SCH_COLS = ["التمويل", "القسط", "تاريخ الاستحقاق", "أصل القسط", "الربح"]

D = dt.date


def _g(bank, desc, contract, gno, amt, margin, issue, exp, note=""):
    return [bank, desc, contract, gno, float(amt), float(margin), issue, exp, ST_OK, note]


DEFAULT_GUAR = [
    # الراجحي: بيان 31/03/2026 (ويُجدَّد تلقائياً سنوياً ما لم يُطلب الإلغاء). هامش ضمانات 2026 = 0 حسب ميزان 30/9/2026
    _g(RAJHI, "ضمان نهائي موحد تبوك (2013)", "4000000920", "48809177", 1346667, 1346667, D(2013, 6, 30), D(2027, 1, 15), "تغطية نقدية 100%"),
    _g(RAJHI, "ضمان نهائي موحد تبوك الجديد (2016)", "4000054893", "48806152", 2051500, 2051500, D(2016, 9, 28), D(2027, 4, 30), "تغطية نقدية 100%"),
    _g(RAJHI, "ضمان نهائي موحد الباحة 2021", "4000069334", "48801799", 4644195, 464419.5, D(2021, 5, 19), D(2026, 12, 1), "هامش 10%"),
    _g(RAJHI, "ضمان نهائي موحد الرياض 2021", "4000069347", "48801820", 2013458, 201345.8, D(2021, 5, 20), D(2026, 12, 1), "هامش 10%"),
    _g(RAJHI, "ضمان نهائي موحد تبوك 2021", "400069341", "48801821", 1634700, 163470.0, D(2021, 5, 20), D(2026, 12, 1), "هامش 10%"),
    _g(RAJHI, "ضمان نهائي موحد مكة المكرمة 2021", "4000069318", "48801822", 2574282, 257428.2, D(2021, 5, 20), D(2026, 12, 1), "هامش 10%"),
    _g(RAJHI, "ضمان نهائي موحد عسير 2021", "4000069363", "48801823", 3079486, 307948.6, D(2021, 5, 20), D(2026, 12, 1), "هامش 10%"),
    _g(RAJHI, "ضمان نهائي موحد تبوك القديم", "20841026", "48805215", 580000, 580000, D(2021, 12, 29), D(2026, 12, 27), "تغطية نقدية 100%"),
    _g(RAJHI, "العقد الموحد لشبكات الطاقة - الرياض (2026)", "4000083770", "48803259", 2421291, 0, D(2026, 4, 4), D(2030, 11, 30), "بدون هامش محتجز (الميزان 30/9: هامش الراجحي 5,372,779)"),
    _g(RAJHI, "العقد الموحد لشبكات الطاقة - الباحة (2026)", "4000083747", "48803256", 1283000, 0, D(2026, 4, 4), D(2030, 11, 30), "بدون هامش محتجز"),
    _g(RAJHI, "العقد الموحد لشبكات الطاقة - عسير (2026)", "4000083755", "48803260", 1540625, 0, D(2026, 4, 4), D(2030, 11, 30), "بدون هامش محتجز"),
    _g(RAJHI, "العقد الموحد لشبكات الطاقة - تبوك (2026)", "4000083773", "48803257", 887500, 0, D(2026, 4, 4), D(2030, 11, 30), "بدون هامش محتجز"),
    # الأهلي: مغطاة بالكامل لعدم وجود تسهيلات مع البنك (إجمالي 4,318,500)
    _g(AHLI, "ضمان نهائي موحد الباحة 2013", "4131025", "125179", 1200000, 1200000, D(2013, 1, 9), D(2026, 12, 18), "مغطى بالكامل (لا توجد تسهيلات)"),
    _g(AHLI, "ضمان نهائي موحد عسير 2013", "41341002", "125178", 1000000, 1000000, D(2013, 1, 9), D(2026, 12, 18), "مغطى بالكامل (لا توجد تسهيلات)"),
    _g(AHLI, "ضمان نهائي موحد الباحة 2016", "4400008867", "174016", 2118500, 2118500, D(2016, 10, 23), D(2026, 10, 31), "مغطى بالكامل. تاريخ الانتهاء متجاوز: يُجدَّد سنوياً"),
    # ساب (يشمل الهولندي سابقاً)
    _g(SAB, "ضمان نهائي موحد مكة 2013", "4000000916", "1313300014", 2291538, 687461.4, D(2013, 5, 19), D(2027, 1, 25), "هامش 30%"),
    _g(SAB, "ضمان نهائي موحد مكة 2016", "4000054877", "1628737", 2529000, 758700, D(2016, 9, 28), D(2027, 4, 30), "هامش 30%"),
    _g(SAB, "ضمان نهائي موحد مكة 2026", "", "166197", 1909231, 0, D(2026, 6, 2), D(2030, 11, 30), "بدون هامش محتجز (إجمالي هامش ساب 1,446,161 يطابق الميزان)"),
    _g(SAB, "ضمان ابتدائي (الحكير)", "", "", 5700000, 0, D(2026, 5, 6), D(2026, 11, 30), "ضمان ابتدائي، ينتهي 30/11/2026 ويُراجع تجديده أو إلغاؤه"),
]

DEFAULT_FAC = [
    [RAJHI, "R-TOT", "إجمالي حدود تسهيلات الراجحي (اتفاقية التجديد 3/2/2026)", 65000000.0, "إجمالي"],
    [RAJHI, "R-1.1", "1.1 تسهيل النفقات الرأسمالية وتوسيع الأعمال (تمويل مستورد / بيع آجل / اعتمادات)", 20000000.0, "فرعي"],
    [RAJHI, "R-1.2", "1.2 تسهيل تمويل المشاريع: ضمانات ابتدائية ونهائية", 25000000.0, "فرعي"],
    [RAJHI, "R-1.3", "1.3 تسهيل بيع آجل (يشمل الرواتب ومتطلبات العميل)", 20000000.0, "فرعي"],
    [SAB, "S-TOT", "إجمالي التسهيلات (خطاب العرض SAB-261779 بتاريخ 10/9/2026)", 17291538.0, "إجمالي"],
]

DEFAULT_MST = [
    ["تمويل 1", "فاتورة هلا السعودية (29 مركبة)", "1.1", D(2025, 6, 24), 4049999.99, MST_ACTIVE],
    ["تمويل 2", "هلا السعودية + اليمني للسيارات + الجفالي + تقنيات الشاحنات (دفعة 1 من 3)", "1.1", D(2025, 11, 10), 7239069.00, MST_ACTIVE],
    ["تمويل 3", "اليمني للسيارات + تقنيات الشاحنات (دفعة 2 من 3)", "1.1", D(2026, 3, 27), 5049764.98, MST_ACTIVE],
    ["تمويل 4", "تقنيات الشاحنات (دفعة 3 من 3)", "1.1", D(2026, 6, 22), 3001500.00, MST_ACTIVE],
    ["تمويل 5", "تمويل رواتب ومتطلبات التشغيل (12 شهراً، سداد دفعة واحدة، سايبور 12 شهراً + 3%)", "1.3", D(2026, 10, 27), 12000000.00, MST_ACTIVE],
]

DEFAULT_SCH = [
    ["تمويل 1", 1, D(2025, 12, 24), 675000.03, 175209.51],
    ["تمويل 1", 2, D(2026, 6, 24), 674999.98, 141681.54],
    ["تمويل 1", 3, D(2026, 12, 24), 675000.00, 111997.49],
    ["تمويل 1", 4, D(2027, 6, 24), 675000.00, None],
    ["تمويل 1", 5, D(2027, 12, 24), 675000.00, None],
    ["تمويل 1", 6, D(2028, 6, 24), 674999.98, None],
    ["تمويل 2", 1, D(2026, 5, 10), 1206511.50, 293069.00],
    ["تمويل 2", 2, D(2026, 11, 10), 1206511.50, 251697.76],
    ["تمويل 2", 3, D(2027, 5, 10), 1206511.50, None],
    ["تمويل 2", 4, D(2027, 11, 10), 1206511.50, None],
    ["تمويل 2", 5, D(2028, 5, 10), 1206511.50, None],
    ["تمويل 2", 6, D(2028, 11, 10), 1206511.50, None],
    ["تمويل 3", 1, D(2026, 9, 27), 841627.50, 208926.72],
    ["تمويل 3", 2, D(2027, 3, 27), 841627.50, 178557.07],
    ["تمويل 3", 3, D(2027, 9, 27), 841627.50, None],
    ["تمويل 3", 4, D(2028, 3, 27), 841627.50, None],
    ["تمويل 3", 5, D(2028, 9, 27), 841627.50, None],
    ["تمويل 3", 6, D(2029, 3, 27), 841627.48, None],
    ["تمويل 4", 1, D(2026, 12, 22), 500250.00, 123662.74],
    ["تمويل 4", 2, D(2027, 6, 22), 500250.00, None],
    ["تمويل 4", 3, D(2027, 12, 22), 500250.00, None],
    ["تمويل 4", 4, D(2028, 6, 22), 500250.00, None],
    ["تمويل 4", 5, D(2028, 12, 22), 500250.00, None],
    ["تمويل 4", 6, D(2029, 6, 22), 500250.00, None],
    ["تمويل 5", 1, D(2027, 10, 27), 12000000.00, 1050918.95],
]

_TB = [
    (RAJHI, "مصرف الراجحي 504608010013689", "1-01-01-01-001", 23300950.50),
    (RAJHI, "مصرف الراجحي 504608010013408", "1-01-01-01-002", 0.98),
    (RAJHI, "مصرف الراجحي 504608010013697", "1-01-01-01-003", 3374340.69),
    (RAJHI, "مصرف الراجحي 504608010014984", "1-01-01-01-006", 224781.60),
    (RAJHI, "504608010199736 حساب الإقامات", "1-01-01-01-110", 586319.23),
    (RAJHI, "مصرف الراجحي 504608010129832", "1-01-01-01-120", 0.23),
    (RAJHI, "504608010183656 - 4400014802", "1-01-01-01-130", 77204.06),
    (RAJHI, "مصرف الراجحي 504608010487164", "1-01-01-01-131", 2164003.00),
    (RAJHI, "مصرف الراجحي 5046080104847716", "1-01-01-01-132", 318229.37),
    (RAJHI, "مصرف الراجحي 504608010183649 - عسير", "1-01-01-01-133", 1157871.46),
    (RAJHI, "مصرف الراجحي 504608010487156 عقد 14756", "1-01-01-01-134", 79900.32),
    (AHLI, "البنك الأهلي 62511484000100", "1-01-01-02-001", 14198.43),
    (AHLI, "البنك الأهلي التجاري -209", "1-01-01-02-014", 937.85),
    (AHLI, "البنك الأهلي 29547316890100", "1-01-01-02-015", 62.54),
    (ARAB, "البنك العربي 0108055347060010", "1-01-01-04-001", 10899.70),
    (RIYAD, "بنك الرياض 2095122229940", "1-01-01-05-001", 61.30),
    (SAB, "البنك السعودي الهولندي 010193170042", "1-01-01-06-006", 26911.43),
    (SAB, "حساب 005-10193170166 موحد مكة (الهولندي)", "1-01-01-06-012", 470484.88),
    (SAB, "البنك الهولندي 002-010193170174", "1-01-01-06-013", 100.00),
    (SAB, "حساب 003-042223-896 الجاري (رقم حساب ساب في خطاب العرض 896-042223)", "1-01-01-20-001", 2804.84),
    (INMA, "الإنماء SA4505000000200216923022", "1-01-01-08-001", 17572.17),
    (SAIB, "بنك الاستثمار SA4165000000101507967001", "1-01-01-30-001", 876935.94),
    (CASHB, "صندوق الإدارة", "1-01-02-01-001", 88155.66),
    (CASHB, "صندوق تسوية الغرفة التجارية", "1-01-02-01-406", 3010.00),
    (CASHB, "عهد أخرى (أرصدة صغيرة)", "1-01-02-01", 14.14),
]
DEFAULT_BAL = [[b, n, "جاري", "SAR", v, D(2026, 9, 30), "ميزان المراجعة 30/9/2026 (استرشادي)، الحساب " + c] for b, n, c, v in _TB]

AST_COLS = ["التمويل", "المورد", "عدد الأصول", "قيمة الأصول بسجل الأصول (قبل الضريبة)", "إجمالي الفاتورة / الدفعة"]
DEFAULT_AST = [
    ["تمويل 1", "شركة هلا السعودية للسيارات", 29, 3882000.0, 4500000.0],
    ["تمويل 2", "شركة هلا السعودية للسيارات", 12, 954000.0, 1110060.0],
    ["تمويل 2", "شركة اليمني للسيارات", 14, 3100000.0, 3565000.0],
    ["تمويل 2", "شركة الجفالي", 1, 450000.0, 517500.0],
    ["تمويل 2", "شركة تقنيات الشاحنات (دفعة 1 من 3)", None, 2479000.0, 2850850.0],
    ["تمويل 3", "شركة اليمني للسيارات", 10, 2400000.0, 2760000.0],
    ["تمويل 3", "شركة تقنيات الشاحنات (دفعة 2 من 3)", None, 2479000.0, 2850850.0],
    ["تمويل 4", "شركة تقنيات الشاحنات (دفعة 3 من 3)", None, 2900000.0, 3335000.0],
]

NA = "غير محدد: يُستكمل"
DEFAULT_COST = [
    ["نوع التسهيل والغرض", "تسهيلات مرابحة وبيع آجل وضمانات ابتدائية ونهائية", "ضمانات بنكية (خطاب عرض تسهيلات إسلامية)", "ضمانات مغطاة نقدياً بالكامل، لا توجد تسهيلات"],
    ["السقف الإجمالي", "65,000,000 ريال (تسهيلات 1.1 و1.2 و1.3)", "17,291,538 ريال", "لا يوجد سقف (تغطية نقدية 100%)"],
    ["آخر اتفاقية ومراجعتها", "اتفاقية تجديد وتعديل 3/2/2026، مراجعة سنوية 31/12/2026", "خطاب عرض SAB-261779 بتاريخ 10/9/2026، يتجدد تلقائياً بشروط مماثلة ما لم يُخطَر خلاف ذلك", "لا يوجد"],
    ["هامش الربح على التمويل", "سايبور 6 أشهر + 3% سنوياً (1.5% لكل فترة 6 أشهر)، وتمويل 12 شهراً: سايبور 12 شهراً + 3%", "لا يوجد تمويل", "لا يوجد تمويل"],
    ["المصاريف الإدارية للتمويل", "1% من مبلغ التمويل + ضريبة قيمة مضافة 15% (تُخصم من التمويل)", NA, "لا يوجد"],
    ["رسوم الترتيب والإدارة والالتزام", "وفق جدول التسهيلات والتعرفة الموحدة للمصرف", "مستحقة وغير مستردة بصرف النظر عن الاستخدام (المبلغ غير مذكور في الخطاب)", "لا يوجد"],
    ["رسوم إصدار الضمان", "نحو 1.02% سنوياً لضمانات 2021 ونحو 1.46% سنوياً لضمانات 2026 (مستنتج من ملف مصاريف الضمانات، وتشمل غالباً ضريبة القيمة المضافة)", "نحو 1.46% سنوياً لضمان مكة 2026 (مستنتج من الملف). الباقي " + NA, NA],
    ["رسوم تجديد الضمان", "تُجدَّد الضمانات سنوياً تلقائياً ما لم يُطلب الإلغاء، وتُحتسب الرسوم وفق التعرفة", "رسوم تجديد مستحقة وغير مستردة (المبلغ غير مذكور في الخطاب)", NA],
    ["الغطاء النقدي (الهامش) للضمانات", "100% لضمانات تبوك القديمة، و10% لضمانات 2021، و0% لضمانات 2026", "30% لضمانات 2013 و2016، و5% لضمان مكة 2026", "100%"],
    ["حدود إصدار الضمان", "ابتدائي حتى 2,000,000 (وما زاد عن 700,000 بموافقة البنك)، ونهائي ما زاد عن 3,500,000 بموافقة البنك", NA, NA],
    ["حد تمويل المشاريع", "حتى 25,000,000 للمشروع وبما لا يزيد عن 50% من قيمة العقود المتوقعة", "لا يوجد", "لا يوجد"],
    ["الضمانات المقدمة للبنك", "سند لأمر 33,830,559 + كفالة مجموعة الحكير + تنازل عن مستحقات المشاريع (للضمان النهائي)", "سند لأمر 17,291,538 + تفويض بالخصم من الحسابات", "الهامش النقدي"],
    ["مدة التمويل", "36 شهراً، يُعاد تسعيرها كل 6 أشهر، وتُسجل قصيرة الأجل محاسبياً", "لا يوجد", "لا يوجد"],
]

DATE_COLS = {"bal": ["تاريخ الرصيد"], "guar": ["تاريخ الإصدار", "تاريخ الانتهاء"],
             "mst": ["تاريخ التمويل"], "sch": ["تاريخ الاستحقاق"], "fac": [], "cost": [], "ast": []}
COLS = {"bal": BAL_COLS, "guar": GUAR_COLS, "fac": FAC_COLS, "mst": MST_COLS, "sch": SCH_COLS, "cost": COST_COLS, "ast": AST_COLS}
NUM_COLS = {"bal": ["الرصيد (ريال)"], "guar": ["مبلغ الضمان", "الغطاء النقدي (الهامش)"], "fac": ["السقف"], "cost": [], "ast": ["عدد الأصول", "قيمة الأصول بسجل الأصول (قبل الضريبة)", "إجمالي الفاتورة / الدفعة"],
            "mst": ["أصل التمويل"], "sch": ["القسط", "أصل القسط", "الربح"]}


def _num(v):
    try:
        v = float(v)
        return 0.0 if np.isnan(v) else v
    except Exception:
        return 0.0


def _norm(df, kind):
    df = df.copy()
    for c in COLS[kind]:
        if c not in df.columns:
            df[c] = None
    df = df[COLS[kind]]
    for c in DATE_COLS[kind]:
        df[c] = pd.to_datetime(df[c], errors="coerce").dt.date
        df[c] = df[c].where(pd.notna(df[c]), None)
    for c in NUM_COLS[kind]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df.reset_index(drop=True)


def _defaults():
    return {
        "bal": _norm(pd.DataFrame(DEFAULT_BAL, columns=BAL_COLS), "bal"),
        "cost": _norm(pd.DataFrame(DEFAULT_COST, columns=COST_COLS), "cost"),
        "ast": _norm(pd.DataFrame(DEFAULT_AST, columns=AST_COLS), "ast"),
        "guar": _norm(pd.DataFrame(DEFAULT_GUAR, columns=GUAR_COLS), "guar"),
        "fac": _norm(pd.DataFrame(DEFAULT_FAC, columns=FAC_COLS), "fac"),
        "mst": _norm(pd.DataFrame(DEFAULT_MST, columns=MST_COLS), "mst"),
        "sch": _norm(pd.DataFrame(DEFAULT_SCH, columns=SCH_COLS), "sch"),
    }


def _load_saved():
    out = _defaults()
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                raw = json.load(f)
            for k in out:
                if k in raw and raw[k]:
                    out[k] = _norm(pd.DataFrame(raw[k]), k)
                elif k in raw and k == "bal":
                    out[k] = _norm(pd.DataFrame(columns=BAL_COLS), k)
    except Exception:
        pass
    return out


def _save(cur):
    try:
        payload = {}
        for k, df in cur.items():
            d = df.copy()
            for c in DATE_COLS[k]:
                d[c] = d[c].map(lambda x: x.isoformat() if isinstance(x, (dt.date, dt.datetime)) else None)
            d = d.astype(object).where(pd.notna(d), None)
            payload[k] = d.to_dict("records")
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
    except Exception:
        pass


def _state():
    ss = st.session_state
    if "bk_base" not in ss:
        ss["bk_base"] = _load_saved()
    if "bk_cur" not in ss:
        ss["bk_cur"] = {k: v.copy() for k, v in ss["bk_base"].items()}
    if "bk_ver" not in ss:
        ss["bk_ver"] = {k: 0 for k in ss["bk_base"]}
    return ss["bk_base"], ss["bk_cur"], ss["bk_ver"]


def _ts(x):
    return pd.Timestamp(x) if x is not None and not pd.isna(x) else pd.NaT


# ------------------------------------------------------------------
# الحسابات
# ------------------------------------------------------------------
def guar_status(exp, as_of, rec_status=ST_OK):
    if rec_status == ST_CANCEL:
        return "⚪ ملغي"
    if exp is None or pd.isna(exp):
        return "❔ تاريخ الانتهاء غير محدد"
    exp = pd.Timestamp(exp)
    asof = pd.Timestamp(as_of)
    if exp < asof:
        return "🟡 تاريخ الانتهاء متجاوز: يُجدَّد سنوياً تلقائياً (حدّث التاريخ)"
    if exp <= asof + pd.Timedelta(days=90):
        return "🟠 ينتهي خلال 90 يوماً (يُجدَّد تلقائياً ما لم يُطلب الإلغاء)"
    return "🟢 ساري"


def mur_calc(mst, sch, as_of):
    """يحسب لكل تمويل: المتبقي (أصل)، المتداول (خلال 12 شهراً من تاريخ المركز)، غير المتداول، القسط القادم."""
    asof = pd.Timestamp(as_of)
    lim = asof + pd.DateOffset(years=1)
    rows = []
    s = sch.copy()
    s["_d"] = pd.to_datetime(s["تاريخ الاستحقاق"], errors="coerce")
    s["_p"] = pd.to_numeric(s["أصل القسط"], errors="coerce").fillna(0.0)
    s["_i"] = pd.to_numeric(s["الربح"], errors="coerce").fillna(0.0)
    for _, m in mst.iterrows():
        fid = m["التمويل"]
        status = m["الحالة"]
        x = s[s["التمويل"] == fid]
        paid = x[x["_d"] <= asof]
        fut = x[x["_d"] > asof].sort_values("_d")
        dd = pd.to_datetime(m["تاريخ التمويل"], errors="coerce")
        counts = (status == MST_ACTIVE) and (pd.isna(dd) or dd <= asof)
        rem = float(fut["_p"].sum()) if counts else 0.0
        cur = float(fut[fut["_d"] <= lim]["_p"].sum()) if counts else 0.0
        nxt = fut.iloc[0] if len(fut) else None
        rows.append({
            "التمويل": fid, "الوصف": m["الوصف"], "التسهيل": m["التسهيل"], "تاريخ التمويل": m["تاريخ التمويل"],
            "أصل التمويل": _num(m["أصل التمويل"]), "الحالة": status if counts or status != MST_ACTIVE else "قائم (بعد تاريخ المركز)",
            "المسدد من الأصل": float(paid["_p"].sum()) if counts else 0.0,
            "المتبقي (أصل)": rem, "المتداول": cur, "غير المتداول": rem - cur,
            "القسط القادم (أصل)": float(nxt["_p"]) if (nxt is not None and counts) else 0.0,
            "ربح القسط القادم": float(nxt["_i"]) if (nxt is not None and counts) else 0.0,
            "تاريخ القسط القادم": nxt["_d"].date() if (nxt is not None and counts) else None,
            "عدد الأقساط المتبقية": int(len(fut)) if counts else 0,
        })
    return pd.DataFrame(rows)


def under_facility(g):
    """الضمان الذي يستهلك سقف التسهيل: الغطاء النقدي أقل من 100% وحالة السجل قائم (منطق ملف الضمانات)."""
    amt = pd.to_numeric(g["مبلغ الضمان"], errors="coerce").fillna(0.0)
    mar = pd.to_numeric(g["الغطاء النقدي (الهامش)"], errors="coerce").fillna(0.0)
    return (g["حالة السجل"] == ST_OK) & (mar < amt - 0.5)


def fac_used(cur, as_of):
    fac, g = cur["fac"], cur["guar"]
    mc = mur_calc(cur["mst"], cur["sch"], as_of)
    used_11 = float(mc[(mc["التسهيل"] == "1.1")]["المتبقي (أصل)"].sum())
    used_13 = float(mc[(mc["التسهيل"] == "1.3")]["المتبقي (أصل)"].sum())
    ra = g[(g["البنك"] == RAJHI) & under_facility(g)]
    used_12 = float(pd.to_numeric(ra["مبلغ الضمان"], errors="coerce").fillna(0).sum())
    sg = g[(g["البنك"] == SAB) & (g["حالة السجل"] == ST_OK)]
    used_s = float(pd.to_numeric(sg["مبلغ الضمان"], errors="coerce").fillna(0).sum())
    used = {"R-1.1": used_11, "R-1.2": used_12, "R-1.3": used_13, "R-TOT": used_11 + used_12 + used_13,
            "S-TOT": used_s}
    return used, mc


def summary(as_of=DEFAULT_ASOF):
    """ملخص للفحوصات والواجهة الرئيسية."""
    _, cur, _ = _state()
    used, mc = fac_used(cur, as_of)
    g = cur["guar"]
    act = g[g["حالة السجل"] == ST_OK].copy()
    act["_exp"] = pd.to_datetime(act["تاريخ الانتهاء"], errors="coerce")
    live = act[~(act["_exp"] < pd.Timestamp(as_of))]
    bal = pd.to_numeric(cur["bal"]["الرصيد (ريال)"], errors="coerce").fillna(0.0).sum()
    bank_only = pd.to_numeric(cur["bal"].loc[cur["bal"]["البنك"] != CASHB, "الرصيد (ريال)"], errors="coerce").fillna(0.0).sum()
    return {
        "mur_principal": float(mc["المتبقي (أصل)"].sum()),
        "mur_current": float(mc["المتداول"].sum()),
        "mur_noncurrent": float(mc["غير المتداول"].sum()),
        "mur_next_profit": float(mc["ربح القسط القادم"].sum()),
        "guar_total": float(pd.to_numeric(act["مبلغ الضمان"], errors="coerce").fillna(0).sum()),
        "guar_margin": float(pd.to_numeric(act["الغطاء النقدي (الهامش)"], errors="coerce").fillna(0).sum()),
        "guar_margin_live": float(pd.to_numeric(act["الغطاء النقدي (الهامش)"], errors="coerce").fillna(0).sum()),
        "bal_total": float(bal), "bal_banks": float(bank_only), "bal_rows": int(len(cur["bal"])), "used": used,
    }


# ------------------------------------------------------------------
# أدوات واجهة
# ------------------------------------------------------------------
def _fmtd(d):
    return d.strftime("%Y-%m-%d") if isinstance(d, (dt.date, dt.datetime, pd.Timestamp)) and not pd.isna(d) else ""


def _editor(kind, label, locked, base, cur, ver, extra_cfg=None, key_prefix="bk"):
    cfg = {c: st.column_config.NumberColumn(c, format="%.2f") for c in NUM_COLS[kind]}
    for c in DATE_COLS[kind]:
        cfg[c] = st.column_config.DateColumn(c, format="YYYY-MM-DD")
    if extra_cfg:
        cfg.update(extra_cfg)
    ed = st.data_editor(base[kind], num_rows="dynamic", use_container_width=True, hide_index=True,
                        key=f"{key_prefix}_ed_{kind}_{ver[kind]}", column_config=cfg, disabled=locked)
    ed = _norm(ed, kind)
    if not locked:
        if not ed.equals(cur[kind]):
            cur[kind] = ed
            _save(cur)
    return cur[kind]


def _template_bytes():
    try:
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "أرصدة البنوك"
        ws.sheet_view.rightToLeft = True
        ws.append(BAL_COLS)
        ws.append([RAJHI, "SA0000000000000000000000", "جاري", "SAR", 0, "2026-09-30", "مثال: احذف هذا الصف"])
        for i, w in enumerate([24, 30, 14, 10, 18, 16, 36], start=1):
            ws.column_dimensions[chr(64 + i)].width = w
        bio = io.BytesIO()
        wb.save(bio)
        return bio.getvalue()
    except Exception:
        return ("﻿" + ",".join(BAL_COLS) + "\n").encode("utf-8")


_ALIASES = {
    "البنك": ["البنك", "اسم البنك", "bank"],
    "رقم الحساب / IBAN": ["رقم الحساب / IBAN", "رقم الحساب", "الحساب", "iban", "account"],
    "نوع الحساب": ["نوع الحساب", "النوع", "type"],
    "العملة": ["العملة", "currency"],
    "الرصيد (ريال)": ["الرصيد (ريال)", "الرصيد", "الرصيد بالريال", "balance", "amount", "المبلغ"],
    "تاريخ الرصيد": ["تاريخ الرصيد", "التاريخ", "date"],
    "ملاحظات": ["ملاحظات", "ملاحظة", "notes"],
}


_CODE_BANK = {"1-01-01-01": RAJHI, "1-01-01-02": AHLI, "1-01-01-04": ARAB, "1-01-01-05": RIYAD,
              "1-01-01-06": SAB, "1-01-01-08": INMA, "1-01-01-20": SAB, "1-01-01-30": SAIB, "1-01-02": CASHB}


def canon_bank(name, code=""):
    """توحيد اسم البنك: أي إشارة للبنك السعودي الهولندي أو البريطاني أو الأول تُدمج مع ساب."""
    code = str(code or "").strip()
    for k, v in _CODE_BANK.items():
        if code.startswith(k):
            return v
    n = str(name or "")
    for keys, v in [(("راجحي", "الراجحي"), RAJHI), (("هولند", "ساب", "SAB", "بريطان", "الأول", "الاول"), SAB),
                    (("اهلي", "الأهلي", "الاهلي"), AHLI), (("العربي",), ARAB), (("الرياض",), RIYAD),
                    (("الانماء", "الإنماء"), INMA), (("الاستثمار",), SAIB), (("صندوق", "عهد"), CASHB)]:
        if any(k in n for k in keys):
            return v
    return n.strip() or "أخرى"


def _parse_tb(raw, as_of):
    """قراءة ميزان مراجعة بصيغة التقرير الحالي: الاسم في العمود 9 والكود في العمود 11؛ الرصيد الختامي مدين في العمود 8 أو العمود 1."""
    df = pd.read_excel(io.BytesIO(raw), header=None)
    rows = []
    for _, r in df.iterrows():
        code = str(r.iloc[10]).strip() if len(r) > 10 else ""
        if not (code.startswith("1-01-01") or code.startswith("1-01-02-01")):
            continue
        cl = _num(r.iloc[7]) or _num(r.iloc[0])
        if abs(cl) < 0.005:
            continue
        nm = " ".join(str(r.iloc[8]).split())
        rows.append([canon_bank(nm, code), nm, "جاري", "SAR", cl, as_of, "ميزان المراجعة، الحساب " + code])
    return _norm(pd.DataFrame(rows, columns=BAL_COLS), "bal")


def _parse_balances(f, as_of=DEFAULT_ASOF):
    name = getattr(f, "name", "")
    raw = f.read() if hasattr(f, "read") else f
    if not name.lower().endswith(".csv"):
        try:
            tb = _parse_tb(raw, as_of)
            if len(tb):
                return tb
        except Exception:
            pass
    if name.lower().endswith(".csv"):
        df = pd.read_csv(io.BytesIO(raw), encoding="utf-8-sig")
    else:
        try:
            df = pd.read_excel(io.BytesIO(raw))
        except Exception:
            import re, zipfile
            zin = zipfile.ZipFile(io.BytesIO(raw))
            out = io.BytesIO()
            with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
                for it in zin.infolist():
                    data = zin.read(it.filename)
                    if it.filename.startswith("xl/worksheets/") or it.filename == "xl/workbook.xml":
                        s = data.decode("utf-8", "ignore")
                        s = re.sub(r"<bookViews>.*?</bookViews>|<pageSetup[^>]*/>|<headerFooter>.*?</headerFooter>", "", s, flags=re.S)
                        data = s.encode("utf-8")
                    zout.writestr(it, data)
            df = pd.read_excel(io.BytesIO(out.getvalue()))
    df.columns = [str(c).strip() for c in df.columns]
    lowmap = {c.lower(): c for c in df.columns}
    res = pd.DataFrame()
    for std, alts in _ALIASES.items():
        src = next((lowmap[a.lower()] for a in alts if a.lower() in lowmap), None)
        res[std] = df[src] if src else None
    res = res[res["الرصيد (ريال)"].notna() | res["البنك"].notna()]
    res["العملة"] = res["العملة"].fillna("SAR")
    res["البنك"] = [canon_bank(b, "") for b in res["البنك"]]
    return _norm(res, "bal")


def _chart(fig):
    try:
        import contracts_view as cv
        fig = cv.finish_fig(fig)
    except Exception:
        pass
    st.plotly_chart(fig, use_container_width=True)


# ------------------------------------------------------------------
# الواجهة الرئيسية
# ------------------------------------------------------------------
def render_banks(ctx, build_styled_table):
    import plotly.express as px
    st.markdown(CSS, unsafe_allow_html=True)
    base, cur, ver = _state()
    unlocked = bool(ctx.get("UP_UNLOCKED", False))
    locked = not unlocked

    st.subheader("🏦 البنوك: الأرصدة والتسهيلات والضمانات والمرابحات")
    c0, c1 = st.columns([1, 3])
    as_of = c0.date_input("تاريخ احتساب المستخدم والاستحقاق", value=max(TODAY, DEFAULT_ASOF), key="bk_asof")
    c1.markdown('<div class="bk-note">البيانات من الملفات المرسلة (اتفاقية تجديد الراجحي 3/2/2026، خطاب عرض ساب 10/9/2026، جداول المرابحات، '
                'بيانات الضمانات 2025-2026). التعديل والرفع محميان بكلمة سر مركز التحديث. ويُحفظ التعديل في ملف bank_data.json بجوار التطبيق '
                '(على الاستضافة المؤقتة قد يُفقد عند إعادة النشر، فاحتفظ بنسخة من الملف).</div>', unsafe_allow_html=True)

    S = summary(as_of)
    S0 = summary(DEFAULT_ASOF)
    k = st.columns(4)
    k[0].metric("المرابحات القائمة (أصل)", f"{S['mur_principal']:,.0f}")
    k[1].metric("استحقاق تعاقدي بعد 12 شهراً", f"{S['mur_noncurrent']:,.0f}")
    k[2].metric("الضمانات القائمة", f"{S['guar_total']:,.0f}")
    k[3].metric("حدود الراجحي المتاحة", f"{_rajhi_limit(cur) - S['used']['R-TOT']:,.0f}")

    t_bal, t_fac, t_gu, t_mu = st.tabs(["💰 أرصدة البنوك", "🏦 التسهيلات", "🛡️ الضمانات القائمة", "📆 المرابحات القائمة"])

    # ------------------ أرصدة البنوك ------------------
    with t_bal:
        st.markdown('<div class="bk-title">أرصدة البنوك كما في آخر ميزان مراجعة</div>', unsafe_allow_html=True)
        bal_date = st.date_input("تاريخ الأرصدة المرفوعة", value=DEFAULT_ASOF, key="bk_baldate")
        cA, cB = st.columns([1, 2])
        cA.download_button("⬇️ تنزيل نموذج رفع الأرصدة", _template_bytes(), file_name="نموذج_ارصدة_البنوك.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="bk_tpl")
        up = cB.file_uploader("رفع ميزان المراجعة (بصيغة التقرير الحالي) أو نموذج أرصدة البنوك (Excel/CSV)", type=["xlsx", "csv"], key="bk_bal_up", disabled=locked)
        if up is not None and unlocked:
            raw = up.getvalue()
            h = hashlib.md5(raw).hexdigest()
            if st.session_state.get("bk_bal_hash") != h:
                try:
                    class _F:
                        name = up.name
                        def read(self_):
                            return raw
                    newdf = _parse_balances(_F(), bal_date)
                    base["bal"] = newdf
                    cur["bal"] = newdf.copy()
                    ver["bal"] += 1
                    st.session_state["bk_bal_hash"] = h
                    _save(cur)
                    st.success(f"تم تحميل {len(newdf)} سطراً من الملف.")
                except Exception as e:
                    st.error(f"تعذر قراءة الملف: {e}")
        if locked:
            st.info("🔒 الرفع والتعديل مقفلان. أدخل كلمة السر في الشريط الجانبي.")
        with st.expander("✏️ تعديل / إضافة أرصدة يدوياً", expanded=False):
            bal = _editor("bal", "bal", locked, base, cur, ver,
                          extra_cfg={"البنك": st.column_config.SelectboxColumn("البنك", options=BANKS),
                                     "نوع الحساب": st.column_config.SelectboxColumn("نوع الحساب", options=["جاري", "ودائع", "حساب مشاريع", "هامش ضمان", "أخرى"])})
        bal = bal.copy()
        bal["الرصيد (ريال)"] = pd.to_numeric(bal["الرصيد (ريال)"], errors="coerce").fillna(0.0)
        bal["البنك"] = [canon_bank(b, "") if str(b) not in BANKS else b for b in bal["البنك"]]   # دمج الهولندي مع ساب
        bs_cash = float(ctx.get("bs_cash_26", 0.0))
        if len(bal) == 0:
            st.markdown('<div class="bk-note">لم تُدخل أرصدة بعد. ارفع ميزان المراجعة أو النموذج المعبأ (أو أدخل الأرصدة في قسم التعديل).</div>', unsafe_allow_html=True)
        else:
            dts = [d for d in bal["تاريخ الرصيد"] if d is not None and not pd.isna(d)]
            st.caption(f"الأرصدة بتاريخ {_fmtd(max(dts)) if dts else ''}، مجمّعة لكل بنك. أي حساب بالهولندي أو بالبنك السعودي الأول يُدمج مع ساب.")
            bank_df = bal[bal["البنك"] != CASHB]
            cash_df = bal[bal["البنك"] == CASHB]
            rows = []
            for b, grp in bank_df.groupby("البنك", sort=False):
                rows.append(("item", str(b), [int(len(grp)), grp["الرصيد (ريال)"].sum(),
                                              grp["الرصيد (ريال)"].sum() / max(bank_df["الرصيد (ريال)"].sum(), 1) * 100]))
            tb_ = float(bank_df["الرصيد (ريال)"].sum())
            tc_ = float(cash_df["الرصيد (ريال)"].sum())
            rows.append(("subtotal", "إجمالي أرصدة البنوك", [int(len(bank_df)), tb_, 100.0]))
            if len(cash_df):
                rows.append(("item", CASHB, [int(len(cash_df)), tc_, None]))
            rows.append(("total", "إجمالي النقد وما في حكمه حسب الميزان", [int(len(bal)), tb_ + tc_, None]))
            tbl = build_styled_table(rows, ["البنك", "عدد الحسابات", "الرصيد (ريال)", "النسبة من البنوك %"])
            st.table(tbl)
            fb = bank_df.groupby("البنك", as_index=False)["الرصيد (ريال)"].sum()
            if len(fb) > 1:
                _chart(px.bar(fb.sort_values("الرصيد (ريال)", ascending=False), x="البنك", y="الرصيد (ريال)", title="أرصدة البنوك (ريال)"))
            with st.expander("🔎 تفصيل الحسابات"):
                drows = []
                for b, grp in bal.groupby("البنك", sort=False):
                    drows.append(("section", str(b), []))
                    for _, r in grp.iterrows():
                        drows.append(("item", str(r["رقم الحساب / IBAN"] or "حساب"), [r["الرصيد (ريال)"], _fmtd(r["تاريخ الرصيد"]), str(r["ملاحظات"] or "")]))
                    drows.append(("subtotal", f"إجمالي {b}", [grp["الرصيد (ريال)"].sum(), "", ""]))
                st.table(build_styled_table(drows, ["الحساب", "الرصيد (ريال)", "تاريخ الرصيد", "ملاحظات"]))
            rec = [
                ("item", "أرصدة البنوك حسب الميزان", [tb_]),
                ("item", "الصناديق والعهد النقدية", [tc_]),
                ("subtotal", "إجمالي النقد حسب الميزان", [tb_ + tc_]),
                ("item", "النقد وما في حكمه في المركز المالي (30 سبتمبر 2026)", [bs_cash]),
                ("total", "الفرق (الميزان − المركز المالي)", [tb_ + tc_ - bs_cash]),
            ]
            st.table(build_styled_table(rec, ["المطابقة مع المركز المالي", "المبلغ (ريال)"]))
            if abs(tb_ + tc_ - bs_cash) > 10:
                st.markdown('<div class="bk-note">يوجد فرق بين الميزان (استرشادي) ورصيد النقد في المركز المالي، ويُسجل قيد المراجعة في تبويب الفحوصات إلى حين اعتماد ميزان 30/9. '
                            'وتُعرض أرصدة الهامش المحتجز للضمانات في بند منفصل بالمركز المالي (تأمين خطابات ضمان) ولا تدخل في النقد.</div>', unsafe_allow_html=True)

    # ------------------ التسهيلات ------------------
    with t_fac:
        st.markdown('<div class="bk-title">التسهيلات المصرفية: الإجمالي والمستخدم والمتاح</div>', unsafe_allow_html=True)
        with st.expander("✏️ تعديل حدود التسهيلات", expanded=False):
            fac = _editor("fac", "fac", locked, base, cur, ver,
                          extra_cfg={"البنك": st.column_config.SelectboxColumn("البنك", options=BANKS),
                                     "النوع": st.column_config.SelectboxColumn("النوع", options=["إجمالي", "فرعي"])})
        fac = fac.copy()
        fac["السقف"] = pd.to_numeric(fac["السقف"], errors="coerce").fillna(0.0)
        used, mc = fac_used(cur, as_of)
        rows = []
        tot_lim = tot_used = 0.0
        FX = {
            "R-TOT": "المستخدم = مجموع المستخدم من التسهيلات 1.1 + 1.2 + 1.3",
            "R-1.1": "المستخدم = المتبقي من أصل المرابحات القائمة (تمويل 1 إلى 4)",
            "R-1.2": "المستخدم = الضمانات القائمة المغطاة نقداً بأقل من 100% (منطق ملف الضمانات)",
            "R-1.3": "المستخدم = تمويل الرواتب 12 مليون (مسحوب 27/10/2026، فلا يظهر قبل هذا التاريخ)",
            "S-TOT": "المستخدم = مجموع الضمانات القائمة لدى ساب (4 ضمانات)",
        }
        for b, grp in fac.groupby("البنك", sort=False):
            rows.append(("section", str(b), []))
            for _, r in grp.sort_values("النوع", key=lambda s: s.map({"فرعي": 0, "إجمالي": 1})).iterrows():
                u = used.get(r["الرمز"], 0.0)
                lim = float(r["السقف"])
                rt = "total" if r["النوع"] == "إجمالي" else "item"
                rows.append((rt, r["التسهيل"], [lim, u, lim - u, (u / lim * 100) if lim else 0.0, FX.get(r["الرمز"], "")]))
        st.table(build_styled_table(rows, ["التسهيل", "السقف", "المستخدم", "المتاح", "نسبة الاستخدام %", "طريقة احتساب المستخدم"],
                                    formula_col="طريقة احتساب المستخدم"))
        # عرض نسبة الاستخدام مع % : نص جاهز
        rj_lim = _rajhi_limit(cur)
        ex = []
        if rj_lim:
            ex.append(f"استخدام تسهيلات الراجحي {used['R-TOT'] / rj_lim * 100:.1f}% من {rj_lim:,.0f}.")
        ex.append("تمويل الرواتب (12 مليون) يُحتسب مستخدماً من تاريخ سحبه 27/10/2026؛ غيّر تاريخ المركز لإظهاره.")
        ex.append("ساب: الإجمالي 17,291,538 والمستخدم 12,429,769 (4 ضمانات) والمتاح 4,861,769، وهو يطابق ملف الضمانات المحدَّث.")
        for t in ex:
            st.markdown(f'<div class="bk-fx">{t}</div>', unsafe_allow_html=True)

        fig_rows = []
        for sym, lab in [("R-1.1", "الراجحي 1.1"), ("R-1.2", "الراجحي 1.2 ضمانات"), ("R-1.3", "الراجحي 1.3")]:
            lim = float(fac.loc[fac["الرمز"] == sym, "السقف"].sum())
            fig_rows += [{"التسهيل": lab, "البند": "المستخدم", "المبلغ": used[sym]},
                         {"التسهيل": lab, "البند": "المتاح", "المبلغ": max(lim - used[sym], 0.0)}]
        if fig_rows:
            fig = px.bar(pd.DataFrame(fig_rows), x="التسهيل", y="المبلغ", color="البند", barmode="stack",
                         title="استخدام تسهيلات الراجحي (ريال)", color_discrete_map={"المستخدم": "#1E3A8A", "المتاح": "#93C5FD"})
            _chart(fig)

        with st.expander("📜 شروط وحدود تسهيلات الراجحي الأساسية (من اتفاقية التجديد 3/2/2026)"):
            st.markdown("""
- **مدة التسهيلات**: حتى تاريخ المراجعة السنوية **31/12/2026**، والتجديد بموافقة المصرف.
- **المديونية القائمة وقت الاتفاقية**: 30,000,000 ريال، وسند لأمر بمبلغ 33,830,559 ريال، وكفالة مجموعة الحكير.
- **الضمانات**: الحد 25,000,000 ريال؛ الحد الأعلى للضمان الابتدائي 2,000,000، وما زاد عن 700,000 يحتاج موافقة؛ والنهائي ما زاد عن 3,500,000 يحتاج موافقة. وتخص المشاريع الحكومية وشبه الحكومية، وتوريد تنازل المستحقات خلال 60 يوماً من الضمان النهائي.
- **التمويل**: بحد أقصى 25,000,000 ريال للمشروع، وبنسبة لا تتجاوز 50% من قيمة عقود المشاريع المتوقعة.
- **تمويل المستورد (1.1.1)**: مدة 36 شهراً، سايبور 6 أشهر + هامش 3% سنوياً (يُحتسب 1.5% لكل فترة 6 أشهر، ويُعاد التسعير كل 6 أشهر).
- **ساب**: ضمان سند لأمر 17,291,538 ريال، وتفويض بالخصم من الحسابات، وزيارات ميدانية دورية سنوياً، ورسوم الترتيب والتجديد غير مستردة.
""")

        st.markdown('<div class="bk-title">تكلفة التسهيلات وشروطها: مرجع مقارنة بين البنوك</div>', unsafe_allow_html=True)
        st.caption("الصفوف بنود التسهيلات والأعمدة البنوك. أُخذت من اتفاقية الراجحي وخطاب ساب وملفات التمويل والضمانات. والخانات المكتوب فيها 'غير محدد' تُستكمل. يمكن تعديل أي خانة من قسم التعديل.")
        with st.expander("✏️ تعديل جدول التكاليف والشروط", expanded=False):
            costdf = _editor("cost", "cost", locked, base, cur, ver)
        cost_rows = [("item", str(r["البند"]), [str(r[RAJHI] or ""), str(r[SAB] or ""), str(r[AHLI] or "")]) for _, r in costdf.iterrows()]
        st.table(build_styled_table(cost_rows, ["البند", RAJHI, SAB, AHLI]))

    # ------------------ الضمانات ------------------
    with t_gu:
        st.markdown('<div class="bk-title">الضمانات البنكية القائمة</div>', unsafe_allow_html=True)
        with st.expander("✏️ تعديل / إضافة ضمانات (إلغاء ضمان: غيّر حالة السجل إلى 'ملغي')", expanded=False):
            gdf = _editor("guar", "guar", locked, base, cur, ver,
                          extra_cfg={"البنك": st.column_config.SelectboxColumn("البنك", options=BANKS),
                                     "حالة السجل": st.column_config.SelectboxColumn("حالة السجل", options=[ST_OK, ST_CANCEL])})
        g = gdf.copy()
        g["مبلغ الضمان"] = pd.to_numeric(g["مبلغ الضمان"], errors="coerce").fillna(0.0)
        g["الغطاء النقدي (الهامش)"] = pd.to_numeric(g["الغطاء النقدي (الهامش)"], errors="coerce").fillna(0.0)
        sel = st.multiselect("البنك", [b for b in BANKS if b in set(g["البنك"])], default=[b for b in BANKS if b in set(g["البنك"])], key="bk_gsel")
        show_cancel = st.checkbox("إظهار الضمانات الملغاة", value=False, key="bk_gcancel")
        gv = g[g["البنك"].isin(sel)]
        if not show_cancel:
            gv = gv[gv["حالة السجل"] == ST_OK]
        rows = []
        for b, grp in gv.groupby("البنك", sort=False):
            rows.append(("section", str(b), []))
            for _, r in grp.iterrows():
                cov = (r["الغطاء النقدي (الهامش)"] / r["مبلغ الضمان"] * 100) if r["مبلغ الضمان"] else 0.0
                rows.append(("item", r["البيان"], [str(r["رقم الضمان"] or ""), r["مبلغ الضمان"], r["الغطاء النقدي (الهامش)"], f"{cov:.0f}%",
                                                 _fmtd(r["تاريخ الإصدار"]), _fmtd(r["تاريخ الانتهاء"]),
                                                 guar_status(_ts(r["تاريخ الانتهاء"]), as_of, r["حالة السجل"]), str(r["ملاحظات"] or "")]))
            rows.append(("subtotal", f"إجمالي {b}", ["", grp["مبلغ الضمان"].sum(), grp["الغطاء النقدي (الهامش)"].sum(), "", "", "", "", ""]))
        rows.append(("total", "إجمالي الضمانات", ["", gv["مبلغ الضمان"].sum(), gv["الغطاء النقدي (الهامش)"].sum(), "", "", "", "", ""]))
        st.table(build_styled_table(rows, ["البيان", "رقم الضمان", "مبلغ الضمان", "الغطاء النقدي", "نسبة الغطاء", "الإصدار", "الانتهاء", "الحالة", "ملاحظات"],
                                    formula_col="ملاحظات"))

        act = g[g["حالة السجل"] == ST_OK].copy()
        act["_exp"] = pd.to_datetime(act["تاريخ الانتهاء"], errors="coerce")
        near = act[(act["_exp"] >= pd.Timestamp(as_of)) & (act["_exp"] <= pd.Timestamp(as_of) + pd.Timedelta(days=90))]
        expd = act[act["_exp"] < pd.Timestamp(as_of)]
        m = st.columns(3)
        m[0].metric("ضمانات تنتهي خلال 90 يوماً", f"{len(near)}", f"{near['مبلغ الضمان'].sum():,.0f} ريال")
        m[1].metric("تاريخ انتهائها متجاوز (تجديد سنوي)", f"{len(expd)}", f"{expd['مبلغ الضمان'].sum():,.0f} ريال")
        m[2].metric("إجمالي الضمانات القائمة", f"{len(act)}", f"{act['مبلغ الضمان'].sum():,.0f} ريال")
        if len(near):
            st.markdown('<div class="bk-note">⏰ ضمانات تنتهي خلال 90 يوماً (تُجدَّد سنوياً تلقائياً ما لم يُطلب الإلغاء؛ للمتابعة): '
                        + "، ".join(f"{r['البيان']} ({_fmtd(r['تاريخ الانتهاء'])})" for _, r in near.iterrows()) + "</div>", unsafe_allow_html=True)
        if len(expd):
            st.markdown('<div class="bk-note">ℹ️ ضمانات تجاوزت تاريخ انتهائها في الملف (تُجدَّد تلقائياً فيلزم تحديث التاريخ): '
                        + "، ".join(f"{r['البيان']} ({_fmtd(r['تاريخ الانتهاء'])})" for _, r in expd.iterrows()) + "</div>", unsafe_allow_html=True)
        by_bank = act.groupby("البنك", as_index=False).agg(الضمانات=("مبلغ الضمان", "sum"), الهامش=("الغطاء النقدي (الهامش)", "sum"))
        if len(by_bank):
            fb = by_bank.melt(id_vars="البنك", var_name="البند", value_name="المبلغ")
            _chart(px.bar(fb, x="البنك", y="المبلغ", color="البند", barmode="group", title="الضمانات والهامش النقدي حسب البنك (ريال)",
                          color_discrete_map={"الضمانات": "#1E3A8A", "الهامش": "#60A5FA"}))
        st.markdown('<div class="bk-fx">المطابقة: إجمالي الهامش النقدي للضمانات القائمة يُقارن في تبويب الفحوصات مع رصيد حسابات تأمين خطابات الضمان بميزان 30/9 (11,137,440) ومع المركز المالي (9,550,682).</div>', unsafe_allow_html=True)

    # ------------------ المرابحات ------------------
    with t_mu:
        st.markdown('<div class="bk-title">المرابحات القائمة (قصيرة وطويلة الأجل)</div>', unsafe_allow_html=True)
        with st.expander("✏️ تعديل التمويلات (الحالة والأصل والتواريخ)", expanded=False):
            mst = _editor("mst", "mst", locked, base, cur, ver,
                          extra_cfg={"الحالة": st.column_config.SelectboxColumn("الحالة", options=[MST_ACTIVE, MST_PLANNED, MST_CLOSED]),
                                     "التسهيل": st.column_config.SelectboxColumn("التسهيل", options=["1.1", "1.2", "1.3"])})
        with st.expander("✏️ تعديل جدول الأقساط (أصل القسط والربح وتواريخ الاستحقاق)", expanded=False):
            sch = _editor("sch", "sch", locked, base, cur, ver)
        mc = mur_calc(mst, sch, as_of)
        rows = []
        for _, r in mc.iterrows():
            rows.append(("item", f"{r['التمويل']}: {r['الوصف']}",
                         [_fmtd(r["تاريخ التمويل"]), r["أصل التمويل"], r["المسدد من الأصل"], r["المتبقي (أصل)"], r["المتداول"], r["غير المتداول"],
                          r["القسط القادم (أصل)"], r["ربح القسط القادم"], _fmtd(r["تاريخ القسط القادم"]), r["الحالة"]]))
        tt = lambda c: float(mc[c].sum())
        rows.append(("total", "الإجمالي (القائم فقط في المتبقي)", ["", tt("أصل التمويل"), tt("المسدد من الأصل"), tt("المتبقي (أصل)"), tt("المتداول"),
                                                                    tt("غير المتداول"), tt("القسط القادم (أصل)"), tt("ربح القسط القادم"), "", ""]))
        st.table(build_styled_table(rows, ["التمويل", "تاريخ التمويل", "أصل التمويل", "المسدد من الأصل", "المتبقي (أصل)",
                                           "استحقاق تعاقدي ≤12 شهراً", "استحقاق تعاقدي >12 شهراً", "القسط القادم (أصل)", "ربح القسط القادم", "تاريخ القسط القادم", "الحالة"]))
        st.markdown('<div class="bk-fx">التصنيف المحاسبي: كامل المتبقي قصير الأجل، لأن التمويل مدته التعاقدية 3 سنوات لكنه يُعاد تسعيره ويُجدَّد كل 6 أشهر '
                    '(سايبور 6 أشهر + 1.5% لكل فترة)، وهو كما في نموذج التمويل والمركز المالي. العمودان الأخيران معلومة تعاقدية فقط. '
                    'ربح الأقساط المستقبلية متغير فلا يظهر إلا للقسط القادم.</div>', unsafe_allow_html=True)

        bs_loans = float(ctx.get("bs_loans_26", 0.0))
        tb_loans = float(ctx.get("tb_loans_30_09", 0.0))
        defc = float(ctx.get("bs_def_fin_26", 0.0))
        tot_sched = tt("المتبقي (أصل)") + tt("ربح القسط القادم")
        rec = [
            ("item", "المتبقي من أصل المرابحات القائمة", [tt("المتبقي (أصل)")]),
            ("item", "يضاف: ربح القسط القادم المستحق (كما في جدول الأقساط)", [tt("ربح القسط القادم")]),
            ("subtotal", "المتبقي حسب جداول الأقساط", [tot_sched]),
            ("item", "رصيد حساب المرابحات في ميزان 30/9/2026", [tb_loans]),
            ("item", "الفرق (جداول الأقساط − الميزان)", [tot_sched - tb_loans]),
            ("item", "ناقصاً: نفقات تمويل متداولة مؤجلة (كما في المركز المالي)", [-defc]),
            ("subtotal", "المرابحات بعد خصم النفقات المؤجلة", [tot_sched - defc]),
            ("item", "قروض وتسهيلات قصيرة الأجل في المركز المالي", [bs_loans]),
            ("total", "الفرق", [tot_sched - defc - bs_loans]),
        ]
        st.table(build_styled_table(rec, ["مطابقة المرابحات مع الميزان والمركز المالي", "المبلغ (ريال)"]))

        st.markdown('<div class="bk-title">تفاصيل التمويلات: الموردون وأوامر الشراء</div>', unsafe_allow_html=True)
        with st.expander("✏️ تعديل تفاصيل الموردين", expanded=False):
            ast = _editor("ast", "ast", locked, base, cur, ver)
        a = ast.copy()
        for c in ["عدد الأصول", "قيمة الأصول بسجل الأصول (قبل الضريبة)", "إجمالي الفاتورة / الدفعة"]:
            a[c] = pd.to_numeric(a[c], errors="coerce")
        a["_reg"] = a["قيمة الأصول بسجل الأصول (قبل الضريبة)"].fillna(0.0)
        a["_inv"] = a["إجمالي الفاتورة / الدفعة"].fillna(0.0)
        a["_vat"] = a["_reg"] * 0.15
        a["_oth"] = a["_inv"] - a["_reg"] - a["_vat"]
        rows = []
        for fid, grp in a.groupby("التمويل", sort=False):
            rows.append(("section", str(fid), []))
            for _, r in grp.iterrows():
                rows.append(("item", str(r["المورد"]), [None if pd.isna(r["عدد الأصول"]) else int(r["عدد الأصول"]), r["_reg"], r["_vat"], r["_oth"], r["_inv"]]))
            inv = float(grp["_inv"].sum())
            rows.append(("subtotal", f"إجمالي {fid}: تمويل البنك 90% = {inv * 0.9:,.0f}، والدفعة المقدمة 10% = {inv * 0.1:,.0f}",
                         [None, grp["_reg"].sum(), grp["_vat"].sum(), grp["_oth"].sum(), inv]))
        rows.append(("total", "إجمالي التمويلات", [None, a["_reg"].sum(), a["_vat"].sum(), a["_oth"].sum(), a["_inv"].sum()]))
        st.table(build_styled_table(rows, ["المورد", "عدد الأصول", "قيمة الأصول (سجل الأصول)", "ضريبة القيمة المضافة 15%", "رسوم تسجيل وأخرى (الفرق)", "إجمالي الفاتورة / الدفعة"]))
        st.markdown('<div class="bk-fx">رسوم التسجيل والأخرى = إجمالي الفاتورة − قيمة سجل الأصول − 15% ضريبة. تقنيات الشاحنات أمر شراء واحد مموَّل بثلاث دفعات (تمويل 2 و3 و4)، '
                    'وقيمة كل دفعة قبل الضريبة موزعة من الفاتورة، ومجموع الشاحنات بسجل الأصول 7,858,000 × 1.15 = 9,036,700 تماماً.</div>', unsafe_allow_html=True)

        st.markdown('<div class="bk-title">جدول الأقساط التفصيلي</div>', unsafe_allow_html=True)
        s = sch.copy()
        s["_d"] = pd.to_datetime(s["تاريخ الاستحقاق"], errors="coerce")
        rows = []
        for fid, grp in s.groupby("التمويل", sort=False):
            stt = mst.loc[mst["التمويل"] == fid, "الحالة"]
            stt = stt.iloc[0] if len(stt) else ""
            rows.append(("section", f"{fid} ({stt})", []))
            for _, r in grp.sort_values("_d").iterrows():
                pr, pf = _num(r["أصل القسط"]), (None if pd.isna(r["الربح"]) else float(r["الربح"]))
                paid = (r["_d"] <= pd.Timestamp(as_of)) if pd.notna(r["_d"]) else False
                rows.append(("item", f"قسط {int(_num(r['القسط']))}",
                             [_fmtd(r["_d"]), pr, pf, (pr + pf) if pf is not None else None,
                              "✅ مسدد" if paid else ("⏳ قادم" if stt == MST_ACTIVE else "غير مسحوب")]))
        st.table(build_styled_table(rows, ["القسط", "تاريخ الاستحقاق", "أصل القسط", "الربح", "الإجمالي", "الحالة"]))

        _tl = []
        for _, r in s.iterrows():
            stt = mst.loc[mst["التمويل"] == r["التمويل"], "الحالة"]
            if len(stt) and stt.iloc[0] == MST_ACTIVE and pd.notna(r["_d"]) and r["_d"] > pd.Timestamp(as_of):
                _tl.append({"الربع": f"{r['_d'].year}-Q{(r['_d'].month - 1) // 3 + 1}", "التمويل": r["التمويل"], "أصل القسط": _num(r["أصل القسط"])})
        if _tl:
            tl = pd.DataFrame(_tl).groupby(["الربع", "التمويل"], as_index=False).sum().sort_values("الربع")
            _chart(px.bar(tl, x="الربع", y="أصل القسط", color="التمويل", title="الأقساط المستحقة (أصل) حسب الربع (ريال)"))


def _rajhi_limit(cur):
    f = cur["fac"]
    v = f.loc[f["الرمز"] == "R-TOT", "السقف"]
    return _num(v.iloc[0]) if len(v) else 0.0
