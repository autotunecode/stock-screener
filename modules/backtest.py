"""バックテストモジュール

指定された複数銘柄に対し、均等投資した場合の過去シミュレーションを実行する。
"""

import yfinance as yf
import pandas as pd
import numpy as np


def run_backtest(tickers, start_date, end_date, initial_cash):
    """
    指定された複数銘柄に対し、開始日に均等な金額で買い、
    そのまま保持した場合のバックテストを実行する。
    """
    if not tickers:
        return None, None

    # .Tがない場合は付与（日本の銘柄を前提）
    processed_tickers = [t if t.endswith('.T') else f"{t}.T" for t in tickers]

    # yfinanceで一括ダウンロード (Close価格を使用)
    try:
        data = yf.download(processed_tickers, start=start_date, end=end_date)['Close']
    except Exception as e:
        print(f"Error downloading data: {e}")
        return None, None

    # 銘柄が1つの場合、SeriesからDataFrameに変換する
    if isinstance(data, pd.Series):
        data = data.to_frame(processed_tickers[0])

    # 欠損値処理（pandas 2.x対応: メソッドチェーン方式）
    data = data.ffill().bfill()

    if data.empty:
        return None, None

    # 投資配分の計算（均等分散）
    num_stocks = len(data.columns)
    cash_per_stock = initial_cash / num_stocks

    # 初期保有株数を計算（初日の終値で買えたと仮定）
    initial_prices = data.iloc[0]
    shares = (cash_per_stock / initial_prices).astype(float)

    # 毎日の各銘柄の評価額と全体ポートフォリオの評価額を計算
    portfolio_daily_value = data.multiply(shares, axis=1)

    total_value = portfolio_daily_value.sum(axis=1)
    portfolio_df = total_value.to_frame('Total Value')

    # パフォーマンス指標の計算
    final_value = total_value.iloc[-1]
    total_profit = final_value - initial_cash
    total_return_pct = (total_profit / initial_cash) * 100

    # ドローダウンの計算
    running_max = total_value.cummax()
    drawdown = (total_value - running_max) / running_max * 100
    max_drawdown = drawdown.min()

    results = {
        'initial_cash': initial_cash,
        'final_value': final_value,
        'total_profit': total_profit,
        'total_return_pct': total_return_pct,
        'max_drawdown': max_drawdown
    }

    return results, portfolio_df
