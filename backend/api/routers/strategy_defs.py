# strategy_defs.py
from api.routers.strategy_registry import register_strategy
from api.models.strategies import EquityBondsModel, DeltaHedgingModel, CointegrationModel
from strategies.cross_asset.equity_bonds import EquitiesBondsDynamic
from strategies.derivatives.delta_hedging import DeltaHedging
from strategies.mean_reversion.cointegration_based import CointegrationBased

@register_strategy("cross_asset/equity_bonds", EquityBondsModel, asset_fields=["equity", "bond"])
def _build_equity_bonds(params: EquityBondsModel, price_data, enhancements):
    return EquitiesBondsDynamic(
        data=None, enhancements=enhancements,
        eq_data=price_data[params.equity], bonds_data=price_data[params.bond],
        equity=params.equity, bond=params.bond,
        lookback=params.lookback, bond_momentum_window=params.bond_momentum_window,
    )

@register_strategy("derivatives/delta_hedging", DeltaHedgingModel, asset_fields=["equity"])
def _build_delta_hedging(params: DeltaHedgingModel, price_data, enhancements):
    return DeltaHedging(
        data=price_data[params.equity], enhancements=enhancements,
        asset=params.equity, strike=params.strike, days_to_expiry=params.days_to_expiry,
        r=params.r, assumed_vol=params.assumed_vol, cash_balance=params.cash_balance,
    )

@register_strategy("mean_rev/cointegration", CointegrationModel, asset_fields=["asset1", "asset2"])
def _build_cointegration(params: CointegrationModel, price_data, enhancements):
    return CointegrationBased(
        data1=price_data[params.asset1], data2=price_data[params.asset2],
        asset1=params.asset1, asset2=params.asset2,
        window=params.window, threshold=params.threshold, beta=params.beta,
    )