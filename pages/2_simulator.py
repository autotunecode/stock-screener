"""シミュレーターページ

複数のシミュレーション戦略を登録し、ペーパートレードを実行するページ。
スクリーニング結果から直接戦略を作成することも可能。
"""

import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go

from modules import portfolio_manager as pm


def fetch_current_price(ticker):
    """yfinanceから現在の価格（直近終値または現在値）を取得"""
    processed_ticker = ticker if ticker.endswith('.T') else f"{ticker}.T"
    try:
        data = yf.Ticker(processed_ticker).history(period="1d")
        if not data.empty:
            return round(data['Close'].iloc[-1], 1)
    except Exception:
        pass
    return None


# ===========================
# ページ本体
# ===========================

st.title("📈 複数戦略対応 ペーパートレードシミュレーター")
st.markdown("複数のCSV（スクリーニング基準）をそれぞれ別の「シミュレーション戦略」として登録し、同時に運用して成績を比較できます。")

# 全データのロード
portfolios_data = pm.load_portfolios()
strategies = portfolios_data.get("strategies", {})

# ==========================
# サイドバー：戦略の管理
# ==========================
with st.sidebar:
    st.header("⚙️ 戦略（口座）管理")

    # 1. アクティブ戦略の選択
    strategy_names = list(strategies.keys())
    active_strategy_name = None

    if len(strategy_names) > 0:
        active_strategy_name = st.selectbox("現在操作する戦略を選択", options=strategy_names)
    else:
        st.warning("現在登録されている戦略がありません。下から新規作成してください。")

    st.divider()

    # 2. 新規戦略の作成
    st.subheader("➕ 新規戦略の作成")

    # スクリーニング結果があるかチェック
    has_screened = "screened_stocks" in st.session_state and st.session_state["screened_stocks"]

    source_option = st.radio(
        "銘柄リストの取得方法",
        options=["CSVファイルをアップロード"] + (["スクリーニング結果を使用"] if has_screened else []),
        help="スクリーニングページで結果を登録すると、ここから直接戦略を作成できます。"
    )

    with st.form("create_strategy_form", clear_on_submit=True):
        new_strat_name = st.text_input("戦略名 (例: 高ROE・割安株)")
        options_cash = [i * 1000000 for i in range(1, 101)]
        new_strat_cash = st.selectbox("初期資金", options=options_cash, index=0,
                                       format_func=lambda x: f"{x // 10000}万円")

        uploaded_csv = None
        if source_option == "CSVファイルをアップロード":
            uploaded_csv = st.file_uploader("対象銘柄リスト(CSV)をアップロード", type=["csv"])
        elif has_screened:
            count = len(st.session_state["screened_stocks"])
            st.info(f"スクリーニング結果から {count} 銘柄を使用します。")

        submit_create = st.form_submit_button("作成する")
        if submit_create:
            if not new_strat_name:
                st.error("戦略名を入力してください。")
            elif new_strat_name in strategy_names:
                st.error("その戦略名は既に存在します。")
            else:
                allowed_stocks = None

                if source_option == "スクリーニング結果を使用" and has_screened:
                    allowed_stocks = st.session_state["screened_stocks"]
                elif uploaded_csv is not None:
                    df_csv = pd.read_csv(uploaded_csv)
                    if 'Ticker' not in df_csv.columns:
                        st.error("アップロードされたCSVに 'Ticker' カラムが含まれていません。")
                        allowed_stocks = None
                    else:
                        allowed_stocks = []
                        for _, row in df_csv.iterrows():
                            t = str(row['Ticker'])
                            n = str(row['Name']) if 'Name' in df_csv.columns else ""
                            allowed_stocks.append({"Ticker": t, "Name": n})
                else:
                    st.error("銘柄リストを指定してください（CSVアップロードまたはスクリーニング結果）。")

                if allowed_stocks is not None:
                    success, msg = pm.create_strategy(new_strat_name, new_strat_cash, allowed_stocks)
                    if success:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)

    # 3. 戦略の削除
    if active_strategy_name:
        st.divider()
        with st.expander("⚠️ 戦略の削除"):
            st.warning(f"現在選択中の「{active_strategy_name}」を削除しますか？データは復旧できません。")
            if st.button("この戦略を完全に削除する"):
                if pm.delete_strategy(active_strategy_name):
                    st.success("削除しました。")
                    st.rerun()

# ==========================
# メイン画面の分岐
# ==========================
if not active_strategy_name:
    st.info("👈 左のサイドバーから「新規戦略」を作成してください。")
    if has_screened:
        st.success(f"スクリーニングページから {len(st.session_state['screened_stocks'])} 銘柄が登録済みです。サイドバーから戦略を作成できます。")
    st.stop()

# 現在選択されている戦略データの取得
active_strat = pm.get_strategy(portfolios_data, active_strategy_name)

# タブ構成（比較は別ページに分離）
tab_dash, tab_trade, tab_chart = st.tabs(["📊 ダッシュボード", "🛒 取引実行", "📜 資産推移・履歴"])

# --- 現在の価格と資産額の計算 ---
holdings = active_strat["holdings"]
current_cash = active_strat["cash"]

total_stock_value = 0
holdings_display = []

for ticker, h_info in holdings.items():
    curr_price = fetch_current_price(ticker)
    if curr_price is None:
        curr_price = h_info["avg_price"]

    shares = h_info["shares"]
    avg_price = h_info["avg_price"]
    current_val = shares * curr_price
    pnl = current_val - (shares * avg_price)
    pnl_pct = (pnl / (shares * avg_price)) * 100 if shares > 0 else 0

    total_stock_value += current_val

    holdings_display.append({
        "Ticker": ticker,
        "銘柄名": h_info["name"],
        "保有株数": shares,
        "平均取得単価": round(avg_price, 1),
        "現在値": curr_price,
        "評価額": round(current_val, 1),
        "含み損益": round(pnl, 1),
        "損益率(%)": round(pnl_pct, 2)
    })

total_asset = current_cash + total_stock_value

# 日次資産を記録
pm.record_daily_value(portfolios_data, active_strategy_name, total_asset)

# ==========================
# ダッシュボード
# ==========================
with tab_dash:
    st.subheader(f"「{active_strategy_name}」の状況")
    col1, col2, col3 = st.columns(3)
    col1.metric("総資産額", f"¥{total_asset:,.0f}")
    col2.metric("現金残高 (買付余力)", f"¥{current_cash:,.0f}")
    col3.metric("保有株式評価額", f"¥{total_stock_value:,.0f}")

    st.divider()
    st.subheader("ポートフォリオ内訳")
    if len(holdings_display) > 0:
        df_holdings = pd.DataFrame(holdings_display)

        def color_pnl(val):
            return 'color: red' if val < 0 else 'color: green'

        # applymap → map に修正（pandas 2.x対応）
        st.dataframe(
            df_holdings.style.map(color_pnl, subset=['含み損益', '損益率(%)']),
            use_container_width=True
        )
    else:
        st.info("現在保有している銘柄はありません。")

# ==========================
# トレード実行パネル
# ==========================
with tab_trade:
    st.subheader(f"取引パネル ({active_strategy_name})")
    allowed_stocks = active_strat.get("allowed_stocks", [])

    if not allowed_stocks:
        st.warning("この戦略には銘柄リストが登録されていません。")
    else:
        stock_strs = [f"{s['Ticker']} - {s['Name']}" for s in allowed_stocks]
        selected_stock_str = st.selectbox("取引する銘柄を選択してください", options=stock_strs)

        selected_ticker = selected_stock_str.split(" - ")[0].strip()
        selected_name = selected_stock_str.split(" - ")[1].strip() if " - " in selected_stock_str else ""

        curr_price = fetch_current_price(selected_ticker)

        if curr_price is not None:
            st.write(f"現在価格: ¥{curr_price:,.1f}")

            trade_mode = st.radio("売買区分", ["買い (BUY)", "売り (SELL)"], horizontal=True)

            if trade_mode == "買い (BUY)":
                max_shares = int(current_cash // curr_price) if curr_price > 0 else 0
                st.write(f"買付可能数量(目安): {max_shares} 株")
                qty = st.number_input("注文株数", min_value=1, step=100, value=100)

                est_cost = qty * curr_price
                st.write(f"概算約定代金: ¥{est_cost:,.0f}")

                if st.button("買付実行（現在値）", type="primary"):
                    success, msg = pm.execute_trade(portfolios_data, active_strategy_name, "BUY",
                                                     selected_ticker, selected_name, qty, curr_price)
                    if success:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
            else:
                owned_shares = active_strat["holdings"].get(selected_ticker, {}).get("shares", 0)
                st.write(f"保有数量: {owned_shares} 株")
                if owned_shares == 0:
                    st.warning("この銘柄は保有していません。")
                else:
                    qty = st.number_input("売却株数", min_value=1, max_value=owned_shares, step=100, value=owned_shares)
                    est_cost = qty * curr_price
                    st.write(f"概算受渡金額: ¥{est_cost:,.0f}")

                    if st.button("売却実行（現在値）", type="primary"):
                        success, msg = pm.execute_trade(portfolios_data, active_strategy_name, "SELL",
                                                         selected_ticker, selected_name, qty, curr_price)
                        if success:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)
        else:
            st.error("現在価格が取得できないため取引できません。")

# ==========================
# 資産推移・取引履歴
# ==========================
with tab_chart:
    daily_history = active_strat.get("daily_history", [])
    if len(daily_history) > 0:
        st.subheader("日次資産推移")
        df_hist = pd.DataFrame(daily_history)
        fig = px.line(df_hist, x='date', y='total_value',
                      title=f'[{active_strategy_name}] 総資産の推移', markers=True)
        fig.update_yaxes(tickformat=",.0f")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("推移データがありません。")

    st.divider()
    st.subheader("取引履歴")
    history = active_strat.get("history", [])
    if len(history) > 0:
        df_trades = pd.DataFrame(history)[::-1]
        st.dataframe(df_trades, use_container_width=True)
    else:
        st.info("まだ取引履歴はありません。")
