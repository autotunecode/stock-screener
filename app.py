import streamlit as st

st.set_page_config(
    page_title="株式分析プラットフォーム",
    page_icon="📈",
    layout="wide"
)

st.title("📈 株式分析プラットフォーム")
st.markdown("お宝銘柄のスクリーニングからペーパートレードまで、一つのアプリで完結します。")

st.markdown("---")

col1, col2, col3 = st.columns(3)

with col1:
    st.subheader("📊 スクリーニング")
    st.markdown("""
    - JPX全上場企業データを自動取得
    - PER/PBR/ROE等の多条件フィルタ
    - 成長性・割安度の総合評価
    - Gemini AIによる銘柄分析
    - 結果を直接シミュレーターへ連携
    """)

with col2:
    st.subheader("📈 シミュレーター")
    st.markdown("""
    - 複数戦略の同時運用
    - リアルタイム株価での評価
    - 売買シミュレーション（ペーパートレード）
    - 資産推移の記録・可視化
    """)

with col3:
    st.subheader("🏆 戦略比較")
    st.markdown("""
    - 全戦略の成績を一目で比較
    - 資産推移チャートの重ね合わせ
    - パフォーマンス分析
    """)

st.markdown("---")

# スクリーニング結果のステータス表示
if "screened_stocks" in st.session_state and st.session_state["screened_stocks"]:
    count = len(st.session_state["screened_stocks"])
    st.success(f"スクリーニング結果: {count} 銘柄がシミュレーター連携用に保持されています。「シミュレーター」ページで戦略を作成できます。")

st.info("👈 左のサイドバーからページを選択してください。")
