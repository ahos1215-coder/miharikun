"""
Google Drive API v3 ラッパーモジュール。
Service Account 認証でテキスト/JSON ファイルをアップロードする。
認証情報未設定時はローカルファイル保存（output/ ディレクトリ）にフォールバック。
"""

import json
import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Google API ライブラリは実行環境にインストール済みの前提
# 未インストール時は ImportError → ローカルフォールバックへ

try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaInMemoryUpload

    _GOOGLE_API_AVAILABLE = True
except ImportError:
    _GOOGLE_API_AVAILABLE = False

_SCOPES = ["https://www.googleapis.com/auth/drive"]
_LOCAL_OUTPUT_DIR = Path("output")


# ---------- 内部ユーティリティ ----------

def _build_drive_service():
    """
    Google Drive API サービスオブジェクトを構築する。
    GOOGLE_SERVICE_ACCOUNT_JSON が未設定の場合は None を返す。
    """
    if not _GOOGLE_API_AVAILABLE:
        print("[GDrive] google-api-python-client が未インストール。ローカル保存にフォールバック。")
        return None

    sa_json_str = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")
    if not sa_json_str:
        print("[GDrive] GOOGLE_SERVICE_ACCOUNT_JSON が未設定。ローカル保存にフォールバック。")
        return None

    try:
        sa_info = json.loads(sa_json_str)
        creds = service_account.Credentials.from_service_account_info(sa_info, scopes=_SCOPES)
        service = build("drive", "v3", credentials=creds, cache_discovery=False)
        return service
    except Exception as e:
        logger.info(f"[GDrive] 認証エラー: {e}。ローカル保存にフォールバック。")
        return None


def _save_local(content: str, filename: str) -> str:
    """ローカルの output/ ディレクトリにファイルを保存する。"""
    _LOCAL_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    local_path = _LOCAL_OUTPUT_DIR / filename
    local_path.write_text(content, encoding="utf-8")
    logger.info(f"[GDrive] ローカル保存: {local_path}")
    return str(local_path)


def _get_default_folder_id() -> Optional[str]:
    """環境変数から Google Drive フォルダ ID を取得する。"""
    return os.environ.get("GDRIVE_FOLDER_ID") or None


# ---------- パブリック API ----------

def upload_text(
    content: str,
    filename: str,
    folder_id: Optional[str] = None,
) -> Optional[str]:
    """
    テキスト文字列を Google Drive にアップロードする。

    Args:
        content:   アップロードするテキスト内容
        filename:  Drive 上のファイル名
        folder_id: アップロード先フォルダ ID（None の場合は環境変数 GDRIVE_FOLDER_ID を使用）

    Returns:
        Drive のファイル ID。ローカル保存フォールバック時はローカルパス文字列。
        エラー時は None。
    """
    service = _build_drive_service()
    if service is None:
        return _save_local(content, filename)

    target_folder = folder_id or _get_default_folder_id()

    try:
        file_metadata: dict = {"name": filename}
        if target_folder:
            file_metadata["parents"] = [target_folder]

        media = MediaInMemoryUpload(
            content.encode("utf-8"),
            mimetype="text/plain",
            resumable=False,
        )
        result = service.files().create(
            body=file_metadata,
            media_body=media,
            fields="id",
        ).execute()
        file_id: str = result["id"]
        logger.info(f"[GDrive] アップロード完了 filename={filename!r} file_id={file_id!r}")
        return file_id
    except Exception as e:
        logger.info(f"[GDrive] アップロードエラー filename={filename!r}: {e}")
        # フォールバック
        return _save_local(content, filename)


def upload_json(
    data: dict,
    filename: str,
    folder_id: Optional[str] = None,
) -> Optional[str]:
    """
    dict を JSON 形式で Google Drive にアップロードする。

    Args:
        data:      アップロードする辞書データ
        filename:  Drive 上のファイル名（.json 拡張子を推奨）
        folder_id: アップロード先フォルダ ID

    Returns:
        Drive のファイル ID、またはローカルパス。エラー時は None。
    """
    service = _build_drive_service()
    json_content = json.dumps(data, ensure_ascii=False, indent=2)

    if service is None:
        return _save_local(json_content, filename)

    target_folder = folder_id or _get_default_folder_id()

    try:
        file_metadata: dict = {"name": filename}
        if target_folder:
            file_metadata["parents"] = [target_folder]

        media = MediaInMemoryUpload(
            json_content.encode("utf-8"),
            mimetype="application/json",
            resumable=False,
        )
        result = service.files().create(
            body=file_metadata,
            media_body=media,
            fields="id",
        ).execute()
        file_id: str = result["id"]
        logger.info(f"[GDrive] JSON アップロード完了 filename={filename!r} file_id={file_id!r}")
        return file_id
    except Exception as e:
        logger.info(f"[GDrive] JSON アップロードエラー filename={filename!r}: {e}")
        return _save_local(json_content, filename)


def create_subfolder(
    name: str,
    parent_id: Optional[str] = None,
) -> Optional[str]:
    """
    Google Drive にサブフォルダを作成する。

    Args:
        name:      作成するフォルダ名
        parent_id: 親フォルダ ID（None の場合は環境変数 GDRIVE_FOLDER_ID を使用）

    Returns:
        作成したフォルダの ID。エラー時は None。
    """
    service = _build_drive_service()
    if service is None:
        logger.info(f"[GDrive] サービス未接続。フォルダ作成スキップ: {name!r}")
        return None

    target_parent = parent_id or _get_default_folder_id()

    try:
        file_metadata: dict = {
            "name": name,
            "mimeType": "application/vnd.google-apps.folder",
        }
        if target_parent:
            file_metadata["parents"] = [target_parent]

        result = service.files().create(
            body=file_metadata,
            fields="id",
        ).execute()
        folder_id: str = result["id"]
        logger.info(f"[GDrive] フォルダ作成完了 name={name!r} folder_id={folder_id!r}")
        return folder_id
    except Exception as e:
        logger.info(f"[GDrive] フォルダ作成エラー name={name!r}: {e}")
        return None
