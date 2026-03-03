"""
動画アップ管理 — Supabase ストレージ（クラウド共有版）

設計:
  - ユーザーごとに独立したデータ行（username カラムで完全分離）
  - 他のユーザーのデータには一切アクセスしない
  - Google Sheets 不要、Supabase (PostgreSQL) で永続化
  - 接続クライアントは st.cache_resource でセッション間で再利用
"""

import uuid
from datetime import datetime

import pandas as pd
import streamlit as st
from supabase import create_client, Client

# ── Supabase 接続設定 ──────────────────────────────────────────────────────────
# .streamlit/secrets.toml または Streamlit Cloud の Secrets に以下を設定:
#   SUPABASE_URL = "https://xxxxxxxxxxxx.supabase.co"
#   SUPABASE_KEY = "eyJhbGciOiJI..."

TABLE   = "videos"
HEADERS = ["ID", "タイトル", "投稿予定日", "ステータス", "台本URL", "素材フォルダURL", "最終更新日時"]

# DB のカラム名（英語） ↔ DataFrame のカラム名（日本語）
_COL = {
    "id":             "ID",
    "title":          "タイトル",
    "scheduled_date": "投稿予定日",
    "status":         "ステータス",
    "script_url":     "台本URL",
    "material_url":   "素材フォルダURL",
    "updated_at":     "最終更新日時",
}
_COL_REV = {v: k for k, v in _COL.items()}


# ── Supabase クライアント（アプリ起動中は1インスタンスを再利用）────────────────

@st.cache_resource(show_spinner=False)
def _get_client() -> Client:
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
    except KeyError as e:
        st.error(
            f"Supabase の認証情報が設定されていません: {e}\n\n"
            "`.streamlit/secrets.toml` に `SUPABASE_URL` と `SUPABASE_KEY` を設定してください。"
        )
        st.stop()
    return create_client(url, key)


# ── 公開 API（app.py から呼ばれるインターフェース）──────────────────────────────

def load_data(username: str) -> pd.DataFrame:
    """
    ユーザー専用データを全件取得して DataFrame で返す。
    投稿予定日の昇順（期限が近い順）でソートして返す。
    """
    resp = (
        _get_client()
        .table(TABLE)
        .select("id, title, scheduled_date, status, script_url, material_url, updated_at")
        .eq("username", username)
        .order("scheduled_date", desc=False)
        .execute()
    )

    if not resp.data:
        return pd.DataFrame(columns=HEADERS)

    df = pd.DataFrame(resp.data).rename(columns=_COL)
    for col in HEADERS:
        if col not in df.columns:
            df[col] = ""

    return df[HEADERS]


def add_row(username: str, data: dict) -> None:
    """
    ユーザー専用データに新しい動画を 1 件追加する。
    """
    record = {
        "id":             str(uuid.uuid4()).replace("-", "")[:12].upper(),
        "username":       username,
        "title":          str(data.get("タイトル",   "")),
        "scheduled_date": str(data.get("投稿予定日", "")),
        "status":         str(data.get("ステータス",    "未投稿")),
        "script_url":     str(data.get("台本URL",       "")),
        "material_url":   str(data.get("素材フォルダURL", "")),
        "updated_at":     datetime.now().strftime("%Y/%m/%d %H:%M"),
    }
    _get_client().table(TABLE).insert(record).execute()


def update_status(username: str, row_id: str, new_status: str) -> None:
    """
    ID をキーに対象レコードを特定し、ステータスと最終更新日時を更新する。
    username 条件を AND することで他ユーザーのデータを書き換えられないようにする。
    """
    (
        _get_client()
        .table(TABLE)
        .update({
            "status":     new_status,
            "updated_at": datetime.now().strftime("%Y/%m/%d %H:%M"),
        })
        .eq("id",       row_id)
        .eq("username", username)
        .execute()
    )


def delete_row(username: str, row_id: str) -> None:
    """
    ID をキーに対象レコードを削除する。
    username 条件を AND することで他ユーザーのデータを削除できないようにする。
    """
    (
        _get_client()
        .table(TABLE)
        .delete()
        .eq("id",       row_id)
        .eq("username", username)
        .execute()
    )
