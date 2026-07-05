from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
from market_data import infer_quote_currency


TRACKED_SYMBOLS: tuple[tuple[str, str], ...] = (
    ("TSLA", "Tesla"),
    ("PLTR", "Palantir"),
    ("NVDA", "Nvidia"),
    ("AMD", "AMD"),
    ("AMZN", "Amazon"),
    ("META", "Meta"),
    ("STLAM.MI", "Stellantis"),
    ("FDJU.PA", "FDJ"),
)


@dataclass(frozen=True)
class AutoLevelConfig:
    sell_buffer_pct: float = 1.5
    buy_rebound_pct: float = 1.5


def build_auto_level_row(
    ticker: str,
    label: str,
    prices: pd.DataFrame,
    current_price: float,
    config: AutoLevelConfig,
    eur_usd_rate: float,
) -> dict[str, object]:
    validated = _prepare_prices(prices)
    last_session = validated.iloc[-1]
    currency = infer_quote_currency(ticker)
    support = float(last_session["low"])
    resistance = float(last_session["high"])
    buy_trigger = support * (1 + config.buy_rebound_pct / 100.0)
    sell_trigger = resistance
    distance_to_support = (current_price / support - 1) * 100 if support else 0.0
    distance_to_buy_trigger = (current_price / buy_trigger - 1) * 100 if buy_trigger else 0.0
    distance_to_resistance = (current_price / resistance - 1) * 100 if resistance else 0.0
    distance_to_sell_trigger = (current_price / sell_trigger - 1) * 100 if sell_trigger else 0.0

    if buy_trigger >= resistance:
        status = "Setup invalide"
    elif current_price <= support:
        status = "Support atteint"
    elif current_price < buy_trigger:
        status = "Attente rebond"
    elif current_price >= resistance:
        status = "Resistance atteinte"
    elif current_price >= sell_trigger:
        status = "Vente possible"
    elif current_price >= buy_trigger:
        status = "Achat possible"
    else:
        status = "Attendre"

    latest_date = pd.to_datetime(last_session["date"]).date()
    conversion_rate = 1.0 if currency == "EUR" else 1 / float(eur_usd_rate)
    price_eur = current_price * conversion_rate
    support_eur = support * conversion_rate
    buy_trigger_eur = buy_trigger * conversion_rate
    resistance_eur = resistance * conversion_rate
    sell_trigger_eur = sell_trigger * conversion_rate
    upside_from_buy_pct = (resistance / buy_trigger - 1) * 100 if buy_trigger else 0.0
    return {
        "ticker": ticker,
        "nom": label,
        "date_reference": latest_date,
        "devise": currency,
        "prix_actuel": float(current_price),
        "prix_actuel_eur": round(price_eur, 4),
        "support": round(support, 4),
        "support_eur": round(support_eur, 4),
        "declenchement_achat": round(buy_trigger, 4),
        "declenchement_achat_eur": round(buy_trigger_eur, 4),
        "resistance": round(resistance, 4),
        "resistance_eur": round(resistance_eur, 4),
        "declenchement_vente": round(sell_trigger, 4),
        "declenchement_vente_eur": round(sell_trigger_eur, 4),
        "distance_support_pct": round(distance_to_support, 2),
        "distance_declenchement_achat_pct": round(distance_to_buy_trigger, 2),
        "distance_resistance_pct": round(distance_to_resistance, 2),
        "distance_declenchement_vente_pct": round(distance_to_sell_trigger, 2),
        "marge_achat_vers_resistance_pct": round(upside_from_buy_pct, 2),
        "statut": status,
        "plus_bas_seance_reference": round(support, 4),
        "plus_haut_seance_reference": round(resistance, 4),
    }


def _prepare_prices(prices: pd.DataFrame) -> pd.DataFrame:
    required = {"date", "high", "low", "close"}
    missing = required - set(prices.columns)
    if missing:
        raise ValueError(f"Colonnes manquantes: {', '.join(sorted(missing))}.")

    data = prices.copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    for column in ["high", "low", "close"]:
        data[column] = pd.to_numeric(data[column], errors="coerce")
    data = data.dropna(subset=["date", "high", "low", "close"]).sort_values("date").reset_index(drop=True)
    if data.empty:
        raise ValueError("Historique insuffisant pour calculer les seuils automatiques.")
    return data
