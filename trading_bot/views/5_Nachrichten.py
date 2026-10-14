"""Seite 'Nachrichten': wichtigste Börsennachrichten und die betroffenen Aktien."""

from datetime import date, timedelta

import pandas as pd
import streamlit as st

from tradingbot import config, data, news
from tradingbot.portfolio import get_state
from tradingbot.watchlist import get_watchlist

TOP_COUNT = 15   # so viele Nachrichten werden direkt angezeigt, der Rest aufklappbar

st.set_page_config(page_title="Nachrichten", page_icon="📰", layout="wide")
st.title("📰 Nachrichten")
st.warning(config.DISCLAIMER)
st.caption("Quelle: Yahoo Finance (meist auf Englisch). Welche Aktien betroffen sind, ordnet Yahoo zu. "
           "Die Kursänderung neben einer Aktie zeigt nur, wie sie sich am letzten Handelstag bewegt hat – "
           "das beweist nicht, dass die Nachricht der Grund war.")

# ---------------------------------------------------------------- Auswahl
c = st.columns([1, 1, 1, 1, 1, 1])
days = c[0].selectbox("Zeitraum", [1, 3, 7], index=1, format_func=lambda d: f"letzte {d} Tag{'e' if d > 1 else ''}")
use_depot = c[1].checkbox("Depot", value=True)
use_watch = c[2].checkbox("Watchlist", value=True)
use_scan = c[3].checkbox("Scan-Liste", value=False, help="Viele Aktien – das erste Laden dauert länger.")
use_market = c[4].checkbox("Gesamtmarkt", value=True, help="Nachrichten zu DAX und S&P 500")
force = c[5].button("🔄 Neu laden")

roles = news.build_roles(
    depot=list(get_state().positions) if use_depot else [],
    watchlist=get_watchlist() if use_watch else [],
    scanlist=get_watchlist(name="scanlist") if use_scan else [],
    market=use_market,
)
if not roles:
    st.info("Wähle oben mindestens eine Quelle aus.")
    st.stop()

with st.spinner(f"Lade Nachrichten für {len(roles)} Symbole (gespeicherte bis {news.MAX_AGE_HOURS} h alt) …"):
    errors = news.refresh_news(list(roles), force=force)
if errors:
    with st.expander(f"⚠️ Nachrichten nicht ladbar für: {', '.join(errors)}"):
        st.write("\n".join(f"- **{t}**: {msg}" for t, msg in errors.items()))

items = news.ranked_news(roles, days=days)
if items.empty:
    st.info("Keine Nachrichten im gewählten Zeitraum gefunden.")
    st.stop()

# ---------------------------------------------------------------- Kursänderungen der betroffenen Aktien
stocks = sorted({t for a in items["affected"] for t in a if t not in news.MARKET_SYMBOLS})
change: dict[str, float] = {}
if stocks:
    loaded = data.load_prices(stocks, (date.today() - timedelta(days=14)).isoformat())
    if len(loaded.prices) >= 2:
        change = loaded.prices_local.pct_change(fill_method=None).iloc[-1].dropna().to_dict()

# ---------------------------------------------------------------- Filter
mentioned = sorted({t for a in items["affected"] for t in a},
                   key=lambda t: (-news.ROLE_WEIGHTS[roles[t]], t))
only = st.multiselect("Nur Nachrichten zu …", mentioned, placeholder="Alle Aktien",
                      format_func=lambda t: news.MARKET_SYMBOLS.get(t, t))
if only:
    items = items[items["affected"].apply(lambda a: bool(set(a) & set(only)))]
st.write(f"**{len(items)} Nachrichten**, wichtigste zuerst (Depot zählt mehr als Watchlist, neuere mehr als ältere).")


# ---------------------------------------------------------------- Anzeige
def md(text: str) -> str:
    """Zeichen entschärfen, die Streamlit sonst als Formatierung/Formel deutet."""
    for ch in "\\$*_[]`<>":
        text = text.replace(ch, "\\" + ch)
    return text


def stock_label(t: str) -> str:
    name = news.MARKET_SYMBOLS.get(t, t)
    label = f"**{md(name)}** ({news.ROLE_LABELS[roles[t]]})"
    if t in change:
        rounded = round(change[t], 3)  # so wie angezeigt – sonst stünde "▼ -0,0 %" da
        pct = f"{rounded:+.1%}".replace(".", ",")
        label += f" :green[▲ {pct}]" if rounded > 0 else f" :red[▼ {pct}]" if rounded < 0 else " ±0,0%"
    return label


now = pd.Timestamp.now(tz="UTC")


def show(row) -> None:
    with st.container(border=True):
        title = md(row["title"])
        url = row["url"] or ""
        st.markdown(f"#### [{title}]({url})" if url.startswith("http") else f"#### {title}")
        hours = int((now - row["published"]).total_seconds() // 3600)
        age = f"vor {hours} Std." if hours < 48 else f"vor {hours // 24} Tagen"
        local = row["published"].tz_convert("Europe/Berlin")
        st.caption(f"{md(row['publisher'] or 'Unbekannte Quelle')} · {local:%d.%m.%Y %H:%M} · {age}")
        if row["summary"]:
            summary = row["summary"]
            st.write(md(summary if len(summary) <= 400 else summary[:400].rsplit(" ", 1)[0] + " …"))
        st.markdown("Betrifft: " + " · ".join(stock_label(t) for t in row["affected"]))


for _, row in items.head(TOP_COUNT).iterrows():
    show(row)
if len(items) > TOP_COUNT:
    with st.expander(f"Weitere {len(items) - TOP_COUNT} Nachrichten"):
        for _, row in items.iloc[TOP_COUNT:].iterrows():
            show(row)
