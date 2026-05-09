"""戦略比較ページ

作成されたすべてのシミュレーション戦略の資産推移を重ね合わせて比較する。
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from modules import portfolio_manager as pm

# ===========================
# ページ本体
# ===========================

st.title("🏆 複数戦略（ポートフォリオ）の成績比較")
st.markdown("作成されたすべてのシミュレーション戦略の資産推移を重ね合わせて表示します。")

# 全データのロード
portfolios_data = pm.load_portfolios()
strategies = portfolios_data.get("strategies", {})

if not strategies:
    st.info("まだ戦略が作成されていません。「シミュレーター」ページで戦略を作成してください。")
    st.stop()

# --- 比較チャート ---
compare_fig = go.Figure()
has_data = False

for s_name, s_data in strategies.items():
    dh = s_data.get("daily_history", [])
    if len(dh) > 0:
        df_c = pd.DataFrame(dh)
        compare_fig.add_trace(
            go.Scatter(x=df_c['date'], y=df_c['total_value'], mode='lines+markers', name=s_name)
        )
        has_data = True

if has_data:
    compare_fig.update_layout(
        title='全戦略 資産推移比較チャート',
        xaxis_title='日付',
        yaxis_title='総資産額 (円)',
        yaxis_tickformat=",.0f",
        hovermode='x unified'
    )
    st.plotly_chart(compare_fig, use_container_width=True)
else:
    st.info("比較可能な推移データがまだありません。各戦略で取引を行い、データを蓄積してください。")

# --- 戦略サマリーテーブル ---
st.markdown("---")
st.subheader("戦略サマリー")

summary_rows = []
for s_name, s_data in strategies.items():
    initial_cash = s_data.get("cash", 0)
    # 保有株の評価額を加算
    total_holdings = 0
    for ticker, h_info in s_data.get("holdings", {}).items():
        total_holdings += h_info.get("shares", 0) * h_info.get("avg_price", 0)

    total_asset = initial_cash + total_holdings
    num_holdings = len(s_data.get("holdings", {}))
    num_trades = len(s_data.get("history", []))
    num_stocks = len(s_data.get("allowed_stocks", []))

    dh = s_data.get("daily_history", [])
    latest_total = dh[-1]["total_value"] if dh else total_asset

    summary_rows.append({
        "戦略名": s_name,
        "登録銘柄数": num_stocks,
        "保有銘柄数": num_holdings,
        "取引回数": num_trades,
        "現金残高": f"¥{initial_cash:,.0f}",
        "最新総資産": f"¥{latest_total:,.0f}",
    })

if summary_rows:
    st.dataframe(pd.DataFrame(summary_rows), use_container_width=True, hide_index=True)
