# Quant Trading Strategy Evaluation Platform

## Repo Structure
- api -- a wrapper around engine for input/output management
    - main.py
    - routers/
- evaluation
    - metrics.py -- compute metrics like sharpe, drawdown, pnl, volatility, etc
    - backtest_report.py-- overall report generation, combines everything
    - risk.py -- more advanced (optional): VaR, conditional VaR, exposure, risk decomp
- core-logic
    - engine/ -- main computation, most important
    - event-system/ -- what happens at each step in time
    - portfolio/ -- what positions are currently held + how much money do i have: cash, positions, pnl, trade history
- factors -- signal generation, makes these functions reusable
    - base_factor.py
    - momentum.py
    - volatility.py
    - mean_reversion.py
    - lob_factor.py 
    - derivatives - optional, could bre complicated
- ml -- build simple ml models
    - predict direction (classification) - logistic regression, random forest
    - predict volatility
    - regime classification (high vs low volatility, trending vs mean-reverting)
- strategies -- uses factors to decide 
    - base_strategy.py -- define the interface, basically null
    - rule_based/ # MA crossover, mean reversion, threshold based
    - ml_based/ # this is just ml
- data: fetch, clean, format -- store data, do not fetch every time
- visuals -- convert into json to send to frontend to process

## Factors
1. Price based
  - momentum 
    - [x] returns (1d, 5d, 20d)
    - [x] moving averages (compute once in dataframe, and factor reads from dataframe)
      - SMA
      - EMA
    - [x] Relative Strength Index (RSI)
    - Moving Average Convergence Divergence (MACD)
    - [x] Average Directional Index (ADX)
      - `pip install ta`

  - mean reversion
    - is mean reversion a factor or a strategy
  - limit order book
    - how could i use limit order book if i'm not simulating high frequency trading?
    - if it's not application, should i just drop it?
  - what other factors?
2. Volatility Factors
 - Standard Deviation
 - Average True Range (ATR)
 - Volatility Index (VIX)
3. Cross-asset / macro factors
 - SPY vs TLT (equities vs bonds) correlation
 - VIX
4. Volume / Liquidity
 - volume spike
 - volume moving averages
 - price-volume divergence

## Strategies
For each strategy:
- define a list `strategy.requires ` of features that the strategy needs to reference, compute only those features, then pass to the engine
1. Mean Reversion Strategies
   1. Bollinger Bands
   2. Z-score reversion
   3. Oscillator-based:
      1. $RSI > 30 \rightarrow$ buy
      2. $RSI < 70 \rightarrow$ sell
   4. Statistical
      1. pairs trading
      2. cointegration-based spreads
2. Momentum / Trend Following
   1. MA crossover
   2. price momentum
   3. dual momentum (relative + absolute)
   4. ADX-filtered trends
3. Regime-Switching Strategies
   ```
   If high volatility:
        use mean reversion
   Else:
        use momentum
    ```
    Define regimes using: VIX, volatility factor, ML classifier
4. ML-Based Strategies
   1. Direction prediction
   2. volatility prediction -> adjust position size
   3. regime classification
5. Cross-Asset Strategies
   1. equities vs bonds: e.g. if TLT is rising, reduce equity exposure; if VIX is high, reduce risk
6. Strategy Enhancements
   1. Filters:
      1. volatility
      2. momentum
      3. volume
   2. Position sizing
      1. fixed
      2. volatility scaling
      3. Kelly-style
   3. Risk controls
      1. stop loss
      2. max drawdown cutoff
      3. max position size
   4. Transaction cost modelling

## Evaluations
- backtest_report
  - average return + median return + annualized
  - std dev - volatility
  - sharpe
  - max drawdown
  - equity_curve
  - number of trades
  - average holding period
  - market regime analysis
## Visuals
- 


Notes
Design decision on factors
❗ Factors should NOT:
- access t
- use .iloc
- be called inside loop
✅ Factors SHOULD:
- operate on entire DataFrame
- create columns
- run once before backtest

BacktestEngine contains:
- Strategy (which contains Enhancements)
   - Strategy should not contain portfolio - it should be passed on by BacktestEngine
   - Strategy first gives a signal, then calls the Enhancement to give the final signal
- Portfolio

To research
- Cointegration 
  - Engel-Granger https://youtu.be/4DBXBLIOHGE?si=dr2b60z6919To66e
  - Johansen
- Z-score reversion
  - half-life calculation - Ornstein-Uhlenbeck
- Regime swtiching
  - HMM anything probabilistic 
- Kelly sizing
- Options pricing
- Pairs trading
  - Kalman filter
  - Dicky Fuller https://www.quantstart.com/articles/Cointegrated-Augmented-Dickey-Fuller-Test-for-Pairs-Trading-Evaluation-in-R/