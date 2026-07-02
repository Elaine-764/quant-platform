class DataFormatter:
    def format_equity_curve(self, history):
        return [
            {"time": h["timestamp"], "value": h["portfolio_value"]}
            for h in history
        ]