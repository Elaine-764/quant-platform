from core_logic.events.signal_event import FullSignalEvent
from strategies.enhancements.signal_types import SignalType
from core_logic.events.order_event import OrderEvent
class Portfolio:
    def __init__(self, initial_cash=100000, transaction_costs=None):
        self.cash = initial_cash
        self.positions = {}  # asset -> quantity
        self.trades = []
        self.transaction_costs = transaction_costs or {
            "fixed": 0.0,
            "pct": 0.0,
            "slippage_pct": 0.0,
            "by_asset": {}
        }

    def calculate_cost(self, asset, price, quantity):
        base = self.transaction_costs
        fee = base["fixed"]
        fee += price * quantity * base["pct"]
        fee += price * quantity * base["slippage_pct"]
        asset_cost = base["by_asset"].get(asset, {})
        fee += asset_cost.get("fixed", 0.0)
        fee += price * quantity * asset_cost.get("pct", 0.0)
        return fee

    def update(self, signal: FullSignalEvent, price):
        sig = signal.signal
        asset = signal.asset
        quantity = signal.size
        cost = self.calculate_cost(asset, price, quantity)
        trade_value = price * quantity

        if sig == SignalType.OPEN_LONG or sig == SignalType.CLOSE_SHORT: # buy
            total_needed = trade_value + cost
            if total_needed > self.cash:
                return
            self.cash -= total_needed
            self.positions[asset] = self.positions.get(asset, 0) + quantity
            direction = "BUY"

        elif sig == SignalType.CLOSE_LONG or sig == SignalType.OPEN_SHORT:  # SELL
            if self.positions.get(asset, 0) < quantity:
                return
            self.positions[asset] -= quantity
            self.cash += trade_value - cost
            direction = "SELL"
        else:
            return

        order = Trade(timestamp=signal.timestamp, 
                    asset=asset,
                    price=price,
                    quantity=quantity,
                    direction=direction,
                    cost=cost)
        self.trades.append(order)

    def total_value(self, market_prices):
        value = self.cash
        for asset, qty in self.positions.items():
            value += qty * market_prices.get(asset, 0.0)
        return value
    
 
class Trade: 
    def __init__(self, timestamp, asset, price, quantity, direction, cost):
        self.timestamp = timestamp
        self.asset = asset
        self.price = price
        self.quantity = quantity
        self.direction = direction
        self.cost = cost