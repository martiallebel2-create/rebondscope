from __future__ import annotations

from datetime import date, timedelta
from textwrap import dedent

import pandas as pd
import streamlit as st

from auto_levels import AutoLevelConfig, TRACKED_SYMBOLS, build_auto_level_row
from exchange_rate_store import get_cached_eur_usd_rate, load_cached_eur_usd_rate
from market_data import download_latest_quote, download_prices


APP_NAME = "RebondScope"

st.set_page_config(page_title=APP_NAME, page_icon="chart_with_upwards_trend", layout="wide")


def main() -> None:
    inject_theme()
    render_header()
    render_simple_dashboard()


def inject_theme() -> None:
    st.markdown(
        """
        <style>
        :root {
            --surface: #fffaf3;
            --surface-strong: #ffffff;
            --line: #e8ded0;
            --text: #1f2937;
            --muted: #7c6f64;
            --green: #177245;
            --blue: #0f4c5c;
            --amber: #b7791f;
        }
        .stApp {
            background:
                radial-gradient(circle at top left, rgba(180, 131, 72, 0.08), transparent 28%),
                linear-gradient(180deg, #f7f2ea 0%, #efe6d9 100%);
        }
        .block-container {
            max-width: 1480px;
            padding-top: 1.4rem;
            padding-bottom: 3rem;
        }
        .hero-card {
            background:
                linear-gradient(135deg, rgba(255, 251, 245, 0.97), rgba(248, 240, 228, 0.97)),
                radial-gradient(circle at top right, rgba(180, 131, 72, 0.12), transparent 36%);
            border: 1px solid rgba(224, 210, 189, 0.9);
            border-radius: 30px;
            padding: 26px 28px;
            box-shadow: 0 20px 60px rgba(88, 65, 43, 0.08);
            margin-bottom: 1rem;
        }
        .hero-title {
            text-align: center;
            font-size: 2.4rem;
            font-weight: 800;
            color: #1f2937;
            margin: 0.15rem 0 0.2rem;
        }
        .hero-kicker {
            text-align: center;
            font-size: 0.80rem;
            letter-spacing: 0.18em;
            text-transform: uppercase;
            color: #8d7d70;
        }
        .hero-subtitle {
            text-align: center;
            color: #6b7280;
            margin: 0.2rem 0 0;
        }
        .stock-top {
            display: flex;
            justify-content: space-between;
            gap: 10px;
            align-items: flex-start;
            margin-bottom: 10px;
        }
        .stock-name {
            font-size: 1rem;
            font-weight: 800;
            color: #2b241f;
            line-height: 1.15;
        }
        .stock-ticker {
            margin-top: 2px;
            font-size: 0.78rem;
            color: #7c6f64;
        }
        .stock-date {
            font-size: 0.74rem;
            color: #8d7d70;
            white-space: nowrap;
        }
        .stock-badge {
            display: inline-flex;
            align-items: center;
            border-radius: 999px;
            padding: 0.28rem 0.62rem;
            font-size: 0.76rem;
            font-weight: 800;
        }
        .stock-badge.buy {
            background: #d9edf1;
            color: #0f4c5c;
        }
        .stock-badge.sell {
            background: #def3e6;
            color: #177245;
        }
        .stock-badge.watch {
            background: #efe7db;
            color: #6b5d52;
        }
        .stock-price {
            margin: 2px 0 10px;
        }
        .stock-price strong {
            display: block;
            font-size: 1.25rem;
            color: #221b16;
            line-height: 1.05;
        }
        .stock-price span {
            font-size: 0.74rem;
            color: #7c6f64;
        }
        .stock-grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 8px 10px;
        }
        .stock-item-label {
            font-size: 0.84rem;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            color: #8d7d70;
            margin-bottom: 2px;
            font-weight: 700;
        }
        .stock-item-value {
            font-size: 1.08rem;
            font-weight: 800;
            color: #2b241f;
        }
        .simple-table-wrap {
            margin-top: 1rem;
            background: rgba(255, 252, 247, 0.9);
            border: 1px solid rgba(229, 218, 202, 0.95);
            border-radius: 24px;
            padding: 10px 12px 14px;
            box-shadow: 0 14px 34px rgba(88, 65, 43, 0.05);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_header() -> None:
    st.markdown(
        """
        <div class="hero-card">
            <div class="hero-kicker">Tableau simple</div>
            <div class="hero-title">RebondScope</div>
            <div class="hero-subtitle">Niveaux automatiques de veille, lisibles en un coup d'oeil</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_simple_dashboard() -> None:
    st.info(
        "Supports, achats, resistances et ventes sont calcules automatiquement pour Tesla, Palantir, Nvidia, AMD, Amazon, Meta, Stellantis et FDJ."
    )
    with st.expander("Comment lire cet ecran", expanded=False):
        st.write(
            """
            - `Support`: plus bas de la derniere seance disponible.
            - `Achat`: support + rebond minimum choisi.
            - `Resistance`: plus haut de la derniere seance disponible.
            - `Vente`: niveau de verification de sortie, aligne sur la resistance.
            - `Setup invalide`: achat trop proche ou au-dessus de la resistance.
            """
        )

    controls = st.columns([1, 1, 2])
    lookback_days = controls[0].selectbox("Historique", [90, 120, 180, 252], index=2)
    buy_rebound_pct = controls[1].number_input("Rebond achat (%)", min_value=0.5, value=1.5, step=0.1)
    controls[2].button("Actualiser les niveaux", type="primary", use_container_width=True)

    config = AutoLevelConfig(buy_rebound_pct=float(buy_rebound_pct), sell_buffer_pct=1.5)
    start_date = date.today() - timedelta(days=int(lookback_days))
    end_date = date.today() + timedelta(days=1)
    rows: list[dict[str, object]] = []
    errors: list[str] = []

    eur_rate_note: str | None = None
    try:
        eur_usd_rate = get_cached_eur_usd_rate()
    except ValueError:
        cached_rate = load_cached_eur_usd_rate()
        if cached_rate is not None:
            eur_usd_rate = float(cached_rate[0])
            eur_rate_note = "Taux EUR/USD recupere depuis le cache local."
        else:
            eur_usd_rate = 1.0
            eur_rate_note = "Taux EUR/USD indisponible. Les actions USD sont affichees provisoirement avec un taux 1.00."

    with st.spinner("Calcul automatique des niveaux..."):
        for ticker, label in TRACKED_SYMBOLS:
            try:
                prices = cached_download_prices(ticker, start_date, end_date)
                try:
                    quote = cached_download_latest_quote(ticker)
                    current_price = float(quote["price"])
                except ValueError:
                    current_price = float(prices.iloc[-1]["close"])
                rows.append(build_auto_level_row(ticker, label, prices, current_price, config, eur_usd_rate))
            except ValueError as exc:
                errors.append(f"{label} ({ticker}): {exc}")

    if errors:
        st.warning("Certaines actions n'ont pas pu etre chargees.")
        for message in errors:
            st.caption(message)

    if not rows:
        st.error("Aucune action n'a pu etre calculee.")
        return

    rows_df = pd.DataFrame(rows)
    st.caption(f"Derniere mise a jour: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}")
    st.caption(f"Taux EUR/USD utilise: {eur_usd_rate:.4f}")
    if eur_rate_note:
        st.caption(eur_rate_note)
    render_simple_dashboard_table(rows_df)


def render_simple_dashboard_table(rows: pd.DataFrame) -> None:
    display = rows.copy()
    status_order = {
        "Support atteint": 0,
        "Attente rebond": 1,
        "Achat possible": 2,
        "Vente possible": 3,
        "Resistance atteinte": 4,
        "Attendre": 5,
        "Setup invalide": 6,
    }
    display["_ordre"] = display["statut"].map(status_order).fillna(99)
    display = display.sort_values(["_ordre", "nom"]).drop(columns="_ordre")

    render_summary(display)
    render_simple_stock_cards(display.copy())

    table_display = display.rename(
        columns={
            "date_reference": "Date",
            "nom": "Action",
            "ticker": "Ticker",
            "devise": "Devise",
            "prix_actuel_eur": "Prix actuel EUR",
            "support_eur": "Support EUR",
            "declenchement_achat_eur": "Achat EUR",
            "resistance_eur": "Resistance EUR",
            "declenchement_vente_eur": "Vente EUR",
            "statut": "Statut",
            "distance_support_pct": "Ecart support",
            "distance_declenchement_achat_pct": "Ecart achat",
            "distance_resistance_pct": "Ecart resistance",
            "distance_declenchement_vente_pct": "Ecart vente",
            "marge_achat_vers_resistance_pct": "Marge achat->resistance",
        }
    )

    def highlight_status(row: pd.Series) -> list[str]:
        if row["Statut"] in {"Support atteint", "Attente rebond", "Achat possible"}:
            return ["background-color: #dbeafe"] * len(row)
        if row["Statut"] in {"Vente possible", "Resistance atteinte"}:
            return ["background-color: #dcfce7"] * len(row)
        if row["Statut"] == "Setup invalide":
            return ["background-color: #fef3c7"] * len(row)
        return [""] * len(row)

    st.markdown('<div class="simple-table-wrap">', unsafe_allow_html=True)
    st.markdown("#### Tableau detaille")
    st.dataframe(
        table_display.style.apply(highlight_status, axis=1).format(
            {
                "Prix actuel EUR": "{:.2f}",
                "Support EUR": "{:.2f}",
                "Achat EUR": "{:.2f}",
                "Resistance EUR": "{:.2f}",
                "Vente EUR": "{:.2f}",
                "Ecart support": "{:.2f}%",
                "Ecart achat": "{:.2f}%",
                "Ecart resistance": "{:.2f}%",
                "Ecart vente": "{:.2f}%",
                "Marge achat->resistance": "{:.2f}%",
            }
        ),
        use_container_width=True,
        column_order=[
            "Date",
            "Action",
            "Ticker",
            "Devise",
            "Prix actuel EUR",
            "Support EUR",
            "Achat EUR",
            "Resistance EUR",
            "Vente EUR",
            "Statut",
            "Ecart support",
            "Ecart achat",
            "Ecart resistance",
            "Ecart vente",
            "Marge achat->resistance",
        ],
    )
    st.markdown("</div>", unsafe_allow_html=True)


def render_summary(display: pd.DataFrame) -> None:
    summary = display["statut"].value_counts()
    buy_zone_count = int(
        summary.get("Achat possible", 0) + summary.get("Attente rebond", 0) + summary.get("Support atteint", 0)
    )
    sell_zone_count = int(summary.get("Vente possible", 0) + summary.get("Resistance atteinte", 0))

    summary_cards = st.columns(4)
    summary_cards[0].metric("Actions suivies", f"{len(display)}")
    summary_cards[1].metric("A surveiller achat", f"{buy_zone_count}")
    summary_cards[2].metric("A surveiller vente", f"{sell_zone_count}")
    summary_cards[3].metric("A eviter", f"{int(summary.get('Setup invalide', 0))}")


def render_simple_stock_cards(rows: pd.DataFrame) -> None:
    st.markdown("#### Vue cartes")
    st.caption("Cartes triees par ordre alphabetique. Tous les montants sont affiches en euros en priorite.")

    cards = rows.sort_values(["nom", "ticker"], ignore_index=True)
    columns = st.columns(3)

    for index, (_, row) in enumerate(cards.iterrows()):
        status = str(row.get("statut", "Attendre"))
        tone = "watch"
        if status in {"Support atteint", "Attente rebond", "Achat possible"}:
            tone = "buy"
        elif status in {"Vente possible", "Resistance atteinte"}:
            tone = "sell"

        reference_date = pd.to_datetime(row.get("date_reference"), errors="coerce")
        display_date = reference_date.strftime("%Y-%m-%d") if not pd.isna(reference_date) else "-"

        with columns[index % 3]:
            with st.container(border=True):
                st.markdown(
                    dedent(
                        f"""
                        <div class="stock-top">
                            <div>
                                <div class="stock-name">{row.get("nom", "")}</div>
                                <div class="stock-ticker">{row.get("ticker", "")} · {row.get("devise", "")}</div>
                            </div>
                            <div class="stock-date">{display_date}</div>
                        </div>
                        <div style="margin-bottom:10px;">
                            <span class="stock-badge {tone}">{status}</span>
                        </div>
                        <div class="stock-price">
                            <strong>{format_numeric(row.get("prix_actuel_eur"), " EUR")}</strong>
                            <span>{format_numeric(row.get("prix_actuel"))} {row.get("devise", "")}</span>
                        </div>
                        <div class="stock-grid">
                            <div>
                                <div class="stock-item-label">Support</div>
                                <div class="stock-item-value">{format_numeric(row.get("support_eur"), " EUR")}</div>
                            </div>
                            <div>
                                <div class="stock-item-label">Achat</div>
                                <div class="stock-item-value">{format_numeric(row.get("declenchement_achat_eur"), " EUR")}</div>
                            </div>
                            <div>
                                <div class="stock-item-label">Resistance</div>
                                <div class="stock-item-value">{format_numeric(row.get("resistance_eur"), " EUR")}</div>
                            </div>
                            <div>
                                <div class="stock-item-label">Vente</div>
                                <div class="stock-item-value">{format_numeric(row.get("declenchement_vente_eur"), " EUR")}</div>
                            </div>
                            <div>
                                <div class="stock-item-label">Prix vs achat</div>
                                <div class="stock-item-value">{format_numeric(row.get("distance_declenchement_achat_pct"), "%")}</div>
                            </div>
                            <div>
                                <div class="stock-item-label">Prix vs vente</div>
                                <div class="stock-item-value">{format_numeric(row.get("distance_declenchement_vente_pct"), "%")}</div>
                            </div>
                            <div>
                                <div class="stock-item-label">Marge achat-resistance</div>
                                <div class="stock-item-value">{format_numeric(row.get("marge_achat_vers_resistance_pct"), "%")}</div>
                            </div>
                        </div>
                        """
                    ),
                    unsafe_allow_html=True,
                )


def format_numeric(value: object, suffix: str = "", decimals: int = 2) -> str:
    numeric = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(numeric):
        return "-"
    return f"{float(numeric):.{decimals}f}{suffix}"


@st.cache_data(show_spinner=False)
def cached_download_prices(ticker: str, start_date: date, end_date: date) -> pd.DataFrame:
    return download_prices(ticker, start_date, end_date)


@st.cache_data(show_spinner=False, ttl=30)
def cached_download_latest_quote(ticker: str) -> dict[str, object]:
    return download_latest_quote(ticker)


if __name__ == "__main__":
    main()
