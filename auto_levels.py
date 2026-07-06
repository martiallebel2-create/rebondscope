from __future__ import annotations

from dataclasses import dataclass
from math import isnan

import pandas as pd
from market_data import infer_quote_currency


TRACKED_SYMBOLS: tuple[tuple[str, str], ...] = (
    ("TSLA", "Tesla"),
    ("PLTR", "Palantir"),
    ("NVDA", "Nvidia"),
    ("AMD", "AMD"),
    ("AMZN", "Amazon"),
    ("ASTS", "AST SpaceMobile"),
    ("STLAM.MI", "Stellantis"),
    ("SPCX", "SpaceX"),
)


@dataclass(frozen=True)
class AutoLevelConfig:
    sell_buffer_pct: float = 1.5
    buy_rebound_pct: float = 1.5
    tolerance_pct: float = 0.5
    min_contacts: int = 2
    quantity: int = 3
    buy_fee_eur: float = 1.0
    sell_fee_eur: float = 1.0
    ratio_min_acceptable: float = 1.8
    ratio_ideal: float = 2.0
    min_rebound_confirmation_pct: float = 1.0


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
    tolerance_ratio = config.tolerance_pct / 100.0

    support1, support1_contacts = _find_level(validated, current_price, "low", "below", tolerance_ratio)
    support2, support2_contacts = _find_level(
        validated, support1 * (1 - tolerance_ratio) if support1 else current_price, "low", "below", tolerance_ratio
    )
    resistance1, resistance1_contacts = _find_level(validated, current_price, "high", "above", tolerance_ratio)
    resistance2, resistance2_contacts = _find_level(
        validated,
        resistance1 * (1 + tolerance_ratio) if resistance1 else current_price,
        "high",
        "above",
        tolerance_ratio,
    )

    last_session_low = float(last_session["low"])
    last_session_high = float(last_session["high"])
    support1 = support1 or last_session_low
    support2 = support2 or min(last_session_low, support1 * (1 - 0.015))
    resistance1 = resistance1 or last_session_high
    resistance2 = resistance2 or max(last_session_high, resistance1 * (1 + 0.015))

    support1_contacts = max(support1_contacts, 1 if support1 == last_session_low else 0)
    support2_contacts = max(support2_contacts, 1 if support2 == last_session_low else 0)
    resistance1_contacts = max(resistance1_contacts, 1 if resistance1 == last_session_high else 0)
    resistance2_contacts = max(resistance2_contacts, 1 if resistance2 == last_session_high else 0)

    entry_confirmation = max(current_price, support1 * (1 + config.min_rebound_confirmation_pct / 100.0))
    stop_loss = support2 * (1 - tolerance_ratio)
    risk_per_share = max(entry_confirmation - stop_loss, 0.0)
    gain_r1 = max(resistance1 - entry_confirmation, 0.0)
    gain_r2 = max(resistance2 - entry_confirmation, 0.0)
    ratio_r1 = gain_r1 / risk_per_share if risk_per_share > 0 else 0.0
    ratio_r2 = gain_r2 / risk_per_share if risk_per_share > 0 else 0.0

    gross_gain_r1 = gain_r1 * config.quantity
    gross_gain_r2 = gain_r2 * config.quantity
    gross_loss = risk_per_share * config.quantity
    total_fees = config.buy_fee_eur + config.sell_fee_eur
    net_gain_r1 = gross_gain_r1 - total_fees
    net_gain_r2 = gross_gain_r2 - total_fees
    net_loss = gross_loss + total_fees

    support_status = _infer_support_status(current_price, support1, support2, entry_confirmation)
    status, explanation = _infer_analysis_status(
        current_price=current_price,
        entry_confirmation=entry_confirmation,
        resistance1=resistance1,
        support1=support1,
        risk_per_share=risk_per_share,
        gain_r1=gain_r1,
        ratio_r1=ratio_r1,
        net_gain_r1=net_gain_r1,
        config=config,
    )

    latest_date = pd.to_datetime(last_session["date"]).date()
    conversion_rate = 1.0 if currency == "EUR" else 1 / float(eur_usd_rate)
    price_eur = current_price * conversion_rate
    support1_eur = support1 * conversion_rate
    support2_eur = support2 * conversion_rate
    entry_eur = entry_confirmation * conversion_rate
    stop_loss_eur = stop_loss * conversion_rate
    resistance1_eur = resistance1 * conversion_rate
    resistance2_eur = resistance2 * conversion_rate
    veille_low_eur = last_session_low * conversion_rate
    veille_high_eur = last_session_high * conversion_rate
    return {
        "ticker": ticker,
        "nom": label,
        "date_reference": latest_date,
        "devise": currency,
        "prix_actuel": float(current_price),
        "prix_actuel_eur": round(price_eur, 4),
        "plus_bas_veille": round(last_session_low, 4),
        "plus_bas_veille_eur": round(veille_low_eur, 4),
        "plus_haut_veille": round(last_session_high, 4),
        "plus_haut_veille_eur": round(veille_high_eur, 4),
        "support_1": round(support1, 4),
        "support_1_eur": round(support1_eur, 4),
        "support_2": round(support2, 4),
        "support_2_eur": round(support2_eur, 4),
        "resistance_1": round(resistance1, 4),
        "resistance_1_eur": round(resistance1_eur, 4),
        "resistance_2": round(resistance2, 4),
        "resistance_2_eur": round(resistance2_eur, 4),
        "entree_confirmation": round(entry_confirmation, 4),
        "entree_confirmation_eur": round(entry_eur, 4),
        "stop_loss": round(stop_loss, 4),
        "stop_loss_eur": round(stop_loss_eur, 4),
        "distance_support_1_pct": round((current_price / support1 - 1) * 100 if support1 else 0.0, 2),
        "distance_support_2_pct": round((current_price / support2 - 1) * 100 if support2 else 0.0, 2),
        "distance_resistance_1_pct": round((current_price / resistance1 - 1) * 100 if resistance1 else 0.0, 2),
        "distance_resistance_2_pct": round((current_price / resistance2 - 1) * 100 if resistance2 else 0.0, 2),
        "risque_par_action_eur": round(risk_per_share * conversion_rate, 4),
        "gain_potentiel_r1_eur": round(gain_r1 * conversion_rate, 4),
        "gain_potentiel_r2_eur": round(gain_r2 * conversion_rate, 4),
        "ratio_r1": round(ratio_r1, 2),
        "ratio_r2": round(ratio_r2, 2),
        "gain_net_potentiel_r1_eur": round(net_gain_r1 * conversion_rate, 4),
        "gain_net_potentiel_r2_eur": round(net_gain_r2 * conversion_rate, 4),
        "perte_nette_possible_eur": round(net_loss * conversion_rate, 4),
        "fiabilite_support_1": _score_to_label(_compute_reliability_score(support1_contacts, latest_weight=1.0)),
        "fiabilite_support_2": _score_to_label(_compute_reliability_score(support2_contacts, latest_weight=1.2)),
        "fiabilite_resistance_1": _score_to_label(_compute_reliability_score(resistance1_contacts, latest_weight=1.0)),
        "fiabilite_resistance_2": _score_to_label(_compute_reliability_score(resistance2_contacts, latest_weight=1.2)),
        "support_statut": support_status,
        "statut": status,
        "explication": explanation,
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


def _find_level(
    prices: pd.DataFrame,
    pivot_price: float,
    column: str,
    direction: str,
    tolerance_ratio: float,
) -> tuple[float | None, int]:
    values = pd.to_numeric(prices[column], errors="coerce").dropna().tolist()
    candidates: list[tuple[float, int]] = []
    for value in values:
        value = float(value)
        if direction == "below" and value >= pivot_price:
            continue
        if direction == "above" and value <= pivot_price:
            continue
        matched = False
        for idx, (zone_value, contacts) in enumerate(candidates):
            if abs(value - zone_value) / zone_value <= tolerance_ratio:
                new_contacts = contacts + 1
                new_zone = (zone_value * contacts + value) / new_contacts
                candidates[idx] = (new_zone, new_contacts)
                matched = True
                break
        if not matched:
            candidates.append((value, 1))

    if not candidates:
        return None, 0

    if direction == "below":
        candidates.sort(key=lambda item: item[0], reverse=True)
    else:
        candidates.sort(key=lambda item: item[0])
    return round(candidates[0][0], 4), int(candidates[0][1])


def _compute_reliability_score(contacts: int, latest_weight: float = 1.0) -> float:
    return contacts * latest_weight


def _score_to_label(score: float) -> str:
    if score >= 3:
        return "Fort"
    if score >= 2:
        return "Moyen"
    return "Faible"


def _infer_support_status(current_price: float, support1: float, support2: float, entry_confirmation: float) -> str:
    if current_price <= support1 * 1.002:
        return "Support potentiel"
    if current_price < entry_confirmation:
        return "Support en confirmation"
    if current_price > support1 and support1 >= support2:
        return "Support confirme"
    return "Support potentiel"


def _infer_analysis_status(
    *,
    current_price: float,
    entry_confirmation: float,
    resistance1: float,
    support1: float,
    risk_per_share: float,
    gain_r1: float,
    ratio_r1: float,
    net_gain_r1: float,
    config: AutoLevelConfig,
) -> tuple[str, str]:
    if risk_per_share <= 0:
        return "Pas interessant", "Stop-loss trop proche."
    if entry_confirmation >= resistance1:
        return "Pas interessant", "Entree trop proche de R1."
    if gain_r1 < risk_per_share or ratio_r1 < 1 or net_gain_r1 <= 0:
        return "Pas interessant", "Gain trop faible avant R1."
    if current_price <= support1 * 1.01 and ratio_r1 >= config.ratio_ideal:
        return "Interessant", "Marge correcte jusqu'a R1."
    if current_price <= support1 * 1.01 and ratio_r1 >= config.ratio_min_acceptable:
        return "A confirmer", "Rebond encore a confirmer."
    if 1 <= ratio_r1 < config.ratio_min_acceptable:
        return "Vigilant", "R1 reste encore proche."
    return "Vigilant", "Lecture trop fine pour un signal clair."
