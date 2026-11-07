# teams.py
# تبويب فرق العمل: من بيان بونص الفرق الشهري لكل موقع — الفرق وأنواعها ومراقبوها وأفرادها وإنتاجيتها.

import io
import os
import re

import numpy as np
import openpyxl
import pandas as pd
import streamlit as st

import uitable as ut

HERE = os.path.dirname(os.path.abspath(__file__))
F_TEAMS = os.path.join(HERE, "hr_teams.csv")
F_TEXTRA = os.path.join(HERE, "hr_teams_extra.csv")
T_COLS = ["الموقع", "الشهر", "الفرقة", "مفتاح الفرقة", "النوع", "رقم الفرقة", "المراقب",
          "الاسم", "المهنة", "البونص", "بونص الفرقة", "أجور التنفيذ"]
X_COLS = ["الموقع", "الشهر", "البند", "البونص", "بونص الفرقة", "أجور التنفيذ"]

CENTRES = ["ابها", "السراة", "محايل", "المجاردة", "صيانة عسير", "الباحة", "المخواة", "القنفذة",
           "صيانة الباحة", "قراء عدادات الباحة", "تبوك", "ضباء", "الوجه", "حقل", "املج",
           "صيانة تبوك", "قراء عدادات تبوك", "مكة", "خليص", "صيانة مكة", "قراء عدادات مكة",
           "الرياض"]
AR_MONTHS = {"يناير": 1, "فبراير": 2, "مارس": 3, "ابريل": 4, "مايو": 5, "يونيو": 6, "يوليو": 7,
             "اغسطس": 8, "سبتمبر": 9, "اكتوبر": 10, "نوفمبر": 11, "ديسمبر": 12}
MONTH_AR = {v: k for k, v in AR_MONTHS.items()}
# صفوف تجميعية لا تمثل أفراداً
SKIP = ("الاجمال", "اجمالي", "عمال الشركه", "مقاولين الباطن", "مقاول باطن", "الورشه",
        "طوارئ", "طواري", "تقدير", "الانتاجيه")
TYPES = [("ارض", "أرضية"), ("هوائ", "هوائية"), ("عداد", "عدادات"), ("جوينتر", "جوينترية"),
         ("جونتر", "جوينترية"), ("فرم", "فرم"), ("صرف", "صرف ومستودع"), ("فحص", "فحص"),
         ("ترقيم", "ترقيم"), ("اتصال", "اتصالات"), ("اسفلت", "أسفلت"), ("سفلت", "أسفلت"),
         ("مدني", "مدنية"), ("خرسان", "مدنية")]

CSS = """
<style>
  .tm-note { direction: rtl; background: #F8FAFC; border-right: 4px solid #2563EB; padding: 10px 14px;
             border-radius: 8px; color: #334155; font-size: .98rem; margin: 8px 0 12px; }
  .tm-warn { direction: rtl; background: #FEF3C7; border-right: 4px solid #D97706; padding: 10px 14px;
             border-radius: 8px; color: #78350F; font-size: .98rem; margin: 8px 0 12px; }
</style>
"""


def _note(t, warn=False):
    st.markdown(f'<div class="{"tm-warn" if warn else "tm-note"}">{t}</div>', unsafe_allow_html=True)


def _n(s):
    s = re.sub(r"[ً-ْـ]", "", str(s or ""))
    for a, b in (("أ", "ا"), ("إ", "ا"), ("آ", "ا"), ("ة", "ه"), ("ى", "ي")):
        s = s.replace(a, b)
    return re.sub(r"\s+", " ", s).strip()


def _num(v):
    if v is None or isinstance(v, str) and not v.strip():
        return np.nan
    try:
        return float(v)
    except Exception:
        return np.nan


def team_type(name):
    t = _n(name)
    for k, lbl in TYPES:
        if k in t:
            return lbl
    return "أخرى"


def team_no(name):
    m = re.search(r"\d+", _n(name))
    return m.group(0) if m else ""


_STOP_W = {"فرقه", "فرقة", "رقم", "طوارئ", "طواري", "طوارى"}


def _words(name):
    t = re.sub(r"\d+", " ", _n(name))
    return [w for w in t.split() if w not in _STOP_W]


def _rest(name):
    """كلمات اسم الفرقة بعد حذف كلمة «فرقة» ورقمها وكلمات نوعها."""
    return [w for w in _words(name) if not any(k in w for k, _ in TYPES)]


def team_key(name):
    """مفتاح موحّد للفرقة: النوع + الرقم، فلا تتفرّق «هوائى2» عن «هوائى 2»."""
    ty, no = team_type(name), team_no(name)
    if no:
        return f"{ty} {no}"
    return (ty + " " + " ".join(_rest(name))).strip()


def _watcher(name, members):
    """المراقب: من مهنته مراقب داخل الفرقة، وإلا ما تبقّى من اسم الفرقة إن كان اسماً معقولاً."""
    m = [x for x in members if "مراقب" in _n(x[1])]
    if m:
        return m[0][0]
    s = " ".join(_rest(name)).strip()
    return s if len(s) >= 3 else ""


# مرادفات أسماء الأعمدة بين المواقع، فلا يُشترط تطابق التسمية
SYN = {
    "الاسم": ("الاسم", "اسم الموظف", "اسم العامل", "الموظف", "العامل", "اسم الفرد"),
    "المهنة": ("المهنه", "المهنة", "الوظيفه", "الوظيفة", "المسمي الوظيفي", "التخصص"),
    "البونص": ("البونص", "بونص", "بونص الفرد", "البونص الشهري", "المستحق", "بونص الموظف"),
    "بونص الفرقة": ("بونص الفرقه", "بونص الفريق", "اجمالي بونص الفرقه", "بونص المجموعه"),
    "أجور التنفيذ": ("اجور التنفيذ الفعليه", "اجور التنفيذ", "قيمه التنفيذ", "قيمة التنفيذ",
                     "التنفيذ الفعلي", "اجمالي التنفيذ", "الانتاجيه", "انتاجيه الفرقه"),
    "الفرقة": ("الفرقه", "الفرقة", "اسم الفرقه", "الفريق", "اسم الفريق", "المجموعه"),
}


def _col(H, key):
    """يعيد رقم العمود المطابق لأي مرادف للاسم."""
    for a in SYN[key]:
        if a in H:
            return H[a]
    for a in SYN[key]:
        for k, j in H.items():
            if a and a in k:
                return j
    return None


def month_from_name(name):
    """الشهر من اسم الملف: «سبتمبر 2026» أو 2026-09 أو 09-2026."""
    t = _n(name)
    m = re.search(r"(\d{4})[\-_/\s]?(\d{1,2})", t)
    if m and 1 <= int(m.group(2)) <= 12:
        return f"{m.group(1)}-{int(m.group(2)):02d}"
    m = re.search(r"(\d{1,2})[\-_/\s](\d{4})", t)
    if m and 1 <= int(m.group(1)) <= 12:
        return f"{m.group(2)}-{int(m.group(1)):02d}"
    for ar, no in AR_MONTHS.items():
        if ar in t:
            y = re.search(r"(20\d{2})", t)
            if y:
                return f"{y.group(1)}-{no:02d}"
    return ""


def parse_teams(raw):
    """بيان بونص الفرق: يعيد (الأفراد، البنود التجميعية، الشهر، اسم الورقة)."""
    wb = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
    for sn in wb.sheetnames:
        rows = [list(r) for r in wb[sn].iter_rows(values_only=True)]
        hdr = None
        for i, r in enumerate(rows[:14]):
            t = [_n(x) for x in r]
            if any(a in t for a in SYN["الاسم"]) and any(x.startswith("بونص") for x in t):
                hdr = i
                break
        if hdr is None:
            continue
        H = {_n(v): j for j, v in enumerate(rows[hdr]) if v is not None}
        w = max(len(r) for r in rows) if rows else 0
        body = rows[hdr + 1:]
        cnt = {j: sum(1 for r in body if j < len(r) and r[j] and "فرق" in _n(r[j])) for j in range(w)}
        jteam = max(cnt, key=cnt.get) if cnt and max(cnt.values()) > 1 else None
        jn = _col(H, "الفرقة")
        if jn is not None and cnt.get(jn, 0) > 1:
            jteam = jn
        ym = ""
        for r in rows[:hdr + 1]:
            for v in r:
                m = re.search(r"شهر\s+(\S+)\s+(\d{4})", str(v or ""))
                if m and AR_MONTHS.get(_n(m.group(1))):
                    ym = f"{m.group(2)}-{AR_MONTHS[_n(m.group(1))]:02d}"
        C = {k: _col(H, k) for k in SYN}
        g = lambda r, k: (r[C[k]] if C.get(k) is not None and C[k] < len(r) else None)
        rec, extra, team = [], [], ""
        for r in rows[hdr + 1:]:
            if jteam is not None and jteam < len(r) and r[jteam] and "فرق" in _n(r[jteam]):
                team = str(r[jteam]).strip()
            nm = str(g(r, "الاسم") or "").strip()
            job = str(g(r, "المهنة") or "").strip()
            if not nm and not job:
                continue
            b, tb = _num(g(r, "البونص")), _num(g(r, "بونص الفرقة"))
            wg = _num(g(r, "أجور التنفيذ"))
            if any(k in _n(nm) or k in _n(job) for k in SKIP):
                extra.append({"البند": nm or job, "البونص": b, "بونص الفرقة": tb, "أجور التنفيذ": wg})
                team = ""          # صف تجميعي يفصل بين المجموعات فلا يُورَّث انتماؤها
                continue
            rec.append({"الفرقة": team, "الاسم": nm, "المهنة": job,
                        "البونص": b, "بونص الفرقة": tb, "أجور التنفيذ": wg})
        M = pd.DataFrame(rec)
        if len(M):
            M["مفتاح الفرقة"] = M["الفرقة"].map(lambda x: team_key(x) if x else "بلا فرقة")
            M["النوع"] = M["الفرقة"].map(lambda x: team_type(x) if x else "غير محدد")
            M["رقم الفرقة"] = M["الفرقة"].map(team_no)
            w_ = {k: _watcher(k, list(zip(v["الاسم"], v["المهنة"])))
                  for k, v in M.groupby("الفرقة")}
            M["المراقب"] = M["الفرقة"].map(w_).fillna("")
            M["الشهر"] = ym
        X = pd.DataFrame(extra)
        if len(X):
            X["الشهر"] = ym
        return M, X, ym, sn
    return pd.DataFrame(), pd.DataFrame(), "", ""


# ---------------- التخزين ----------------
def _read(path, cols):
    if not os.path.exists(path):
        return pd.DataFrame(columns=cols)
    try:
        D = pd.read_csv(path, dtype={"رقم الفرقة": str})
    except Exception:
        return pd.DataFrame(columns=cols)
    for c in cols:
        if c not in D.columns:
            D[c] = np.nan
    D = D[cols]
    num = {"البونص", "بونص الفرقة", "أجور التنفيذ"}
    for c in cols:
        if c in num:
            D[c] = pd.to_numeric(D[c], errors="coerce")
        else:
            D[c] = D[c].fillna("").astype(str)
    return D


def _state():
    ss = st.session_state
    if "tm_m" not in ss:
        ss["tm_m"] = _read(F_TEAMS, T_COLS)
    if "tm_x" not in ss:
        ss["tm_x"] = _read(F_TEXTRA, X_COLS)
    return ss["tm_m"], ss["tm_x"]


def _store(M, X):
    st.session_state["tm_m"], st.session_state["tm_x"] = M, X
    try:
        M.to_csv(F_TEAMS, index=False, encoding="utf-8-sig")
        X.to_csv(F_TEXTRA, index=False, encoding="utf-8-sig")
        return True, ""
    except Exception as e:
        return False, str(e)


def _merge(old, new, keys):
    """يستبدل بيانات نفس الموقع والشهر ويبقي الباقي."""
    if not len(new):
        return old
    if len(old):
        k = set(map(tuple, new[keys].drop_duplicates().values))
        old = old[~old[keys].apply(tuple, axis=1).isin(k)]
    return pd.concat([old, new], ignore_index=True)


# ---------------- الواجهة ----------------
def _upload(unlocked):
    st.markdown("#### رفع بيان بونص الفرق")
    _note("ارفع ملف «بونص الفرق» لكل موقع وشهر. تُقرأ الفرقة من عمود اسم الفرقة ويُنسب إليها كل من يليها "
          "حتى الفرقة التالية، ويُستنتج نوعها ورقمها ومراقبها آلياً. رفع الشهر نفسه مرة أخرى يستبدل بياناته.")
    if not unlocked:
        _note("أدخل كلمة سر مركز التحديث في الشريط الجانبي لتفعيل الرفع.", True)
        return
    c1, c2, c3 = st.columns([1.1, 1, 1])
    site = c1.selectbox("الموقع", CENTRES, key="tm_site")
    yr = c2.number_input("السنة (عند تعذّر قراءتها)", 2021, 2035, 2026, key="tm_y")
    mo = c3.selectbox("الشهر (عند تعذّر قراءته)", ["يُقرأ من الملف"] + [MONTH_AR[i] for i in range(1, 13)],
                      key="tm_mon")
    st.download_button("⬇️ تنزيل النموذج الموحّد لبيان بونص الفرق",
                       _template(), "نموذج_بونص_الفرق.xlsx",
                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="tm_tpl")
    up = st.file_uploader("ملفات بونص الفرق (Excel)", type=["xlsx", "xlsm"],
                          accept_multiple_files=True, key="tm_up")
    if not up:
        return
    M, X = _state()
    log = []
    for f in up:
        try:
            m, x, ym, sn = parse_teams(f.read())
        except Exception as e:
            log.append(("e", f"{f.name}: تعذّرت القراءة — {e}"))
            continue
        if not len(m):
            log.append(("e", f"{f.name}: لم يُعثر على ورقة بونص الفرق (يلزم عمودا «الاسم» و«البونص»)."))
            continue
        if not ym:
            ym = month_from_name(f.name)
        if not ym and mo != "يُقرأ من الملف":
            ym = f"{int(yr)}-{AR_MONTHS[_n(mo)]:02d}"
        if not ym:
            log.append(("e", f"{f.name}: لم يتبيّن الشهر لا من عنوان الورقة ولا من اسم الملف. "
                             "اختر الشهر والسنة أعلاه ثم أعد الرفع."))
            continue
        m["الموقع"], x["الموقع"] = site, site
        for c in T_COLS:
            if c not in m.columns:
                m[c] = np.nan
        M = _merge(M, m[T_COLS], ["الموقع", "الشهر"])
        X = _merge(X, x[X_COLS] if len(x) else pd.DataFrame(columns=X_COLS), ["الموقع", "الشهر"])
        nt = m["مفتاح الفرقة"].nunique()
        log.append(("s", f"{f.name}: {site} — شهر {ym}: {nt} فرقة و{len(m)} فرداً."))
    ok, err = _store(M, X)
    for k, t in log:
        (st.success if k == "s" else st.error)(t)
    if not ok:
        st.error(f"تعذّر الحفظ: {err}")


def _template():
    """نموذج موحّد لبيان بونص الفرق يُوزَّع على المواقع فتتوحّد التسمية والترتيب."""
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.utils import get_column_letter
    cols = ["الفرقة", "الاسم", "المهنة", "البونص", "بونص الفرقة", "أجور التنفيذ"]
    ex = [["فرقة أرضية رقم 1", "اسم المراقب", "مراقب أرضي", 500, 24796, 826540],
          ["", "اسم الفرد الثاني", "سائق شيول", 300, "", ""],
          ["", "اسم الفرد الثالث", "عامل أرضي", 300, "", ""],
          ["فرقة هوائية رقم 1", "اسم المراقب", "مراقب هوائي", 550, 6000, 200000],
          ["", "اسم الفرد الثاني", "فني هوائي", 400, "", ""]]
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        pd.DataFrame(ex, columns=cols).to_excel(w, sheet_name="بونص الفرق", index=False, startrow=1)
        ws = w.sheets["بونص الفرق"]
        ws.sheet_view.rightToLeft = True
        ws["A1"] = "بونص شهر أكتوبر 2026"
        ws["A1"].font = Font(name="Arial", size=13, bold=True, color="1F4E79")
        for c in ws[2]:
            c.font = Font(name="Arial", size=11, bold=True, color="FFFFFF")
            c.fill = PatternFill("solid", fgColor="1F4E79")
            c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        for j, c in enumerate(cols, 1):
            ws.column_dimensions[get_column_letter(j)].width = {"الفرقة": 26, "الاسم": 30, "المهنة": 22}.get(c, 16)
        ws.freeze_panes = "A3"
        g = pd.DataFrame({"التعليمات": [
            "١. عنوان الخلية A1 يحمل الشهر بصيغة «بونص شهر أكتوبر 2026»، وإن غاب يُقرأ الشهر من اسم الملف.",
            "٢. اسم الفرقة يُكتب مرة واحدة في أول صف من صفوف الفرقة، ويُترك فارغاً لباقي أفرادها. لا تدمج الخلايا.",
            "٣. سمِّ الفرقة بنوعها ورقمها واسم مراقبها، مثل: فرقة أرضية رقم 1 عرفان.",
            "٤. «أجور التنفيذ» تُكتب أمام كل فرقة على حدة إن توفّرت؛ وإن سُجّلت لمجموعة كاملة فاكتبها "
            "أمام أول فرقة فيها، وتوزّعها المنصة على فرق النوع نفسه بنسبة عدد الأفراد.",
            "٥. الصفوف التجميعية (طوارئ، عمال الشركة، مقاولو الباطن، الورشة، الإجمالي) تُترك كما هي "
            "وتُعرض في المنصة خارج الفرق.",
            "٦. ترتيب الأعمدة غير ملزم، والمنصة تقبل مرادفات التسمية، لكن الالتزام بالنموذج يمنع أي خطأ قراءة."]})
        g.to_excel(w, sheet_name="التعليمات", index=False)
        ws2 = w.sheets["التعليمات"]
        ws2.sheet_view.rightToLeft = True
        ws2.column_dimensions["A"].width = 120
        for r in ws2.iter_rows():
            for c in r:
                c.alignment = Alignment(horizontal="right", vertical="center", wrap_text=True)
    return buf.getvalue()


def _teams_table(M, build):
    G = M.groupby(["الموقع", "الشهر", "مفتاح الفرقة"], as_index=False).agg(
        **{"الفرقة": ("الفرقة", "first"), "النوع": ("النوع", "first"), "المراقب": ("المراقب", "first"),
           "عدد الأفراد": ("الاسم", "nunique"), "بونص الأفراد": ("البونص", "sum"),
           "بونص الفرقة": ("بونص الفرقة", "sum"), "أجور التنفيذ": ("أجور التنفيذ", "sum")})
    # أجور التنفيذ تُسجَّل غالباً أمام فرقة واحدة من المجموعة، فتُوزَّع على فرق النوع نفسه بعدد الأفراد
    k = ["الموقع", "الشهر", "النوع"]
    tot = G.groupby(k)["أجور التنفيذ"].transform("sum")
    mem = G.groupby(k)["عدد الأفراد"].transform("sum")
    G["أجور التنفيذ (موزّعة)"] = np.where(mem > 0, tot * G["عدد الأفراد"] / mem, 0.0)
    have = G.assign(_p=(G["أجور التنفيذ"] > 0).astype(int)).groupby(k)["_p"].transform("sum")
    n_t = G.groupby(k)["مفتاح الفرقة"].transform("size")
    G["توزيع"] = np.where((tot > 0) & (have < n_t), "موزّعة على النوع",
                          np.where(tot > 0, "كما وردت", "بلا أجور مسجّلة"))
    G["الإنتاجية للفرد"] = np.where(G["عدد الأفراد"] > 0, G["أجور التنفيذ (موزّعة)"] / G["عدد الأفراد"], 0)
    G["البونص للفرد"] = np.where(G["عدد الأفراد"] > 0, G["بونص الأفراد"] / G["عدد الأفراد"], 0)
    return G


def _overview(M, X, build):
    G = _teams_table(M, build)
    s = G.groupby("النوع").agg(**{"الفرق": ("مفتاح الفرقة", "nunique"), "الأفراد": ("عدد الأفراد", "sum"),
                                  "بونص الأفراد": ("بونص الأفراد", "sum"),
                                  "أجور التنفيذ": ("أجور التنفيذ", "sum")}).sort_values("الأفراد", ascending=False)
    f = lambda v: f"{v:,.0f}"
    rows = [("item", k, [f(r.الفرق), f(r.الأفراد), f(r["بونص الأفراد"]), f(r["أجور التنفيذ"])])
            for k, r in s.iterrows()]
    rows.append(("total", "الإجمالي", [f(s.الفرق.sum()), f(s.الأفراد.sum()),
                                       f(s["بونص الأفراد"].sum()), f(s["أجور التنفيذ"].sum())]))
    st.table(build(rows, ["نوع الفرقة", "عدد الفرق", "عدد الأفراد", "بونص الأفراد", "أجور التنفيذ"]))
    _note("حين تُسجَّل أجور التنفيذ لمجموعة كاملة أمام فرقة واحدة، تُوزّعها المنصة على فرق النوع نفسه "
          "بنسبة عدد الأفراد ليصبح لكل فرقة رقم إنتاجية. ولتسجيلها لكل فرقة على حدة استخدم النموذج الموحّد.")
    if len(X):
        Y = X.groupby("البند", as_index=False).agg(**{"بونص الفرقة": ("بونص الفرقة", "sum"),
                                                      "أجور التنفيذ": ("أجور التنفيذ", "sum")})
        with st.expander("بنود خارج الفرق (طوارئ، عمال الشركة، مقاولو الباطن)"):
            ut.wide(Y, "البند", key_font=1.1, height="26vh")


def _teams_view(M, build):
    G = _teams_table(M, build)
    c1, c2 = st.columns(2)
    ty = c1.multiselect("نوع الفرقة", sorted(G["النوع"].unique()), key="tm_ty")
    if ty:
        G = G[G["النوع"].isin(ty)]
    srt = c2.radio("الترتيب", ["عدد الأفراد", "أجور التنفيذ (موزّعة)", "بونص الأفراد", "الإنتاجية للفرد"],
                   horizontal=True, key="tm_sort")
    V = G.sort_values(srt, ascending=False)[
        ["الفرقة", "النوع", "المراقب", "الموقع", "الشهر", "عدد الأفراد", "بونص الأفراد",
         "البونص للفرد", "بونص الفرقة", "أجور التنفيذ", "أجور التنفيذ (موزّعة)",
         "توزيع", "الإنتاجية للفرد"]]
    _note("«أجور التنفيذ» كما وردت في الملف، و«الموزّعة» هي حصة الفرقة حين تُسجَّل الأجور لمجموعة كاملة "
          "أمام فرقة واحدة: تُوزَّع على فرق النوع نفسه بنسبة عدد الأفراد. الإنتاجية للفرد محسوبة من الموزّعة.")
    ut.wide(V, "الفرقة", key_font=1.2, height="52vh")
    st.download_button("⬇️ تنزيل بيان الفرق (CSV)", V.to_csv(index=False).encode("utf-8-sig"),
                       "teams.csv", "text/csv", key="tm_dl_t")


def _members_view(M):
    c1, c2 = st.columns(2)
    teams = sorted(M["الفرقة"].replace("", "بلا فرقة").unique())
    pick = c1.selectbox("الفرقة", ["الكل"] + teams, key="tm_pick")
    q = c2.text_input("بحث بالاسم أو المهنة", key="tm_q")
    V = M.copy()
    V["الفرقة"] = V["الفرقة"].replace("", "بلا فرقة")
    if pick != "الكل":
        V = V[V["الفرقة"] == pick]
    if q.strip():
        k = _n(q)
        V = V[V["الاسم"].map(lambda x: k in _n(x)) | V["المهنة"].map(lambda x: k in _n(x))]
    V = V[["الاسم", "المهنة", "الفرقة", "النوع", "المراقب", "الموقع", "الشهر", "البونص"]]
    st.caption(f"{len(V):,} فرداً")
    ut.wide(V.sort_values(["الفرقة", "البونص"], ascending=[True, False]), "الاسم",
            key_font=1.3, height="56vh")
    st.download_button("⬇️ تنزيل أفراد الفرق (CSV)", V.to_csv(index=False).encode("utf-8-sig"),
                       "team_members.csv", "text/csv", key="tm_dl_m")


def _trend(M, build):
    if M["الشهر"].nunique() < 2:
        _note("ارفع شهراً آخر على الأقل لتظهر مقارنة تطور الفرق عبر الشهور.")
        return
    P = M.groupby(["الشهر", "مفتاح الفرقة"], as_index=False).agg(
        **{"الأفراد": ("الاسم", "nunique"), "البونص": ("البونص", "sum"),
           "أجور التنفيذ": ("أجور التنفيذ", "sum")})
    for metric in ("الأفراد", "البونص", "أجور التنفيذ"):
        T = P.pivot_table(index="مفتاح الفرقة", columns="الشهر", values=metric,
                          aggfunc="sum").fillna(0).reset_index()
        st.markdown(f"**{metric} لكل فرقة عبر الشهور**")
        ut.wide(T, "مفتاح الفرقة", key_font=1.15, height="34vh")


def _link_hr(M, emp):
    """ربط أفراد الفرق بملف الموظفين بمطابقة الاسم."""
    if emp is None or not len(emp):
        _note("ارفع ملف بيانات الموظفين في «البيانات والإعدادات» ليُربط أفراد الفرق بأرقامهم الوظيفية.", True)
        return
    E = emp.copy()
    E["_k"] = E["الاسم"].map(_n)
    E = E.drop_duplicates("_k")
    V = M.drop_duplicates(["الاسم", "الفرقة"]).copy()
    V["_k"] = V["الاسم"].map(_n)
    V = V.merge(E[["_k", "الرقم الوظيفي", "الموقع", "المهنة"]].rename(
        columns={"الموقع": "موقع الموظفين", "المهنة": "مهنة الموظفين"}), on="_k", how="left")
    hit = int(V["الرقم الوظيفي"].notna().sum())
    _note(f"طوبق {hit:,} من {len(V):,} فرداً مع ملف الموظفين بالاسم. غير المطابق إما مختلف كتابة الاسم "
          "أو غير مُدرج في ملف الموظفين.")
    V = V[["الاسم", "الرقم الوظيفي", "الفرقة", "النوع", "المراقب", "المهنة", "مهنة الموظفين",
           "الموقع", "موقع الموظفين", "البونص"]]
    ut.wide(V.sort_values("الرقم الوظيفي", na_position="first"), "الاسم", key_font=1.3, height="52vh")
    st.download_button("⬇️ تنزيل الربط مع الموارد البشرية (CSV)",
                       V.to_csv(index=False).encode("utf-8-sig"), "teams_hr_link.csv",
                       "text/csv", key="tm_dl_l")


def render_teams(ctx, build, emp=None):
    st.markdown(CSS, unsafe_allow_html=True)
    ut.css()
    unlocked = bool(ctx.get("UP_UNLOCKED", False))
    M, X = _state()
    st.subheader("🧑‍🏭 فرق العمل")
    if not len(M):
        _note("لا توجد بيانات فرق بعد. ارفع ملف «بونص الفرق» من القسم أدناه — ملف لكل موقع وشهر.")
        _upload(unlocked)
        return
    c1, c2 = st.columns(2)
    sites = sorted(M["الموقع"].dropna().unique())
    months = sorted(M["الشهر"].dropna().unique())
    ssel = c1.multiselect("الموقع", sites, default=sites, key="tm_fs")
    msel = c2.multiselect("الشهر", months, default=months[-1:], key="tm_fm")
    V = M[M["الموقع"].isin(ssel or sites) & M["الشهر"].isin(msel or months)]
    XV = X[X["الموقع"].isin(ssel or sites) & X["الشهر"].isin(msel or months)] if len(X) else X
    if not len(V):
        _note("لا توجد بيانات للاختيار الحالي.", True)
        return
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("عدد الفرق", f"{V['مفتاح الفرقة'].nunique():,}")
    k2.metric("أفراد الفرق", f"{V['الاسم'].nunique():,}")
    k3.metric("بونص الأفراد", f"{V['البونص'].sum():,.0f}")
    k4.metric("أجور التنفيذ", f"{V['أجور التنفيذ'].sum():,.0f}")
    t = st.tabs(["📋 الفرق", "👥 الأفراد", "📊 نظرة عامة", "📈 التطور الشهري",
                 "🔗 الربط بالموارد البشرية", "⬆️ رفع البيانات"])
    with t[0]:
        _teams_view(V, build)
    with t[1]:
        _members_view(V)
    with t[2]:
        _overview(V, XV, build)
    with t[3]:
        _trend(M, build)
    with t[4]:
        _link_hr(V, emp)
    with t[5]:
        _upload(unlocked)
