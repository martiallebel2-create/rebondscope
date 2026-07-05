from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

from market_data import get_eur_usd_rate


EXCHANGE_RATE_PATH = Path(__file__).with_name("exchange_rate_cache.json")
DEFAULT_TTL_SECONDS = 10 * 60


def get_cached_eur_usd_rate(
    fetcher: Callable[[], float] = get_eur_usd_rate,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> float:
    cached = load_cached_eur_usd_rate()
    if cached is not None:
        rate, updated_at = cached
        if datetime.now(timezone.utc) - updated_at <= timedelta(seconds=int(ttl_seconds)):
            return rate

    try:
        rate = float(fetcher())
    except Exception:
        if cached is not None:
            return cached[0]
        raise
    else:
        save_cached_eur_usd_rate(rate)
        return rate


def load_cached_eur_usd_rate() -> tuple[float, datetime] | None:
    if not EXCHANGE_RATE_PATH.exists():
        return None
    try:
        payload = json.loads(EXCHANGE_RATE_PATH.read_text(encoding="utf-8"))
        rate = float(payload["eur_usd"])
        updated_at = datetime.fromisoformat(str(payload["updated_at"]))
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    return rate, updated_at.astimezone(timezone.utc)


def save_cached_eur_usd_rate(rate: float) -> None:
    payload = {
        "eur_usd": float(rate),
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    EXCHANGE_RATE_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
