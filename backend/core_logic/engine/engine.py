from core_logic.events.base_event import Event
from core_logic.events.market_event import MarketEvent
from core_logic.events.order_event import OrderEvent
from strategies.enhancements.filters import Filter
from strategies.enhancements.position_resizing import PositionSizer
from core_logic.portfolio.portfolio import Portfolio
from strategies.enhancements.signal_types import SignalType
from strategies.base_strategy import Strategy
import pandas as pd

class BacktestEngine:
    def __init__(self, data, strategy: Strategy, portfolio: Portfolio):
        self.data = data # TODO: might need to process this before instantiation
        self.strategy = strategy # contains enhancements
        self.portfolio = portfolio
        self.history = []  # store results over time
    
    def run(self):
        self.strategy.compute_factors()
        for t in range(len(self.data)):
            # print(self.data.columns)
            cols = self.data.columns
            prices = {}
            for col in cols:
                if "Close" in col:
                    prices[col.rstrip("_Close")] = self.data[col][t] 
            # print(prices)

            # 1. Create market event
            event = MarketEvent(timestamp=t, prices=prices)

            # get current positions snapshot
            pos = self.portfolio.positions

            # 2. Strategy generates signal
            signals = self.strategy.get_signals(event) 

            # 3. Portfolio updates based on signal
            for signal in signals:
                # print(f"asset = {signal.asset}")
                self.portfolio.update(signal, prices)
            self.strategy.update_portfolio_state(self.portfolio.positions)
            # do we need to maintain portfolio in two places

            # 4. Record state
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
    