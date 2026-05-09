"""ポートフォリオ管理モジュール

複数のシミュレーション戦略（ポートフォリオ）を管理し、
売買取引の実行や日次資産記録を行う。
"""

import os
import datetime

from modules import storage

PORTFOLIOS_FILE = os.path.join("data", "portfolios_data.json")


def _get_default_structure():
    return {
        "strategies": {}
    }


def _get_default_strategy(initial_cash=1000000.0, allowed_stocks=None):
    return {
        "cash": initial_cash,
        "holdings": {},
        "history": [],
        "daily_history": [],
        "allowed_stocks": allowed_stocks if allowed_stocks else []
    }


def load_portfolios():
    data = storage.read_json(PORTFOLIOS_FILE)
    if data is None:
        return _get_default_structure()
    try:
        # 移行用の処理: 単一ポートフォリオ形式だった場合は変換
        if "cash" in data and "strategies" not in data:
            return {
                "strategies": {
                    "旧ポートフォリオ": data
                }
            }
        return data
    except Exception as e:
        print(f"Error loading portfolios: {e}")
        return _get_default_structure()


def save_portfolios(data):
    storage.write_json(PORTFOLIOS_FILE, data)


def create_strategy(name, initial_cash, allowed_stocks):
    data = load_portfolios()
    if name in data["strategies"]:
        return False, f"戦略名「{name}」は既に存在します。"

    data["strategies"][name] = _get_default_strategy(initial_cash, allowed_stocks)
    save_portfolios(data)
    return True, f"シミュレーション戦略「{name}」を作成しました。"


def delete_strategy(name):
    data = load_portfolios()
    if name in data["strategies"]:
        del data["strategies"][name]
        save_portfolios(data)
        return True
    return False


def get_strategy(data, name):
    return data["strategies"].get(name)


def execute_trade(data, strategy_name, trade_type, ticker, name, shares, price):
    """
    trade_type: "BUY" or "SELL"
    """
    strategy = get_strategy(data, strategy_name)
    if not strategy:
        return False, "対象の戦略が見つかりません。"

    total_amount = shares * price

    if trade_type == "BUY":
        if strategy["cash"] < total_amount:
            return False, "現金残高が不足しています。"

        # 購入処理
        strategy["cash"] -= total_amount
        if ticker in strategy["holdings"]:
            h = strategy["holdings"][ticker]
            old_total_cost = h["shares"] * h["avg_price"]
            new_total_cost = old_total_cost + total_amount
            h["shares"] += shares
            h["avg_price"] = new_total_cost / h["shares"]
        else:
            strategy["holdings"][ticker] = {
                "name": name,
                "shares": shares,
                "avg_price": price
            }
    elif trade_type == "SELL":
        if ticker not in strategy["holdings"] or strategy["holdings"][ticker]["shares"] < shares:
            return False, "売却するだけの保有株数がありません。"

        strategy["cash"] += total_amount
        h = strategy["holdings"][ticker]
        h["shares"] -= shares

        if h["shares"] == 0:
            del strategy["holdings"][ticker]
    else:
        return False, "不正な取引タイプです。"

    # 履歴追加
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    strategy["history"].append({
        "date": now_str,
        "type": trade_type,
        "ticker": ticker,
        "name": name,
        "shares": shares,
        "price": price
    })

    save_portfolios(data)
    return True, f"{ticker} ({name}) を {shares}株 {trade_type} しました。"


def record_daily_value(data, strategy_name, current_total_value):
    """戦略単位で日次総資産を記録する"""
    strategy = get_strategy(data, strategy_name)
    if not strategy:
        return

    today_str = datetime.date.today().strftime("%Y-%m-%d")

    for record in strategy["daily_history"]:
        if record["date"] == today_str:
            record["total_value"] = current_total_value
            save_portfolios(data)
            return

    strategy["daily_history"].append({
        "date": today_str,
        "total_value": current_total_value
    })
    save_portfolios(data)
