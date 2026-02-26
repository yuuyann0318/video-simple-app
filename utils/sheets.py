"""
動画アップ管理 — Google Sheets 操作（ユーザー完全分離版）

設計:
  - ユーザーごとに独立したシートを自動作成: "UploadList_{名前}"
  - 他のユーザーのデータには一切アクセスしない
  - 初回アクセス時にシートを自動作成してヘッダーを書き込む
"""

import warnings
warnings.filterwarnings("ignore")

import re
import gspread
from gspread import Cell
from google.oauth2.service_account import Credentials
import pandas as pd
import streamlit as st
from datetime import datetime
import uuid
import json
import base64
import os

SPREADSHEET_ID   = "1RlV-mj83pKmeOe4DkfpllAJxvs6g0R7VUPMPZXAOzoU"
SHEET_PREFIX     = "UploadList"
CREDENTIALS_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "credentials.json")

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

HEADERS = ["ID", "タイトル", "投稿予定日", "ステータス", "最終更新日時"]


# ─── ユーティリティ ────────────────────────────────────────────────────────────

def sheet_name_for(username: str) -> str:
    """
    ユーザー名から安全なシート名を生成する。
    Googleシートで使えない文字 / ? * [ ] : を除去。
    """
    safe = re.sub(r'[/\?\*\[\]:\\]', '', username).strip()[:50]
    return f"{SHEET_PREFIX}_{safe}"


# ─── 接続 ─────────────────────────────────────────────────────────────────────

def _get_credentials() -> Credentials:
    if "GOOGLE_CREDENTIALS_B64" in st.secrets:
        raw  = base64.b64decode(st.secrets["GOOGLE_CREDENTIALS_B64"]).decode("utf-8")
        info = json.loads(raw)
        return Credentials.from_service_account_info(info, scopes=SCOPES)
    if "gcp_service_account" in st.secrets:
        info = {k: v for k, v in st.secrets["gcp_service_account"].items()}
        return Credentials.from_service_account_info(info, scopes=SCOPES)
    return Credentials.from_service_account_file(CREDENTIALS_PATH, scopes=SCOPES)


@st.cache_resource(show_spinner="接続中...")
def _get_spreadsheet():
    try:
        creds  = _get_credentials()
        client = gspread.authorize(creds)
        return client.open_by_key(SPREADSHEET_ID)
    except Exception as e:
        st.error(f"スプレッドシートに接続できませんでした: {e}")
        st.stop()


def _get_user_sheet(username: str) -> gspread.Worksheet:
    """
    ユーザー専用シートを取得する。
    存在しない場合はシートを自動作成してヘッダーを書き込む。
    """
    name        = sheet_name_for(username)
    spreadsheet = _get_spreadsheet()
    try:
        return spreadsheet.worksheet(name)
    except gspread.exceptions.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(title=name, rows=1000, cols=10)
        ws.append_row(HEADERS)
        return ws


# ─── データ取得 ────────────────────────────────────────────────────────────────

@st.cache_data(ttl=30, show_spinner="読み込み中...")
def load_data(username: str) -> pd.DataFrame:
    """ユーザー専用シートの全データを取得して DataFrame で返す。"""
    sheet      = _get_user_sheet(username)
    all_values = sheet.get_all_values()

    if len(all_values) <= 1:
        return pd.DataFrame(columns=HEADERS)

    header_row = all_values[0]
    data_rows  = all_values[1:]

    records = []
    for row in data_rows:
        if not any(v.strip() for v in row):
            continue
        record = {}
        for i, h in enumerate(header_row):
            h = h.strip()
            if h:
                record[h] = row[i].strip() if i < len(row) else ""
        records.append(record)

    if not records:
        return pd.DataFrame(columns=HEADERS)

    df = pd.DataFrame(records)
    for col in HEADERS:
        if col not in df.columns:
            df[col] = ""

    return df


def clear_cache(username: str) -> None:
    load_data.clear()


# ─── データ追加 ────────────────────────────────────────────────────────────────

def add_row(username: str, data: dict) -> None:
    """ユーザー専用シートに新しい動画を1行追加する。"""
    sheet         = _get_user_sheet(username)
    data["ID"]    = str(uuid.uuid4()).replace("-", "")[:12].upper()
    data["最終更新日時"] = datetime.now().strftime("%Y/%m/%d %H:%M")
    row = [str(data.get(h, "")) for h in HEADERS]
    sheet.append_row(row, value_input_option="USER_ENTERED")
    clear_cache(username)


# ─── ステータス更新 ────────────────────────────────────────────────────────────

def update_status(username: str, row_id: str, new_status: str) -> None:
    """ID を key に対象行を特定し、ステータスを更新する。"""
    sheet      = _get_user_sheet(username)
    all_values = sheet.get_all_values()
    if not all_values:
        return

    header_row  = all_values[0]
    id_col      = header_row.index("ID")
    status_col  = header_row.index("ステータス")
    updated_col = header_row.index("最終更新日時")

    for i, row in enumerate(all_values[1:], start=2):
        if len(row) > id_col and row[id_col].strip() == row_id:
            cells = [
                Cell(i, status_col  + 1, new_status),
                Cell(i, updated_col + 1, datetime.now().strftime("%Y/%m/%d %H:%M")),
            ]
            sheet.update_cells(cells, value_input_option="USER_ENTERED")
            break

    clear_cache(username)


# ─── データ削除 ────────────────────────────────────────────────────────────────

def delete_row(username: str, row_id: str) -> None:
    """ID を key に対象行を特定し、その行を削除する。"""
    sheet      = _get_user_sheet(username)
    all_values = sheet.get_all_values()
    if not all_values:
        return

    header_row = all_values[0]
    id_col     = header_row.index("ID")

    for i, row in enumerate(all_values[1:], start=2):
        if len(row) > id_col and row[id_col].strip() == row_id:
            sheet.delete_rows(i)
            break

    clear_cache(username)
