'''
Walk forward analysis
1. Data Split: Divide your historical dataset into sequential pairs (e.g., three years in-sample, six months out-of-sample).
2. In-Sample Optimization: Train and fine-tune your strategy’s parameters (like indicator settings or profit targets) solely using the in-sample data.
3. Out-of-Sample Testing: Lock the optimized parameters and run the strategy on the next chronological out-of-sample chunk to evaluate its profitability and risk.
4. Step and Repeat: Roll or expand the window forward, optimizing on the new training data, and testing on the next block until you walk through the entire dataset.
'''