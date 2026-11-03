# actuary.py
# التقييم الاكتواري لنهاية الخدمة وفق IAS 19 بطريقة وحدة الائتمان المتوقعة (PUC)، مُعايَر على تقرير 31/12/2025.
# دوال خالصة (بدون Streamlit) لتسهيل الاختبار.

import numpy as np
import pandas as pd

DEFAULT = dict(
    dr=5.30,         # معدل الخصم عند نهاية السنة %
    dr_open=5.30,    # معدل الخصم في بداية السنة % (لتكلفة الفائدة)
    si=2.0,          # نمو الرواتب %
    ret=60,          # سن التقاعد
    qa=1e-4, qb=0.12,  # وفيات غومبرتز q(x)=qa*exp(qb*x) مُعايَرة على نتائج 2025 (جدول الوفيات السعودي غير متاح رقمياً)
    # معدل ترك الخدمة السنوي حسب سنوات الخدمة المكتملة (الحد الأعلى للشريحة، النسبة %): 0–5: 25، 6–10: 15، 11–19: 10، 20+: 1
    turn=[[5, 25.0], [10, 15.0], [20, 10.0], [999, 1.0]],
)


def fac(S):
    """أشهر الأجر المستحقة لمدة خدمة S سنة: نصف شهر عن كل سنة من الخمس الأولى وشهر عن كل سنة بعدها."""
    S = np.asarray(S, dtype=float)
    return 0.5 * np.minimum(S, 5) + np.maximum(S - 5, 0)


def resf(S):
    """نسبة المستحق عند الاستقالة: أقل من سنتين لا شيء، 2–5 ثلث، 5–10 ثلثان، 10+ كامل."""
    S = np.asarray(S, dtype=float)
    return np.where(S < 2, 0.0, np.where(S < 5, 1 / 3, np.where(S < 10, 2 / 3, 1.0)))


def wrate(S, tbl, shift=0.0):
    S = np.floor(np.asarray(S, dtype=float))
    out = np.full(S.shape, float(tbl[-1][1]))
    for lim, r in reversed(tbl):
        out = np.where(S < lim, r, out)
    return np.clip(out / 100.0 + shift, 0.0, 1.0)


def valuate(age, yos, sal_m, dr, si, ret, qa, qb, tbl, shift=0.0, mid=0.5):
    """يعيد (الالتزام DBO، المنافع المتوقعة خلال سنة، تكلفة الخدمة المتوقعة = DBO ÷ سنوات الخدمة) لكل موظف.
    age/yos بالسنوات العشرية، sal_m الأجر الشهري الإجمالي، المعدلات كنسب مئوية."""
    age = np.asarray(age, dtype=float)
    yos = np.asarray(yos, dtype=float)
    m = np.asarray(sal_m, dtype=float)
    dr, si = dr / 100.0, si / 100.0
    n = len(age)
    dbo = np.zeros(n)
    e1 = np.zeros(n)
    surv = np.ones(n)
    T = int(np.ceil(max(float((ret - age).max()), 1.0))) + 1 if n else 1
    for k in range(T):
        x = age + k
        alive = x < ret
        span = np.clip(ret - x, 0.0, 1.0)
        S = yos + k
        q = np.minimum(1.0, qa * np.exp(qb * x) * span)
        ww = np.minimum(1.0, wrate(S, tbl, shift) * span)
        t = k + mid * span
        Sx = yos + t
        sal_t = m * (1 + si) ** t
        ben_res = fac(Sx) * sal_t * resf(Sx)
        ben_full = fac(Sx) * sal_t
        ac = np.where(Sx > 0, yos / np.maximum(Sx, 1e-9), 0.0)
        pay = alive * surv * (ww * ben_res + q * (1 - ww) * ben_full)
        dbo += pay * ac / (1 + dr) ** t
        if k == 0:
            e1 += pay
        surv = surv * (1 - ww) * (1 - q) * alive
        reach = (x + span >= ret - 1e-9) & alive
        tr = k + span
        Sr = yos + tr
        ben = fac(Sr) * m * (1 + si) ** tr
        dbo += reach * surv * ben * np.where(Sr > 0, yos / np.maximum(Sr, 1e-9), 0.0) / (1 + dr) ** tr
        if k == 0:
            e1 += reach * surv * ben
        surv = surv * (~reach)
    over = age >= ret  # بلغ سن التقاعد: يُستحق كاملاً
    ben_now = fac(yos) * m * (1 + si) ** 0.5
    dbo = np.where(over, ben_now, dbo)
    e1 = np.where(over, ben_now, e1)
    psc = np.where(yos > 0, dbo / np.maximum(yos, 1e-9), 0.0)
    return dbo, e1, psc


def run(D, a, shift=0.0, dr=None, si=None):
    """D: DataFrame بأعمدة age, yos, sal_m؛ a: الفرضيات."""
    return valuate(D["age"].values, D["yos"].values, D["sal_m"].values,
                   a["dr"] if dr is None else dr, a["si"] if si is None else si, a["ret"], a["qa"], a["qb"], a["turn"], shift)


def movement(open_net, sc, interest_rate_open, payments, close_net):
    """حركة صافي الالتزام: الفائدة = معدل بداية السنة × (الرصيد الافتتاحي + تكلفة الخدمة − نصف المدفوعات)
    (تطابق أرقام تقرير 2025: 1,364,000 وإسقاط 2026: 914,000)."""
    interest = interest_rate_open / 100.0 * (open_net + sc - 0.5 * payments)
    remeas = close_net - (open_net + sc + interest - payments)
    return interest, remeas
