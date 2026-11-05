# uitable.py
# عرض موحّد للجداول العريضة في المنصة: رأس ثابت، عمود أساسي ثابت على اليمين،
# خط أوضح للعمود الأساسي، أرقام في منتصف الخلية بفاصلة آلاف بلا كسور.

import html as _html
import itertools

import numpy as np
import pandas as pd
import streamlit as st

CSS = """
<style>
  .uw-wrap { direction: rtl; overflow: auto; border: 1px solid #E2E8F0; border-radius: 8px;
             background: #fff; margin-bottom: 6px; }
  .uw { direction: rtl; border-collapse: separate; border-spacing: 0; width: max-content; min-width: 100%;
        font-family: 'Segoe UI', Tahoma, sans-serif; }
  .uw th, .uw td { text-align: center !important; vertical-align: middle !important; white-space: nowrap;
                   padding: 9px 12px; border-bottom: 1px solid #EEF2F7; font-size: 1.1rem;
                   font-variant-numeric: tabular-nums; color: #111827; unicode-bidi: plaintext; }
  .uw thead th { position: -webkit-sticky; position: sticky; top: 0; z-index: 3; background: #1E3A8A;
                 color: #fff !important; font-weight: 700; font-size: 1.0rem; white-space: pre-line;
                 line-height: 1.35; }
  .uw tbody td.k, .uw thead th.k { position: -webkit-sticky; position: sticky; right: 0; z-index: 2;
                                   box-shadow: -1px 0 0 0 #CBD5E1 inset; }
  .uw tbody td.k { background: #F8FAFC; font-weight: 600; color: #0B2A6F; }
  .uw thead th.k { z-index: 4; }
  .uw tbody tr:nth-child(even) td { background: #FCFDFF; }
  .uw tbody tr:nth-child(even) td.k { background: #F1F5F9; }
  .uw tbody tr:hover td { background: #EFF6FF; }
  .uw tbody tr.tot td { background: #DCFCE7 !important; color: #14532D !important; font-weight: 700;
                        border-top: 2px solid #166534; border-bottom: 2px double #166534; }
  .uw tbody tr.sub td { background: #DBEAFE !important; color: #1E3A8A !important; font-weight: 700; }
  .uw td.neg { color: #B91C1C; }
  .uw td.zero { color: #94A3B8; }
</style>
"""


_SEQ = itertools.count(1)


def css():
    """تُستدعى مرة في كل تبويب يستخدم الجداول."""
    st.markdown(CSS, unsafe_allow_html=True)


def _txt(v, f):
    if isinstance(v, bool):
        return "نعم" if v else "لا"
    if v is None or (isinstance(v, float) and pd.isna(v)) or (not isinstance(v, (int, float, np.number)) and pd.isna(v)):
        return "—"
    if isinstance(v, (int, float, np.integer, np.floating)):
        return f.format(v) if f else (f"{v:,.0f}" if float(v) == int(v) else f"{v:,.2f}")
    return str(v)


_DEC2 = ("نسبة", "معامل", "تطابق", "درجة", "سعر", "متوسط")


def autofmt(df, key_col=None):
    """فاصلة آلاف بلا كسور، إلا النسب والمعاملات والأسعار فبخانتين."""
    out = {}
    for c in df.columns:
        if c == key_col:
            continue
        try:
            if pd.api.types.is_numeric_dtype(df[c]) and not pd.api.types.is_bool_dtype(df[c]):
                out[c] = "{:,.2f}" if any(k in str(c) for k in _DEC2) else "{:,.0f}"
        except Exception:
            continue
    return out


def wide(df, key_col=None, fmts=None, key_font=1.5, height="72vh", totals=(), subs=(),
         max_rows=700, note=True):
    """جدول عريض برأس ثابت وعمود أساسي ثابت. يتجاوز العدد الأقصى ⇒ يُعرض أول max_rows سطر."""
    if df is None or not len(df):
        st.caption("لا توجد بيانات للعرض.")
        return
    D = df
    cut = len(D) > max_rows
    if cut:
        D = D.head(max_rows)
    key_col = key_col if (key_col and key_col in D.columns) else D.columns[0]
    cols = [key_col] + [c for c in D.columns if c != key_col]
    f = dict(autofmt(D, key_col))
    f.update(fmts or {})
    head = "".join(f'<th class="{"k" if c == key_col else ""}">{_html.escape(str(c))}</th>' for c in cols)
    body = []
    for _, r in D.iterrows():
        kv = str(r[key_col])
        cls = "tot" if kv in totals else ("sub" if kv in subs else "")
        tds = []
        for c in cols:
            v = r[c]
            t = _txt(v, f.get(c))
            cc = "k" if c == key_col else ""
            if not cc and isinstance(v, (int, float, np.integer, np.floating)) and not isinstance(v, bool):
                if v < 0:
                    cc, t = "neg", "(" + t.lstrip("-") + ")"
                elif v == 0:
                    cc = "zero"
            tds.append(f'<td class="{cc}">{_html.escape(t)}</td>')
        body.append(f'<tr class="{cls}">' + "".join(tds) + "</tr>")
    uid = "uw%d" % next(_SEQ)
    st.markdown(
        f'<style>.{uid} tbody td.k{{font-size:{key_font}rem}}</style>'
        f'<div class="uw-wrap" style="max-height:{height}">'
        f'<table class="uw {uid}"><thead><tr>{head}</tr></thead>'
        f'<tbody>{"".join(body)}</tbody></table></div>',
        unsafe_allow_html=True)
    if cut and note:
        st.caption(f"يُعرض أول {max_rows:,} سطر من {len(df):,}. نزّل الملف للاطلاع على الباقي.")
