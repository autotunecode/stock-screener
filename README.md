# 📈 株式分析プラットフォーム (stock_platform)

お宝銘柄のスクリーニングからペーパートレードまで、一つのStreamlitアプリで完結する統合プラットフォームです。

## 機能

### 📊 スクリーニング
- JPX全上場企業データの自動取得（プライム/スタンダード/グロース市場）
- PER/PBR/ROE/成長率等の多条件フィルタ
- データ品質ダッシュボード
- Gemini AIによる銘柄分析・バリュートラップ判定
- 結果をシミュレーターへ直接連携

### 📈 ペーパートレードシミュレーター
- 複数戦略の同時運用
- リアルタイム株価での評価
- 買い/売りシミュレーション
- 資産推移の記録・可視化

### 🏆 戦略比較
- 全戦略の成績を一目で比較
- 資産推移チャートの重ね合わせ

## ローカルでの実行

```bash
# 仮想環境の作成
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Mac/Linux

# 依存パッケージのインストール
pip install -r requirements.txt

# 環境変数の設定
copy .env.example .env
# .env を編集して GEMINI_API_KEY を設定

# アプリの起動
streamlit run app.py
```

## Google Cloud Runへのデプロイ

### 前提条件
- GCPプロジェクトの作成
- gcloud CLIのインストール・認証
- Cloud Run API / Cloud Storage APIの有効化

### 手順

```bash
# 1. GCSバケットの作成（データ永続化用）
gcloud storage buckets create gs://your-bucket-name --location=asia-northeast1

# 2. Cloud Runにデプロイ
gcloud run deploy stock-platform \
  --source . \
  --region asia-northeast1 \
  --allow-unauthenticated \
  --set-env-vars="GCS_BUCKET_NAME=your-bucket-name,GEMINI_API_KEY=your-key"

# 3. デプロイ後のURL確認
gcloud run services describe stock-platform --region asia-northeast1 --format="value(status.url)"
```

## 環境変数

| 変数名 | 必須 | 説明 |
|--------|------|------|
| `GEMINI_API_KEY` | AI分析使用時 | Google Gemini APIキー |
| `GCS_BUCKET_NAME` | Cloud Run時 | GCSバケット名（データ永続化用） |

## ディレクトリ構成

```
stock_platform/
├── app.py                  # ホーム画面
├── pages/
│   ├── 1_screening.py      # スクリーニング
│   ├── 2_simulator.py      # シミュレーター
│   └── 3_comparison.py     # 戦略比較
├── modules/
│   ├── storage.py          # ストレージ抽象化（ローカル/GCS）
│   ├── data_fetcher.py     # JPX/yfinanceデータ取得
│   ├── portfolio_manager.py # ポートフォリオ管理
│   └── backtest.py         # バックテスト
├── .streamlit/config.toml  # Streamlit設定
├── Dockerfile              # Cloud Run用
├── requirements.txt
└── .env.example
```
