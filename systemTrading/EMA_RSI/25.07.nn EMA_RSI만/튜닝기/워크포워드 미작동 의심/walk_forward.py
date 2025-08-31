import numpy as np
import pandas as pd
from strategy_core import enhanced_backtest_strategy
from param_ranges import param_ranges
from itertools import product

def walk_forward(df, train_days=180, test_days=60, min_trades=3):
    results = []
    start = 0
    n = len(df)

    while start + train_days + test_days <= n:
        train_df = df.iloc[start:start+train_days]
        test_df = df.iloc[start+train_days:start+train_days+test_days]

        keys, values = zip(*param_ranges.items())
        best_cfg = None
        best_sharpe = -np.inf

        for comb in product(*values):
            config = dict(zip(keys, comb))

            r = enhanced_backtest_strategy(train_df, **config)
            if r['trades'] < min_trades:
                continue  # 거래가 너무 적으면 패스

            if r['sharpe'] > best_sharpe:
                best_sharpe = r['sharpe']
                best_cfg = config

        if best_cfg is None:
            start += test_days
            continue

        out_r = enhanced_backtest_strategy(test_df, **best_cfg)
        out_r.update(best_cfg)
        results.append(out_r)

        start += test_days

    return pd.DataFrame(results)
