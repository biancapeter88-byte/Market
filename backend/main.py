"""
AI Market Leadership Dashboard - backend (Twelve Data REST API).
Ruleaza local: uvicorn main:app --reload --port 8000
Deschide in browser: http://localhost:8000
"""
import datetime
import os
import traceback

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

import data
import scoring

app = FastAPI(title="Market Leadership Dashboard")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)

MOVE_WINDOW = 5  # bare (zile) folosite pentru momentum in scoruri

FX_MAJORS = ["EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "NZDUSD", "USDCAD"]
JPY_CROSSES = ["USDJPY", "EURJPY", "GBPJPY", "AUDJPY", "CADJPY", "CHFJPY", "NZDJPY"]
CORE_DAILY = [
    "GOLD", "SILVER", "OIL", "COPPER", "US30", "NAS100", "US10Y_PROXY",
] + list(set(FX_MAJORS + JPY_CROSSES))


def build_dashboard():
    daily = data.get_all_daily(CORE_DAILY, count=180)

    moves = {name: scoring.pct_change_n(df["Close"], MOVE_WINDOW) for name, df in daily.items()}

    fx_moves = {p: moves[p] for p in FX_MAJORS}
    jpy_moves = {p: moves[p] for p in JPY_CROSSES}
    usd_move = scoring.usd_basket_move(fx_moves)

    s_gold_usd, n_gold_usd = scoring.gold_vs_usd_basket(moves["GOLD"], usd_move)
    s_gold_silver, n_gold_silver = scoring.gold_vs_silver(moves["GOLD"], moves["SILVER"])
    s_gold_yields, n_gold_yields = scoring.gold_vs_yields(moves["GOLD"], moves["US10Y_PROXY"])
    s_us30_nas, n_us30_nas = scoring.us30_vs_nas100(moves["US30"], moves["NAS100"])
    s_usd, n_usd = scoring.usd_strength(fx_moves)
    s_jpy, n_jpy = scoring.jpy_strength(jpy_moves)
    s_commodity, n_commodity = scoring.commodity_strength(moves["GOLD"], moves["SILVER"], moves["OIL"])

    # Volatilitate realizata pe US30 (proxy pt VIX, care nu exista ca CFD la brokerii forex)
    us30_adx_series, us30_atr_series = scoring.adx_atr(daily["US30"])
    us30_atr_pct = (us30_atr_series / daily["US30"]["Close"]) * 100
    vol_trend = float(us30_atr_pct.iloc[-1] - us30_atr_pct.iloc[-6:-1].mean())

    s_risk, n_risk = scoring.risk_sentiment(moves["US30"], moves["NAS100"], s_jpy, vol_trend)

    regime = scoring.market_regime(
        {"GOLD": daily["GOLD"], "US30": daily["US30"], "NAS100": daily["NAS100"]}
    )

    component_scores = {
        "gold_vs_usd": s_gold_usd,
        "gold_vs_silver": s_gold_silver,
        "gold_vs_yields": s_gold_yields,
        "us30_vs_nas100": s_us30_nas,
        "risk_sentiment": s_risk,
        "usd_strength": s_usd,
        "jpy_strength": s_jpy,
        "commodity_strength": s_commodity,
    }
    conf = scoring.confluence(component_scores, regime["confidence_multiplier"])

    # Day type predictor - pentru XAUUSD si US30
    weekday = datetime.datetime.utcnow().weekday()
    day_types = {}
    for name in ["GOLD", "US30"]:
        try:
            intraday = data.get_intraday(name, count=500, granularity="M15")
            daily_adx, _ = scoring.adx_atr(daily[name])
            dt_score, dt_notes = scoring.day_type_score(
                intraday, daily[name], float(daily_adx.iloc[-1]), weekday
            )
        except Exception:
            dt_score, dt_notes = 50.0, ["Date insuficiente pentru predictie precisa."]
        day_types[name] = {"trend_day_probability": dt_score, "notes": dt_notes}

    # Bonus: divergente suplimentare
    s_copper_gold, n_copper_gold = scoring.confirmation_score(moves["GOLD"], moves["COPPER"], "direct")
    s_cad_oil, n_cad_oil = scoring.confirmation_score(-moves["USDCAD"], moves["OIL"], "direct")
    s_eur_gbp, n_eur_gbp = scoring.confirmation_score(moves["EURUSD"], moves["GBPUSD"], "direct")

    return {
        "generated_at_utc": datetime.datetime.utcnow().isoformat(),
        "note": "Date de la Twelve Data (forex + ETF-uri proxy pentru US30/Nasdaq/commodity). Folosește pentru bias/context; confirmă entry-ul pe MT5/TradingView.",
        "components": {
            "gold_vs_usd": {"score": s_gold_usd, "note": n_gold_usd},
            "gold_vs_silver": {"score": s_gold_silver, "note": n_gold_silver},
            "gold_vs_yields": {"score": s_gold_yields, "note": n_gold_yields},
            "us30_vs_nas100": {"score": s_us30_nas, "note": n_us30_nas},
            "risk_sentiment": {"score": s_risk, "note": n_risk},
            "usd_strength": {"score": s_usd, "note": n_usd},
            "jpy_strength": {"score": s_jpy, "note": n_jpy},
            "commodity_strength": {"score": s_commodity, "note": n_commodity},
        },
        "bonus_divergences": {
            "copper_vs_gold": {"score": s_copper_gold, "note": n_copper_gold},
            "cad_vs_oil": {"score": s_cad_oil, "note": n_cad_oil},
            "eur_vs_gbp_correlation": {"score": s_eur_gbp, "note": n_eur_gbp},
        },
        "regime": regime,
        "day_type": day_types,
        "confluence": conf,
        "raw_moves_pct_5d": {k: round(v, 2) for k, v in moves.items()},
    }


@app.get("/api/dashboard")
def get_dashboard():
    try:
        return JSONResponse(build_dashboard())
    except Exception as e:
        return JSONResponse(
            {"error": str(e), "trace": traceback.format_exc()}, status_code=500
        )


# Serveste frontend-ul static (index.html + assets) - cale absoluta, robusta indiferent de cwd
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend")
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
