from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
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
from api.strategy_utils import load_prices_df, build_filters, build_position_sizers, build_portfolio

router = APIRouter() 

@router.post("/run-backtest", response_model=None)
def run_backtest(req: Dict[str, Any]):
	# parse request body into Pydantic model inside the function to avoid import-time validation issues
	from ..models.enhancements import BacktestRequest as _BacktestRequest
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
	from ..models.enhancements import MetricsResponse, MetricsRequest
	try:
		req = MetricsRequest.parse_obj(body)
	except Exception as e:
		raise HTTPException(status_code=422, detail=str(e))

	# Use the project's MetricsCalculator if available, otherwise compute basic metrics here
	try:
		from evaluation.metrics_calculator import MetricsCalculator
		mc = MetricsCalculator(req.history)
		out = mc.all()
		return JSONResponse(content=out)
	except Exception:
		# fallback simple calculations using pandas
		import pandas as pd
		df = pd.DataFrame(req.history).set_index("timestamp").sort_index()
		pv = df["portfolio_value"]
		total_return = (pv.iloc[-1] - pv.iloc[0]) / pv.iloc[0]
		returns = pv.pct_change().dropna()
		sharpe = None if returns.std() == 0 else float((returns.mean() / returns.std()) * (252 ** 0.5))
		rolling_max = pv.cummax()
		drawdown = (pv - rolling_max) / rolling_max
		max_dd = float(drawdown.min())
		volatility = float(returns.std() * (252 ** 0.5))
		out = {
			"final_portfolio_value": float(pv.iloc[-1]),
			"total_return": float(total_return),
			"sharpe": sharpe,
			"max_drawdown": max_dd,
			"volatility": volatility,
		}
		return JSONResponse(content=out)


@router.post("/backtest/montecarlo/noise_ohlc", response_model=StrategyResponse, tags=["backtest"])
def montecarlo_noise_ohlc(body: Dict[str, Any]):
	from ..models.enhancements import NoiseOHLCRequest
	try:
		req = NoiseOHLCRequest.parse_obj(body)
	except Exception as e:
		raise HTTPException(status_code=422, detail=str(e))

	try:
		df = load_prices_df(req.instrument)
	except FileNotFoundError:
		raise HTTPException(status_code=404, detail="Instrument not found")

	try:
		from evaluation.noise_injection import NoiseInjectionOHLC
		from core_logic.engine.engine import BacktestEngine
		from core_logic.portfolio.portfolio import Portfolio

		dummy_portfolio = Portfolio(initial_cash=req.start_cash)
		engine = BacktestEngine(df, None, dummy_portfolio)
		mc = NoiseInjectionOHLC(df, engine,
								epsilon=req.epsilon,
								confidence=req.confidence,
								k=req.k,
								noise_factor=req.noise_factor,
								vol_window=req.vol_window,
								metric=req.metric)
		res = mc.run()
		return JSONResponse(content=res)
	except Exception as e:
		raise HTTPException(status_code=500, detail=f"Monte Carlo error: {e}")

@router.post("/montecarlo/bootstrap", response_model=None, tags=["backtest"])
def montecarlo_bootstrap(body: Dict[str, Any]):
	from ..models.enhancements import BootstrapRequest
	try:
		req = BootstrapRequest.parse_obj(body)
	except Exception as e:
		raise HTTPException(status_code=422, detail=str(e))

	# load data as DataFrame for evaluation classes
	try:
		df = load_prices_df(req.instrument)
	except FileNotFoundError:
		raise HTTPException(status_code=404, detail="Instrument not found")

	# attempt to initialize BacktestEngine
	try:
		from evaluation.bootstrap_confidence_interval import BootstrappedConfidenceIntervals
		from core_logic.engine.engine import BacktestEngine
		from core_logic.portfolio.portfolio import Portfolio
		# try to create a backtest engine; keep it simple by passing DataFrame and a minimal portfolio
		dummy_portfolio = Portfolio(initial_cash=req.start_cash)
		# BacktestEngine may accept different signatures; attempt to instantiate
		engine = BacktestEngine(df, None, dummy_portfolio)
		mc = BootstrappedConfidenceIntervals(df, engine,
											epsilon=req.epsilon,
											confidence=req.confidence,
											k=req.k,
											n_bootstrap=req.n_bootstrap,
											metric=req.metric,
											null_value=req.null_value,
											min_threshold=req.min_threshold,
											avg_block_length=req.avg_block_length)
		res = mc.run()
		return JSONResponse(content=res)
	except Exception as e:
		raise HTTPException(status_code=500, detail=f"Monte Carlo error: {e}")
