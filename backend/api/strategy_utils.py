from typing import Any, Dict, List, Optional
from pathlib import Path

import pandas as pd
import csv

from .models.enhancements import FilterUnion
from .models.enhancements import MomentumFilter as MmtmFilter
from .models.enhancements import KellyCriterion as ModelKelly
from .models.enhancements import FractionalSizer as FrcSizer
from .models.enhancements import PositionSizerBase, VolFilter, EnhancementsModel
from .models.engine import PortfolioModel

from strategies.enhancements.filters import VolatilityFilter, MomentumFilter
from strategies.enhancements.position_resizing import KellyCriterion, FractionalSizer
from core_logic.portfolio.portfolio import Portfolio

def load_prices(data_dir: Path, symbol: str, max_rows: int = 10000) -> List[Dict[str, Any]]:
	path = data_dir / f"{symbol}.csv"
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

def load_prices_df(data_dir: Path, symbol: str):
    path = data_dir / f"{symbol}.csv"
    if not path.exists():
        raise FileNotFoundError(path)
    df = pd.read_csv(path)

    # Normalize to a consistent, predictable casing: Title case for known OHLCV/date columns.
    canonical = {"date": "Date", "open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"}
    df.columns = [canonical.get(c.lower(), c) for c in df.columns]

    for col in canonical.values():
        if col not in df.columns:
            df[col] = None

    return df

def build_filters(filters: Optional[List[FilterUnion]]):
    built = []
    for f in filters or []:
        if f.type == "vol_filter":
            built.append(VolatilityFilter(min_vol=f.min_vol, max_vol=f.max_vol, lookback=f.lookback))
        elif f.type == "momentum_filter":
            built.append(MomentumFilter(lookback=f.lookback))
        # ... etc, one branch per type
    return built

def build_position_sizers(position_sizers: List[PositionSizerBase]):
	if not position_sizers:
		return []
	objects = []
	for ps in position_sizers:
		if isinstance(ps, FrcSizer):
			obj = FractionalSizer(fraction=ps.fraction)
		elif isinstance(ps, ModelKelly):
			obj = KellyCriterion(win_rate=ps.win_rate, avg_win=ps.avg_win, avg_loss=ps.avg_loss, kelly_fraction=ps.kelly_fraction)
		else:
			obj = None
		objects.append(obj)
	return objects

def build_enhancements(enhancements: EnhancementsModel):
	enhcmts = {}
	if enhancements and getattr(enhancements, "filters", None):
		enhcmts["filter"] = build_filters(enhancements.filters)
	if enhancements and getattr(enhancements, "position_sizers", None):
		enhcmts["position_sizing"] = build_position_sizers(enhancements.position_sizers)
	return enhcmts

def build_portfolio(portfolio: PortfolioModel):
	return Portfolio(
		portfolio.initial_cash,
		{
			"fixed": portfolio.transaction_costs.fixed,
			"pct": portfolio.transaction_costs.pct,
			"slippage_pct": portfolio.transaction_costs.slippage_pct,
			"by_asset": portfolio.transaction_costs.by_asset,
		},
	)