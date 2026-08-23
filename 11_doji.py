import io
import pandas as pd
import requests
import streamlit as st
import yfinance as yf

# Streamlit Layout
st.set_page_config(page_title="Doji Scanner weekly", page_icon="📈", layout="wide")

st.title("🕯️ Doji Scanner weekly")
st.markdown(
    "Dieses Tool scannt alle Aktien des S&P 500 im **Wochenchart** nach Doji-Mustern. "
    "Ein Doji ist hier definiert als eine Kerze, bei der der Körper (Open bis Close) "
    "höchstens **5%** der gesamten Spanne (High bis Low) ausmacht."
)

# Feste Parameter
MAX_BODY_PCT = 0.05  # 5%
YEARS_HISTORY = 2
MIN_HISTORY_WEEKS = 52


@st.cache_data(ttl=3600)
def get_sp500_tickers():
    """Lädt die aktuelle S&P 500 Ticker-Liste von Wikipedia mit io.StringIO."""
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()

        tables = pd.read_html(io.StringIO(response.text))
        df = tables[0]
        tickers = df["Symbol"].tolist()
        tickers = [t.replace(".", "-") for t in tickers]
        return tickers
    except Exception as e:
        st.error(f"Fehler beim Laden der S&P 500 Liste von Wikipedia: {e}")
        return []


if st.button("🚀 Scan starten", type="primary"):
    tickers = get_sp500_tickers()

    if not tickers:
        st.warning("Keine Ticker geladen. Abbruch.")
    else:
        st.info(
            f"Lade Wochen-Daten für {len(tickers)} S&P 500 Unternehmen (letzte {YEARS_HISTORY} Jahre)..."
        )

        # Daten herunterladen (Wochenintervall)
        data = yf.download(
            tickers, period=f"{YEARS_HISTORY}y", interval="1wk", progress=False
        )

        if data.empty:
            st.error(
                "Fehler beim Laden der Kursdaten über yfinance. Bitte versuche es später noch einmal."
            )
        else:
            try:
                opens = data["Open"]
                highs = data["High"]
                lows = data["Low"]
                closes = data["Close"]
            except KeyError:
                opens = data.xs("Open", level=0, axis=1)
                highs = data.xs("High", level=0, axis=1)
                lows = data.xs("Low", level=0, axis=1)
                closes = data.xs("Close", level=0, axis=1)

            doji_results = []
            progress_bar = st.progress(0)
            total_tickers = len(tickers)

            for idx, ticker in enumerate(tickers):
                progress_bar.progress((idx + 1) / total_tickers)

                try:
                    if ticker not in opens.columns:
                        continue

                    df_ticker = pd.DataFrame(
                        {
                            "Open": opens[ticker],
                            "High": highs[ticker],
                            "Low": lows[ticker],
                            "Close": closes[ticker],
                        }
                    ).dropna()

                    if len(df_ticker) < MIN_HISTORY_WEEKS:
                        continue

                    total_range = df_ticker["High"] - df_ticker["Low"]
                    body_size = (df_ticker["Open"] - df_ticker["Close"]).abs()

                    valid_range = total_range > 1e-9
                    body_ratio = pd.Series(0.0, index=df_ticker.index)
                    body_ratio[valid_range] = (
                        body_size[valid_range] / total_range[valid_range]
                    )

                    is_doji = (body_ratio <= MAX_BODY_PCT) & valid_range

                    if not df_ticker.empty:
                        if is_doji.iloc[-1]:
                            last_high = df_ticker["High"].iloc[-1]
                            last_low = df_ticker["Low"].iloc[-1]
                            stop_long = last_high * (1.0 - 0.015)
                            stop_short = last_low * (1.0 + 0.015)

                            doji_results.append(
                                {
                                    "Ticker": ticker,
                                    "Stop Buy": round(last_high, 2),
                                    "Stop Long": round(stop_long, 2),
                                    "Stop Sell": round(last_low, 2),
                                    "Stop Short": round(stop_short, 2),
                                    "Körper in % der Spanne": round(
                                        body_ratio.iloc[-1] * 100, 2
                                    ),
                                }
                            )
                except Exception:
                    continue

            progress_bar.empty()

            if doji_results:
                result_df = pd.DataFrame(doji_results)
                st.success(
                    f"Treffer! {len(result_df)} Aktien zeigen in der aktuellsten Woche ein Doji-Muster."
                )
                st.dataframe(result_df, use_container_width=True, hide_index=True)
            else:
                st.warning(
                    "Keine Aktien gefunden, bei denen die aktuelle Wochenkerze die Doji-Bedingung erfüllt."
                )
