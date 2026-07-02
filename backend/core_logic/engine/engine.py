from ..events.base_event import Event
from ..events.market_event import MarketEvent
from ..events.order_event import OrderEvent
from ...strategies.enhancements.filters import Filter
from ...strategies.enhancements.position_resizing import PositionSizer
from ..portfolio.portfolio import Portfolio
from ...strategies.enhancements.signal_types import SignalType
from ...strategies.base_strategy import Strategy
class BacktestEngine:
    def __init__(self, data, strategy: Strategy, portfolio: Portfolio):
        self.data = data # TODO: might need to process this before instantiation
        self.strategy = strategy # contains enhancements
        self.portfolio = portfolio
        self.history = []  # store results over time
    
    def run(self):
        self.strategy.compute_factors()
        for t in range(len(self.data)):
            price = self.data["price"][t] # TODO: price col does not exist, decide what should be the price

            # 1. Create market event
            event = MarketEvent(timestamp=t, price=price)

            # get current position
            pos = self.portfolio.position # TODO: consider feeding position into strategy instead of strategy having a position field

            # 2. Strategy generates signal
            signals = self.strategy.get_signals(event) 

            # 3. Portfolio updates based on signal
            for signal in signals:
                self.portfolio.update(signal, price)
            self.strategy.update_portfolio_state(self.portfolio) # TODO: is this needed? see TODO from above
            # do we need to maintain portfolio in two places

            # 4. Record state
            self.record(t, price)

        return self.get_results()
    
    def record(self, t, price): # constructing the equity curve
        self.history.append({
            "timestamp": t,
            "price": price,
            "portfolio_value": self.portfolio.total_value(price), 
            "position": self.portfolio.position
        })

    def get_results(self): # retrieving the equity curve
        return self.history
    

'''
Notes:
- in two asset strategies, signal represents the percentage of portfolio that's in asset 1
- given enhancements
    - position resizer: resize on the incremental/decremental difference between current signal
      and previous portfolio position
    - filter or risk control: 
        --> this remains a question for both single- and multi- asset strategies
- portfolio: contains positision as a dict mapping asset -> quantity
'''