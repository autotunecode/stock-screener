"""JPX上場企業一覧の取得とyfinanceによる財務データ取得モジュール"""

import os
import time
import pandas as pd
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    import yfinance as yf
except ImportError:
    yf = None

from modules import storage

JPX_URL = "https://www.jpx.co.jp/markets/statistics-equities/misc/tvdivq0000001vg2-att/data_j.xls"
STOCK_LIST_PATH = os.path.join("data", "stock_list.csv")
DATA_OUTPUT_PATH = os.path.join("data", "stock_data.csv")
DATA_META_PATH = os.path.join("data", "stock_data_meta.json")


def download_jpx_data():
    """JPXからエクセルをダウンロードし、データフレームとして返す"""
    try:
        # JPXのファイルは .xls 形式（xlrd が必要）
        df = pd.read_excel(JPX_URL, engine="xlrd")
        return df
    except ImportError:
        # xlrd が無い場合、openpyxl でフォールバック
        try:
            df = pd.read_excel(JPX_URL, engine="openpyxl")
            return df
        except Exception:
            pass
        print("エラー: xlrd ライブラリがインストールされていません。pip install xlrd で導入してください。")
        return pd.DataFrame()
    except Exception as e:
        print(f"JPXデータの取得に失敗しました: {e}")
        return pd.DataFrame()


def process_jpx_data(df, target_markets):
    """JPXの生データをフィルタリングし、yfinance用のフォーマットに変換して保存する"""
    if df.empty:
        return []

    # "市場・商品区分"列でフィルタ
    if "市場・商品区分" in df.columns:
        filtered_df = df[df["市場・商品区分"].isin(target_markets)]
    else:
        filtered_df = df

    # ETFやREITなどを除外するため、33業種コードがハイフン(-)のものを除外
    if "33業種区分" in filtered_df.columns:
        filtered_df = filtered_df[filtered_df["33業種区分"] != "-"]

    stocks = []
    for _, row in filtered_df.iterrows():
        code = str(row.get("コード", ""))
        name = row.get("銘柄名", "")
        market = row.get("市場・商品区分", "")
        sector = row.get("33業種区分", "Unknown")

        if code:
            ticker = f"{code}.T"
            stocks.append({
                "Ticker": ticker,
                "Name": name,
                "Market": market,
                "Sector": sector
            })

    # 一旦 CSV に保存
    storage.write_csv(STOCK_LIST_PATH, pd.DataFrame(stocks))
    return stocks


def fetch_financial_data(stock_info):
    """個別銘柄の財務データをyfinanceから取得する"""
    ticker_symbol = stock_info.get("Ticker")
    name = stock_info.get("Name", "Unknown")
    market = stock_info.get("Market", "Unknown")
    sector = stock_info.get("Sector", "Unknown")

    try:
        # API制限回避のための待機
        time.sleep(0.5)

        info = {}
        # リトライ機構
        for attempt in range(3):
            try:
                stock = yf.Ticker(ticker_symbol)
                info = stock.info
                if info and not isinstance(info, str):
                    break
            except Exception as inner_e:
                if attempt == 2:
                    raise inner_e
                time.sleep(2)

        # 自己資本比率の簡易推定
        equity_ratio = None
        debt_to_equity = info.get("debtToEquity")
        if debt_to_equity is not None:
            equity_ratio = 100 / (1 + (debt_to_equity / 100))

        # グレアム数による適正株価計算
        trailing_eps = info.get("trailingEps")
        book_value = info.get("bookValue")
        current_price = info.get("currentPrice") or info.get("regularMarketPrice")

        fair_value = None
        upside = None
        if trailing_eps and book_value and trailing_eps > 0 and book_value > 0:
            import math
            fair_value = math.sqrt(22.5 * trailing_eps * book_value)
            if current_price and current_price > 0:
                upside = ((fair_value - current_price) / current_price) * 100

        data = {
            "Ticker": ticker_symbol,
            "Name": name,
            "市場": market,
            "Sector": sector,
            "ROE(%)": (info.get("returnOnEquity", 0) * 100) if info.get("returnOnEquity") is not None else None,
            "PER(倍)": info.get("trailingPE"),
            "PBR(倍)": info.get("priceToBook"),
            "ROA(%)": (info.get("returnOnAssets", 0) * 100) if info.get("returnOnAssets") is not None else None,
            "自己資本比率(%)": round(equity_ratio, 1) if equity_ratio else None,
            "時価総額(億円)": round(info.get("marketCap", 0) / 100000000, 1) if info.get("marketCap") else None,
            "売上高成長率(%)": (info.get("revenueGrowth", 0) * 100) if info.get("revenueGrowth") is not None else None,
            "利益成長率(%)": (info.get("earningsGrowth", 0) * 100) if info.get("earningsGrowth") is not None else None,
            "現在値": current_price,
            "適正株価(円)": round(fair_value, 1) if fair_value else None,
            "アップサイド(%)": round(upside, 1) if upside else None
        }
        return data
    except Exception:
        return None


def update_stock_data(target_markets=None, progress_callback=None):
    """
    対象市場を指定して最新データをJPXから取得し、マルチスレッドでyfinanceから取得する。
    progress_callback は (current, total, elapsed, message) を受け取る関数
    """
    if target_markets is None:
        target_markets = ["プライム（内国株式）", "スタンダード（内国株式）", "グロース（内国株式）"]

    if progress_callback:
        progress_callback(0, 1, 0, "JPXから上場企業一覧をダウンロード中...")

    jpx_df = download_jpx_data()
    stocks = process_jpx_data(jpx_df, target_markets)

    if not stocks:
        # 失敗時は既存のローカルリストを読む
        df_list = storage.read_csv(STOCK_LIST_PATH)
        if not df_list.empty:
            stocks = df_list.to_dict('records')

    if not stocks:
        if progress_callback:
            progress_callback(1, 1, 0, "対象銘柄が見つかりませんでした")
        return False

    total_stocks = len(stocks)
    results = []
    start_time = time.time()

    # マルチスレッドによる並列取得（API制限回避のため並列数を絞る）
    MAX_WORKERS = 5

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(fetch_financial_data, stock): stock for stock in stocks}

        completed = 0
        for future in as_completed(futures):
            completed += 1
            data = future.result()
            if data:
                results.append(data)

            if progress_callback:
                elapsed = time.time() - start_time
                progress_callback(completed, total_stocks, elapsed,
                                  f"Yahoo Financeからデータを取得中: {completed}/{total_stocks} 社完了")

    if results:
        df_results = pd.DataFrame(results)

        cols = [
            "Ticker", "Name", "市場", "Sector", "現在値", "適正株価(円)", "アップサイド(%)",
            "ROE(%)", "PER(倍)", "PBR(倍)", "ROA(%)", "自己資本比率(%)",
            "時価総額(億円)", "売上高成長率(%)", "利益成長率(%)"
        ]
        df_results = df_results[[c for c in cols if c in df_results.columns]]

        storage.write_csv(DATA_OUTPUT_PATH, df_results)

        # メタ情報を保存（データ品質ダッシュボード用）
        meta = {
            "fetched_at": datetime.now().isoformat(),
            "total_attempted": total_stocks,
            "total_fetched": len(results),
            "target_markets": target_markets,
            "elapsed_seconds": round(time.time() - start_time, 1)
        }
        storage.write_json(DATA_META_PATH, meta)

        if progress_callback:
            progress_callback(total_stocks, total_stocks, time.time() - start_time, "データ取得完了！")

        return True
    else:
        if progress_callback:
            progress_callback(total_stocks, total_stocks, time.time() - start_time, "データ取得失敗")
        return False
