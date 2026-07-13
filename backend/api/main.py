from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from typing import List, Dict, Any
import os
import csv
from pathlib import Path
import pandas as pd

from .models.enhancements import Enhancements, Filter as ModelFilter, PositionSizer, VolFilter
from .models.enhancements import MomentumFilter as MmtmFilter
from .models.enhancements import KellyCriterion as ModelKelly
from .models.enhancements import FractionalSizer as FrcSizer
from .models.engine import Portfolio as PortfolioModel

from .models.engine import HealthResponse, InstrumentListResponse, PricesResponse, BacktestRequest, BacktestResult, TransactionCosts
from .models.strategies import EquityBonds, StrategyRequest, StrategyResponse
# strategy implementations (rename imports to avoid name collisions with Pydantic models)
from ..strategies.enhancements.filters import Filter as StrategyFilter, VolatilityFilter, MomentumFilter as StrategyMomentumFilter
from ..strategies.enhancements.position_resizing import KellyCriterion as StrategyKellyCriterion, FractionalSizer as StrategyFractionalSizer
from ..strategies.cross_asset.equity_bonds import EquitiesBondsDynamic
from ..core_logic.engine.engine import BacktestEngine
from ..core_logic.portfolio.portfolio import Portfolio

app = FastAPI(title="Quant Platform API")

# data directory (processed CSVs)
DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "processed"

@app.get("/health", response_model=HealthResponse)
def health():
	return HealthResponse()


@app.get("/instruments", response_model=InstrumentListResponse)
def list_instruments():
	if not DATA_DIR.exists():
		raise HTTPException(status_code=500, detail=f"Data folder not found: {DATA_DIR}")
	files = [f.name for f in DATA_DIR.iterdir() if f.is_file() and f.suffix.lower() == ".csv"]
	symbols = [os.path.splitext(f)[0] for f in files]
	return InstrumentListResponse(instruments=symbols)


def _load_prices(symbol: str, max_rows: int = 10000) -> List[Dict[str, Any]]:
	"""Return a list of rows preserving CSV capitalization (e.g. 'Date', 'Close')."""
	path = DATA_DIR / f"{symbol}.csv"
	if not path.exists():
		raise FileNotFoundError(path)
	rows = []
	with path.open("r", newline='') as fh:
		reader = csv.DictReader(fh)
		for i, r in enumerate(reader):
			if i >= max_rows:
				break
			rows.append(r)
	return rows


def _load_prices_df(symbol: str):
	"""Return a pandas DataFrame normalized to lowercase columns used internally (open, high, low, close).
	Expects CSV headers like 'Open','High','Low','Close'."""
	import pandas as pd
	path = DATA_DIR / f"{symbol}.csv"
	if not path.exists():
		raise FileNotFoundError(path)
	df = pd.read_csv(path)
	# normalize column names to lowercase for internal use
	df.columns = [c.lower() for c in df.columns]
	# ensure required columns exist (lowercase)
	for col in ("date", "open", "high", "low", "close", "volume"):
		if col not in df.columns:
			df[col] = None
	return df


@app.get("/instruments/{symbol}/prices", response_model=PricesResponse)
def get_prices(symbol: str):
	try:
		data = _load_prices(symbol)
	except FileNotFoundError:
		raise HTTPException(status_code=404, detail="Instrument not found")
	return PricesResponse(symbol=symbol, data=data)


@app.post("/run-backtest", response_model=None)
def run_backtest(req: Dict[str, Any]):
	# parse request body into Pydantic model inside the function to avoid import-time validation issues
	from .models.enhancements import BacktestRequest as _BacktestRequest
	try:
		req = _BacktestRequest.parse_obj(req)
	except Exception as e:
		raise HTTPException(status_code=422, detail=str(e))
	# For safety and compatibility we provide a built-in simple strategy (buy-and-hold)
	# and attempt to delegate to the project's BacktestEngine if available.
	try:
		prices = _load_prices_df(req.instrument)
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
			from ..core_logic.engine.engine import BacktestEngine
			from ..core_logic.portfolio.portfolio import Portfolio
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


@app.post("/metrics", response_model=None)
def compute_metrics(body: Dict[str, Any]):
	from .models.enhancements import MetricsResponse, MetricsRequest
	try:
		req = MetricsRequest.parse_obj(body)
	except Exception as e:
		raise HTTPException(status_code=422, detail=str(e))

	# Use the project's MetricsCalculator if available, otherwise compute basic metrics here
	try:
		from ..evaluation.metrics_calculator import MetricsCalculator
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


@app.post("/montecarlo/bootstrap", response_model=None)
def montecarlo_bootstrap(body: Dict[str, Any]):
	from .models.enhancements import BootstrapRequest
	try:
		req = BootstrapRequest.parse_obj(body)
	except Exception as e:
		raise HTTPException(status_code=422, detail=str(e))

	# load data as DataFrame for evaluation classes
	try:
		df = _load_prices_df(req.instrument)
	except FileNotFoundError:
		raise HTTPException(status_code=404, detail="Instrument not found")

	# attempt to initialize BacktestEngine
	try:
		from ..evaluation.bootstrap_confidence_interval import BootstrappedConfidenceIntervals
		from ..core_logic.engine.engine import BacktestEngine
		from ..core_logic.portfolio.portfolio import Portfolio
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


@app.post("/montecarlo/noise_ohlc", response_model=StrategyResponse)
def montecarlo_noise_ohlc(body: Dict[str, Any]):
	from .models.enhancements import NoiseOHLCRequest
	try:
		req = NoiseOHLCRequest.parse_obj(body)
	except Exception as e:
		raise HTTPException(status_code=422, detail=str(e))

	try:
		df = _load_prices_df(req.instrument)
	except FileNotFoundError:
		raise HTTPException(status_code=404, detail="Instrument not found")

	try:
		from ..evaluation.noise_injection import NoiseInjectionOHLC
		from ..core_logic.engine.engine import BacktestEngine
		from ..core_logic.portfolio.portfolio import Portfolio

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

def _build_filters(filters: List[ModelFilter]):
	if not filters:
		return []
	objects = []
	for f in filters:
		if isinstance(f, VolFilter):
			obj = VolatilityFilter(lookback=f.lookback, min_volatility=f.min_vol, max_volatility=f.max_vol)
		elif isinstance(f, MmtmFilter):
			obj = MomentumFilter(lookback=f.lookback)
		else:
			obj = None
		objects.append(obj)
	return objects
				
def _build_position_sizers(position_sizers: List[PositionSizer]):
	if not position_sizers:
		return []
	objects = []
	for ps in position_sizers:
		if isinstance(ps, FrcSizer):
			obj = StrategyFractionalSizer(fraction=ps.fraction)
		elif isinstance(ps, ModelKelly):
			obj = StrategyKellyCriterion(win_rate=ps.win_rate, avg_win=ps.avg_win, avg_loss=ps.avg_loss, kelly_fraction=ps.kelly_fraction)
		else:
			obj = None
		objects.append(obj)
	return objects

def _build_portfolio(portfolio: PortfolioModel):
	return Portfolio(portfolio.initial_cash, {"fixed": portfolio.transaction_costs.fixed,
                                              "pct": portfolio.transaction_costs.pct,
                                              "slippage_pct": portfolio.transaction_costs.slippage_pct,
                                              "by_asset": portfolio.transaction_costs.by_asset
											  })
        		
@app.post("/strategy/cross_asset/equity_bonds", response_model=StrategyResponse)
def strategy_equity_bonds(strategy: EquityBonds, enhancements: Enhancements, portfolio: PortfolioModel):
	# load data
	eq_df = _load_prices_df(strategy.equity)
	bonds_df = _load_prices_df(strategy.bond)

	# build enhancements
	enhcmts = {}
	if enhancements and getattr(enhancements, "filters", None):
		enhcmts["filter"] = _build_filters(enhancements.filters)
	if enhancements and getattr(enhancements, "position_sizers", None):
		enhcmts["position_sizing"] = _build_position_sizers(enhancements.position_sizers)

	# instantiate strategy
	strat = EquitiesBondsDynamic(eq_data=eq_df, bonds_data=bonds_df, equity=strategy.equity, bond=strategy.bond, lookback=strategy.lookback, bond_momentum_window=strategy.bond_momentum_window)
	port = _build_portfolio(portfolio=portfolio)

	engine = BacktestEngine(data=strat.data, strategy=strat, portfolio=port)
	return engine.run()


@app.post("/strategy/run", response_model=StrategyResponse)
def strategy_run(req: Dict[str, Any], enhancements: Enhancements, portfolio: PortfolioModel):
	"""Generic strategy runner: provide `strategy` in body (module or class name) and `params`.
	This will attempt to import `..strategies.<strategy>` and find a class matching the provided name.
	"""
	try:
		parsed = StrategyRequest.parse_obj(req)
	except Exception as e:
		raise HTTPException(status_code=422, detail=str(e))

	# load instrument data if provided
	data_sources = {}
	if parsed.instrument:
		try:
			data_sources[parsed.instrument] = _load_prices_df(parsed.instrument)
		except FileNotFoundError:
			raise HTTPException(status_code=404, detail=f"Instrument not found: {parsed.instrument}")

	# attempt dynamic import of strategy
	import importlib
	strategy_name = parsed.strategy
	StrategyClass = None
	try:
		# try module path ..strategies.<strategy_name>
		mod = importlib.import_module(f"..strategies.{strategy_name}", package=__package__)
		StrategyClass = getattr(mod, strategy_name, None) or getattr(mod, "Strategy", None)
	except Exception:
		StrategyClass = None

	if StrategyClass is None:
		raise HTTPException(status_code=404, detail=f"Strategy class not found: {strategy_name}")

	# instantiate strategy (best-effort: pass data and params)
	try:
		strategy_obj = StrategyClass(data_sources, **(parsed.params or {}))
	except Exception:
		# try alternate constructor signature
		strategy_obj = StrategyClass(parsed.params or {})

	port = _build_portfolio(portfolio=portfolio)
	engine = BacktestEngine(data=getattr(strategy_obj, "data", data_sources), strategy=strategy_obj, portfolio=port)
	return engine.run()

	
	