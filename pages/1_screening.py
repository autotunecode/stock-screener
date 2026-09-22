"""スクリーニングページ

JPXの全上場企業情報と連携し、成長性（売上・利益成長）や割安度（PER・PBR・ROE）から
隠れた中小型株・優良株をスクリーニングします。
"""

import streamlit as st
import pandas as pd
import numpy as np
import os
import time
from datetime import datetime
from dotenv import load_dotenv

# モジュールインポート
from modules import data_fetcher, storage

load_dotenv()

# データパス定数
DATA_PATH = os.path.join("data", "stock_data.csv")
DATA_META_PATH = os.path.join("data", "stock_data_meta.json")

# データ品質判定に使う「重要指標」のリスト
KEY_METRICS = [
    "ROE(%)", "PER(倍)", "PBR(倍)", "ROA(%)", "自己資本比率(%)",
    "時価総額(億円)", "売上高成長率(%)", "利益成長率(%)",
    "現在値", "適正株価(円)", "アップサイド(%)"
]


@st.cache_data
def load_data():
    return storage.read_csv(DATA_PATH)


def load_meta():
    """データ取得時のメタ情報を読み込む"""
    return storage.read_json(DATA_META_PATH)


def calc_completeness(row):
    """重要指標のうち欠損していない割合を返す"""
    present = sum(1 for col in KEY_METRICS if col in row.index and pd.notnull(row[col]))
    return round(present / len(KEY_METRICS) * 100)


def calc_comprehensive_score(row):
    """銘柄データから100点満点の総合スコア（整数値）を算出する。

    引数:
        row (pd.Series): 銘柄の各指標データを含む行

    戻り値:
        int: 0〜100の総合スコア
    """
    try:
        score = 0.0

        # 1. データ充足度 (最大20点)
        comp_rate = row.get('データ充足率(%)', 0)
        if pd.notnull(comp_rate):
            score += float(comp_rate) * 0.2

        # 2. 割安度・アップサイド (最大25点)
        upside = row.get('アップサイド(%)', 0)
        if pd.notnull(upside):
            if upside >= 100:
                score += 25
            elif upside >= 50:
                score += 15
            elif upside >= 20:
                score += 10

        # 3. 稼ぐ力・ROE (最大20点)
        roe = row.get('ROE(%)', 0)
        if pd.notnull(roe):
            if roe >= 15:
                score += 20
            elif roe >= 10:
                score += 15
            elif roe >= 8:
                score += 10

        # 4. 成長性 (最大20点)
        rev_growth = row.get('売上高成長率(%)', 0)
        if pd.notnull(rev_growth):
            if rev_growth >= 20:
                score += 20
            elif rev_growth >= 10:
                score += 15
            elif rev_growth >= 5:
                score += 10

        # 5. 安全性 (最大15点)
        equity_ratio = row.get('自己資本比率(%)', 0)
        if pd.notnull(equity_ratio):
            if equity_ratio >= 50:
                score += 15
            elif equity_ratio >= 30:
                score += 10

        return int(min(max(score, 0), 100))
    except Exception:
        return 0


def calc_comprehensive_rating(score_or_row):
    """総合スコアまたは行データからA〜Dの総合評価とスコア文字列を生成する。

    引数:
        score_or_row (int | float | pd.Series): 総合スコア数値または銘柄行データ

    戻り値:
        str: "A (100点)" などの総合評価判定文字列
    """
    try:
        if hasattr(score_or_row, 'get'):
            score = calc_comprehensive_score(score_or_row)
        else:
            score = int(score_or_row)

        if score >= 80:
            grade = "A"
        elif score >= 60:
            grade = "B"
        elif score >= 40:
            grade = "C"
        else:
            grade = "D"

        return f"{grade} ({score}点)"
    except Exception:
        return "D (0点)"



def style_dataframe(df):
    """DataFrameにスタイルを適用する"""
    if df.empty:
        return df

    def color_pbr(val):
        if pd.isna(val): return ''
        return 'background-color: rgba(144, 238, 144, 0.4)' if val <= 1.0 else ''

    def color_roe(val):
        if pd.isna(val): return ''
        return 'background-color: rgba(255, 255, 224, 0.8)' if val >= 15.0 else ''

    def color_growth(val):
        if pd.isna(val): return ''
        return 'background-color: rgba(173, 216, 230, 0.5)' if val >= 10.0 else ''

    def color_upside(val):
        if pd.isna(val): return ''
        return 'background-color: rgba(255, 182, 193, 0.5)' if val >= 50.0 else ''

    def color_completeness(val):
        if pd.isna(val): return ''
        if val >= 90: return 'background-color: rgba(144, 238, 144, 0.5)'
        if val >= 70: return 'background-color: rgba(255, 255, 224, 0.7)'
        if val >= 50: return 'background-color: rgba(255, 200, 100, 0.5)'
        return 'background-color: rgba(255, 130, 130, 0.5)'

    def color_rating(val):
        if pd.isna(val) or not isinstance(val, str): return ''
        if val.startswith('A'):
            return 'background-color: rgba(255, 215, 0, 0.6); font-weight: bold; color: black;'
        elif val.startswith('B'):
            return 'background-color: rgba(144, 238, 144, 0.5); font-weight: bold; color: black;'
        elif val.startswith('C'):
            return 'background-color: rgba(255, 255, 224, 0.7); color: black;'
        else:
            return 'background-color: rgba(211, 211, 211, 0.6); color: #555;'

    # applymap → map に修正（pandas 2.x対応）
    styled = df.style.map(color_pbr, subset=['PBR(倍)']).map(color_roe, subset=['ROE(%)'])

    if 'データ充足率(%)' in df.columns:
        styled = styled.map(color_completeness, subset=['データ充足率(%)'])

    if '総合評価判定' in df.columns:
        styled = styled.map(color_rating, subset=['総合評価判定'])

    if 'アップサイド(%)' in df.columns:
        styled = styled.map(color_upside, subset=['アップサイド(%)'])

    if '売上高成長率(%)' in df.columns:
        styled = styled.map(color_growth, subset=['売上高成長率(%)', '利益成長率(%)'])

    return styled


# ===========================
# ページ本体
# ===========================

st.title("💎 お宝中小型＆成長株発掘ツール")
st.markdown("JPXの全上場企業情報と連携し、成長性（売上・利益成長）や割安度（PER・PBR・ROE）から隠れた中小型株・優良株をスクリーニングします。")

# --- サイドバー ---
st.sidebar.header("1. データ管理")
st.sidebar.markdown("対象の市場区分を選択し、最新データを再取得します。")

market_prime = st.sidebar.checkbox("プライム市場 (大型・中型株)", value=False)
market_standard = st.sidebar.checkbox("スタンダード市場 (中・小型株)", value=True)
market_growth = st.sidebar.checkbox("グロース市場 (新興・中小型株)", value=True)

selected_markets = []
if market_prime: selected_markets.append("プライム（内国株式）")
if market_standard: selected_markets.append("スタンダード（内国株式）")
if market_growth: selected_markets.append("グロース（内国株式）")

help_text_safe = "各市場の取得銘柄数（目安）: 【プライム】約1,650件 【スタンダード】約1,600件 【グロース】約550件。 ※チェックを入れた市場の合計（最大約3,800件）を取得します。"

col1, col2 = st.sidebar.columns([6, 1], vertical_alignment="center")
with col1:
    update_btn = st.button("データの新規取得・更新", use_container_width=True)
with col2:
    st.markdown(" ", help=help_text_safe)

if update_btn:
    if not selected_markets:
        st.sidebar.error("少なくとも1つの市場を選択してください。")
    else:
        progress_placeholder = st.sidebar.empty()
        progress_bar = st.sidebar.progress(0)

        def update_progress(current, total, elapsed, message):
            percent = int((current / total) * 100) if total > 0 else 0
            percent = min(max(percent, 0), 100)

            eta_str = ""
            if current > 0 and current < total:
                eta = elapsed / current * (total - current)
                eta_str = f" / 残り予想: {int(eta//60)}分{int(eta%60):02d}秒"

            progress_bar.progress(percent)
            progress_placeholder.text(f"{message}\n進捗: {percent}% {eta_str}")

        success = data_fetcher.update_stock_data(target_markets=selected_markets, progress_callback=update_progress)
        if success:
            st.sidebar.success("データ取得が完了しました！")
            load_data.clear()  # キャッシュクリア
        else:
            st.sidebar.error("データ取得に失敗しました。")

df = load_data()
if df.empty:
    st.warning("データがありません。左のサイドバーから市場を選択して「データの新規取得・更新」を実行してください。")
    st.stop()

st.sidebar.header("2. スクリーニング条件")

st.sidebar.subheader("成長性")
min_rev_growth = st.sidebar.slider("売上高成長率(%) 下限", min_value=-50.0, max_value=100.0, value=5.0, step=1.0,
    help="企業の大元の稼ぎである「売上」が過去1年でどれだけ伸びたか。一般に10%以上だと成長企業とみなされます。")
min_earn_growth = st.sidebar.slider("利益成長率(%) 下限", min_value=-50.0, max_value=100.0, value=0.0, step=1.0,
    help="最終的な「利益」が過去1年でどれだけ伸びたか。赤字から黒字に転換した場合も高く表示されます。")

st.sidebar.subheader("割安度・効率性")
min_upside = st.sidebar.slider("アップサイド(%) 下限", min_value=-50.0, max_value=300.0, value=0.0, step=10.0,
    help="計算上の適正株価（グレアム数）と現在の株価の差。大きければ大きいほど「本来の価値より安く放置されている（上値余地がある）」ことを示します。")
min_roe = st.sidebar.slider("ROE(%) 下限", min_value=0.0, max_value=30.0, value=8.0, step=1.0,
    help="株主のお金をどれだけ効率よく増やしているか。一般的に8〜10%以上が優良企業です。")
max_per = st.sidebar.slider("PER(倍) 上限", min_value=0.0, max_value=100.0, value=20.0, step=1.0,
    help="今の株価が純利益の何倍か。一般的に15倍以下が割安水準で、低ければ低いほど割安です。")
max_pbr = st.sidebar.slider("PBR(倍) 上限", min_value=0.0, max_value=10.0, value=2.0, step=0.1,
    help="「会社の解散価値」に対する株価の倍率。1倍を下回ると「資産面から見て極めて割安」です。")

st.sidebar.subheader("安全性")
exclude_deficit = st.sidebar.checkbox("赤字企業を除外", value=True)

# --- フィルタリング処理 ---
filtered_df = df.copy()

filtered_df = filtered_df[
    (filtered_df['ROE(%)'].fillna(-999) >= min_roe) &
    (filtered_df['PER(倍)'].fillna(999) <= max_per) &
    (filtered_df['PBR(倍)'].fillna(999) <= max_pbr)
]

if 'アップサイド(%)' in filtered_df.columns:
    filtered_df = filtered_df[
        (filtered_df['アップサイド(%)'].fillna(-999) >= min_upside)
    ]

if '売上高成長率(%)' in filtered_df.columns:
    filtered_df = filtered_df[
        (filtered_df['売上高成長率(%)'].fillna(-999) >= min_rev_growth) &
        (filtered_df['利益成長率(%)'].fillna(-999) >= min_earn_growth)
    ]

if exclude_deficit:
    filtered_df = filtered_df[
        (filtered_df['ROE(%)'].fillna(0) > 0) &
        (filtered_df['ROA(%)'].fillna(0) > 0)
    ]

# --- データ充足率列を追加 ---
filtered_df = filtered_df.copy()
if not filtered_df.empty:
    filtered_df['データ充足率(%)'] = filtered_df.apply(calc_completeness, axis=1)
    # 総合スコア（0〜100の整数）と総合評価判定（グレード表記文字列）を追加
    filtered_df['総合スコア'] = filtered_df.apply(calc_comprehensive_score, axis=1)
    filtered_df['総合評価判定'] = filtered_df['総合スコア'].apply(calc_comprehensive_rating)
    # デフォルトで総合スコア降順、データ充足率降順にソート
    filtered_df = filtered_df.sort_values(by=['総合スコア', 'データ充足率(%)'], ascending=[False, False])
else:
    filtered_df['データ充足率(%)'] = pd.Series(dtype=float)
    filtered_df['総合スコア'] = pd.Series(dtype=int)
    filtered_df['総合評価判定'] = pd.Series(dtype=str)

# 総合評価判定カラムをTickerの次(見やすい位置)に移動
cols = filtered_df.columns.tolist()
if '総合評価判定' in cols:
    cols.insert(2, cols.pop(cols.index('総合評価判定')))
    filtered_df = filtered_df[cols]

# --- 総合評価スコアによる抽出フィルター ---
display_df = filtered_df.copy()
filter_summary_label = "全件"

if not filtered_df.empty:
    score_100_count = len(filtered_df[filtered_df['総合スコア'] == 100])
    score_90_count = len(filtered_df[filtered_df['総合スコア'] >= 90])
    score_80_count = len(filtered_df[filtered_df['総合スコア'] >= 80])

    st.markdown("---")
    st.subheader("🎯 総合評価スコアによる抽出・絞り込み")

    col_filter_mode, col_filter_detail = st.columns([1.8, 2.2])

    with col_filter_mode:
        filter_mode = st.radio(
            "抽出条件の選択",
            options=[
                f"すべて表示 ({len(filtered_df)}件)",
                f"100点満点のみ ({score_100_count}件)",
                f"90点以上 ({score_90_count}件)",
                f"80点以上・A判定 ({score_80_count}件)",
                "指定スコア以上（スライダー）",
                "特定の点数を個別選択"
            ],
            index=0,
            help="総合評価判定のスコアによって銘柄を絞り込み、シミュレーター用への一括登録や詳細分析ができます。"
        )

    with col_filter_detail:
        if "100点満点のみ" in filter_mode:
            display_df = filtered_df[filtered_df['総合スコア'] == 100]
            filter_summary_label = "100点満点"
            if score_100_count > 0:
                st.success(f"🏆 総合評価が100点満点の銘柄が {score_100_count} 件抽出されました。このまま下のボタンからシミュレーターへ登録できます。")
            else:
                st.info("💡 現在のスクリーニング条件に合致する100点満点の銘柄はありません。スクリーニング条件を緩和するか他の条件をお選びください。")
        elif "90点以上" in filter_mode:
            display_df = filtered_df[filtered_df['総合スコア'] >= 90]
            filter_summary_label = "90点以上"
            st.info(f"✨ 総合評価90点以上の優秀銘柄: {len(display_df)} 件")
        elif "80点以上" in filter_mode:
            display_df = filtered_df[filtered_df['総合スコア'] >= 80]
            filter_summary_label = "80点以上 (A判定)"
            st.info(f"🏅 A判定（80点以上）の銘柄: {len(display_df)} 件")
        elif "指定スコア以上" in filter_mode:
            slider_score = st.slider(
                "抽出する最低総合スコア (点)",
                min_value=0,
                max_value=100,
                value=80,
                step=5,
                help="指定した点数以上の銘柄のみを抽出します。"
            )
            display_df = filtered_df[filtered_df['総合スコア'] >= slider_score]
            filter_summary_label = f"{slider_score}点以上"
            st.caption(f"スコア {slider_score} 点以上の銘柄: {len(display_df)} 件 / 全体 {len(filtered_df)} 件")
        elif "特定の点数を個別選択" in filter_mode:
            available_scores = sorted(filtered_df['総合スコア'].unique().tolist(), reverse=True)
            default_selection = [100] if 100 in available_scores else ([available_scores[0]] if available_scores else [])
            selected_scores = st.multiselect(
                "抽出するスコアを選択（複数選択可）",
                options=available_scores,
                default=default_selection,
                format_func=lambda s: f"{s}点 ({len(filtered_df[filtered_df['総合スコア'] == s])}件)"
            )
            if selected_scores:
                display_df = filtered_df[filtered_df['総合スコア'].isin(selected_scores)]
                score_tags = ", ".join(f"{s}点" for s in selected_scores)
                filter_summary_label = f"指定点数 ({score_tags})"
            else:
                display_df = filtered_df.iloc[0:0]
                filter_summary_label = "未選択"
                st.warning("スコアを1つ以上選択してください。")
        else:
            display_df = filtered_df
            filter_summary_label = "全件"

# --- 結果ヘッダー & アクション ---
col_res1, col_res2, col_res3 = st.columns([2, 1, 1.3])
with col_res1:
    if filter_summary_label == "全件":
        st.subheader(f"スクリーニング結果: {len(display_df)} 件")
    else:
        st.subheader(f"抽出結果 ({filter_summary_label}): {len(display_df)} 件")
        st.caption(f"※ スクリーニング合致全体: {len(filtered_df)} 件")

with col_res2:
    csv_data = display_df.to_csv(index=False).encode('utf-8-sig')
    download_filename = "screened_stocks_100pts.csv" if filter_summary_label == "100点満点" else "screened_stocks.csv"
    st.download_button(
        label=f"📥 抽出結果をCSV出力 ({len(display_df)}件)",
        data=csv_data,
        file_name=download_filename,
        mime="text/csv",
        disabled=display_df.empty,
        use_container_width=True
    )

with col_res3:
    reg_btn_label = f"📈 シミュレーター用に登録 ({len(display_df)}件)"
    if st.button(reg_btn_label, use_container_width=True, disabled=display_df.empty):
        if not display_df.empty:
            # 抽出された銘柄リストを登録
            screened_stocks = [
                {"Ticker": str(t), "Name": str(n)}
                for t, n in zip(display_df['Ticker'].tolist(), display_df['Name'].tolist())
            ]
            st.session_state["screened_stocks"] = screened_stocks
            st.session_state["screened_metadata"] = {
                "filter_label": filter_summary_label,
                "count": len(screened_stocks),
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            st.success(f"総合評価「{filter_summary_label}」の銘柄 {len(screened_stocks)} 件をシミュレーター用に登録しました。「シミュレーター」ページで戦略を作成してください。")
        else:
            st.warning("登録できる銘柄がありません。")


# --- データ品質ダッシュボード ---
with st.expander("📊 データ品質ダッシュボード — スクリーニング結果の信頼性", expanded=False):
    meta = load_meta()

    q1, q2, q3, q4 = st.columns(4)

    with q1:
        if meta and "fetched_at" in meta:
            fetched_dt = datetime.fromisoformat(meta["fetched_at"])
            age_hours = (datetime.now() - fetched_dt).total_seconds() / 3600
            freshness_label = f"{int(age_hours)}時間前" if age_hours < 24 else f"{int(age_hours / 24)}日前"
            freshness_color = "🟢" if age_hours < 12 else ("🟡" if age_hours < 48 else "🔴")
            st.metric("データ鮮度", freshness_label, delta=f"{freshness_color} {'OK' if age_hours < 48 else '古い'}", delta_color="off")
        else:
            st.metric("データ鮮度", "不明", delta="⚠️ 取得記録なし", delta_color="off")

    with q2:
        if meta:
            attempted = meta.get("total_attempted", 0)
            fetched = meta.get("total_fetched", 0)
            rate = round(fetched / attempted * 100, 1) if attempted > 0 else 0
            rate_color = "🟢" if rate >= 80 else ("🟡" if rate >= 50 else "🔴")
            st.metric("取得成功率", f"{rate}%", delta=f"{rate_color} {fetched}/{attempted}社", delta_color="off")
        else:
            st.metric("取得成功率", "不明")

    with q3:
        avg_comp = filtered_df['データ充足率(%)'].mean() if not filtered_df.empty else 0
        comp_color = "🟢" if avg_comp >= 80 else ("🟡" if avg_comp >= 60 else "🔴")
        st.metric("平均データ充足率", f"{avg_comp:.0f}%", delta=f"{comp_color} {'OK' if avg_comp >= 70 else '注意'}", delta_color="off")

    with q4:
        outlier_warnings = []
        if 'PER(倍)' in filtered_df.columns:
            extreme_per = filtered_df[filtered_df['PER(倍)'].fillna(0) > 200]
            if len(extreme_per) > 0:
                outlier_warnings.append(f"PER>200倍: {len(extreme_per)}件")
        if 'PBR(倍)' in filtered_df.columns:
            extreme_pbr = filtered_df[filtered_df['PBR(倍)'].fillna(0) > 20]
            if len(extreme_pbr) > 0:
                outlier_warnings.append(f"PBR>20倍: {len(extreme_pbr)}件")
        if 'アップサイド(%)' in filtered_df.columns:
            extreme_up = filtered_df[filtered_df['アップサイド(%)'].fillna(0) > 500]
            if len(extreme_up) > 0:
                outlier_warnings.append(f"アップサイド>500%: {len(extreme_up)}件")

        warn_count = len(outlier_warnings)
        warn_color = "🟢" if warn_count == 0 else ("🟡" if warn_count <= 2 else "🔴")
        st.metric("外れ値警告", f"{warn_count}件", delta=f"{warn_color} {'OK' if warn_count == 0 else '要確認'}", delta_color="off")

    st.markdown("---")
    st.markdown("""
■ 各指標の見かた:
- データ鮮度: 🟢 12時間以内 / 🟡 48時間以内 / 🔴 48時間以上。 古いデータは現在の株価と乖離がある可能性があります。
- 取得成功率: Yahoo Finance APIからデータ取得できた割合。 低い場合、API制限により一部銘柄が落ちている可能性があります。
- 平均データ充足率: 各銘柄の重要指標(11項目)のうち、欠損なく取得できた割合の平均。 低い場合、スクリーニングの網羅性が下がります。
- 外れ値警告: PER>200倍、PBR>20倍、アップサイド>500%などの極端な値の件数。 データエラーや特殊事情の可能性があります。

■ 「データ充足率」列のハイライト:
  🟢 90%以上 = 高信頼 / 🟡 70%以上 = OK / 🟠 50%以上 = 注意 / 🔴 50%未満 = 低信頼
""")

st.caption("※ アップサイド50%以上(赤)、PBR 1倍以下(緑)、ROE 15%以上(黄)、成長率10%超え(青) はハイライトされます。「データ充足率」列も緑(高)・赤(低)で色分けされています。")
if not display_df.empty:
    st.dataframe(style_dataframe(display_df), use_container_width=True, hide_index=True)
else:
    st.warning("⚠️ 選択したスコア条件に該当する銘柄はありません。上の「総合評価スコアによる抽出・絞り込み」またはサイドバーのスクリーニング条件を変更してください。")

st.markdown("---")

# --- 詳細分析機能 ---
st.header("🔍 銘柄詳細分析 & バリュートラップ判定")

analysis_target_df = display_df if not display_df.empty else filtered_df

if not analysis_target_df.empty:
    try:
        import yfinance as yf
    except ImportError:
        yf = None

    analysis_label = f"分析する銘柄を選択してください（対象: {filter_summary_label} {len(analysis_target_df)}件）"
    selected_ticker_name = st.selectbox(
        analysis_label,
        options=analysis_target_df.apply(lambda row: f"{row['Ticker']} - {row['Name']}", axis=1).tolist()
    )

    selected_ticker = selected_ticker_name.split(" - ")[0]
    target_data = df[df['Ticker'] == selected_ticker].iloc[0]

    # yfinance用にティッカーを加工（日本株の場合は .T を付与）
    yf_ticker = selected_ticker if selected_ticker.endswith('.T') else f"{selected_ticker}.T"

    col1, col2, col3 = st.columns(3)

    with col1:
        st.subheader("基本指標")
        st.write(f"銘柄名: {target_data['Name']} ({target_data['Ticker']})")
        st.write(f"市場: {target_data.get('市場', 'N/A')}")
        st.write(f"現在値: {target_data.get('現在値', 'N/A')} 円")
        fv = target_data.get('適正株価(円)', 'N/A')
        up = target_data.get('アップサイド(%)', 'N/A')
        st.write(f"適正株価(グレアム数): {fv} 円 (アップサイド: {up}%)")
        st.write(f"時価総額: {target_data.get('時価総額(億円)', 'N/A')} 億円")

    with col2:
        st.subheader("割安・効率性")
        roe_val = target_data.get('ROE(%)', 'N/A')
        per_val = target_data.get('PER(倍)', 'N/A')
        pbr_val = target_data.get('PBR(倍)', 'N/A')
        st.metric("ROE (自己資本利益率)", f"{roe_val} %",
            help="株主のお金をどれだけ効率よく増やしているか。目安: 10%以上なら優良。")
        st.metric("PER (株価収益率)", f"{per_val} 倍",
            help="今の株価が「1年間の純利益」の何倍か。目安: 15倍以下なら割安。低ければ低いほど良い。")
        st.metric("PBR (株価純資産倍率)", f"{pbr_val} 倍",
            help="「会社の解散価値」に対する株価の倍率。目安: 1倍以下は「会社の資産価値よりも株価が安い」状態の超割安。")

    with col3:
        st.subheader("成長・安全性")
        rev_val = target_data.get('売上高成長率(%)', 'N/A')
        earn_val = target_data.get('利益成長率(%)', 'N/A')
        st.metric("売上高成長率", f"{rev_val} %", help="企業の規模（売上）がどれだけ前年より拡大したか。")
        st.metric("利益成長率", f"{earn_val} %", help="企業の手元に残る利益がどれほど増えたか。")

        roa = target_data.get('ROA(%)', 0)
        equity_ratio = target_data.get('自己資本比率(%)', 0)
        roa_status = "🟢 安全" if pd.notnull(roa) and roa >= 5 else "🟡 注意"
        eq_status = "🟢 安全" if pd.notnull(equity_ratio) and equity_ratio >= 40 else "🟡 注意"
        st.metric("ROA (総資産利益率)", f"{roa} %", delta=roa_status, delta_color="off",
            help="借金も含めた全ての資産を使ってどれだけ効率よく稼いでいるか。5%以上がバリュートラップではないことの目安です。")
        st.metric("自己資本比率", f"{equity_ratio} %", delta=eq_status, delta_color="off",
            help="全資産のうち、借金ではない自分のお金の割合。40%以上なら概ね倒産リスクが低いと言われます。")

    # 業種比較
    st.subheader("業種内比較")
    sector = target_data['Sector']
    sector_df = df[df['Sector'] == sector]

    avg_per, avg_pbr = "N/A", "N/A"
    avg_rev = "N/A"
    if not sector_df.empty:
        avg_per = sector_df['PER(倍)'].mean()
        avg_pbr = sector_df['PBR(倍)'].mean()
        if '売上高成長率(%)' in sector_df.columns:
            avg_rev = sector_df['売上高成長率(%)'].mean()

        st.write(f"所属セクター: {sector} (該当リスト内 {len(sector_df)} 社)")
        st.write(f"- 同業種 平均PER: {avg_per:.1f} 倍")
        st.write(f"- 同業種 平均PBR: {avg_pbr:.1f} 倍")
        if avg_rev != "N/A":
            st.write(f"- 同業種 平均売上高成長率: {avg_rev:.1f} %")
    else:
        st.write(f"所属セクター: {sector} (比較対象がありません)")

    # 過去チャート
    if yf:
        st.subheader("過去5年の株価推移")
        with st.spinner("株価データを取得中..."):
            try:
                hist_data = yf.Ticker(yf_ticker).history(period="5y")
                # NaNデータを除外してチャート描画時の「Infinite extent」警告を防ぐ
                valid_data = hist_data['Close'].dropna()
                if not valid_data.empty:
                    st.line_chart(valid_data)
                else:
                    st.write("過去の株価データが取得できませんでした。")
            except Exception as e:
                st.error(f"株価データの取得エラー: {e}")

    # Gemini AI コメント
    st.markdown("---")
    st.subheader("🤖 AI分析コメント & 定性評価 (Gemini)")
    st.caption("対象銘柄の現在の「割安度」だけでなく「今後の成長性」や、アップロードした資料から「定性的な展望・リスク」を総合的に考察します。")

    try:
        import pdfplumber
        uploaded_pdf = st.file_uploader(
            f"【任意】{target_data['Name']} の決算短信や四季報レポート(PDF)をアップロードして分析精度を上げる",
            type=["pdf"]
        )
        extracted_text = ""

        if uploaded_pdf is not None:
            with st.spinner("PDFからテキストを抽出しています..."):
                try:
                    with pdfplumber.open(uploaded_pdf) as pdf:
                        for page in pdf.pages:
                            text = page.extract_text()
                            if text:
                                extracted_text += text + "\n"

                    if len(extracted_text) > 0:
                        st.success(f"PDFからのテキスト抽出に成功しました。（文字数: {len(extracted_text)}文字）")
                    else:
                        st.warning("PDFからテキストが抽出できませんでした。画像PDFの可能性があります。")
                except Exception as e:
                    st.error(f"PDFの読み込み中にエラーが発生しました: {e}")
    except ImportError:
        uploaded_pdf = None
        extracted_text = ""
        st.info("PDF解析機能を使用するには pdfplumber をインストールしてください。")

    if st.button("AIに分析させる"):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            st.error("エラー: `.env` ファイルに `GEMINI_API_KEY` が設定されていません。")
        else:
            with st.spinner("Gemini API で分析中..."):
                try:
                    from google import genai
                    client = genai.Client(api_key=api_key)

                    avg_per_str = f"{avg_per:.1f}" if isinstance(avg_per, float) else "データなし"
                    avg_pbr_str = f"{avg_pbr:.1f}" if isinstance(avg_pbr, float) else "データなし"
                    avg_rev_str = f"{avg_rev:.1f}" if isinstance(avg_rev, float) else "データなし"

                    prompt = f'''
あなたは日本の中小型・成長株発掘に定評のあるプロの証券アナリストです。
以下の企業について、投資の観点から「なぜ今後有望な成長株（もしくはお宝銘柄）として注目できるか」「バリュートラップ（割安の罠）または一時的な成長のフェイクではないか」を、指標をもとに分析しわかりやすく解説してください。
初心者向けに300〜500文字程度で結論を出してください。

【対象銘柄】
銘柄: {target_data['Name']} ({selected_ticker})
市場区分: {target_data.get('市場', '不明')}
業種(セクター): {sector}

【成長性指標】
売上高成長率(直近): {target_data.get('売上高成長率(%)')} % (セクター平均: {avg_rev_str} %)
利益成長率(直近): {target_data.get('利益成長率(%)')} %

【割安度・効率性指標】
現在株価: {target_data.get('現在値')} 円 / 適正株価(グレアム数基準): {target_data.get('適正株価(円)')} 円
理論上のアップサイド(上値余地): {target_data.get('アップサイド(%)')} %
ROE: {target_data.get('ROE(%)')} % (高ければ稼ぐ力が強い)
PER: {target_data.get('PER(倍)')} 倍 (セクター平均: {avg_per_str} 倍)
PBR: {target_data.get('PBR(倍)')} 倍 (セクター平均: {avg_pbr_str} 倍)
ROA: {target_data.get('ROA(%)')} %
自己資本比率: {target_data.get('自己資本比率(%)')} %
'''
                    if extracted_text:
                        prompt += f"\n【特別提供：IR/四季報レポートテキスト】\n以下のテキストデータを最重要の定性情報として分析に加えてください：\n{extracted_text[:30000]}\n"
                        prompt += "\n上記レポートの文脈（中期的な業績見通し、事業特有のリスク、経営戦略の解像度、競合優位性など）を必ず加味し、「数字だけでは見えない真の投資価値」を評価し、コメントの質を向上させてください。\n"

                    max_retries = 3
                    for attempt in range(max_retries):
                        try:
                            response = client.models.generate_content(
                                model='gemini-2.5-flash',
                                contents=prompt,
                            )
                            st.info(response.text)
                            break
                        except Exception as api_err:
                            if "503" in str(api_err) and attempt < max_retries - 1:
                                st.warning(f"APIが混雑しています。3秒後に再試行します... (試行 {attempt+1}/{max_retries})")
                                time.sleep(3)
                            else:
                                raise api_err
                except Exception as e:
                    st.error(f"AIコメントの生成中にエラーが発生しました: {e}")
else:
    st.info("条件に合致する銘柄がありません。左のサイドバーからスライダーの条件を緩和してください。")
