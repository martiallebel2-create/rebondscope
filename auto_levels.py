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
    ("ASTS", "AST SpaceMobile"),
    ("STMPA.PA", "STMicroelectronics"),
    ("STLAM.MI", "Stellantis"),
    ("SPCX", "SpaceX"),
)

LEVEL_WINDOWS: tuple[tuple[str, str, int], ...] = (
    ("2j", "2 jours", 2),
    ("5j", "5 jours", 5),
    ("9j", "9 jours", 9),
    ("20j", "20 jours", 20),
    ("1m", "1 mois", 22),
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


@dataclass(frozen=True)
class PriceZone:
    low: float
    high: float
    center: float
    contacts: int


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

    supports: dict[str, PriceZone | None] = {}
    resistances: dict[str, PriceZone | None] = {}
    for key, _, sessions in LEVEL_WINDOWS:
        sample = validated.tail(sessions)
        supports[key] = _select_nearest_zone(sample["low"], current_price, "support", tolerance_ratio)
        resistances[key] = _select_nearest_zone(sample["high"], current_price, "resistance", tolerance_ratio)

    active_support_key, active_support = _select_active_support(supports, current_price)
    active_resistance_key, active_resistance = _select_active_resistance(resistances, current_price)

    if active_support is None:
        active_support = _single_value_zone(float(last_session["low"]), tolerance_ratio)
        active_support_key = "veille"
    if active_resistance is None:
        active_resistance = _single_value_zone(float(last_session["high"]), tolerance_ratio)
        active_resistance_key = "veille"

    rebound_ratio = config.buy_rebound_pct / 100.0
    entry_confirmation = active_support.high * (1 + rebound_ratio)
    stop_loss = active_support.low * (1 - tolerance_ratio)
    target_resistance = active_resistance.low
    risk_per_share = max(entry_confirmation - stop_loss, 0.0)
    gain_r1 = max(target_resistance - entry_confirmation, 0.0)
    ratio_r1 = gain_r1 / risk_per_share if risk_per_share > 0 else 0.0
    security_stop = (
        entry_confirmation + (target_resistance - entry_confirmation) / 2
        if target_resistance > entry_confirmation
        else None
    )

    total_fees = config.buy_fee_eur + config.sell_fee_eur
    gross_gain = gain_r1 * config.quantity
    gross_loss = risk_per_share * config.quantity
    net_gain = gross_gain - total_fees
    net_loss = gross_loss + total_fees

    support_2d = supports.get("2j")
    support_5d = supports.get("5j")
    support_5d_confirms = _zones_confirm(
        support_2d,
        support_5d,
        tolerance_ratio,
        config.min_contacts,
    )
    status, explanation = _infer_hierarchical_status(
        current_price=current_price,
        entry_confirmation=entry_confirmation,
        active_resistance=active_resistance,
        support_2d=support_2d,
        support_5d=support_5d,
        support_5d_confirms=support_5d_confirms,
        ratio=ratio_r1,
        net_gain=net_gain,
        config=config,
    )
    context = _build_support_context(current_price, support_2d, support_5d, tolerance_ratio)

    conversion_rate = 1.0 if currency == "EUR" else 1 / float(eur_usd_rate)
    latest_date = pd.to_datetime(last_session["date"]).date()
    row: dict[str, object] = {
        "ticker": ticker,
        "nom": label,
        "date_reference": latest_date,
        "devise": currency,
        "prix_actuel": round(float(current_price), 4),
        "prix_actuel_eur": round(float(current_price) * conversion_rate, 4),
        "plus_bas_veille": round(float(last_session["low"]), 4),
        "plus_bas_veille_eur": round(float(last_session["low"]) * conversion_rate, 4),
        "plus_haut_veille": round(float(last_session["high"]), 4),
        "plus_haut_veille_eur": round(float(last_session["high"]) * conversion_rate, 4),
        "support_actif_source": active_support_key,
        "resistance_active_source": active_resistance_key,
        "support_actif_bas_eur": round(active_support.low * conversion_rate, 4),
        "support_actif_haut_eur": round(active_support.high * conversion_rate, 4),
        "resistance_active_bas_eur": round(active_resistance.low * conversion_rate, 4),
        "resistance_active_haut_eur": round(active_resistance.high * conversion_rate, 4),
        "entree_confirmation": round(entry_confirmation, 4),
        "entree_confirmation_eur": round(entry_confirmation * conversion_rate, 4),
        "stop_loss": round(stop_loss, 4),
        "stop_loss_eur": round(stop_loss * conversion_rate, 4),
        "stop_securisation": round(security_stop, 4) if security_stop is not None else None,
        "stop_securisation_eur": round(security_stop * conversion_rate, 4) if security_stop is not None else None,
        "risque_par_action_eur": round(risk_per_share * conversion_rate, 4),
        "gain_potentiel_r1_eur": round(gain_r1 * conversion_rate, 4),
        "ratio_r1": round(ratio_r1, 2),
        "gain_net_potentiel_r1_eur": round(net_gain * conversion_rate, 4),
        "perte_nette_possible_eur": round(net_loss * conversion_rate, 4),
        "confirmation_5j": "Oui" if support_5d_confirms else "Non",
        "statut": status,
        "explication": explanation,
        "contexte_support": context,
    }

    for key, _, _ in LEVEL_WINDOWS:
        _append_zone_fields(row, f"support_{key}", supports[key], conversion_rate)
        _append_zone_fields(row, f"resistance_{key}", resistances[key], conversion_rate)

    # Compatibility fields for older table consumers.
    row.update(
        {
            "support_1": round(active_support.center, 4),
            "support_1_eur": round(active_support.center * conversion_rate, 4),
            "resistance_1": round(active_resistance.center, 4),
            "resistance_1_eur": round(active_resistance.center * conversion_rate, 4),
            "support_statut": f"Actif {active_support_key}",
            "fiabilite_support_1": _score_to_label(active_support.contacts),
            "fiabilite_resistance_1": _score_to_label(active_resistance.contacts),
        }
    )
    return row


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


def _single_value_zone(value: float, tolerance_ratio: float) -> PriceZone:
    half_width = value * tolerance_ratio / 2
    return PriceZone(value - half_width, value + half_width, value, 1)


def _cluster_zones(values: pd.Series, tolerance_ratio: float) -> list[PriceZone]:
    clean = sorted(float(value) for value in pd.to_numeric(values, errors="coerce").dropna())
    clusters: list[list[float]] = []
    for value in clean:
        if clusters and abs(value - sum(clusters[-1]) / len(clusters[-1])) / value <= tolerance_ratio:
            clusters[-1].append(value)
        else:
            clusters.append([value])

    zones: list[PriceZone] = []
    for cluster in clusters:
        center = sum(cluster) / len(cluster)
        observed_half_width = (max(cluster) - min(cluster)) / 2
        half_width = observed_half_width if observed_half_width > 0 else center * tolerance_ratio / 2
        zones.append(PriceZone(center - half_width, center + half_width, center, len(cluster)))
    return zones


def _select_nearest_zone(
    values: pd.Series,
    current_price: float,
    kind: str,
    tolerance_ratio: float,
) -> PriceZone | None:
    zones = _cluster_zones(values, tolerance_ratio)
    if kind == "support":
        candidates = [zone for zone in zones if zone.low <= current_price]
        return (
            min(candidates, key=lambda zone: (-zone.contacts, max(current_price - zone.high, 0.0)))
            if candidates
            else None
        )
    candidates = [zone for zone in zones if zone.low > current_price]
    return min(candidates, key=lambda zone: (-zone.contacts, zone.low - current_price)) if candidates else None


def _select_active_support(
    zones: dict[str, PriceZone | None], current_price: float
) -> tuple[str | None, PriceZone | None]:
    candidates = [(key, zone) for key, zone in zones.items() if zone is not None and zone.low <= current_price]
    if not candidates:
        return None, None
    return min(candidates, key=lambda item: max(current_price - item[1].high, 0.0))


def _select_active_resistance(
    zones: dict[str, PriceZone | None], current_price: float
) -> tuple[str | None, PriceZone | None]:
    candidates = [(key, zone) for key, zone in zones.items() if zone is not None and zone.low > current_price]
    if not candidates:
        return None, None
    return min(candidates, key=lambda item: item[1].low - current_price)


def _zones_confirm(
    short_zone: PriceZone | None,
    confirmation_zone: PriceZone | None,
    tolerance_ratio: float,
    min_contacts: int,
) -> bool:
    if short_zone is None or confirmation_zone is None:
        return False
    close_enough = abs(short_zone.center - confirmation_zone.center) / short_zone.center <= tolerance_ratio
    overlap = short_zone.low <= confirmation_zone.high and confirmation_zone.low <= short_zone.high
    return (close_enough or overlap) and confirmation_zone.contacts >= min_contacts


def _infer_hierarchical_status(
    *,
    current_price: float,
    entry_confirmation: float,
    active_resistance: PriceZone,
    support_2d: PriceZone | None,
    support_5d: PriceZone | None,
    support_5d_confirms: bool,
    ratio: float,
    net_gain: float,
    config: AutoLevelConfig,
) -> tuple[str, str]:
    tolerance_ratio = config.tolerance_pct / 100.0
    if support_2d is not None and current_price < support_2d.low * (1 - tolerance_ratio):
        if support_5d is not None:
            return "Pas interessant", "Support 2 jours casse; prochain support 5 jours plus bas."
        return "Pas interessant", "Support 2 jours casse sans support proche en dessous."
    if entry_confirmation >= active_resistance.low:
        return "Pas interessant", "Resistance active trop proche de l'entree."
    if current_price > entry_confirmation * (1 + tolerance_ratio):
        return "Pas interessant", "Entree depassee, attendre un repli."
    if ratio < 1 or net_gain <= 0:
        return "Pas interessant", "Gain trop faible avant la premiere resistance."
    if ratio >= config.ratio_min_acceptable and support_5d_confirms:
        return "Interessant", "Support court terme confirme; ratio suffisant avant resistance."
    if ratio >= config.ratio_min_acceptable:
        return "A confirmer", "Ratio suffisant, mais le support 5 jours ne confirme pas encore."
    return "Vigilant", "Resistance court terme trop proche pour le risque pris."


def _build_support_context(
    current_price: float,
    support_2d: PriceZone | None,
    support_5d: PriceZone | None,
    tolerance_ratio: float,
) -> str:
    if support_2d is None:
        return "Aucun support 2 jours exploitable."
    if support_5d is None:
        return "Si le support 2 jours casse, aucun support 5 jours proche n'est detecte."
    if current_price < support_2d.low * (1 - tolerance_ratio):
        return "Le support 2 jours est casse; le support 5 jours devient le prochain repere."
    return "Si le support 2 jours casse, le support 5 jours devient le prochain repere."


def _append_zone_fields(
    row: dict[str, object], prefix: str, zone: PriceZone | None, conversion_rate: float
) -> None:
    if zone is None:
        row[f"{prefix}_bas_eur"] = None
        row[f"{prefix}_haut_eur"] = None
        row[f"{prefix}_contacts"] = 0
        return
    row[f"{prefix}_bas_eur"] = round(zone.low * conversion_rate, 4)
    row[f"{prefix}_haut_eur"] = round(zone.high * conversion_rate, 4)
    row[f"{prefix}_contacts"] = zone.contacts


def _score_to_label(contacts: int) -> str:
    if contacts >= 3:
        return "Fort"
    if contacts >= 2:
        return "Moyen"
    return "Faible"
