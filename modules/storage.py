"""ストレージ抽象化モジュール

環境変数 GCS_BUCKET_NAME が設定されている場合はGoogle Cloud Storageを使用し、
未設定の場合はローカルファイルシステムを使用する。
これにより、ローカル開発とCloud Runデプロイの両方で同じコードが動作する。
"""

import os
import io
import json
import pandas as pd

GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME")


def _get_gcs_client():
    from google.cloud import storage
    return storage.Client()


def _get_blob(path):
    client = _get_gcs_client()
    bucket = client.bucket(GCS_BUCKET_NAME)
    return bucket.blob(path)


def file_exists(path):
    """ファイルが存在するかチェックする"""
    if GCS_BUCKET_NAME:
        try:
            blob = _get_blob(path)
            return blob.exists()
        except Exception:
            return False
    else:
        return os.path.exists(path)


def read_json(path):
    """JSONファイルを読み込む。存在しない場合はNoneを返す"""
    if GCS_BUCKET_NAME:
        try:
            blob = _get_blob(path)
            if blob.exists():
                return json.loads(blob.download_as_text())
        except Exception:
            pass
        return None
    else:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return None


def write_json(path, data):
    """JSONファイルを書き込む"""
    if GCS_BUCKET_NAME:
        blob = _get_blob(path)
        blob.upload_from_string(
            json.dumps(data, ensure_ascii=False, indent=4),
            content_type="application/json"
        )
    else:
        dirpath = os.path.dirname(path)
        if dirpath:
            os.makedirs(dirpath, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)


def read_csv(path):
    """CSVファイルを読み込む。存在しない場合は空のDataFrameを返す"""
    if GCS_BUCKET_NAME:
        try:
            blob = _get_blob(path)
            if blob.exists():
                return pd.read_csv(io.BytesIO(blob.download_as_bytes()))
        except Exception:
            pass
        return pd.DataFrame()
    else:
        if os.path.exists(path):
            return pd.read_csv(path)
        return pd.DataFrame()


def write_csv(path, df):
    """DataFrameをCSVファイルとして書き込む"""
    if GCS_BUCKET_NAME:
        blob = _get_blob(path)
        csv_content = df.to_csv(index=False, encoding="utf-8-sig")
        blob.upload_from_string(csv_content, content_type="text/csv")
    else:
        dirpath = os.path.dirname(path)
        if dirpath:
            os.makedirs(dirpath, exist_ok=True)
        df.to_csv(path, index=False, encoding="utf-8-sig")
