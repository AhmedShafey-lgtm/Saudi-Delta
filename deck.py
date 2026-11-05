# deck.py
# العرض التقديمي للشركة: شرائح جاهزة للعرض على الإدارة والملاك، مبنية كلها من أرقام المنصة نفسها.
# لا يحتوي أي رقم مُدخل يدوياً: كل قيمة تُحسب من سياق القوائم المالية وقواعد المواقع والعقود.

import datetime as dt
import numpy as np
import pandas as pd
import streamlit as st

ANN = 12.0 / 9.0
PERIOD = "حتى 30 سبتمبر 2026 (9 أشهر)"
NAVY, GOLD, TEAL, RED, GREY = "#0B2A6F", "#C9A227", "#0E9F6E", "#B91C1C", "#64748B"

CSS = """
<style>
  .dk-wrap { direction: rtl; text-align: right; }
  .dk-slide { background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 14px; padding: 22px 26px 18px 26px;
              box-shadow: 0 2px 14px rgba(11,42,111,.07); margin-bottom: 10px; }
  .dk-head { background: linear-gradient(90deg,#0B2A6F 0%,#1E3A8A 55%,#2D4FA2 100%); color: #fff;
             border-radius: 12px; padding: 16px 22px; margin-bottom: 14px; }
  .dk-head h2 { margin: 0; font-size: 1.45rem; font-weight: 800; letter-spacing: .2px; }
  .dk-head .sub { opacity: .88; font-size: .95rem; margin-top: 4px; }
  .dk-kpis { display: flex; flex-wrap: wrap; gap: 12px; margin: 6px 0 14px 0; }
  .dk-kpi { flex: 1 1 180px; background: #F8FAFC; border: 1px solid #E2E8F0; border-top: 3px solid #0B2A6F;
            border-radius: 10px; padding: 12px 14px; min-width: 170px; }
  .dk-kpi .lbl { color: #475569; font-size: .86rem; font-weight: 600; }
  .dk-kpi .val { color: #0B2A6F; font-size: 1.62rem; font-weight: 800; line-height: 1.25; margin-top: 2px;
                 font-variant-numeric: tabular-nums; }
  .dk-kpi .sub { color: #64748B; font-size: .82rem; margin-top: 2px; }
  .dk-kpi.up { border-top-color: #0E9F6E; } .dk-kpi.up .val { color: #0E7C57; }
  .dk-kpi.down { border-top-color: #B91C1C; } .dk-kpi.down .val { color: #B91C1C; }
  .dk-kpi.gold { border-top-color: #C9A227; } .dk-kpi.gold .val { color: #8A6D12; }
  .dk-point { background:#F8FAFC; border-right: 4px solid #0B2A6F; border-radius: 8px; padding: 9px 13px;
              margin: 7px 0; color:#111827; font-size: .98rem; line-height: 1.7; }
  .dk-point.good { border-right-color:#0E9F6E; background:#F0FDF7; }
  .dk-point.warn { border-right-color:#C9A227; background:#FFFBEB; }
  .dk-point.bad  { border-right-color:#B91C1C; background:#FEF2F2; }
  .dk-foot { color:#94A3B8; font-size:.82rem; margin-top:10px; border-top:1px dashed #E2E8F0; padding-top:7px; }
  .dk-cover { background: linear-gradient(135deg,#0B2A6F 0%,#16307E 45%,#24409A 100%); color:#fff;
              border-radius: 16px; padding: 34px 30px; }
  .dk-cover h1 { font-size: 2.1rem; margin: 0 0 6px 0; font-weight: 800; }
  .dk-cover .tag { color:#E7C84F; font-weight:700; font-size:1.02rem; letter-spacing:.3px; }
  .dk-cover .meta { opacity:.9; margin-top:12px; font-size:.95rem; }
  .dk-chips { display:flex; flex-wrap:wrap; gap:8px; margin-top:16px; }
  .dk-chip { background: rgba(255,255,255,.12); border:1px solid rgba(255,255,255,.25); color:#fff;
             border-radius: 999px; padding: 6px 14px; font-size:.9rem; font-weight:600; }
  [class*="st-key-dk_grid"] [data-testid="stDataFrame"], [class*="st-key-dk_grid"] [data-testid="stDataFrame"] * {
      direction: ltr !important; text-align: left !important; }
  @media print { .dk-slide { break-inside: avoid; box-shadow:none; } }
</style>
"""


# ---------------- أدوات ----------------
def _n(v, d=0):
    try:
        v = float(v)
        if not np.isfinite(v):
            return "—"
        return f"({abs(v):,.{d}f})" if v < 0 else f"{v:,.{d}f}"
    except Exception:
        return "—"


def _m(v, d=1):
    """بالمليون."""
    try:
        v = float(v)
        if not np.isfinite(v):
            return "—"
        return f"({abs(v) / 1e6:,.{d}f})" if v < 0 else f"{v / 1e6:,.{d}f}"
    except Exception:
        return "—"


def _p(v, d=1):
    """نسبة مئوية بأسلوب القوائم: السالب بين قوسين حتى لا تنقلب إشارته في الاتجاه من اليمين."""
    try:
        v = float(v)
        if not np.isfinite(v):
            return "—"
        return f"({abs(v):.{d}f}%)" if v < 0 else f"{v:.{d}f}%"
    except Exception:
        return "—"


def _chg(v, d=1, unit="%"):
    """تغيّر موصوف بالكلمات بدل إشارة قد تنقلب في العرض من اليمين."""
    try:
        v = float(v)
        if not np.isfinite(v):
            return "—"
        if abs(v) < 0.05:
            return f"بلا تغيّر يذكر"
        return ("بزيادة " if v > 0 else "بانخفاض ") + f"{abs(v):.{d}f}{unit}"
    except Exception:
        return "—"


def _div(a, b, mult=1.0):
    try:
        return (a / b * mult) if b else np.nan
    except Exception:
        return np.nan


def head(title, sub=""):
    st.markdown(f'<div class="dk-head"><h2>{title}</h2>' + (f'<div class="sub">{sub}</div>' if sub else "") + "</div>",
                unsafe_allow_html=True)


def kpis(items):
    """items: (label, value, sub, tone) — tone: '', 'up', 'down', 'gold'."""
    h = '<div class="dk-kpis">'
    for lbl, val, sub, tone in items:
        h += (f'<div class="dk-kpi {tone}"><div class="lbl">{lbl}</div><div class="val">{val}</div>'
              f'<div class="sub">{sub}</div></div>')
    st.markdown(h + "</div>", unsafe_allow_html=True)


def point(text, tone=""):
    st.markdown(f'<div class="dk-point {tone}">{text}</div>', unsafe_allow_html=True)


def foot(text):
    st.markdown(f'<div class="dk-foot">{text}</div>', unsafe_allow_html=True)


def _fig(fig, h=340, legend=True):
    fig.update_layout(
        height=h, margin=dict(l=30, r=20, t=42, b=60 if legend else 30),
        font=dict(family="Segoe UI, Tahoma, sans-serif", size=12),
        title=dict(x=0.5, xanchor="center", font=dict(size=14, color=NAVY)),
        plot_bgcolor="#FFFFFF", paper_bgcolor="#FFFFFF",
        legend=dict(orientation="h", yanchor="top", y=-0.16, xanchor="center", x=0.5, title_text=""),
        showlegend=legend)
    fig.update_xaxes(title_text=None, showgrid=False, linecolor="#CBD5E1")
    fig.update_yaxes(title_text=None, gridcolor="#EEF2F7", zerolinecolor="#CBD5E1")
    return fig


def _tbl(df):
    """جدول عرض نظيف بلا فهرس، بخط أكبر ومحاذاة مناسبة."""
    df = df.reset_index(drop=True)
    sty = df.style.set_properties(**{"font-size": "1.02rem", "color": "#111827"})
    for fn in ("hide_index", "hide"):
        try:
            sty = sty.hide(axis="index") if fn == "hide" else sty.hide_index()
            break
        except Exception:
            continue
    st.table(sty)


# ---------------- حساب الأرقام ----------------
def facts(ctx, cv):
    """كل الأرقام المستخدمة في العرض، محسوبة مرة واحدة."""
    F = {}
    F["rev"] = [ctx["rev_24"], ctx["rev_25"], ctx["rev_26"]]
    F["ebitda"] = [ctx["ebitda_24"], ctx["ebitda_25"], ctx["ebitda_26_a"]]
    F["ebit"] = [ctx["ebit_24"], ctx["ebit_25"], ctx["ebit_26_a"]]
    F["net"] = [ctx["net_24"], ctx["net_25"], ctx["net_26_a"]]
    F["gp"] = [ctx["gp_24"], ctx["gp_25"], ctx["gp_26_a"]]
    F["ga"] = [ctx["ga_24"], ctx["ga_25"], ctx["ga_26"]]
    F["fin"] = [ctx["fin_24"], ctx["fin_25"], ctx["fin_26"]]
    F["dep"] = [ctx["dep_total_24"], ctx["dep_total_25"], ctx["dep_total_26"]]
    F["years"] = ["2024", "2025", "2026 (9 أشهر)"]
    F["ann"] = [1.0, 1.0, ANN]
    F["team26"], F["sub26"] = ctx["team_exec_total_26"], ctx["sub_exec_total_26"]
    F["assets"], F["equity"] = ctx["tot_assets_26_a"], ctx["tot_eq_26_a"]
    F["cash"] = ctx.get("bs_cash_26", 0.0)
    F["loans"] = ctx.get("bs_loans_26", 0.0)
    F["ca"], F["cl"] = ctx["tot_ca_26_a"], ctx["cl_26"]
    F["liab"] = ctx.get("liab_26", F["assets"] - F["equity"])
    F["accrued"] = ctx["accrued_rev_26"]
    F["ccc"] = ctx.get("ccc_26", np.nan)
    F["dso"] = ctx.get("dso_total_26", np.nan)
    F["dpo"] = ctx.get("dpo_26", np.nan)
    # هوامش
    F["gm"] = [_div(F["gp"][i], F["rev"][i], 100) for i in range(3)]
    F["em"] = [_div(F["ebitda"][i], F["rev"][i], 100) for i in range(3)]
    F["nm"] = [_div(F["net"][i], F["rev"][i], 100) for i in range(3)]
    F["roe"] = _div(F["net"][2] * ANN, F["equity"], 100)
    F["cr"] = _div(F["ca"], F["cl"])
    F["de"] = _div(F["liab"], F["equity"], 100)
    # العقود
    rows = []
    for c in cv.CONTRACT_ORDER:
        s = cv.sites_of_contract(c)
        a = cv.aggregate(s)
        rv, cv_ = a["rev"][5], a["cost"][5]
        rows.append({"العقد": c, "المراكز": len(s), "الإيراد": rv, "التكلفة": cv_, "النتيجة": rv - cv_,
                     "الهامش": _div(rv - cv_, rv, 100), "الرواتب": a["pl"]["salaries"][5],
                     "الباطن": a["pl"]["subcontractors"][5], "المواد": a["pl"]["materials"][5],
                     "المعدات": a["pl"]["maint_veh"][5] + a["pl"]["dep_exp"][5],
                     "العمالة": a["pay"]["hc_total"], "المنتجة": a["pay"]["hc_prod"],
                     "أصول": a["ast"]["equip_cost"],
                     "رواتب%": _div(a["pl"]["salaries"][5], rv, 100),
                     "rev_prev": a["rev"][4]})
    F["C"] = pd.DataFrame(rows)
    adm = cv.aggregate([cv.ADMIN_SITE])
    F["adm_cost"], F["adm_rev"] = adm["cost"][5], adm["rev"][5]
    pool = [s for s in cv._db if s != cv.ADMIN_SITE]
    F["all"] = cv.aggregate(pool)
    # بنود التكلفة للمراكز في 2026
    F["cat"] = [(lbl.split(".")[1].strip(), F["all"]["pl"][k][5]) for k, lbl in cv.EXP_CATEGORIES]
    F["cat"] = sorted(F["cat"], key=lambda x: -x[1])
    F["cost26"] = F["all"]["cost"][5]
    F["rev26c"] = F["all"]["rev"][5]
    # الإسناد
    A = ctx.get("ASSIGN", {}) or {}
    g = lambda k: float(sum(float(v.get(k, 0) or 0) for v in A.values()))
    F["asg"] = {"avail": g("open_unexec") + g("new_wo") + g("new_emerg"),
                "new": g("new_wo") + g("new_emerg"), "open_unexec": g("open_unexec"),
                "exec": g("total_exec"), "billed": g("billed"),
                "open_unbilled": g("open_exec_unbilled"),
                "wip": g("open_exec_unbilled") + g("total_exec") - g("billed"),
                "avail_bill": g("avail_billing"),
                "remain": g("remaining_unexec")}
    # العمالة
    P = ctx.get("PAYROLL", {}) or {}
    F["hc"] = sum(float(v.get("hc_total", 0)) for v in P.values())
    F["hc_s"] = sum(float(v.get("hc_saudi", 0)) for v in P.values())
    F["hc_p"] = sum(float(v.get("hc_prod", 0)) for v in P.values())
    F["hc_a"] = sum(float(v.get("hc_admin", 0)) for v in P.values())
    F["comp"] = sum(float(v.get("total_comp", 0)) for v in P.values())
    F["adm_pay"] = sum(float(v.get("admin_cost", 0)) for v in P.values())
    # الكادر الإداري لكل موقع (مركز تكلفة)
    ACT_AR = {"construction": "إنشاءات وتعزيزات", "maintenance": "صيانة", "readers": "قراء عدادات", "admin": "الإدارة"}
    rows = []
    for site, d in cv._db.items():
        if site == cv.ADMIN_SITE:          # الإدارة ومصنع الأعمدة مركز مركزي بلا إيراد تشغيلي
            continue
        p = P.get(site, {})
        rv = cv.site_revs(site)[5]
        hc_t = float(p.get("hc_total", 0)); hc_a = float(p.get("hc_admin", 0)); hc_p = float(p.get("hc_prod", 0))
        adm = float(p.get("admin_cost", 0)); comp = float(p.get("total_comp", 0))
        if hc_t <= 0 and adm <= 0:
            continue
        rows.append({"الموقع": site, "العقد": d.get("contract", ""), "النشاط": ACT_AR.get(cv.activity_of(site), ""),
                     "الإيراد": rv, "العمالة": hc_t, "إداري": hc_a, "منتج": hc_p,
                     "تكلفة الإدارة": adm, "تكلفة العمالة": comp,
                     "إداري %": _div(hc_a, hc_t, 100), "إدارة/إيراد": _div(adm, rv, 100),
                     "إدارة/عمالة": _div(adm, comp, 100),
                     "منتج لكل إداري": _div(hc_p, hc_a),
                     "كلفة الإداري": _div(adm, hc_a)})
    F["ADM"] = pd.DataFrame(rows)
    ap = P.get(cv.ADMIN_SITE, {})
    F["HO"] = {"hc": float(ap.get("hc_admin", 0)), "cost": float(ap.get("admin_cost", 0)),
               "comp": float(ap.get("total_comp", 0))}
    # الأصول
    AS = cv._ast
    F["ast_cost"] = sum(float(v.get("total_cost", 0)) for v in AS.values())
    F["ast_nbv"] = sum(float(v.get("nbv_total", 0)) for v in AS.values())
    F["ast_cnt"] = sum(int(v.get("total_count", 0)) for v in AS.values())
    F["ast_fd"] = sum(int(v.get("fully_dep_count", 0)) for v in AS.values())
    return F


# ---------------- الشرائح ----------------
def s_cover(F, ctx):
    n_sites = len([s for s in st.session_state.get("_dk_sites", [])]) or None
    chips = "".join(f'<span class="dk-chip">{c.replace("العقد الموحد ", "")}</span>' for c in F["C"]["العقد"])
    st.markdown(
        f'<div class="dk-cover"><div class="tag">شركة دلتا السعودية لمشاريع الكهرباء</div>'
        f'<h1>الأداء التشغيلي والمالي {PERIOD}</h1>'
        f'<div class="meta">خمسة عقود موحدة لإنشاء وصيانة شبكات التوزيع مع الشركة السعودية للكهرباء · '
        f'{len(F["C"]):,} عقود · {int(F["C"]["المراكز"].sum())} مركز تكلفة · {F["hc"]:,.0f} موظف</div>'
        f'<div class="dk-chips">{chips}</div></div>', unsafe_allow_html=True)
    st.markdown("")
    kpis([
        ("الإيراد المعتمد", _m(F["rev"][2]) + " م", f"تنفيذ فعلي مقابل {_m(F['rev'][1])} م في 2025 الكاملة", ""),
        ("الربح قبل الفوائد والإهلاك", _m(F["ebitda"][2]) + " م", f"هامش {_p(F['em'][2])}", "up" if F["em"][2] > 0 else "down"),
        ("صافي الربح", _m(F["net"][2]) + " م", f"هامش {_p(F['nm'][2])}", "up" if F["net"][2] > 0 else "down"),
        ("حقوق الملكية", _m(F["equity"]) + " م", f"إجمالي الأصول {_m(F['assets'])} م", "gold"),
    ])
    c1, c2 = st.columns(2)
    with c1:
        point(f"<b>التنفيذ الفعلي في 2026:</b> فرق الشركة {_m(F['team26'])} مليون ريال ومقاولو الباطن "
              f"{_m(F['sub26'])} مليون، أي أن {_p(_div(F['sub26'], F['team26'] + F['sub26'], 100))} من التنفيذ يُسند للباطن.")
        point(f"<b>القوة المالية:</b> نسبة التداول {F['cr']:.2f} ونسبة الالتزامات إلى حقوق الملكية "
              f"{_p(F['de'])}، والنقدية {_m(F['cash'])} مليون مقابل قروض {_m(F['loans'])} مليون.",
              "good" if (F["cr"] >= 1.2 and F["cash"] >= F["loans"]) else "warn")
    with c2:
        point(f"<b>العمالة:</b> {F['hc']:,.0f} موظفاً منهم {F['hc_p']:,.0f} في الإنتاج و{F['hc_a']:,.0f} في الإدارة، "
              f"ونسبة السعودة {_p(_div(F['hc_s'], F['hc'], 100))}.")
        point(f"<b>الأعمال تحت التنفيذ:</b> منفذ غير مفوتر {_m(F['asg']['wip'])} مليون ريال، "
              f"ورصيد إسناد غير منفذ {_m(F['asg']['remain'])} مليون.", "warn")
    foot("كل الأرقام في هذا العرض محسوبة من بيانات المنصة نفسها: القوائم المالية المدققة لسنوات 2024 و2025، "
         "وقيود 2026 حتى 30 سبتمبر، وقواعد المواقع والعقود والعمالة والأصول.")


def s_financial(F, build):
    head("الأداء المالي عبر السنوات", "الإيراد والربحية والهوامش · 2026 فترة تسعة أشهر")
    import plotly.graph_objects as go
    c1, c2 = st.columns([1.25, 1])
    with c1:
        fig = go.Figure()
        fig.add_bar(x=F["years"], y=F["rev"], name="الإيراد", marker_color=NAVY)
        fig.add_bar(x=F["years"], y=F["ebitda"], name="الربح قبل الفوائد والإهلاك", marker_color=TEAL)
        fig.add_bar(x=F["years"], y=F["net"], name="صافي الربح", marker_color=GOLD)
        fig.update_layout(barmode="group", title="الإيراد والربحية (ريال)")
        st.plotly_chart(_fig(fig), use_container_width=True)
    with c2:
        fig2 = go.Figure()
        for key, nm, col in (("gm", "هامش مجمل الربح", NAVY), ("em", "هامش التشغيل قبل الإهلاك", TEAL), ("nm", "هامش صافي الربح", GOLD)):
            fig2.add_scatter(x=F["years"], y=[round(v, 1) for v in F[key]], name=nm, mode="lines+markers",
                             line=dict(color=col, width=3))
        fig2.update_layout(title="الهوامش (%)")
        st.plotly_chart(_fig(fig2), use_container_width=True)
    rows = [("item", "الإيراد المعتمد", [F["rev"][i] for i in range(3)]),
            ("item", "مجمل الربح", [F["gp"][i] for i in range(3)]),
            ("pct", "هامش مجمل الربح %", [F["gm"][i] for i in range(3)]),
            ("item", "المصاريف الإدارية والعمومية", [-F["ga"][i] for i in range(3)]),
            ("subtotal", "الربح قبل الفوائد والإهلاك", [F["ebitda"][i] for i in range(3)]),
            ("item", "الإهلاك", [-F["dep"][i] for i in range(3)]),
            ("item", "تكاليف التمويل", [F["fin"][i] for i in range(3)]),
            ("total", "صافي الربح", [F["net"][i] for i in range(3)]),
            ("pct", "هامش صافي الربح %", [F["nm"][i] for i in range(3)])]
    st.table(build(rows, ["البند"] + F["years"]))
    d_rev = _div(F["rev"][2] * ANN - F["rev"][1], F["rev"][1], 100)
    d_mg = F["nm"][2] - F["nm"][1]
    point(f"بالتسنين إلى سنة كاملة يبلغ إيراد 2026 نحو {_m(F['rev'][2] * ANN)} مليون ريال، أي "
          f"{_chg(d_rev)} عن 2025، وهامش صافي الربح {_chg(d_mg, unit=' نقطة')}.",
          "good" if d_mg >= 0 else "bad")
    foot("هامش صافي الربح لسنة 2026 محسوب على إيراد التنفيذ الفعلي لا على المفوتر، لأن جزءاً من المنفذ لم يُفوتر بعد.")


def s_contracts(F, build):
    head("العقود الخمسة: أين يُصنع الربح", "نتيجة مراكز كل عقد في 2026 قبل تكاليف الإدارة")
    import plotly.graph_objects as go
    C = F["C"].sort_values("الإيراد", ascending=False)
    k = [("إجمالي إيراد العقود", _m(C["الإيراد"].sum()) + " م", "تنفيذ فعلي 9 أشهر", ""),
         ("نتيجة المراكز", _m(C["النتيجة"].sum()) + " م", f"هامش {_p(_div(C['النتيجة'].sum(), C['الإيراد'].sum(), 100))}", "up" if C["النتيجة"].sum() > 0 else "down"),
         ("تكلفة الإدارة والمصنع", _m(F["adm_cost"]) + " م", f"{_p(_div(F['adm_cost'], C['الإيراد'].sum(), 100))} من إيراد العقود", "gold"),
         ("النتيجة بعد الإدارة", _m(C["النتيجة"].sum() - F["adm_cost"] + F["adm_rev"]) + " م", "قبل الزكاة والضريبة", "")]
    kpis(k)
    c1, c2 = st.columns([1.3, 1])
    with c1:
        fig = go.Figure()
        fig.add_bar(y=C["العقد"], x=C["الإيراد"], name="الإيراد", orientation="h", marker_color=NAVY)
        fig.add_bar(y=C["العقد"], x=C["التكلفة"], name="التكلفة", orientation="h", marker_color="#94A3B8")
        fig.update_layout(barmode="group", title="الإيراد مقابل التكلفة لكل عقد")
        st.plotly_chart(_fig(fig, 360), use_container_width=True)
    with c2:
        col = [TEAL if v >= 0 else RED for v in C["الهامش"]]
        fig2 = go.Figure(go.Bar(y=C["العقد"], x=[round(v, 1) for v in C["الهامش"]], orientation="h",
                                marker_color=col, text=[f"{v:.1f}%" for v in C["الهامش"]], textposition="auto"))
        fig2.update_layout(title="هامش نتيجة المراكز (%)")
        st.plotly_chart(_fig(fig2, 360, legend=False), use_container_width=True)
    D = pd.DataFrame({
        "العقد": C["العقد"].str.replace("العقد الموحد ", "", regex=False),
        "مراكز": C["المراكز"].astype(int),
        "الإيراد (م)": C["الإيراد"].map(lambda v: _m(v)),
        "التكلفة (م)": C["التكلفة"].map(lambda v: _m(v)),
        "النتيجة (م)": C["النتيجة"].map(lambda v: _m(v)),
        "الهامش": C["الهامش"].map(lambda v: _p(v)),
        "الرواتب من الإيراد": C["رواتب%"].map(lambda v: _p(v)),
        "مقاولو الباطن (م)": C["الباطن"].map(lambda v: _m(v)),
        "العمالة": C["العمالة"].map(lambda v: f"{v:,.0f}"),
    })
    _tbl(D)
    best = C.loc[C["الهامش"].idxmax()]
    worst = C.loc[C["الهامش"].idxmin()]
    point(f"أعلى هامش في <b>{best['العقد']}</b> بنسبة {_p(best['الهامش'])}، وأدناه في "
          f"<b>{worst['العقد']}</b> بنسبة {_p(worst['الهامش'])}، والفارق بينهما "
          f"{abs(best['الهامش'] - worst['الهامش']):.1f} نقطة.",
          "warn" if (best["الهامش"] - worst["الهامش"]) > 10 else "")
    neg = C[C["النتيجة"] < 0]
    if len(neg):
        point("عقود بنتيجة سالبة في 2026: " + "، ".join(f"{r['العقد']} ({_m(r['النتيجة'])} م)" for _, r in neg.iterrows())
              + ". تحتاج مراجعة مزيج الأعمال ونسبة الرواتب إلى الإنتاج.", "bad")
    foot("نتيجة المراكز = الإيراد المعتمد − تكاليف مراكز العقد، قبل تحميل الإدارة ومصنع الأعمدة والزكاة والضريبة.")


def s_cost(F):
    head("أين يذهب كل ريال من الإيراد", "هيكل تكلفة مراكز العقود في 2026")
    import plotly.graph_objects as go
    cat = [(n, v) for n, v in F["cat"] if v > 0]
    rev = F["rev26c"]
    c1, c2 = st.columns([1, 1.6])
    with c1:
        top = cat[:6]
        other = sum(v for _, v in cat[6:])
        labels = [n for n, _ in top] + (["بنود أخرى"] if other > 0 else [])
        vals = [v for _, v in top] + ([other] if other > 0 else [])
        fig = go.Figure(go.Pie(labels=labels, values=vals, hole=.52, sort=False,
                               marker=dict(colors=[NAVY, "#1E3A8A", "#2D4FA2", "#4C6FBF", "#7D97D4", "#AFC0E6", "#D7DFF3"]),
                               textinfo="percent", insidetextorientation="horizontal"))
        fig.update_layout(title="توزيع بنود التكلفة")
        st.plotly_chart(_fig(fig, 380), use_container_width=True)
    with c2:
        rows = []
        for n, v in cat:
            rows.append({"البند": n, "القيمة (م)": _m(v), "من الإيراد": _p(_div(v, rev, 100)),
                         "من التكلفة": _p(_div(v, F["cost26"], 100))})
        rows.append({"البند": "إجمالي التكلفة", "القيمة (م)": _m(F["cost26"]),
                     "من الإيراد": _p(_div(F["cost26"], rev, 100)), "من التكلفة": "100.0%"})
        rows.append({"البند": "نتيجة المراكز", "القيمة (م)": _m(rev - F["cost26"]),
                     "من الإيراد": _p(_div(rev - F["cost26"], rev, 100)), "من التكلفة": "—"})
        _tbl(pd.DataFrame(rows))
    sal = dict(cat).get("الرواتب والأجور وملحقاتها", 0.0)
    sub = dict(cat).get("تكلفة مقاولي الباطن", 0.0)
    veh = dict(cat).get("صيانة وتشغيل السيارات والمعدات", 0.0)
    pen = dict(cat).get("غرامات التأخير ومخالفات المشاريع", 0.0)
    point(f"الرواتب وحدها تستهلك {_p(_div(sal, rev, 100))} من الإيراد، ومقاولو الباطن "
          f"{_p(_div(sub, rev, 100))}، وتشغيل المعدات {_p(_div(veh, rev, 100))}. هذه الثلاثة تمثل "
          f"{_p(_div(sal + sub + veh, F['cost26'], 100))} من إجمالي التكلفة.")
    if pen > 0:
        point(f"غرامات التأخير ومخالفات المشاريع بلغت {_n(pen)} ريال في تسعة أشهر، أي "
              f"{_p(_div(pen, rev, 100))} من الإيراد، وهي تكلفة قابلة للتفادي بالكامل.",
              "bad" if _div(pen, rev, 100) >= 1 else "warn")
    foot("النسب محسوبة على إيراد مراكز العقود في 2026 دون الإدارة ومصنع الأعمدة.")


def s_backlog(F):
    head("الإسناد والتنفيذ والفوترة", "دورة تحويل العمل إلى نقد")
    a = F["asg"]
    import plotly.graph_objects as go
    kpis([("الإسناد المتاح للتنفيذ", _m(a["avail"]) + " م", f"منه إسناد جديد في 2026 {_m(a['new'])} م", ""),
          ("التنفيذ الفعلي 2026", _m(a["exec"]) + " م", f"{_p(_div(a['exec'], a['avail'], 100))} من المتاح", "up"),
          ("المفوتر 2026", _m(a["billed"]) + " م", f"{_p(_div(a['billed'], a['exec'], 100))} من المنفذ", "gold"),
          ("رصيد إسناد غير منفذ", _m(a["remain"]) + " م",
           f"يكفي {_div(a['remain'], a['exec'] / 9.0):.1f} شهراً بمعدل التنفيذ الحالي", "warn")])
    c1, c2 = st.columns([1.15, 1])
    with c1:
        stages = ["الإسناد المتاح", "التنفيذ الفعلي", "المفوتر"]
        vals = [a["avail"], a["exec"], a["billed"]]
        fig = go.Figure(go.Bar(x=stages, y=vals, marker_color=[NAVY, TEAL, GOLD],
                               text=[f"{v / 1e6:,.1f} م" for v in vals], textposition="outside"))
        fig.update_layout(title="من الإسناد إلى الفاتورة (ريال)")
        st.plotly_chart(_fig(fig, 340, legend=False), use_container_width=True)
    with c2:
        D = pd.DataFrame([
            {"البند": "منفذ غير مفوتر مرحّل من 2025", "القيمة (م)": _m(a["open_unbilled"])},
            {"البند": "يضاف: التنفيذ الفعلي 2026", "القيمة (م)": _m(a["exec"])},
            {"البند": "يخصم: المفوتر 2026", "القيمة (م)": _m(-a["billed"])},
            {"البند": "الرصيد التراكمي للمنفذ غير المفوتر", "القيمة (م)": _m(a["wip"])},
            {"البند": "منه متاح للفوترة فعلياً", "القيمة (م)": _m(a["avail_bill"])},
            {"البند": "الإيراد المستحق غير المفوتر في المركز المالي", "القيمة (م)": _m(F["accrued"])},
        ])
        _tbl(D)
    gap = a["wip"] - F["accrued"]
    point(f"معدل تحويل الإسناد إلى تنفيذ {_p(_div(a['exec'], a['avail'], 100))}، ومعدل تحويل المنفذ إلى فاتورة "
          f"{_p(_div(a['billed'], a['exec'], 100))}. أي أن نحو {_m(a['exec'] - a['billed'])} مليون ريال من تنفيذ 2026 "
          f"لم يتحول إلى فاتورة بعد.", "warn")
    point(f"<b>بند يحتاج مطابقة:</b> الرصيد التراكمي للمنفذ غير المفوتر في نموذج الإسناد {_m(a['wip'])} مليون ريال، "
          f"بينما الإيراد المستحق غير المفوتر المعترف به في المركز المالي {_m(F['accrued'])} مليون ريال، بفارق "
          f"{_m(gap)} مليون. الفارق إما أعمال فُوترت خارج النموذج أو أرصدة مرحّلة سبق الاعتراف بإيرادها، "
          f"ومطابقته تحدد حجم الإيراد القابل للتحصيل فعلاً.", "bad")
    foot("الأرقام من نموذج الإسناد والتنفيذ الشهري الموحد لكل المواقع، والإيراد المستحق من المركز المالي في 30 سبتمبر.")


def s_liquidity(F):
    head("السيولة ورأس المال العامل", "قدرة الشركة على تمويل دورتها التشغيلية")
    kpis([("النقد وما في حكمه", _m(F["cash"]) + " م", f"مقابل قروض {_m(F['loans'])} م", "up" if F["cash"] > F["loans"] else "down"),
          ("رأس المال العامل", _m(F["ca"] - F["cl"]) + " م", f"نسبة التداول {F['cr']:.2f}", "up" if F["cr"] >= 1.2 else "warn"),
          ("دورة التحويل النقدي", f"{F['ccc']:,.0f} يوم" if np.isfinite(F["ccc"]) else "—",
           f"تحصيل {F['dso']:,.0f} يوم · سداد {F['dpo']:,.0f} يوم" if np.isfinite(F["dso"]) else "", "down" if (np.isfinite(F["ccc"]) and F["ccc"] > 120) else ""),
          ("الالتزامات إلى حقوق الملكية", _p(F["de"]), f"حقوق الملكية {_m(F['equity'])} م", "gold")])
    point(f"الشركة تموّل دورتها من حقوق الملكية أساساً: القروض البنكية {_m(F['loans'])} مليون ريال فقط "
          f"مقابل حقوق ملكية {_m(F['equity'])} مليون، أي رافعة منخفضة.", "good")
    if np.isfinite(F["dso"]) and np.isfinite(F["dpo"]) and F["dso"] - F["dpo"] > 30:
        point(f"<b>فجوة التمويل:</b> الشركة تُحصّل بعد {F['dso']:,.0f} يوماً وتسدد لمورديها خلال "
              f"{F['dpo']:,.0f} أيام. هذه الفجوة البالغة {F['dso'] - F['dpo']:,.0f} يوماً تُموَّل بالكامل من نقد الشركة، "
              f"وكل يوم تأخير إضافي في التحصيل يكلف نحو {_n(F['rev'][2] / 273.0)} ريال.", "warn")
    if np.isfinite(F["ccc"]) and F["ccc"] > 90:
        point(f"دورة التحويل النقدي {F['ccc']:,.0f} يوماً: كل تأخير في الفوترة أو التحصيل يستهلك نقداً "
              f"بمقدار نحو {_n(F['rev'][2] / 273.0)} ريال يومياً.", "warn")
    point(f"تنفيذ 2026 الذي لم يُفوتر بعد {_m(F['asg']['exec'] - F['asg']['billed'])} مليون ريال. تسريع إصدار "
          f"شهادات الإنجاز والمستخلصات هو أسرع رافعة لتحسين السيولة دون تمويل خارجي.", "warn")
    foot("الأرصدة كما في 30 سبتمبر 2026 دون تسنين، ومعدلات الدوران محسوبة على أساس سنوي.")


def s_people(F):
    head("العمالة والإنتاجية", "أكبر بند تكلفة وأكبر مصدر للقيمة")
    import plotly.graph_objects as go
    C = F["C"].sort_values("الإيراد", ascending=False)
    ppp = _div(F["rev26c"], F["hc_p"])
    sal_pl = F["all"]["pl"]["salaries"][5]
    kpis([("إجمالي العمالة", f"{F['hc']:,.0f}", f"منتجة {F['hc_p']:,.0f} · إدارية {F['hc_a']:,.0f}", ""),
          ("نسبة السعودة", _p(_div(F["hc_s"], F["hc"], 100)), f"{F['hc_s']:,.0f} موظف سعودي", "gold"),
          ("إنتاجية الفرد المنتج", _n(ppp) + " ريال", "إيراد 9 أشهر لكل عامل منتج", "up"),
          ("تكلفة الرواتب المحمّلة", _m(sal_pl) + " م", f"{_p(_div(sal_pl, F['rev26c'], 100))} من إيراد المراكز", "down" if _div(sal_pl, F["rev26c"], 100) > 45 else "")])
    c1, c2 = st.columns([1.2, 1])
    with c1:
        C2 = C.copy()
        C2["إنتاجية"] = C2.apply(lambda r: _div(r["الإيراد"], r["المنتجة"]), axis=1)
        C2 = C2.sort_values("إنتاجية", ascending=True)
        fig = go.Figure(go.Bar(y=C2["العقد"].str.replace("العقد الموحد ", "", regex=False), x=C2["إنتاجية"],
                               orientation="h", marker_color=NAVY,
                               text=[f"{v:,.0f}" for v in C2["إنتاجية"]], textposition="auto"))
        fig.update_layout(title="إنتاجية العامل المنتج لكل عقد (ريال / 9 أشهر)")
        st.plotly_chart(_fig(fig, 350, legend=False), use_container_width=True)
    with c2:
        D = pd.DataFrame({
            "العقد": C["العقد"].str.replace("العقد الموحد ", "", regex=False),
            "العمالة": C["العمالة"].map(lambda v: f"{v:,.0f}"),
            "المنتجة": C["المنتجة"].map(lambda v: f"{v:,.0f}"),
            "الرواتب من الإيراد": C["رواتب%"].map(lambda v: _p(v)),
        })
        _tbl(D)
    hi = C.loc[C["رواتب%"].idxmax()]
    point(f"أعلى عبء رواتب في <b>{hi['العقد']}</b> حيث تمثل الرواتب {_p(hi['رواتب%'])} من الإيراد، "
          f"مقابل متوسط {_p(_div(C['الرواتب'].sum(), C['الإيراد'].sum(), 100))} على مستوى العقود.",
          "bad" if hi["رواتب%"] > 60 else "warn")
    point(f"الكادر الإداري في المواقع {F['hc_a']:,.0f} موظفاً بتكلفة {_m(F['adm_pay'])} مليون ريال، أي "
          f"{_p(_div(F['hc_a'], F['hc'], 100))} من العمالة و{_p(_div(F['adm_pay'], F['comp'], 100))} من تكلفة العمالة.")
    foot(f"العمالة بالمتوسط المرجح لعدد شهور الخدمة في 2026. تكلفة الرواتب المحمّلة على المراكز "
         f"{_m(sal_pl)} مليون ريال بينما المصروف في ملف الرواتب {_m(F['comp'])} مليون، والفرق "
         f"{_m(sal_pl - F['comp'])} مليون يمثل مخصصات الإجازات ونهاية الخدمة والتذاكر غير المدفوعة نقداً.")


def s_assets(F):
    head("الأصول والمعدات", "قاعدة التشغيل ومدى استهلاكها")
    C = F["C"].sort_values("الإيراد", ascending=False)
    fd = _div(F["ast_fd"], F["ast_cnt"], 100)
    kpis([("التكلفة التاريخية للأصول", _m(F["ast_cost"]) + " م", f"{F['ast_cnt']:,} أصل", ""),
          ("صافي القيمة الدفترية", _m(F["ast_nbv"]) + " م", f"{_p(_div(F['ast_nbv'], F['ast_cost'], 100))} من التكلفة", "gold"),
          ("أصول مهلكة دفترياً", f"{F['ast_fd']:,}", f"{_p(fd)} من العدد", "down" if fd > 45 else "warn"),
          ("إنتاجية الأصول", _p(_div(F["rev26c"], F["ast_cost"], 100)), "إيراد 9 أشهر إلى تكلفة المعدات", "up")])
    D = pd.DataFrame({
        "العقد": C["العقد"].str.replace("العقد الموحد ", "", regex=False),
        "تكلفة المعدات (م)": C["أصول"].map(lambda v: _m(v)),
        "إنتاجية الأصول": C.apply(lambda r: _p(_div(r["الإيراد"], r["أصول"], 100)), axis=1),
        "تشغيل وصيانة واستهلاك (م)": C["المعدات"].map(lambda v: _m(v)),
        "من الإيراد": C.apply(lambda r: _p(_div(r["المعدات"], r["الإيراد"], 100)), axis=1),
    })
    _tbl(D)
    point(f"{_p(fd)} من الأصول مهلكة دفترياً بالكامل لكنها ما زالت في الخدمة، وهذا يرفع تكلفة الصيانة "
          f"ويخفض الإهلاك المحمّل، فالربح الظاهر أعلى من الربح الاقتصادي بمقدار تكلفة الإحلال المؤجلة.",
          "warn")
    point(f"تشغيل وصيانة واستهلاك المعدات بلغت {_m(C['المعدات'].sum())} مليون ريال، أي "
          f"{_p(_div(C['المعدات'].sum(), C['الإيراد'].sum(), 100))} من الإيراد.")
    foot("القيم من سجل الأصول الثابتة موزعة على مراكز التكلفة.")


def s_watch(F):
    head("ما يستحق قرار الإدارة", "مؤشرات مستخرجة آلياً من بيانات الفترة")
    C = F["C"]
    rev = F["rev26c"]
    items = []
    pen = dict(F["cat"]).get("غرامات التأخير ومخالفات المشاريع", 0.0)
    if pen > 0:
        items.append((("bad" if _div(pen, rev, 100) >= 1 else "warn"),
                      f"<b>الغرامات:</b> {_n(pen)} ريال في تسعة أشهر ({_p(_div(pen, rev, 100))} من الإيراد). "
                      f"خفضها إلى النصف يضيف {_n(pen / 2)} ريال إلى النتيجة مباشرة."))
    unb = F["asg"]["exec"] - F["asg"]["billed"]
    if unb > 0:
        items.append(("warn", f"<b>تنفيذ لم يُفوتر:</b> {_m(unb)} مليون ريال من تنفيذ 2026 خارج الفوترة. "
                              f"تحويل نصفها إلى مستخلصات يحرر {_m(unb / 2)} مليون ريال نقداً."))
    gap = F["asg"]["wip"] - F["accrued"]
    if abs(gap) > 0.1 * max(F["accrued"], 1):
        items.append(("bad", f"<b>فجوة مطابقة:</b> المنفذ غير المفوتر في نموذج الإسناد يزيد على الإيراد المستحق "
                             f"في المركز المالي بمقدار {_m(gap)} مليون ريال. مطابقة الرصيدين تسبق أي قرار "
                             f"يستند إلى حجم الأعمال تحت التنفيذ."))
    neg = C[C["النتيجة"] < 0]
    for _, r in neg.iterrows():
        items.append(("bad", f"<b>{r['العقد']}:</b> نتيجة سالبة {_m(r['النتيجة'])} مليون ريال بإيراد "
                             f"{_m(r['الإيراد'])} مليون ورواتب تمثل {_p(r['رواتب%'])} من الإيراد."))
    sub_share = _div(F["sub26"], F["team26"] + F["sub26"], 100)
    if np.isfinite(sub_share) and sub_share > 15:
        items.append(("warn", f"<b>مقاولو الباطن:</b> ينفذون {_p(sub_share)} من إجمالي الأعمال. "
                              f"مراجعة أسعارهم مقابل التكلفة الداخلية تحدد ما إذا كان الإسناد يوفر أم يكلف."))
    fd = _div(F["ast_fd"], F["ast_cnt"], 100)
    if np.isfinite(fd) and fd > 40:
        items.append(("warn", f"<b>أسطول المعدات:</b> {_p(fd)} من الأصول مهلكة دفترياً. "
                              f"خطة إحلال مجدولة تمنع قفزة مفاجئة في الصيانة والتوقفات."))
    if np.isfinite(F["ccc"]) and F["ccc"] > 90:
        items.append(("warn", f"<b>دورة التحويل النقدي:</b> {F['ccc']:,.0f} يوماً. كل عشرة أيام تخفيض تحرر نحو "
                              f"{_n(F['rev'][2] / 273.0 * 10)} ريال."))
    best = C.loc[C["الهامش"].idxmax()]
    items.append(("good", f"<b>الأداء المرجعي:</b> {best['العقد']} يحقق هامشاً {_p(best['الهامش'])}. "
                          f"لو بلغت باقي العقود هذا الهامش لارتفعت النتيجة بمقدار "
                          f"{_m(sum(max(0.0, best['الهامش'] / 100 * r['الإيراد'] - r['النتيجة']) for _, r in C.iterrows() if r['العقد'] != best['العقد']))} مليون ريال."))
    order = {"bad": 0, "warn": 1, "good": 2}
    for tone, txt in sorted(items, key=lambda x: order.get(x[0], 3)):
        point(txt, tone)
    foot("هذه مؤشرات محسوبة من الأرقام، والقرار يبقى للإدارة بعد مراجعة أسباب كل بند.")


def s_summary(F, build):
    head("الخلاصة", "صورة واحدة لأداء الفترة")
    C = F["C"]
    rows = [
        ("section", "الحجم", []),
        ("item", "الإيراد المعتمد (تنفيذ فعلي)", [F["rev"][2]]),
        ("item", "منه تنفيذ فرق الشركة", [F["team26"]]),
        ("item", "منه تنفيذ مقاولي الباطن", [F["sub26"]]),
        ("section", "الربحية", []),
        ("item", "نتيجة مراكز العقود", [C["النتيجة"].sum()]),
        ("item", "تكلفة الإدارة ومصنع الأعمدة", [-F["adm_cost"] + F["adm_rev"]]),
        ("subtotal", "الربح قبل الفوائد والإهلاك", [F["ebitda"][2]]),
        ("total", "صافي الربح", [F["net"][2]]),
        ("pct", "هامش صافي الربح %", [F["nm"][2]]),
        ("section", "المركز المالي في 30 سبتمبر", []),
        ("item", "إجمالي الأصول", [F["assets"]]),
        ("item", "حقوق الملكية", [F["equity"]]),
        ("item", "النقد وما في حكمه", [F["cash"]]),
        ("item", "القروض البنكية", [F["loans"]]),
        ("item", "إيراد مستحق غير مفوتر", [F["accrued"]]),
        ("section", "التشغيل", []),
        ("item", "عدد العمالة", [F["hc"]]),
        ("item", "منها عمالة منتجة", [F["hc_p"]]),
        ("item", "تكلفة العمالة (ملف الرواتب)", [F["comp"]]),
        ("item", "منفذ غير مفوتر (نموذج الإسناد — يحتاج مطابقة)", [F["asg"]["wip"]]),
        ("item", "رصيد إسناد غير منفذ", [F["asg"]["remain"]]),
    ]
    st.table(build(rows, ["البند", PERIOD]))
    foot("عرض معد من منصة التقارير المالية لشركة دلتا السعودية · "
         f"تاريخ الإصدار {dt.date.today():%Y-%m-%d}")


def s_admin(F):
    head("الكادر الإداري في المواقع", "عدد الإداريين وتكلفتهم في كل مركز تكلفة · 2026 تسعة أشهر")
    import plotly.graph_objects as go
    A = F["ADM"]
    if not len(A):
        point("لا توجد بيانات عمالة للمواقع.", "warn")
        return
    tot_a, tot_c, tot_rv = A["إداري"].sum(), A["تكلفة الإدارة"].sum(), A["الإيراد"].sum()
    tot_hc, tot_comp, tot_p = A["العمالة"].sum(), A["تكلفة العمالة"].sum(), A["منتج"].sum()
    kpis([("الكادر الإداري", f"{tot_a:,.0f}", f"{_p(_div(tot_a, tot_hc, 100))} من إجمالي العمالة", ""),
          ("تكلفته", _m(tot_c) + " م", f"{_p(_div(tot_c, tot_comp, 100))} من تكلفة العمالة", "gold"),
          ("من الإيراد", _p(_div(tot_c, tot_rv, 100)), "نسبة تكلفة الإدارة إلى إيراد المواقع", "down" if _div(tot_c, tot_rv, 100) > 10 else "up"),
          ("منتج لكل إداري", f"{_div(tot_p, tot_a):,.1f}", f"متوسط كلفة الإداري {_n(_div(tot_c, tot_a))} ريال", "")])
    V = A[A["الإيراد"] > 0].sort_values("إدارة/إيراد", ascending=True)
    ACOL = {"إنشاءات وتعزيزات": NAVY, "صيانة": TEAL, "قراء عدادات": GOLD}
    c1, c2 = st.columns([1.15, 1])
    with c1:
        avg = _div(tot_c, tot_rv, 100)
        fig = go.Figure()
        for act, col in ACOL.items():
            W = V[V["النشاط"] == act]
            if not len(W):
                continue
            fig.add_bar(y=W["الموقع"], x=[round(v, 1) for v in W["إدارة/إيراد"]], orientation="h", name=act,
                        marker_color=col, text=[f"{v:.1f}%" for v in W["إدارة/إيراد"]], textposition="auto")
        fig.add_vline(x=round(avg, 1), line_dash="dash", line_color=RED,
                      annotation_text=f"متوسط المواقع {avg:.1f}%", annotation_position="top")
        fig.update_layout(title="تكلفة الكادر الإداري من إيراد الموقع (%)", barmode="relative")
        st.plotly_chart(_fig(fig, max(380, 26 * len(V))), use_container_width=True)
    with c2:
        W = V.sort_values("منتج لكل إداري", ascending=False)
        fig2 = go.Figure(go.Bar(y=W["الموقع"], x=[round(v, 1) for v in W["منتج لكل إداري"]], orientation="h",
                                marker_color=NAVY, text=[f"{v:,.1f}" for v in W["منتج لكل إداري"]], textposition="auto"))
        fig2.update_layout(title="عدد العمال المنتجين لكل موظف إداري")
        st.plotly_chart(_fig(fig2, max(360, 26 * len(W)), legend=False), use_container_width=True)
    _ord = {"إنشاءات وتعزيزات": 0, "صيانة": 1, "قراء عدادات": 2}
    D = A.assign(_o=A["النشاط"].map(_ord).fillna(9)).sort_values(["_o", "تكلفة الإدارة"], ascending=[True, False])
    T = pd.DataFrame({
        "الموقع": D["الموقع"],
        "النشاط": D["النشاط"],
        "العقد": D["العقد"].str.replace("العقد الموحد ", "", regex=False),
        "العمالة": D["العمالة"].map(lambda v: f"{v:,.0f}"),
        "إداري": D["إداري"].map(lambda v: f"{v:,.0f}"),
        "نسبته من العمالة": D["إداري %"].map(_p),
        "تكلفة الإدارة (م)": D["تكلفة الإدارة"].map(_m),
        "من تكلفة العمالة": D["إدارة/عمالة"].map(_p),
        "من إيراد الموقع": D["إدارة/إيراد"].map(lambda v: _p(v) if np.isfinite(v) else "—"),
        "منتج لكل إداري": D["منتج لكل إداري"].map(lambda v: f"{v:,.1f}" if np.isfinite(v) else "—"),
        "كلفة الإداري": D["كلفة الإداري"].map(lambda v: _n(v) if np.isfinite(v) else "—"),
    })
    _tbl(T)
    for act in ("إنشاءات وتعزيزات", "صيانة"):
        W = V[V["النشاط"] == act]
        if len(W) < 2:
            continue
        a_avg = _div(W["تكلفة الإدارة"].sum(), W["الإيراد"].sum(), 100)
        hi, lo = W.iloc[-1], W.iloc[0]
        gap = float(sum(max(0.0, r["تكلفة الإدارة"] - r["الإيراد"] * a_avg / 100.0) for _, r in W.iterrows()))
        point(f"<b>{act}:</b> متوسط العبء الإداري {_p(a_avg)} من الإيراد. أعلاه <b>{hi['الموقع']}</b> "
              f"({_p(hi['إدارة/إيراد'])} بـ{hi['إداري']:,.0f} إداريين) وأدناه <b>{lo['الموقع']}</b> ({_p(lo['إدارة/إيراد'])}). "
              f"لو بلغت المواقع فوق المتوسط متوسطَ نشاطها لانخفضت التكلفة {_n(gap)} ريال في تسعة أشهر.",
              "warn" if hi["إدارة/إيراد"] > 2 * a_avg else "")
    con = V[V["النشاط"] == "إنشاءات وتعزيزات"]
    mnt = V[V["النشاط"] == "صيانة"]
    if len(con) and len(mnt):
        point(f"الفارق بين النشاطين بنيوي لا إداري: مواقع الإنشاءات تحمل "
              f"{_p(_div(con['تكلفة الإدارة'].sum(), con['الإيراد'].sum(), 100))} مقابل "
              f"{_p(_div(mnt['تكلفة الإدارة'].sum(), mnt['الإيراد'].sum(), 100))} في الصيانة، لأن أعمال الإنشاءات "
              f"تحتاج تنسيقاً ومتابعة إسناد وفوترة لكل أمر عمل. المقارنة العادلة داخل النشاط الواحد.", "")
    ho = F.get("HO", {})
    if ho.get("cost"):
        point(f"خارج هذا الجدول: الإدارة العامة ومصنع الأعمدة بهما {ho['hc']:,.0f} موظفاً إدارياً بتكلفة "
              f"{_m(ho['cost'])} مليون ريال، وهي مركز مركزي بلا إيراد تشغيلي فلا تدخل المقارنة بين المواقع.", "")
    foot("الكادر الإداري وتكلفته من ملف الرواتب موزعاً على مراكز التكلفة، والإيراد هو التنفيذ المعتمد لكل مركز في 2026. "
         "مراكز قراء العدادات انتهى مشروعها خلال الفترة.")


SLIDES = [
    ("١. الغلاف والصورة العامة", "cover"),
    ("٢. الأداء المالي", "fin"),
    ("٣. العقود الخمسة", "con"),
    ("٤. هيكل التكلفة", "cost"),
    ("٥. الإسناد والتنفيذ والفوترة", "bl"),
    ("٦. السيولة ورأس المال العامل", "liq"),
    ("٧. العمالة والإنتاجية", "ppl"),
    ("٨. الكادر الإداري في المواقع", "adm"),
    ("٩. الأصول والمعدات", "ast"),
    ("١٠. ما يستحق قرار الإدارة", "watch"),
    ("١١. الخلاصة", "sum"),
]


def render_deck(ctx, build_styled_table, cv):
    st.markdown(CSS, unsafe_allow_html=True)
    st.subheader("🎞️ العرض التقديمي للشركة")
    try:
        F = facts(ctx, cv)
    except Exception as e:
        st.error(f"تعذّر تجهيز أرقام العرض: {e}")
        return
    c1, c2 = st.columns([3, 1])
    with c2:
        mode = st.radio("طريقة العرض", ["شريحة واحدة", "كل الشرائح"], horizontal=True, key="dk_mode")
    with c1:
        if mode == "شريحة واحدة":
            pick = st.select_slider("الشريحة", options=[s[0] for s in SLIDES], key="dk_pick")
        else:
            pick = None
            st.caption("كل الشرائح متتابعة في صفحة واحدة، مناسبة للطباعة أو التصدير إلى PDF من المتصفح.")
    draw = {"cover": lambda: s_cover(F, ctx), "fin": lambda: s_financial(F, build_styled_table),
            "con": lambda: s_contracts(F, build_styled_table), "cost": lambda: s_cost(F),
            "bl": lambda: s_backlog(F), "liq": lambda: s_liquidity(F), "ppl": lambda: s_people(F), "adm": lambda: s_admin(F),
            "ast": lambda: s_assets(F), "watch": lambda: s_watch(F), "sum": lambda: s_summary(F, build_styled_table)}
    picked = [s for s in SLIDES if (pick is None or s[0] == pick)]
    for title, key in picked:
        st.markdown('<div class="dk-wrap">', unsafe_allow_html=True)
        draw[key]()
        st.markdown("</div>", unsafe_allow_html=True)
        if len(picked) > 1:
            st.markdown("---")
