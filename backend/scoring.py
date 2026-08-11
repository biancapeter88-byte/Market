"""
Calculul celor 10 componente ale AI Market Leadership Dashboard.
Fiecare functie de scor returneaza (scor -100..100, nota explicativa).
Scorul e semnat: pozitiv = bias bullish (pt scorurile legate de gold/risk),
negativ = bearish. Magnitudinea reflecta increderea/forta semnalului.
"""
import pandas as pd
import numpy as np


# ---------------------------------------------------------------------------
# Helpers generice
# ---------------------------------------------------------------------------

def clip100(x: float) -> float:
    return float(max(-100.0, min(100.0, x)))


def pct_change_n(series: pd.Series, n: int) -> float:
    if len(series) <= n:
        return 0.0
    return float((series.iloc[-1] / series.iloc[-1 - n] - 1) * 100)


def direction(x: float, eps: float = 0.02) -> int:
    if x > eps:
        return 1
    if x < -eps:
        return -1
    return 0


def adx_atr(df: pd.DataFrame, period: int = 14):
    """Wilder ADX + ATR (aproximat via EWM, comportament foarte apropiat de smoothing-ul original)."""
    high, low, close = df["High"], df["Low"], df["Close"]
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = up_move.where((up_move > down_move) & (up_move > 0), 0.0)
    minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0.0)
    tr = pd.concat(
        [high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1
    ).max(axis=1)
    atr = tr.ewm(alpha=1 / period, adjust=False).mean()
    plus_di = 100 * (plus_dm.ewm(alpha=1 / period, adjust=False).mean() / atr.replace(0, np.nan))
    minus_di = 100 * (minus_dm.ewm(alpha=1 / period, adjust=False).mean() / atr.replace(0, np.nan))
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx_series = dx.ewm(alpha=1 / period, adjust=False).mean()
    return adx_series.fillna(0), atr.fillna(0)


# ---------------------------------------------------------------------------
# 1. Confirmare vs divergenta intre doua active (folosit pentru DXY/Silver/Yields)
# ---------------------------------------------------------------------------

def confirmation_score(primary_move: float, secondary_move: float, relationship: str):
    """
    relationship: 'inverse' (normal invers) sau 'direct' (normal impreuna).
    Divergenta de la relatia normala = semnal SLAB (mai putina incredere),
    nu contrariul - o miscare gold neconfirmata de DXY/silver/yields e suspecta.
    """
    dp, ds = direction(primary_move), direction(secondary_move)
    if dp == 0:
        return 0.0, "Miscare primara neglijabila, fara semnal clar."

    expected_ds = -dp if relationship == "inverse" else dp
    combined = abs(primary_move) + abs(secondary_move)
    raw = combined * 8

    if ds == 0:
        raw *= 0.6
        note = "Relatie neconcludenta (activul secundar aproape neschimbat)."
    elif ds == expected_ds:
        raw *= 1.15
        note = "Confirmare: relatia normala se respecta - miscare de incredere."
    else:
        raw *= 0.35
        note = "Divergenta de la relatia normala - miscare mai putin de incredere / posibil overextended."

    return round(dp * min(raw, 100), 1), note


# ---------------------------------------------------------------------------
# 2. Componente individuale
# ---------------------------------------------------------------------------

def usd_basket_move(fx_moves: dict) -> float:
    """Media (neponderata) a contributiilor USD din perechile majore - folosita ca proxy
    pentru DXY, calculata direct din perechile forex (fără nevoie de ticker DXY separat)."""
    usd_quote = ["EURUSD", "GBPUSD", "AUDUSD", "NZDUSD"]
    usd_base = ["USDJPY", "USDCHF", "USDCAD"]
    contributions = [-fx_moves[p] for p in usd_quote if p in fx_moves]
    contributions += [fx_moves[p] for p in usd_base if p in fx_moves]
    return sum(contributions) / len(contributions) if contributions else 0.0


def gold_vs_usd_basket(gold_move: float, usd_move: float):
    return confirmation_score(gold_move, usd_move, "inverse")


def gold_vs_silver(gold_move: float, silver_move: float):
    return confirmation_score(gold_move, silver_move, "direct")


def gold_vs_yields(gold_move: float, bond_price_move: float):
    """bond_price_move = % change al prețului ETF-ului de obligațiuni TLT.
    Pretul bond-ului e INVERS fata de yield, deci relatia normala fata de gold e DIRECTA
    (yields sus -> bond price jos -> gold jos; yields jos -> bond price sus -> gold sus)."""
    return confirmation_score(gold_move, bond_price_move, "direct")


def us30_vs_nas100(us30_move: float, nas100_move: float):
    diff = us30_move - nas100_move
    score = clip100(diff * 15)
    if abs(diff) < 0.15:
        note = "Fara leadership clar - indicii se misca sincron."
    elif diff > 0:
        note = "US30 conduce (value/ciclice peste growth) - posibila rotatie defensiva."
    else:
        note = "NAS100 conduce (growth/tech peste value) - risk appetite orientat spre tech."
    return round(score, 1), note


def usd_strength(fx_moves: dict):
    """fx_moves: % change pt EURUSD, GBPUSD, USDJPY, USDCHF, AUDUSD, NZDUSD, USDCAD."""
    avg = usd_basket_move(fx_moves)
    if avg == 0.0:
        return 0.0, "Date insuficiente."
    score = clip100(avg * 12)
    return round(score, 1), "Medie egal-ponderata pe perechile majore USD (proxy DXY)."


def jpy_strength(jpy_moves: dict):
    """jpy_moves: % change pt USDJPY, EURJPY, GBPJPY, AUDJPY, CADJPY, CHFJPY, NZDJPY (JPY e quote in toate)."""
    contributions = [-v for v in jpy_moves.values()]
    if not contributions:
        return 0.0, "Date insuficiente."
    avg = sum(contributions) / len(contributions)
    score = clip100(avg * 12)
    return round(score, 1), f"Medie egal-ponderata pe {len(contributions)} cross-uri JPY."


def commodity_strength(gold_move: float, silver_move: float, oil_move: float):
    dirs = [direction(x) for x in (gold_move, silver_move, oil_move)]
    nonzero = [d for d in dirs if d != 0]
    avg_move = (gold_move + silver_move + oil_move) / 3
    if not nonzero:
        return 0.0, "Fara miscare semnificativa in complexul de marfuri."
    majority = max(set(nonzero), key=nonzero.count)
    agreement = nonzero.count(majority) / len(dirs)
    raw = avg_move * 8 * (0.5 + agreement)
    score = clip100(raw)
    label = "miscare unitara a complexului (macro/dolar-driven)" if agreement >= 0.66 else "miscare izolata - nu tot complexul confirma"
    return round(score, 1), f"Agreement intern {agreement * 100:.0f}% - {label}."


def risk_sentiment(us30_move: float, nas100_move: float, jpy_strength_val: float, vol_trend: float):
    """vol_trend: ATR% curent al US30 minus media ATR% din ultimele 5 zile.
    Pozitiv = volatilitate in crestere -> tilt risk-off (nu avem VIX ca CFD la niciun
    broker forex, deci folosim volatilitatea realizata a indicelui ca proxy)."""
    equity_component = (us30_move + nas100_move) / 2
    jpy_component = -jpy_strength_val / 2
    vol_component = -vol_trend * 8
    raw = equity_component * 10 + jpy_component + vol_component
    score = clip100(raw / 1.8)
    if score > 20:
        note = "Risk-ON: echities in avans, JPY slab, volatilitate in scadere."
    elif score < -20:
        note = "Risk-OFF: fuga spre siguranta - echities sub presiune, JPY/volatilitate in crestere."
    else:
        note = "Sentiment mixt, fara directie clara de risc."
    return round(score, 1), note


def market_regime(daily_dfs: dict, period: int = 14):
    """daily_dfs: {'GOLD': df, 'US30': df, 'NAS100': df} - OHLC zilnic."""
    adx_vals, atr_pct_ranks = [], []
    for df in daily_dfs.values():
        adx_series, atr_series = adx_atr(df, period)
        adx_vals.append(float(adx_series.iloc[-1]))
        atr_pct_series = (atr_series / df["Close"]) * 100
        current = float(atr_pct_series.iloc[-1])
        window = atr_pct_series.iloc[-60:]
        pct_rank = float((window < current).mean() * 100)
        atr_pct_ranks.append(pct_rank)

    avg_adx = sum(adx_vals) / len(adx_vals)
    avg_atr_rank = sum(atr_pct_ranks) / len(atr_pct_ranks)

    if avg_atr_rank > 85:
        regime, multiplier = "High Volatility", 0.7
    elif avg_atr_rank < 25 and avg_adx < 20:
        regime, multiplier = "Low Volatility", 0.9
    elif avg_adx >= 22:
        regime, multiplier = "Trending", 1.0
    else:
        regime, multiplier = "Mean-Reverting", 0.85

    return {
        "regime": regime,
        "confidence_multiplier": multiplier,
        "avg_adx": round(avg_adx, 1),
        "avg_atr_percentile": round(avg_atr_rank, 1),
    }


def day_type_score(intraday_df: pd.DataFrame, daily_df: pd.DataFrame, adx_daily_value: float, weekday: int):
    """
    weekday: 0=Luni ... 4=Vineri (ignoram weekend).
    Returneaza scor 0-100 = probabilitate relativa de trend day (nu range day).
    """
    notes = []
    score = 50.0

    try:
        idx = intraday_df.index
        if idx.tz is not None:
            idx = idx.tz_convert("UTC")
        last_day = idx[-1].date()
        asia_mask = (idx.date == last_day) & (idx.hour < 7)
        asia_slice = intraday_df.loc[asia_mask.values] if hasattr(asia_mask, "values") else intraday_df[asia_mask]
        adr20 = (daily_df["High"] - daily_df["Low"]).iloc[-20:].mean()
        if len(asia_slice) >= 2 and adr20 > 0:
            asia_range = float(asia_slice["High"].max() - asia_slice["Low"].min())
            pct_of_adr = asia_range / adr20 * 100
            if pct_of_adr < 25:
                score += 20
                notes.append(f"Asia range ingust ({pct_of_adr:.0f}% din ADR20) -> spatiu de expansiune")
            elif pct_of_adr > 55:
                score -= 20
                notes.append(f"Asia range larg ({pct_of_adr:.0f}% din ADR20) -> range deja consumat")
            else:
                notes.append(f"Asia range moderat ({pct_of_adr:.0f}% din ADR20)")
        else:
            notes.append("Date Asia insuficiente pentru acest instrument.")
    except Exception:
        notes.append("Nu s-a putut calcula range-ul Asia (date intraday incomplete).")

    if adx_daily_value >= 22:
        score += 15
        notes.append(f"ADX zilnic {adx_daily_value:.0f} -> trend HTF activ")
    elif adx_daily_value < 15:
        score -= 15
        notes.append(f"ADX zilnic {adx_daily_value:.0f} -> fara trend HTF, risc de chop")

    weekday_adj = {0: -8, 1: 6, 2: 8, 3: 6, 4: -10}
    adj = weekday_adj.get(weekday, 0)
    score += adj
    if adj > 0:
        notes.append("Ziua saptamanii favorizeaza trend day (Marti-Joi)")
    elif adj < 0:
        notes.append("Ziua saptamanii favorizeaza range/manipulare (Luni/Vineri)")

    return round(max(0.0, min(100.0, score)), 1), notes


# ---------------------------------------------------------------------------
# 3. Agregare finala
# ---------------------------------------------------------------------------

WEIGHTS = {
    "gold_vs_usd": 0.15,
    "gold_vs_silver": 0.10,
    "gold_vs_yields": 0.10,
    "us30_vs_nas100": 0.10,
    "risk_sentiment": 0.15,
    "usd_strength": 0.15,
    "jpy_strength": 0.10,
    "commodity_strength": 0.10,
}


def confluence(scores: dict, regime_multiplier: float, entry_threshold: float = 80, watch_threshold: float = 60):
    wsum = sum(WEIGHTS.values())
    raw = sum(scores[k] * WEIGHTS[k] for k in WEIGHTS) / wsum
    confluence_val = round(min(abs(raw), 100) * regime_multiplier, 1)
    bias = "LONG GOLD-BIAS" if raw > 1 else "SHORT GOLD-BIAS" if raw < -1 else "NEUTRU"

    if confluence_val >= entry_threshold:
        action = "CAUTA SETUP pe 15M/5M"
    elif confluence_val >= watch_threshold:
        action = "WATCHLIST - pune alerte, nu deschide chart activ"
    else:
        action = "IGNORA - zgomot, treci la alt instrument"

    return {
        "confluence_score": confluence_val,
        "raw_directional": round(raw, 1),
        "bias": bias,
        "action": action,
    }
