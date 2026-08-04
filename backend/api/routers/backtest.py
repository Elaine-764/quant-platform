from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from typing import List, Dict, Any
import os
import csv
from pathlib import Path
import pandas as pd

from api.models.engine import HealthResponse, InstrumentListResponse, PricesResponse, BacktestRequest, BacktestResult, TransactionCosts
from api.models.strategies import EquityBondsModel, StrategyRequest, StrategyResponse
# strategy implementations (rename imports to avoid name collisions with Pydantic models)
from strategies.enhancements.filters import Filter as StrategyFilter, VolatilityFilter, MomentumFilter as StrategyMomentumFilter
from strategies.enhancements.position_resizing import KellyCriterion as StrategyKellyCriterion, FractionalSizer as StrategyFractionalSizer
from strategies.cross_asset.equity_bonds import EquitiesBondsDynamic
from core_logic.engine.engine import BacktestEngine
from core_logic.portfolio.portfolio import Portfolio
from api.strategy_utils import load_prices_df, build_filters, build_position_sizers, build_portfolio, DATA_DIR
from api.models.eval import NoiseOHLCRequest, BootstrapRequest, NoiseResponse, BootstrapResponse

router = APIRouter() 

@router.post("/run-backtest", response_model=None)
def run_backtest(req: Dict[str, Any]):
	# parse request body into Pydantic model inside the function to avoid import-time validation issues
	from api.models.enhancements import BacktestRequest as _BacktestRequest
	try:
		req = _BacktestRequest.parse_obj(req)
	except Exception as e:
		raise HTTPException(status_code=422, detail=str(e))
	# For safety and compatibility we provide a built-in simple strategy (buy-and-hold)
	# and attempt to delegate to the project's BacktestEngine if available.
	try:
		prices = load_prices_df(req.instrument)
	except FileNotFoundError:
		raise HTTPException(status_code=404, detail="Instrument not found")
	# convert to list of close prices using capitalized CSV 'Close' mapping if present
	# prices is a DataFrame here; ensure 'close' column present
	closes = [float(v) for v in prices["close"].tolist() if v is not None]
	if not closes:
		raise HTTPException(status_code=400, detail="No price data available for instrument")

	# If user requested the special 'engine' strategy, try to run BacktestEngine
	if req.strategy.lower() == "engine":
		try:
			from core_logic.engine.engine import BacktestEngine
			from core_logic.portfolio.portfolio import Portfolio
		except Exception as e:
			# fallback to builtin
			engine_err = str(e)
			engine_err = engine_err or "unable to import engine"
		else:
			# prepare data dict expected by engine
			data = {"price": closes}
			try:
				# attempt to locate strategy class by name under backend/strategies
				import importlib
				strategy_name = req.params.get("strategy_class") or req.strategy
				# attempt several candidate modules
				candidates = [strategy_name, f"{strategy_name}"]
				StrategyClass = None
				try:
					mod = importlib.import_module(f"..strategies.{strategy_name}", package=__package__)
					StrategyClass = getattr(mod, strategy_name, None) or getattr(mod, "Strategy", None)
				except Exception:
					StrategyClass = None

				if StrategyClass is None:
					# cannot find strategy class; fallback to simple buy-and-hold
					raise ImportError("strategy class not found in codebase")

				strategy = StrategyClass(data, enhancements={})
				portfolio = Portfolio(initial_cash=req.start_cash)
				engine = BacktestEngine(data, strategy, portfolio)
				history = engine.run()
				return BacktestResult(history=history)
			except Exception:
				# fall through to builtin implementation
				pass

	# Built-in simple buy-and-hold backtest
	cash = req.start_cash
	price0 = closes[0]
	qty = int(cash // price0)
	cash -= qty * price0
	history = []
	for t, p in enumerate(closes):
		total = cash + qty * p
		history.append({"timestamp": t, "price": p, "portfolio_value": total, "position": {req.instrument: qty}})

	# compute simple metrics
	total_return = (history[-1]["portfolio_value"] - req.start_cash) / req.start_cash
	metrics = {"total_return": total_return}
	return BacktestResult(history=history, metrics=metrics)


@router.post("/backtest/metrics", response_model=None, tags=["backtest"])
def compute_metrics(body: Dict[str, Any]):
    from api.models.engine import MetricsResponse, MetricsRequest
    try:
        req = MetricsRequest.model_validate(body)
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))

    # Use the project's MetricsCalculator 
    from evaluation.metrics_calculator import MetricsCalculator
    mc = MetricsCalculator(req.history)
    out = mc.all()
    
    # Use jsonable_encoder to safely format NaN/inf values into nulls
    return JSONResponse(content=jsonable_encoder(out))


# ------------------------------------------------------------------
# Shared helper — mirrors run_strategy but returns (engine, strat, df)
# instead of running immediately, so MC can wrap the engine
# ------------------------------------------------------------------
def _build_engine_from_strategy_request(strategy_request):
	"""
	Resolves registry → parses params → loads prices → builds strategy + engine.
	Extracted so both the normal strategy endpoint and MC endpoints share it.
	"""
	from api.routers.strategy_registry import REGISTRY
	from api.strategy_utils import load_prices_df, DATA_DIR, build_enhancements, build_portfolio
	from pydantic import ValidationError
	from core_logic.engine.engine import BacktestEngine

	spec = REGISTRY.get(strategy_request.strategy_name)
	if spec is None:
		raise HTTPException(404, f"Unknown strategy '{strategy_request.strategy_name}'.")

	try:
		parsed = spec.model(**strategy_request.params)
	except ValidationError as e:
		raise HTTPException(422, e.errors())

	tickers = {getattr(parsed, f) for f in spec.asset_fields}
	for f in spec.multi_asset_fields:
		tickers.update(getattr(parsed, f))
	price_data = {t: load_prices_df(DATA_DIR, t) for t in tickers}

	enhcmts = build_enhancements(enhancements=strategy_request.enhancements)
	strat   = spec.factory(parsed, price_data, enhcmts)
	port    = build_portfolio(portfolio=strategy_request.portfolio)
	engine  = BacktestEngine(data=strat.data, strategy=strat, portfolio=port)

	return engine, strat


# ------------------------------------------------------------------
# POST /backtest/montecarlo/noise_ohlc
# ------------------------------------------------------------------
@router.post("/backtest/montecarlo/noise_ohlc", response_model=NoiseResponse, tags=["backtest"])
def montecarlo_noise_ohlc(body: Dict[str, Any]):
    from evaluation.noise_injection import NoiseInjectionOHLC

    try:
        req = NoiseOHLCRequest.parse_obj(body)
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))

    try:
        engine, strat = _build_engine_from_strategy_request(req.strategy)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Strategy build error: {e}")

    try:
        mc  = NoiseInjectionOHLC(
            data            = strat.data,
            backtest_engine = engine,
            epsilon         = req.epsilon,
            confidence      = req.confidence,
            k               = req.k,
            noise_factor    = req.noise_factor,
            vol_window      = req.vol_window,
            metric          = req.metric,
        )
        res = mc.run()
        return JSONResponse(content=res)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Monte Carlo (OHLC noise) error: {e}")


# ------------------------------------------------------------------
# POST /backtest/montecarlo/bootstrap
# ------------------------------------------------------------------
@router.post("/backtest/montecarlo/bootstrap", response_model=BootstrapResponse, tags=["backtest"])
def montecarlo_bootstrap(body: Dict[str, Any]):
    from evaluation.bootstrap_confidence_interval import BootstrappedConfidenceIntervals

    try:
        req = BootstrapRequest.parse_obj(body)
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))

    try:
        engine, strat = _build_engine_from_strategy_request(req.strategy)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Strategy build error: {e}")

    try:
        mc  = BootstrappedConfidenceIntervals(
            data             = strat.data,
            backtest_engine  = engine,
            epsilon          = req.epsilon,
            confidence       = req.confidence,
            k                = req.k,
            n_bootstrap      = req.n_bootstrap,
            metric           = req.metric,
            null_value       = req.null_value,
            min_threshold    = req.min_threshold,
            avg_block_length = req.avg_block_length,
        )
        res = mc.run()
        return JSONResponse(content=res)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Monte Carlo (bootstrap) error: {e}")