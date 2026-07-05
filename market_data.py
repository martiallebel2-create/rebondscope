from __future__ import annotations

from datetime import date
from io import StringIO
from urllib.parse import urlencode

import pandas as pd
import requests
import yfinance as yf


def download_prices(ticker: str, start: date, end: date) -> pd.DataFrame:
    symbol = ticker.strip().upper()
    if not symbol:
        raise ValueError("Le ticker est obligatoire.")
    if start >= end:
        raise ValueError("La date de debut doit etre avant la date de fin.")

    try:
        data = yf.download(
            symbol,
            start=start.isoformat(),
            end=end.isoformat(),
            interval="1d",
            auto_adjust=False,
            progress=False,
            threads=False,
        )
    except Exception as exc:  # pragma: no cover - network/provider errors vary
        raise ValueError(f"Impossible de telecharger les donnees pour {symbol}: {exc}") from exc

    if data.empty:
        raise ValueError(f"Aucune donnee trouvee pour {symbol}. Verifie le ticker et la place de cotation.")

    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)

    data = data.reset_index()
    data = data.rename(
        columns={
            "Date": "date",
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
        }
    )

    required = ["date", "open", "high", "low", "close"]
    data = data[[col for col in [*required, "volume"] if col in data.columns]].copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    for col in [*required[1:], "volume"]:
        if col in data.columns:
            data[col] = pd.to_numeric(data[col], errors="coerce")

    data = data.dropna(subset=required).sort_values("date").reset_index(drop=True)
    if data.empty:
        raise ValueError(f"Les donnees telechargees pour {symbol} ne contiennent pas de prix valides.")

    return data


def download_latest_quote(ticker: str) -> dict[str, object]:
    symbol = ticker.strip().upper()
    if not symbol:
        raise ValueError("Le ticker est obligatoire.")

    try:
        data = yf.Ticker(symbol).history(period="1d", interval="1m", prepost=True)
    except Exception as exc:  # pragma: no cover - network/provider errors vary
        raise ValueError(f"Impossible de recuperer le prix actuel pour {symbol}: {exc}") from exc

    if data.empty:
        raise ValueError(f"Aucun prix actuel trouve pour {symbol}.")

    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)

    if "Close" not in data.columns:
        raise ValueError(f"Reponse Yahoo invalide pour {symbol}: prix actuel manquant.")

    close = pd.to_numeric(data["Close"], errors="coerce").dropna()
    if close.empty:
        raise ValueError(f"Le prix actuel recupere pour {symbol} est invalide.")

    latest_time = close.index[-1]
    return {"date": pd.to_datetime(latest_time), "price": float(close.iloc[-1])}


def download_intraday_prices(ticker: str, period: str = "60d", interval: str = "5m") -> pd.DataFrame:
    symbol = ticker.strip().upper()
    if not symbol:
        raise ValueError("Le ticker est obligatoire.")

    try:
        data = yf.Ticker(symbol).history(period=period, interval=interval, prepost=False)
    except Exception as exc:  # pragma: no cover - network/provider errors vary
        raise ValueError(f"Impossible de recuperer les donnees intraday pour {symbol}: {exc}") from exc

    if data.empty:
        raise ValueError(f"Aucune donnee intraday trouvee pour {symbol}.")

    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)

    data = data.reset_index()
    date_column = "Datetime" if "Datetime" in data.columns else data.columns[0]
    data = data.rename(
        columns={
            date_column: "date",
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
        }
    )

    required = ["date", "open", "high", "low", "close"]
    data = data[[col for col in [*required, "volume"] if col in data.columns]].copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    for col in [*required[1:], "volume"]:
        if col in data.columns:
            data[col] = pd.to_numeric(data[col], errors="coerce")

    data = data.dropna(subset=required).sort_values("date").reset_index(drop=True)
    if data.empty:
        raise ValueError(f"Les donnees intraday pour {symbol} ne contiennent pas de prix valides.")
    return data


def get_eur_usd_rate() -> float:
    try:
        intraday = yf.Ticker("EURUSD=X").history(period="1d", interval="1m")
        if not intraday.empty:
            if isinstance(intraday.columns, pd.MultiIndex):
                intraday.columns = intraday.columns.get_level_values(0)
            intraday_close = pd.to_numeric(intraday["Close"], errors="coerce").dropna()
            if not intraday_close.empty:
                return float(intraday_close.iloc[-1])
    except Exception:
        pass

    data = yf.download(
        "EURUSD=X",
        period="5d",
        interval="1d",
        auto_adjust=False,
        progress=False,
        threads=False,
    )
    if data.empty:
        raise ValueError("Impossible de recuperer le taux EUR/USD.")
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    return float(data["Close"].dropna().iloc[-1])


def infer_quote_currency(ticker: str) -> str:
    symbol = ticker.strip().upper()
    eur_suffixes = (".PA", ".DE", ".F", ".BE", ".AS", ".MI", ".MC", ".LS")
    if symbol.endswith(eur_suffixes):
        return "EUR"
    return "USD"


def download_stooq_prices(symbol: str, start: date, end: date, api_key: str = "") -> pd.DataFrame:
    code = symbol.strip().lower()
    if not code:
        raise ValueError("Le symbole Stooq est obligatoire.")
    if start >= end:
        raise ValueError("La date de debut doit etre avant la date de fin.")

    params = urlencode(
        {
            "s": code,
            "i": "d",
            "d1": start.strftime("%Y%m%d"),
            "d2": end.strftime("%Y%m%d"),
            **({"apikey": api_key.strip()} if api_key.strip() else {}),
        }
    )
    url = f"https://stooq.com/q/d/l/?{params}"

    try:
        response = requests.get(url, timeout=20)
        response.raise_for_status()
    except requests.RequestException as exc:  # pragma: no cover - network/provider errors vary
        raise ValueError(f"Impossible de telecharger les donnees Stooq pour {code}: {exc}") from exc

    text = response.text.strip()
    if "get your apikey" in text.lower():
        raise ValueError(
            "Stooq demande une cle API pour ce telechargement. "
            "Ouvre la page Stooq du symbole, recupere la cle, puis colle-la dans l'application."
        )
    if not text or text.lower() == "no data":
        raise ValueError(f"Aucune donnee Stooq trouvee pour {code}. Verifie le symbole.")

    data = pd.read_csv(StringIO(text))
    data = data.rename(columns={col: str(col).strip().lower() for col in data.columns})

    required = ["date", "open", "high", "low", "close"]
    missing = set(required) - set(data.columns)
    if missing:
        raise ValueError(f"Reponse Stooq invalide pour {code}: colonnes manquantes.")

    keep_columns = [col for col in [*required, "volume"] if col in data.columns]
    data = data[keep_columns].copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    for col in ["open", "high", "low", "close", "volume"]:
        if col in data.columns:
            data[col] = pd.to_numeric(data[col], errors="coerce")

    data = data.dropna(subset=required).sort_values("date").reset_index(drop=True)
    if data.empty:
        raise ValueError(f"Les donnees Stooq pour {code} ne contiennent pas de prix valides.")

    return data
