from __future__ import annotations

import os
from datetime import date, timedelta
from textwrap import dedent
from uuid import uuid4

import pandas as pd
import requests
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
        .level-section {
            margin-top: 10px;
            padding: 10px 12px;
            border: 1px solid #cbd5e1;
            border-radius: 12px;
            background: #ffffff;
        }
        .level-section-title {
            margin-bottom: 7px;
            color: #0b4250;
            font-size: 0.76rem;
            font-weight: 900;
            letter-spacing: 0.08em;
        }
        .level-line {
            display: flex;
            justify-content: space-between;
            gap: 10px;
            padding: 3px 0;
            color: #374151;
            font-size: 0.84rem;
            font-weight: 700;
        }
        .level-line strong {
            color: #111827;
            white-space: nowrap;
        }
        .active-plan {
            margin-top: 10px;
            padding: 11px 12px;
            border: 2px solid #0b4250;
            border-radius: 12px;
            background: #e6f4f7;
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


@st.fragment(run_every="60s")
def render_simple_dashboard() -> None:
    st.info(
        "Supports et resistances sont analyses automatiquement pour Tesla, Palantir, Nvidia, AMD, Amazon, "
        "AST SpaceMobile, STMicroelectronics, Stellantis et SpaceX."
    )
    with st.expander("Comment lire cet ecran", expanded=False):
        st.write(
            """
            - `2 jours`: niveau du trade le plus court.
            - `5 et 9 jours`: confirmation et contexte elargi.
            - `20 jours et 1 mois`: structure moyen terme.
            - `Zone active`: support le plus proche sous le cours et premiere resistance au-dessus.
            - `Entree / stop`: calcules uniquement autour du support actif, jamais depuis un support lointain.
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
        strategy_cols_2 = st.columns(3)
        ratio_min = strategy_cols_2[0].number_input("Ratio minimum", min_value=1.0, value=1.8, step=0.1)
        ratio_ideal = strategy_cols_2[1].number_input("Ratio ideal", min_value=1.0, value=2.0, step=0.1)
        min_contacts = strategy_cols_2[2].number_input("Contacts minimum", min_value=1, value=2, step=1)

    controls = st.columns([1, 2])
    buy_rebound_pct = controls[0].number_input("Rebond technique (%)", min_value=0.1, value=0.5, step=0.1)
    controls[1].button("Actualiser les niveaux", type="primary", use_container_width=True)

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
    )
    start_date = date.today() - timedelta(days=45)
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
                prices = cached_download_prices(ticker, start_date, end_date).tail(22).reset_index(drop=True)
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
    st.caption(
        f"Derniere mise a jour: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')} · "
        "actualisation automatique toutes les 60 secondes"
    )
    rate_caption = f"Taux EUR/USD automatique: {eur_usd_rate:.4f}"
    if eur_rate_updated_at:
        rate_caption += f" (maj {eur_rate_updated_at})"
    st.caption(rate_caption)
    if eur_rate_note:
        st.caption(eur_rate_note)
    render_simple_dashboard_table(rows_df)
    render_telegram_alerts(rows_df)


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

    table_display = pd.DataFrame(
        {
            "Date": display["date_reference"],
            "Action": display["nom"],
            "Cours EUR": display["prix_actuel_eur"],
            "Support actif": display.apply(lambda row: format_zone(row, "support_actif"), axis=1),
            "Resistance active": display.apply(lambda row: format_zone(row, "resistance_active"), axis=1),
            "Support 2j": display.apply(lambda row: format_zone(row, "support_2j"), axis=1),
            "Resistance 2j": display.apply(lambda row: format_zone(row, "resistance_2j"), axis=1),
            "Support 5j": display.apply(lambda row: format_zone(row, "support_5j"), axis=1),
            "Resistance 5j": display.apply(lambda row: format_zone(row, "resistance_5j"), axis=1),
            "Entree EUR": display["entree_confirmation_eur"],
            "Stop EUR": display["stop_loss_eur"],
            "Ratio": display["ratio_r1"],
            "Statut": display["statut"],
            "Lecture": display["explication"],
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
                "Cours EUR": "{:.2f}",
                "Entree EUR": "{:.2f}",
                "Stop EUR": "{:.2f}",
                "Ratio": "{:.2f}",
            }
        ),
        use_container_width=True,
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
    st.caption("Zones calculees sur 2, 5, 9, 20 et 22 seances. Montants affiches en euros.")

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
                        <div class="level-section">
                            <div class="level-section-title">NIVEAUX COURT TERME</div>
                            <div class="level-line"><span>Support 2 jours</span><strong>{format_zone(row, "support_2j")}</strong></div>
                            <div class="level-line"><span>Resistance 2 jours</span><strong>{format_zone(row, "resistance_2j")}</strong></div>
                        </div>
                        <div class="level-section">
                            <div class="level-section-title">NIVEAUX DE CONFIRMATION</div>
                            <div class="level-line"><span>Support 5 jours</span><strong>{format_zone(row, "support_5j")}</strong></div>
                            <div class="level-line"><span>Resistance 5 jours</span><strong>{format_zone(row, "resistance_5j")}</strong></div>
                            <div class="level-line"><span>Support 9 jours</span><strong>{format_zone(row, "support_9j")}</strong></div>
                            <div class="level-line"><span>Resistance 9 jours</span><strong>{format_zone(row, "resistance_9j")}</strong></div>
                        </div>
                        <div class="level-section">
                            <div class="level-section-title">NIVEAUX STRUCTURELS</div>
                            <div class="level-line"><span>Support 20 jours</span><strong>{format_zone(row, "support_20j")}</strong></div>
                            <div class="level-line"><span>Resistance 20 jours</span><strong>{format_zone(row, "resistance_20j")}</strong></div>
                            <div class="level-line"><span>Support 1 mois</span><strong>{format_zone(row, "support_1m")}</strong></div>
                            <div class="level-line"><span>Resistance 1 mois</span><strong>{format_zone(row, "resistance_1m")}</strong></div>
                        </div>
                        <div class="active-plan">
                            <div class="level-section-title">SCENARIO ACTIF</div>
                            <div class="level-line"><span>Support actif ({row.get("support_actif_source", "-")})</span><strong>{format_zone(row, "support_actif")}</strong></div>
                            <div class="level-line"><span>Resistance active ({row.get("resistance_active_source", "-")})</span><strong>{format_zone(row, "resistance_active")}</strong></div>
                            <div class="level-line"><span>Entree confirmation</span><strong>{format_numeric(row.get("entree_confirmation_eur"), " EUR")}</strong></div>
                            <div class="level-line"><span>Stop court</span><strong>{format_numeric(row.get("stop_loss_eur"), " EUR")}</strong></div>
                            <div class="level-line"><span>Ratio rendement / risque</span><strong>{format_numeric(row.get("ratio_r1"))}</strong></div>
                        </div>
                        <div class="level-section"><strong>Lecture :</strong> {row.get("explication", "-")}<br><span>{row.get("contexte_support", "-")}</span></div>
                        """
                    ),
                    unsafe_allow_html=True,
                )


def format_zone(row: pd.Series, prefix: str) -> str:
    low = pd.to_numeric(pd.Series([row.get(f"{prefix}_bas_eur")]), errors="coerce").iloc[0]
    high = pd.to_numeric(pd.Series([row.get(f"{prefix}_haut_eur")]), errors="coerce").iloc[0]
    if pd.isna(low) or pd.isna(high):
        return "-"
    return f"{float(low):.2f} - {float(high):.2f} EUR"


def format_numeric(value: object, suffix: str = "", decimals: int = 2) -> str:
    numeric = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(numeric):
        return "-"
    return f"{float(numeric):.{decimals}f}{suffix}"


def render_telegram_alerts(rows: pd.DataFrame) -> None:
    st.markdown("#### Alertes Telegram")
    with st.expander("Programmer mes alertes Telegram", expanded=True):
        token = get_telegram_bot_token()
        st.caption(
            "1. Colle ton chat_id numerique Telegram. 2. Choisis les actions. "
            "3. Clique sur Envoyer un test Telegram."
        )

        chat_id = st.text_input(
            "Mon chat_id Telegram",
            value=str(st.session_state.get("telegram_chat_id", "")),
            placeholder="Exemple: 123456789",
            help="Mets uniquement le numero donne par @userinfobot. Pas de @, pas de pseudo.",
            key="telegram_chat_id_input",
        ).strip()
        st.session_state["telegram_chat_id"] = chat_id

        if not token:
            st.warning(
                "Le bot Telegram RebondScope n'est pas encore configure. "
                "Le champ chat_id reste utilisable, mais l'envoi sera bloque tant que "
                "TELEGRAM_BOT_TOKEN n'est pas reconnu dans les secrets Streamlit."
            )

        st.caption(
            "Chaque utilisateur peut mettre son propre chat_id. "
            "Les alertes fonctionnent tant que la page RebondScope reste ouverte ou se rafraichit."
        )

        sorted_rows = rows.sort_values(["nom", "ticker"], ignore_index=True)
        options = [f"{row['nom']} ({row['ticker']})" for _, row in sorted_rows.iterrows()]
        default_options = options[:]
        selected_labels = st.multiselect("Actions a surveiller", options, default=default_options)
        selected_tickers = {
            str(label).rsplit("(", 1)[-1].replace(")", "").strip()
            for label in selected_labels
            if "(" in str(label)
        }

        alert_types = st.multiselect(
            "Types d'alertes",
            [
                "Scenario interessant",
                "Prix proche de l'entree",
                "Resistance active proche",
            ],
            default=["Scenario interessant", "Prix proche de l'entree"],
        )
        proximity_pct = st.number_input(
            "Marge de proximite (%)",
            min_value=0.1,
            value=0.5,
            step=0.1,
            help="Exemple: 0,5% veut dire que RebondScope previent un peu avant le niveau exact.",
        )

        button_cols = st.columns(2)
        if button_cols[0].button("Envoyer un test Telegram", use_container_width=True):
            if not chat_id:
                st.error("Ajoute d'abord ton chat_id Telegram.")
            elif not token:
                st.error("Le token du bot Telegram n'est pas encore reconnu par l'application.")
            else:
                try:
                    send_telegram_message(token, chat_id, "RebondScope - test Telegram OK.")
                    st.success("Message test envoye.")
                except ValueError as exc:
                    st.error(str(exc))

        if button_cols[1].button("Reinitialiser les alertes deja envoyees", use_container_width=True):
            st.session_state["telegram_sent_alerts"] = set()
            st.success("Les alertes de cette session ont ete reinitialisees.")

        if not chat_id or not selected_tickers or not alert_types or not token:
            st.info("Renseigne ton chat_id, choisis au moins une action et un type d'alerte.")
            return

        triggered = build_telegram_alert_candidates(
            sorted_rows[sorted_rows["ticker"].isin(selected_tickers)],
            set(alert_types),
            float(proximity_pct),
        )
        if not triggered:
            st.caption("Aucune alerte Telegram a envoyer pour l'instant.")
            return

        sent_alerts = st.session_state.setdefault("telegram_sent_alerts", set())
        new_alerts = [alert for alert in triggered if alert["key"] not in sent_alerts]
        st.write(f"Alertes detectees maintenant: {len(triggered)}")

        for alert in triggered:
            st.caption(alert["message"].replace("\n", " · "))

        if not new_alerts:
            st.caption("Ces alertes ont deja ete envoyees pendant cette session.")
            return

        for alert in new_alerts:
            try:
                send_telegram_message(token, chat_id, alert["message"])
                sent_alerts.add(alert["key"])
            except ValueError as exc:
                st.error(str(exc))
                return
        st.success(f"{len(new_alerts)} alerte(s) Telegram envoyee(s).")


def get_telegram_bot_token() -> str:
    try:
        token = st.secrets.get("TELEGRAM_BOT_TOKEN", "")
    except (FileNotFoundError, KeyError):
        token = ""
    return str(token or os.environ.get("TELEGRAM_BOT_TOKEN", "")).strip()


def build_telegram_alert_candidates(
    rows: pd.DataFrame,
    alert_types: set[str],
    proximity_pct: float,
) -> list[dict[str, str]]:
    alerts: list[dict[str, str]] = []
    margin = max(proximity_pct, 0.0) / 100

    for _, row in rows.iterrows():
        ticker = str(row.get("ticker", "")).strip()
        name = str(row.get("nom", ticker)).strip()
        current = safe_float(row.get("prix_actuel_eur"))
        entry = safe_float(row.get("entree_confirmation_eur"))
        resistance_low = safe_float(row.get("resistance_active_bas_eur"))
        status = str(row.get("statut", "")).strip()

        if "Scenario interessant" in alert_types and status == "Interessant":
            alerts.append(
                {
                    "key": f"{ticker}:status:{status}:{format_numeric(current)}",
                    "message": (
                        f"RebondScope - {name} ({ticker})\n"
                        f"Scenario interessant detecte.\n"
                        f"Cours: {format_numeric(current, ' EUR')}\n"
                        f"Entree: {format_numeric(entry, ' EUR')}\n"
                        f"Resistance active: {format_zone(row, 'resistance_active')}\n"
                        f"Lecture: {row.get('explication', '-')}"
                    ),
                }
            )

        if (
            "Prix proche de l'entree" in alert_types
            and current is not None
            and entry is not None
            and current <= entry * (1 + margin)
        ):
            alerts.append(
                {
                    "key": f"{ticker}:entry:{format_numeric(entry)}:{format_numeric(current)}",
                    "message": (
                        f"RebondScope - {name} ({ticker})\n"
                        f"Prix proche de l'entree.\n"
                        f"Cours: {format_numeric(current, ' EUR')}\n"
                        f"Entree: {format_numeric(entry, ' EUR')}\n"
                        f"Stop: {format_numeric(row.get('stop_loss_eur'), ' EUR')}"
                    ),
                }
            )

        if (
            "Resistance active proche" in alert_types
            and current is not None
            and resistance_low is not None
            and current >= resistance_low * (1 - margin)
        ):
            alerts.append(
                {
                    "key": f"{ticker}:resistance:{format_numeric(resistance_low)}:{format_numeric(current)}",
                    "message": (
                        f"RebondScope - {name} ({ticker})\n"
                        f"Resistance active proche.\n"
                        f"Cours: {format_numeric(current, ' EUR')}\n"
                        f"Resistance: {format_zone(row, 'resistance_active')}"
                    ),
                }
            )

    return alerts


def safe_float(value: object) -> float | None:
    numeric = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(numeric):
        return None
    return float(numeric)


def send_telegram_message(bot_token: str, chat_id: str, message: str) -> None:
    token = bot_token.strip()
    destination = chat_id.strip()
    if not token:
        raise ValueError("Le token Telegram est obligatoire.")
    if not destination:
        raise ValueError("Le chat_id Telegram est obligatoire.")
    if not message.strip():
        raise ValueError("Le message Telegram est vide.")

    try:
        response = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": destination, "text": message},
            timeout=15,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise ValueError(f"Impossible d'envoyer la notification Telegram: {exc}") from exc

    payload = response.json()
    if not payload.get("ok"):
        description = payload.get("description", "erreur inconnue")
        raise ValueError(f"Telegram a refuse le message: {description}")


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
