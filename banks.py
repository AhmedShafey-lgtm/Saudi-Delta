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
DEFAULT_ASOF = dt.date(2026, 9, 30)
RAJHI, SAB, AHLI = "مصرف الراجحي", "البنك السعودي الأول (ساب)", "البنك الأهلي"
BANKS = [RAJHI, SAB, AHLI, "أخرى"]
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
    # الراجحي: بيان 31/03/2026 (الضمانات الجديدة 2026 بهامش 10%)
    _g(RAJHI, "ضمان نهائي موحد تبوك (2013)", "4000000920", "48809177", 1346667, 1346667, D(2013, 6, 30), D(2027, 1, 15), "تغطية نقدية 100%"),
    _g(RAJHI, "ضمان نهائي موحد تبوك الجديد (2016)", "4000054893", "48806152", 2051500, 2051500, D(2016, 9, 28), D(2026, 4, 30), "تغطية 100% - انتهى 30/4/2026: يُراجع الإلغاء/الإفراج"),
    _g(RAJHI, "ضمان نهائي موحد الباحة 2021", "4000069334", "48801799", 4644195, 464419.5, D(2021, 5, 19), D(2026, 12, 1), "هامش 10%"),
    _g(RAJHI, "ضمان نهائي موحد الرياض 2021", "4000069347", "48801820", 2013458, 201345.8, D(2021, 5, 20), D(2026, 12, 1), "هامش 10%"),
    _g(RAJHI, "ضمان نهائي موحد تبوك 2021", "400069341", "48801821", 1634700, 163470.0, D(2021, 5, 20), D(2026, 12, 1), "هامش 10%"),
    _g(RAJHI, "ضمان نهائي موحد مكة المكرمة 2021", "4000069318", "48801822", 2574282, 257428.2, D(2021, 5, 20), D(2026, 12, 1), "هامش 10%"),
    _g(RAJHI, "ضمان نهائي موحد عسير 2021", "4000069363", "48801823", 3079486, 307948.6, D(2021, 5, 20), D(2026, 12, 1), "هامش 10%"),
    _g(RAJHI, "ضمان نهائي موحد تبوك القديم", "20841026", "48805215", 580000, 580000, D(2021, 12, 29), D(2026, 12, 27), "تغطية نقدية 100%"),
    _g(RAJHI, "العقد الموحد لشبكات الطاقة - الرياض (2026)", "4000083770", "48803259", 2421291, 242129.1, D(2026, 4, 4), D(2030, 11, 30), "هامش 10%"),
    _g(RAJHI, "العقد الموحد لشبكات الطاقة - الباحة (2026)", "4000083747", "48803256", 1283000, 128300.0, D(2026, 4, 4), D(2030, 11, 30), "هامش 10%"),
    _g(RAJHI, "العقد الموحد لشبكات الطاقة - عسير (2026)", "4000083755", "48803260", 1540625, 154062.5, D(2026, 4, 4), D(2030, 11, 30), "هامش 10%"),
    _g(RAJHI, "العقد الموحد لشبكات الطاقة - تبوك (2026)", "4000083773", "48803257", 887500, 88750.0, D(2026, 4, 4), D(2030, 11, 30), "هامش 10%"),
    # الأهلي: بيان 31/12/2025 - مغطاة بالكامل من الحسابات
    _g(AHLI, "ضمان نهائي موحد الباحة 2013", "4131025", "125179", 1200000, 1200000, D(2013, 1, 9), D(2026, 12, 18), "مغطى بالكامل (حسب عنوان الملف)"),
    _g(AHLI, "ضمان نهائي موحد عسير 2013", "41341002", "125178", 1000000, 1000000, D(2013, 1, 9), D(2026, 12, 18), "مغطى بالكامل (حسب عنوان الملف)"),
    _g(AHLI, "ضمان نهائي موحد عسير 2016", "4400008840", "174015", 2118500, 2118500, None, None, "تاريخا الإصدار والانتهاء غير مذكورين بالملف. يُرجى التأكيد"),
    _g(AHLI, "ضمان نهائي موحد الباحة 2016", "4400008867", "174016", 2118500, 2118500, D(2016, 10, 23), D(2026, 10, 31),
       "إجمالي الملف المرسل 4,318,500 لا يشمل أحد ضماني 2016؛ تم افتراض التغطية الكاملة. يُرجى التأكيد"),
    # ساب
    _g(SAB, "ضمان نهائي موحد مكة 2016", "4000054877", "1628737", 2529000, 0, D(2016, 9, 28), D(2024, 4, 30),
       "من ملف ساب 2022؛ تاريخ الانتهاء والغطاء بحاجة لتأكيد، وحد التسهيل (1-2) عُدّل إلى 2,529,000 في خطاب 10/9/2026"),
]

DEFAULT_FAC = [
    [RAJHI, "R-TOT", "إجمالي حدود تسهيلات الراجحي (اتفاقية التجديد 3/2/2026)", 65000000.0, "إجمالي"],
    [RAJHI, "R-1.1", "1.1 تسهيل النفقات الرأسمالية وتوسيع الأعمال (تمويل مستورد / بيع آجل / اعتمادات)", 20000000.0, "فرعي"],
    [RAJHI, "R-1.2", "1.2 تسهيل تمويل المشاريع: ضمانات ابتدائية ونهائية", 25000000.0, "فرعي"],
    [RAJHI, "R-1.3", "1.3 تسهيل بيع آجل (يشمل الرواتب ومتطلبات العميل)", 20000000.0, "فرعي"],
    [SAB, "S-TOT", "إجمالي التسهيلات (خطاب العرض SAB-261779 بتاريخ 10/9/2026)", 17291538.0, "إجمالي"],
    [SAB, "S-1.2", "منها: التسهيل (1-2) بعد التعديل", 2529000.0, "فرعي"],
]

DEFAULT_MST = [
    ["تمويل 1", "تمويل فاتورة هلا السعودية (شراء سيارات)", "1.1", D(2025, 6, 24), 4049999.99, MST_ACTIVE],
    ["تمويل 2", "تمويل شراء معدات وسيارات (مجموعة موردين)", "1.1", D(2025, 11, 10), 7239069.00, MST_ACTIVE],
    ["تمويل 3", "تمويل شراء أصول (مجموعة موردين)", "1.1", D(2026, 3, 27), 5049764.98, MST_ACTIVE],
    ["تمويل 4", "تمويل شراء شاحنات - تقنيات الشاحنات (بلفنجر)", "1.1", D(2026, 6, 22), 3001500.00, MST_ACTIVE],
    ["تمويل 5", "تمويل رواتب ومتطلبات التشغيل (12 شهراً، سداد دفعة واحدة)", "1.3", None, 12000000.00, MST_PLANNED],
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

DATE_COLS = {"bal": ["تاريخ الرصيد"], "guar": ["تاريخ الإصدار", "تاريخ الانتهاء"],
             "mst": ["تاريخ التمويل"], "sch": ["تاريخ الاستحقاق"], "fac": []}
COLS = {"bal": BAL_COLS, "guar": GUAR_COLS, "fac": FAC_COLS, "mst": MST_COLS, "sch": SCH_COLS}
NUM_COLS = {"bal": ["الرصيد (ريال)"], "guar": ["مبلغ الضمان", "الغطاء النقدي (الهامش)"], "fac": ["السقف"],
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
        "bal": _norm(pd.DataFrame(columns=BAL_COLS), "bal"),
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
        return "🔴 منتهي: يُراجع الإلغاء/التجديد"
    if exp <= asof + pd.Timedelta(days=90):
        return "🟠 ينتهي خلال 90 يوماً"
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
        counts = status == MST_ACTIVE
        rem = float(fut["_p"].sum()) if counts else 0.0
        cur = float(fut[fut["_d"] <= lim]["_p"].sum()) if counts else 0.0
        nxt = fut.iloc[0] if len(fut) else None
        rows.append({
            "التمويل": fid, "الوصف": m["الوصف"], "التسهيل": m["التسهيل"], "تاريخ التمويل": m["تاريخ التمويل"],
            "أصل التمويل": _num(m["أصل التمويل"]), "الحالة": status,
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
            "S-1.2": used_s, "S-TOT": used_s}
    return used, mc


def summary(as_of=None):
    """ملخص للفحوصات والواجهة الرئيسية."""
    _, cur, _ = _state()
    as_of = as_of or st.session_state.get("bk_asof", DEFAULT_ASOF)
    used, mc = fac_used(cur, as_of)
    g = cur["guar"]
    act = g[g["حالة السجل"] == ST_OK].copy()
    act["_exp"] = pd.to_datetime(act["تاريخ الانتهاء"], errors="coerce")
    live = act[~(act["_exp"] < pd.Timestamp(as_of))]
    bal = pd.to_numeric(cur["bal"]["الرصيد (ريال)"], errors="coerce").fillna(0.0).sum()
    return {
        "mur_principal": float(mc["المتبقي (أصل)"].sum()),
        "mur_current": float(mc["المتداول"].sum()),
        "mur_noncurrent": float(mc["غير المتداول"].sum()),
        "mur_next_profit": float(mc["ربح القسط القادم"].sum()),
        "guar_total": float(pd.to_numeric(act["مبلغ الضمان"], errors="coerce").fillna(0).sum()),
        "guar_margin": float(pd.to_numeric(act["الغطاء النقدي (الهامش)"], errors="coerce").fillna(0).sum()),
        "guar_margin_live": float(pd.to_numeric(live["الغطاء النقدي (الهامش)"], errors="coerce").fillna(0).sum()),
        "bal_total": float(bal), "bal_rows": int(len(cur["bal"])), "used": used,
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


def _parse_balances(f):
    name = getattr(f, "name", "")
    raw = f.read() if hasattr(f, "read") else f
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
    as_of = c0.date_input("تاريخ المركز", value=DEFAULT_ASOF, key="bk_asof")
    c1.markdown('<div class="bk-note">البيانات من الملفات المرسلة (اتفاقية تجديد الراجحي 3/2/2026، خطاب عرض ساب 10/9/2026، جداول المرابحات، '
                'بيانات الضمانات 2025-2026). التعديل والرفع محميان بكلمة سر مركز التحديث. ويُحفظ التعديل في ملف bank_data.json بجوار التطبيق '
                '(على الاستضافة المؤقتة قد يُفقد عند إعادة النشر، فاحتفظ بنسخة من الملف).</div>', unsafe_allow_html=True)

    S = summary(as_of)
    k = st.columns(4)
    k[0].metric("المرابحات القائمة (أصل)", f"{S['mur_principal']:,.0f}")
    k[1].metric("منها قصيرة الأجل (≤12 شهراً)", f"{S['mur_current']:,.0f}")
    k[2].metric("الضمانات القائمة", f"{S['guar_total']:,.0f}")
    k[3].metric("حدود الراجحي المتاحة", f"{_rajhi_limit(cur) - S['used']['R-TOT']:,.0f}")

    t_bal, t_fac, t_gu, t_mu = st.tabs(["💰 أرصدة البنوك", "🏦 التسهيلات", "🛡️ الضمانات القائمة", "📆 المرابحات القائمة"])

    # ------------------ أرصدة البنوك ------------------
    with t_bal:
        st.markdown('<div class="bk-title">أرصدة البنوك كما في آخر ميزان مراجعة</div>', unsafe_allow_html=True)
        cA, cB = st.columns([1, 2])
        cA.download_button("⬇️ تنزيل نموذج رفع الأرصدة", _template_bytes(), file_name="نموذج_ارصدة_البنوك.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="bk_tpl")
        up = cB.file_uploader("رفع أرصدة البنوك المحدثة (Excel/CSV بنفس أعمدة النموذج)", type=["xlsx", "csv"], key="bk_bal_up", disabled=locked)
        if up is not None and unlocked:
            raw = up.getvalue()
            h = hashlib.md5(raw).hexdigest()
            if st.session_state.get("bk_bal_hash") != h:
                try:
                    class _F:
                        name = up.name
                        def read(self_):
                            return raw
                    newdf = _parse_balances(_F())
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
        bs_cash = float(ctx.get("bs_cash_26", 0.0))
        if len(bal) == 0:
            st.markdown('<div class="bk-note">لم تُدخل أرصدة بعد. لم يصل ميزان مراجعة تفصيلي بحسابات البنوك. ارفع النموذج المعبأ (أو أدخل الأرصدة في قسم التعديل) ليظهر الجدول والمطابقة مع بند النقد في المركز المالي.</div>', unsafe_allow_html=True)
        else:
            rows = []
            for b, grp in bal.groupby("البنك", sort=False):
                rows.append(("section", str(b), []))
                for _, r in grp.iterrows():
                    rows.append(("item", f"{r['رقم الحساب / IBAN'] or ''} {r['نوع الحساب'] or ''}".strip() or "حساب",
                                 [r["الرصيد (ريال)"], _fmtd(r["تاريخ الرصيد"]), str(r["ملاحظات"] or "")]))
                rows.append(("subtotal", f"إجمالي {b}", [grp["الرصيد (ريال)"].sum(), "", ""]))
            tot = float(bal["الرصيد (ريال)"].sum())
            rows.append(("total", "إجمالي أرصدة البنوك", [tot, "", ""]))
            st.table(build_styled_table(rows, ["الحساب", "الرصيد (ريال)", "تاريخ الرصيد", "ملاحظات"]))
            rec = [
                ("item", "إجمالي أرصدة البنوك أعلاه", [tot]),
                ("item", "النقد وما في حكمه في المركز المالي (30 سبتمبر 2026)", [bs_cash]),
                ("total", "الفرق (نقد بالصندوق / حسابات غير مدرجة / فروق توقيت)", [tot - bs_cash]),
            ]
            st.table(build_styled_table(rec, ["المطابقة مع المركز المالي", "المبلغ (ريال)"]))
            if abs(tot - bs_cash) > 10:
                st.markdown('<div class="bk-note">الفرق يحتاج تفسيراً: قد يشمل النقد بالصندوق أو حسابات لم تُدرج أو فروق توقيت. '
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
            "R-1.3": "المستخدم = تمويل الرواتب إن كانت حالته 'قائم' (حالياً مخطط)",
            "S-TOT": "المستخدم = ضمانات ساب القائمة",
            "S-1.2": "المستخدم = ضمان مكة 2016",
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
        ex.append("تمويل الرواتب (12 مليون) مدرج 'مخطط' ولا يُحتسب مستخدماً حتى يُغيَّر إلى 'قائم' في تبويب المرابحات.")
        ex.append("ساب: خطاب العرض يعدل حد التسهيل (1-2) إلى 2,529,000 ويحدد إجمالي التسهيلات 17,291,538، ولم يرد فيه تفصيل لباقي الحد "
                  f"({17291538 - 2529000:,.0f}) فيلزم تأكيد طبيعته مع البنك.")
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
- **تمويل المستورد (1.1.1)**: مدة 36 شهراً، سايبور 6 أشهر متناقص + هامش 3%، ودفعة مقدمة 1%.
- **تنبيه**: جدول المرابحات المرفق يحتسب هامش 1.5% فوق سايبور، بينما نص الاتفاقية 3%. يُرجى التحقق من الهامش الفعلي.
- **ساب**: ضمان سند لأمر 17,291,538 ريال، وتفويض بالخصم من الحسابات، وزيارات ميدانية دورية سنوياً، ورسوم الترتيب والتجديد غير مستردة.
""")

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
        m[1].metric("ضمانات منتهية لم تُلغَ", f"{len(expd)}", f"{expd['مبلغ الضمان'].sum():,.0f} ريال")
        m[2].metric("إجمالي الضمانات القائمة", f"{len(act)}", f"{act['مبلغ الضمان'].sum():,.0f} ريال")
        if len(near):
            st.markdown('<div class="bk-note">⏰ ضمانات تنتهي خلال 90 يوماً (تحتاج تجديداً أو إفراجاً): '
                        + "، ".join(f"{r['البيان']} ({_fmtd(r['تاريخ الانتهاء'])})" for _, r in near.iterrows()) + "</div>", unsafe_allow_html=True)
        if len(expd):
            st.markdown('<div class="bk-note">⚠️ ضمانات تجاوزت تاريخ انتهائها ولا تزال قائمة في السجل: '
                        + "، ".join(f"{r['البيان']} ({_fmtd(r['تاريخ الانتهاء'])})" for _, r in expd.iterrows()) + "</div>", unsafe_allow_html=True)
        by_bank = act.groupby("البنك", as_index=False).agg(الضمانات=("مبلغ الضمان", "sum"), الهامش=("الغطاء النقدي (الهامش)", "sum"))
        if len(by_bank):
            fb = by_bank.melt(id_vars="البنك", var_name="البند", value_name="المبلغ")
            _chart(px.bar(fb, x="البنك", y="المبلغ", color="البند", barmode="group", title="الضمانات والهامش النقدي حسب البنك (ريال)",
                          color_discrete_map={"الضمانات": "#1E3A8A", "الهامش": "#60A5FA"}))
        st.markdown('<div class="bk-fx">المطابقة: إجمالي الهامش النقدي للضمانات القائمة غير المنتهية يُقارن في تبويب الفحوصات مع بند "تأمين خطابات ضمان بنكية" بالمركز المالي (9,550,682).</div>', unsafe_allow_html=True)

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
                                           "قصير الأجل (≤12 شهراً)", "طويل الأجل", "القسط القادم (أصل)", "ربح القسط القادم", "تاريخ القسط القادم", "الحالة"]))
        st.markdown('<div class="bk-fx">قصير الأجل = أقساط الأصل المستحقة خلال 12 شهراً من تاريخ المركز، وطويل الأجل = ما بعد ذلك. '
                    'ربح الأقساط المستقبلية متغير (سايبور + هامش) فلا يظهر إلا للقسط القادم.</div>', unsafe_allow_html=True)

        bs_loans = float(ctx.get("bs_loans_26", 0.0))
        tot_sched = tt("المتبقي (أصل)") + tt("ربح القسط القادم")
        rec = [
            ("item", "المتبقي من أصل المرابحات القائمة", [tt("المتبقي (أصل)")]),
            ("item", "يضاف: ربح القسط القادم المستحق (كما في جدول الأقساط)", [tt("ربح القسط القادم")]),
            ("subtotal", "المتبقي حسب جداول الأقساط", [tot_sched]),
            ("item", "قروض وتسهيلات قصيرة الأجل في المركز المالي", [bs_loans]),
            ("total", "الفرق (جداول الأقساط − المركز المالي)", [tot_sched - bs_loans]),
        ]
        st.table(build_styled_table(rec, ["مطابقة المرابحات مع المركز المالي", "المبلغ (ريال)"]))
        if tt("غير المتداول") > 0 and bs_loans:
            st.markdown(f'<div class="bk-note">⚠️ المركز المالي يعرض كامل المرابحات ({bs_loans:,.0f}) ضمن القروض قصيرة الأجل، بينما تُظهر الجداول أن الجزء '
                        f'غير المتداول (أقساط تستحق بعد 12 شهراً) نحو {tt("غير المتداول"):,.0f} ريال. يُقترح إعادة تصنيفه ضمن الالتزامات غير المتداولة '
                        f'(وهذا يؤثر في نسب السيولة)، وبانتظار قرارك قبل تعديل القوائم.</div>', unsafe_allow_html=True)

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
