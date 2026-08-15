from core_logic.events.base_event import Event
from core_logic.events.market_event import MarketEvent
from core_logic.events.order_event import OrderEvent
from strategies.enhancements.filters import Filter
from strategies.enhancements.position_resizing import PositionSizer
from core_logic.portfolio.portfolio import Portfolio
from strategies.enhancements.signal_types import SignalType
from strategies.base_strategy import Strategy
import pandas as pd
import copy

class BacktestEngine:
    def __init__(self, data, strategy: Strategy, portfolio: Portfolio):
        self.data = data # TODO: might need to process this before instantiation
        self.strategy = strategy # contains enhancements
        self.portfolio = portfolio
        self.history = []  # store results over time
    def reset_for_new_run(self, new_data=None):
        """
        Prepare this engine for an independent Monte Carlo trial:
          - optionally swap in new (e.g. noise-injected) price data
          - reset the strategy's data reference so compute_factors() uses it
          - give the portfolio a fresh cash/position state, so trials don't
            leak state into one another
          - clear recorded history from the previous run
        """
        if new_data is not None:
            self.data = new_data
            self.strategy.data = new_data

        # Fresh portfolio each trial: same starting cash/costs, zero prior trades.
        self.portfolio = Portfolio(
            initial_cash=self.portfolio.starting_cash,
            transaction_costs=self.portfolio.transaction_costs,
        )
        self.history = []

    def run(self):
        self.strategy.compute_factors()
        for t in range(len(self.data)):
            cols = self.data.columns
            prices = {}
            for col in cols:
                if "Close" in col:
                    prices[col.rstrip("_Close")] = self.data[col][t]

            event = MarketEvent(timestamp=t, prices=prices)
            signals = self.strategy.get_signals(event)

            for signal in signals:
                self.portfolio.update(signal, prices)
            self.strategy.update_portfolio_state(self.portfolio.positions)

            self.record(t, prices)

        return self.get_results()
    
    def record(self, t, prices): # constructing the equity curve
        raw_date = self.data['Date'].iloc[t]
        date_value = pd.to_datetime(raw_date).to_pydatetime()
        self.history.append({
            "timestamp": t,
            "date": date_value,
            "price": prices,
            "portfolio_value": self.portfolio.total_value(prices), 
            "position": dict(self.portfolio.positions)
        })

    def get_results(self): # retrieving the equity curve
        return {
            "history": self.history,
        }
    