from __future__ import annotations

from datetime import date, timedelta
from textwrap import dedent
from uuid import uuid4

import pandas as pd
import streamlit as st

from auto_levels import AutoLevelConfig, TRACKED_SYMBOLS, build_auto_level_row
from exchange_rate_store import get_cached_eur_usd_rate, load_cached_eur_usd_rate
from market_data import download_latest_quote, download_prices


APP_NAME = "RebondScope"

st.set_page_config(page_title=APP_NAME, page_icon="chart_with_upwards_trend", layout="wide")


def main() -> None:
    inject_theme()
    register_visit()
    render_header()
    render_simple_dashboard()


def inject_theme() -> None:
    st.markdown(
        """
        <style>
        :root {
            --surface: #fffdf8;
            --surface-strong: #ffffff;
            --line: #bfae96;
            --text: #111827;
            --muted: #4b5563;
            --green: #0f6b3d;
            --blue: #0b4250;
            --amber: #8a5a12;
            --danger: #b91c1c;
        }
        .stApp {
            background:
                radial-gradient(circle at top left, rgba(180, 131, 72, 0.12), transparent 28%),
                linear-gradient(180deg, #f5ede1 0%, #eadbc6 100%);
        }
        .block-container {
            max-width: 1480px;
            padding-top: 1.4rem;
            padding-bottom: 3rem;
        }
        .hero-card {
            background:
                linear-gradient(135deg, rgba(255, 255, 255, 0.99), rgba(247, 236, 219, 0.99)),
                radial-gradient(circle at top right, rgba(180, 131, 72, 0.18), transparent 36%);
            border: 2px solid rgba(155, 127, 95, 0.55);
            border-radius: 30px;
            padding: 26px 28px;
            box-shadow: 0 20px 60px rgba(88, 65, 43, 0.14);
            margin-bottom: 1rem;
        }
        .hero-title {
            text-align: center;
            font-size: 2.4rem;
            font-weight: 800;
            color: #0f172a;
            margin: 0.15rem 0 0.2rem;
        }
        .hero-kicker {
            text-align: center;
            font-size: 0.80rem;
            letter-spacing: 0.18em;
            text-transform: uppercase;
            color: #6b4f32;
        }
        .hero-subtitle {
            text-align: center;
            color: #374151;
            margin: 0.2rem 0 0;
            font-weight: 600;
        }
        div[data-testid="stMetric"] {
            background: rgba(255, 255, 255, 0.98);
            border: 2px solid rgba(155, 127, 95, 0.42);
            box-shadow: 0 12px 30px rgba(88, 65, 43, 0.12);
        }
        div[data-testid="stMetricLabel"] {
            color: #374151;
            font-weight: 700;
        }
        div[data-testid="stMetricValue"] {
            color: #111827;
            font-weight: 800;
        }
        .stock-top {
            display: flex;
            justify-content: space-between;
            gap: 10px;
            align-items: flex-start;
            margin-bottom: 10px;
        }
        div[data-testid="stVerticalBlock"] div[data-testid="stContainer"] {
            background: rgba(255, 255, 255, 0.98);
            border: 2px solid rgba(155, 127, 95, 0.38);
            box-shadow: 0 12px 28px rgba(88, 65, 43, 0.12);
        }
        .stock-name {
            font-size: 1.08rem;
            font-weight: 800;
            color: #111827;
            line-height: 1.15;
        }
        .stock-ticker {
            margin-top: 2px;
            font-size: 0.82rem;
            color: #374151;
            font-weight: 600;
        }
        .stock-date {
            font-size: 0.78rem;
            color: #374151;
            font-weight: 700;
            white-space: nowrap;
        }
        .stock-badge {
            display: inline-flex;
            align-items: center;
            border-radius: 999px;
            padding: 0.34rem 0.70rem;
            font-size: 0.80rem;
            font-weight: 800;
            border: 1px solid rgba(17, 24, 39, 0.14);
        }
        .stock-badge.buy {
            background: #ccecf3;
            color: #083344;
        }
        .stock-badge.sell {
            background: #d7f5df;
            color: #14532d;
        }
        .stock-badge.invalid {
            background: #b91c1c;
            color: #ffffff;
            border-color: #7f1d1d;
            box-shadow: 0 3px 10px rgba(127, 29, 29, 0.28);
        }
        [class*="st-key-stock_card_invalid_"] {
            background: #fff1f2 !important;
            border: 3px solid #dc2626 !important;
            border-radius: 16px;
            box-shadow: 0 14px 30px rgba(185, 28, 28, 0.25) !important;
        }
        .stock-badge.watch {
            background: #e7dccd;
            color: #4b5563;
        }
        .stock-price {
            margin: 2px 0 10px;
        }
        .stock-price strong {
            display: block;
            font-size: 1.34rem;
            color: #111827;
            line-height: 1.05;
        }
        .stock-price span {
            font-size: 0.80rem;
            color: #374151;
            font-weight: 600;
        }
        .stock-grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 10px 12px;
        }
        .stock-item-label {
            font-size: 0.88rem;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            color: #4b5563;
            margin-bottom: 2px;
            font-weight: 700;
        }
        .stock-item-value {
            font-size: 1.14rem;
            font-weight: 800;
            color: #111827;
        }
        .simple-table-wrap {
            margin-top: 1rem;
            background: rgba(255, 255, 255, 0.98);
            border: 2px solid rgba(155, 127, 95, 0.42);
            border-radius: 24px;
            padding: 10px 12px 14px;
            box-shadow: 0 14px 34px rgba(88, 65, 43, 0.12);
        }
        .summary-danger {
            margin-top: 0.35rem;
            text-align: center;
            color: #ffffff;
            background: #b91c1c;
            border: 2px solid #7f1d1d;
            border-radius: 999px;
            padding: 0.35rem 0.65rem;
            font-size: 0.82rem;
            font-weight: 800;
        }
        div[data-testid="stInfo"] {
            background: #ffffff;
            border: 2px solid #0b4250;
            color: #111827;
        }
        div[data-testid="stExpander"] {
            background: rgba(255, 255, 255, 0.96);
            border: 2px solid rgba(155, 127, 95, 0.35);
            border-radius: 16px;
        }
        @media (max-width: 900px) {
            .hero-title {
                font-size: 2rem;
            }
            .hero-subtitle {
                font-size: 0.98rem;
            }
            .stock-name {
                font-size: 1.14rem;
            }
            .stock-item-label {
                font-size: 0.92rem;
            }
            .stock-item-value {
                font-size: 1.18rem;
            }
            .stock-price strong {
                font-size: 1.4rem;
            }
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
    stats = get_visit_stats()
    visit_cols = st.columns(3)
    visit_cols[0].metric("Visites app", f"{stats['total_visits']}")
    visit_cols[1].metric("Visiteurs uniques", f"{stats['unique_visitors']}")
    visit_cols[2].caption("Compteur simple depuis le dernier redemarrage de l'application")


def render_simple_dashboard() -> None:
    st.info(
        "Supports et resistances sont analyses automatiquement pour Tesla, Palantir, Nvidia, AMD, Amazon, AST SpaceMobile, Stellantis et SpaceX."
    )
    with st.expander("Comment lire cet ecran", expanded=False):
        st.write(
            """
            - `Support 1 / Support 2`: zones de support utiles situees sous le prix actuel.
            - `Resistance 1 / Resistance 2`: niveaux de blocage utiles situes au-dessus du prix actuel.
            - `Entree confirmation`: niveau theorique de confirmation du rebond.
            - `Statut d'analyse`: Interessant, A confirmer, Vigilant ou Pas interessant.
            """
        )

    strategy = st.expander("Reglages de strategie", expanded=False)
    with strategy:
        strategy_cols = st.columns(4)
        quantity = strategy_cols[0].number_input("Nombre d'actions", min_value=1, value=3, step=1)
        buy_fee = strategy_cols[1].number_input("Frais achat (EUR)", min_value=0.0, value=1.0, step=0.5)
        sell_fee = strategy_cols[2].number_input("Frais vente (EUR)", min_value=0.0, value=1.0, step=0.5)
        tolerance_pct = strategy_cols[3].number_input("Tolerance niveaux (%)", min_value=0.1, value=0.5, step=0.1)
        strategy_cols_2 = st.columns(4)
        ratio_min = strategy_cols_2[0].number_input("Ratio minimum", min_value=1.0, value=1.8, step=0.1)
        ratio_ideal = strategy_cols_2[1].number_input("Ratio ideal", min_value=1.0, value=2.0, step=0.1)
        min_contacts = strategy_cols_2[2].number_input("Contacts minimum", min_value=1, value=2, step=1)
        rebound_confirmation_pct = strategy_cols_2[3].number_input(
            "Rebond mini confirmation (%)", min_value=0.1, value=1.0, step=0.1
        )

    controls = st.columns([1, 1, 2])
    lookback_sessions = controls[0].selectbox(
        "Historique (seances)", [2, 5, 10, 20, 30, 90, 120, 180, 252], index=1
    )
    buy_rebound_pct = controls[1].number_input("Rebond technique (%)", min_value=0.5, value=1.5, step=0.1)
    controls[2].button("Actualiser les niveaux", type="primary", use_container_width=True)

    config = AutoLevelConfig(
        buy_rebound_pct=float(buy_rebound_pct),
        sell_buffer_pct=1.5,
        tolerance_pct=float(tolerance_pct),
        min_contacts=int(min_contacts),
        quantity=int(quantity),
        buy_fee_eur=float(buy_fee),
        sell_fee_eur=float(sell_fee),
        ratio_min_acceptable=float(ratio_min),
        ratio_ideal=float(ratio_ideal),
        min_rebound_confirmation_pct=float(rebound_confirmation_pct),
    )
    calendar_days = max(int(lookback_sessions) * 2 + 7, 14)
    start_date = date.today() - timedelta(days=calendar_days)
    end_date = date.today() + timedelta(days=1)
    rows: list[dict[str, object]] = []
    errors: list[str] = []

    eur_rate_note: str | None = None
    eur_rate_updated_at: str | None = None
    try:
        eur_usd_rate = get_cached_eur_usd_rate()
        cached_rate = load_cached_eur_usd_rate()
        if cached_rate is not None:
            eur_rate_updated_at = cached_rate[1].astimezone().strftime("%Y-%m-%d %H:%M")
    except ValueError:
        cached_rate = load_cached_eur_usd_rate()
        if cached_rate is not None:
            eur_usd_rate = float(cached_rate[0])
            eur_rate_updated_at = cached_rate[1].astimezone().strftime("%Y-%m-%d %H:%M")
            eur_rate_note = "Taux EUR/USD recupere depuis le cache local."
        else:
            eur_usd_rate = 1.0
            eur_rate_note = "Taux EUR/USD indisponible. Les actions USD sont affichees provisoirement avec un taux 1.00."

    with st.spinner("Calcul automatique des niveaux..."):
        for ticker, label in TRACKED_SYMBOLS:
            try:
                prices = cached_download_prices(ticker, start_date, end_date).tail(int(lookback_sessions)).reset_index(drop=True)
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
    rate_caption = f"Taux EUR/USD automatique: {eur_usd_rate:.4f}"
    if eur_rate_updated_at:
        rate_caption += f" (maj {eur_rate_updated_at})"
    st.caption(rate_caption)
    if eur_rate_note:
        st.caption(eur_rate_note)
    render_simple_dashboard_table(rows_df)


def render_simple_dashboard_table(rows: pd.DataFrame) -> None:
    display = rows.copy()
    status_order = {
        "Interessant": 0,
        "A confirmer": 1,
        "Vigilant": 2,
        "Pas interessant": 3,
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
            "plus_bas_veille_eur": "Plus bas veille EUR",
            "plus_haut_veille_eur": "Plus haut veille EUR",
            "support_1_eur": "Support 1 EUR",
            "support_2_eur": "Support 2 EUR",
            "resistance_1_eur": "Resistance 1 EUR",
            "resistance_2_eur": "Resistance 2 EUR",
            "entree_confirmation_eur": "Entree confirmation EUR",
            "stop_loss_eur": "Stop-loss EUR",
            "fiabilite_support_1": "Fiabilite S1",
            "fiabilite_support_2": "Fiabilite S2",
            "fiabilite_resistance_1": "Fiabilite R1",
            "fiabilite_resistance_2": "Fiabilite R2",
            "support_statut": "Statut support",
            "risque_par_action_eur": "Risque/action EUR",
            "gain_potentiel_r1_eur": "Gain potentiel R1 EUR",
            "gain_potentiel_r2_eur": "Gain potentiel R2 EUR",
            "ratio_r1": "Ratio R1",
            "ratio_r2": "Ratio R2",
            "gain_net_potentiel_r1_eur": "Gain net R1 EUR",
            "gain_net_potentiel_r2_eur": "Gain net R2 EUR",
            "perte_nette_possible_eur": "Perte nette EUR",
            "statut": "Statut",
            "explication": "Explication",
        }
    )

    def highlight_status(row: pd.Series) -> list[str]:
        if row["Statut"] == "Interessant":
            return ["background-color: #dbeafe"] * len(row)
        if row["Statut"] == "A confirmer":
            return ["background-color: #e0f2fe"] * len(row)
        if row["Statut"] == "Vigilant":
            return ["background-color: #fef3c7"] * len(row)
        if row["Statut"] == "Pas interessant":
            return ["background-color: #dc2626; color: #ffffff; font-weight: 800"] * len(row)
        return [""] * len(row)

    st.markdown('<div class="simple-table-wrap">', unsafe_allow_html=True)
    st.markdown("#### Tableau detaille")
    st.dataframe(
        table_display.style.apply(highlight_status, axis=1).format(
            {
                "Prix actuel EUR": "{:.2f}",
                "Plus bas veille EUR": "{:.2f}",
                "Plus haut veille EUR": "{:.2f}",
                "Support 1 EUR": "{:.2f}",
                "Support 2 EUR": "{:.2f}",
                "Resistance 1 EUR": "{:.2f}",
                "Resistance 2 EUR": "{:.2f}",
                "Entree confirmation EUR": "{:.2f}",
                "Stop-loss EUR": "{:.2f}",
                "Risque/action EUR": "{:.2f}",
                "Gain potentiel R1 EUR": "{:.2f}",
                "Gain potentiel R2 EUR": "{:.2f}",
                "Ratio R1": "{:.2f}",
                "Ratio R2": "{:.2f}",
                "Gain net R1 EUR": "{:.2f}",
                "Gain net R2 EUR": "{:.2f}",
                "Perte nette EUR": "{:.2f}",
            }
        ),
        use_container_width=True,
        column_order=[
            "Date",
            "Action",
            "Ticker",
            "Devise",
            "Prix actuel EUR",
            "Plus bas veille EUR",
            "Plus haut veille EUR",
            "Support 1 EUR",
            "Support 2 EUR",
            "Resistance 1 EUR",
            "Resistance 2 EUR",
            "Fiabilite S1",
            "Fiabilite S2",
            "Fiabilite R1",
            "Fiabilite R2",
            "Entree confirmation EUR",
            "Stop-loss EUR",
            "Risque/action EUR",
            "Gain potentiel R1 EUR",
            "Gain potentiel R2 EUR",
            "Ratio R1",
            "Ratio R2",
            "Gain net R1 EUR",
            "Gain net R2 EUR",
            "Perte nette EUR",
            "Statut support",
            "Statut",
            "Explication",
        ],
    )
    st.markdown("</div>", unsafe_allow_html=True)


def render_summary(display: pd.DataFrame) -> None:
    summary = display["statut"].value_counts()
    summary_cards = st.columns(4)
    summary_cards[0].metric("Actions suivies", f"{len(display)}")
    summary_cards[1].metric("Interessant", f"{int(summary.get('Interessant', 0))}")
    summary_cards[2].metric("A confirmer", f"{int(summary.get('A confirmer', 0))}")
    summary_cards[3].metric("Pas interessant", f"{int(summary.get('Pas interessant', 0))}")
    summary_cards[3].markdown('<div class="summary-danger">Rouge = a ne pas prendre</div>', unsafe_allow_html=True)


def render_simple_stock_cards(rows: pd.DataFrame) -> None:
    st.markdown("#### Vue cartes")
    st.caption("Cartes triees par ordre alphabetique. Tous les montants sont affiches en euros en priorite.")

    cards = rows.sort_values(["nom", "ticker"], ignore_index=True)
    columns = st.columns(3)

    for index, (_, row) in enumerate(cards.iterrows()):
        status = str(row.get("statut", "Attendre"))
        tone = "watch"
        if status == "Interessant":
            tone = "buy"
        elif status in {"A confirmer", "Vigilant"}:
            tone = "sell"
        elif status in {"Pas interessant", "A eviter", "A éviter"}:
            tone = "invalid"

        reference_date = pd.to_datetime(row.get("date_reference"), errors="coerce")
        display_date = reference_date.strftime("%Y-%m-%d") if not pd.isna(reference_date) else "-"

        with columns[index % 3]:
            with st.container(border=True, key=f"stock_card_{tone}_{index}"):
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
                                <div class="stock-item-label">Support 1</div>
                                <div class="stock-item-value">{format_numeric(row.get("support_1_eur"), " EUR")}</div>
                            </div>
                            <div>
                                <div class="stock-item-label">Support 2</div>
                                <div class="stock-item-value">{format_numeric(row.get("support_2_eur"), " EUR")}</div>
                            </div>
                            <div>
                                <div class="stock-item-label">Resistance 1</div>
                                <div class="stock-item-value">{format_numeric(row.get("resistance_1_eur"), " EUR")}</div>
                            </div>
                            <div>
                                <div class="stock-item-label">Resistance 2</div>
                                <div class="stock-item-value">{format_numeric(row.get("resistance_2_eur"), " EUR")}</div>
                            </div>
                            <div>
                                <div class="stock-item-label">Entree confirmation</div>
                                <div class="stock-item-value">{format_numeric(row.get("entree_confirmation_eur"), " EUR")}</div>
                            </div>
                            <div>
                                <div class="stock-item-label">Stop-loss</div>
                                <div class="stock-item-value">{format_numeric(row.get("stop_loss_eur"), " EUR")}</div>
                            </div>
                            <div>
                                <div class="stock-item-label">Ratio R1</div>
                                <div class="stock-item-value">{format_numeric(row.get("ratio_r1"))}</div>
                            </div>
                            <div>
                                <div class="stock-item-label">Ratio R2</div>
                                <div class="stock-item-value">{format_numeric(row.get("ratio_r2"))}</div>
                            </div>
                            <div>
                                <div class="stock-item-label">Support</div>
                                <div class="stock-item-value">{row.get("support_statut", "-")}</div>
                            </div>
                            <div>
                                <div class="stock-item-label">Lecture</div>
                                <div class="stock-item-value">{row.get("explication", "-")}</div>
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


@st.cache_resource
def get_visit_store() -> dict[str, object]:
    return {
        "total_visits": 0,
        "unique_visitors": set(),
    }


def register_visit() -> None:
    if "rebondscope_visitor_id" not in st.session_state:
        st.session_state["rebondscope_visitor_id"] = str(uuid4())

    if st.session_state.get("rebondscope_visit_registered"):
        return

    store = get_visit_store()
    visitor_id = str(st.session_state["rebondscope_visitor_id"])
    store["total_visits"] = int(store["total_visits"]) + 1
    unique_visitors = store["unique_visitors"]
    if isinstance(unique_visitors, set):
        unique_visitors.add(visitor_id)
    st.session_state["rebondscope_visit_registered"] = True


def get_visit_stats() -> dict[str, int]:
    store = get_visit_store()
    unique_visitors = store["unique_visitors"]
    unique_count = len(unique_visitors) if isinstance(unique_visitors, set) else 0
    return {
        "total_visits": int(store["total_visits"]),
        "unique_visitors": unique_count,
    }


@st.cache_data(show_spinner=False)
def cached_download_prices(ticker: str, start_date: date, end_date: date) -> pd.DataFrame:
    return download_prices(ticker, start_date, end_date)


@st.cache_data(show_spinner=False, ttl=30)
def cached_download_latest_quote(ticker: str) -> dict[str, object]:
    return download_latest_quote(ticker)


if __name__ == "__main__":
    main()
