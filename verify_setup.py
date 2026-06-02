"""一鍵檢查三項串接：Gemini / Gmail SMTP / Google Sheet。

只印狀態，絕不印出任何金鑰值。
  python verify_setup.py              # 檢查
  python verify_setup.py --send-test  # Gmail OK 時寄一封測試信
"""
from __future__ import annotations

import json
import os
import sys

import config

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

OK, WARN, BAD = "✅", "⚠️", "❌"


def check_gemini() -> tuple[str, str]:
    if not config.GEMINI_API_KEY:
        return BAD, "無 GEMINI_API_KEY"
    try:
        from google import genai
        client = genai.Client(api_key=config.GEMINI_API_KEY)
        client.models.generate_content(model=config.GEMINI_MODEL, contents="ok")
        return OK, f"可用（{config.GEMINI_MODEL}）"
    except Exception as exc:  # noqa: BLE001
        msg = str(exc)
        if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
            return WARN, "key 有效但免費額度用盡(429)；菜單自動退 template，額度重置後恢復"
        return BAD, f"{type(exc).__name__}: {msg[:90]}"


def check_gmail(send_test: bool = False) -> tuple[str, str]:
    if not config.GMAIL_APP_PASSWORD:
        return BAD, "無 GMAIL_APP_PASSWORD（週報暫存 last_report.html 不寄出）"
    import smtplib
    import ssl
    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ctx) as server:
            server.login(config.GMAIL_ADDRESS, config.GMAIL_APP_PASSWORD)
            if send_test:
                from email.mime.text import MIMEText
                m = MIMEText("PSMF-Coach 測試信：SMTP 串接成功。", "plain", "utf-8")
                m["Subject"] = "PSMF-Coach 測試信"
                m["From"] = config.GMAIL_ADDRESS
                m["To"] = config.REPORT_TO_EMAIL
                server.send_message(m)
                return OK, f"SMTP 登入成功 + 已寄測試信至 {config.REPORT_TO_EMAIL}"
        return OK, f"SMTP 登入成功（{config.GMAIL_ADDRESS}）"
    except Exception as exc:  # noqa: BLE001
        return BAD, f"{type(exc).__name__}: {str(exc)[:90]}"


def check_sheet() -> tuple[str, str]:
    if not config.SHEET_ID:
        return BAD, "無 SHEET_ID（.env 填你的 Sheet ID）"
    # 有 service account 走 gspread（可回寫）；否則走 gviz CSV（唯讀，現行模式）
    if os.path.exists(config.GOOGLE_SA_JSON):
        try:
            import gspread
            from google.oauth2.service_account import Credentials
            scopes = ["https://www.googleapis.com/auth/spreadsheets"]
            creds = Credentials.from_service_account_file(config.GOOGLE_SA_JSON, scopes=scopes)
            ws = gspread.authorize(creds).open_by_key(config.SHEET_ID).worksheet(config.SHEET_LOG_TAB)
            return OK, f"service account 可讀「{config.SHEET_LOG_TAB}」，{len(ws.get_all_records())} 列"
        except Exception as exc:  # noqa: BLE001
            return BAD, f"SA: {type(exc).__name__}: {str(exc)[:90]}"
    try:
        from sheets import CsvSheet
        row = CsvSheet().read_today_log()
        n = "1+（最新已讀到）" if row else "0（只有標題列，待填）"
        return OK, f"gviz CSV 唯讀可用；資料列 {n}；菜單走 email 推送"
    except Exception as exc:  # noqa: BLE001
        return BAD, f"CSV: {type(exc).__name__}: {str(exc)[:90]}"


def print_sa_email() -> None:
    """印出 service account 的 client_email，方便你把 Sheet 共用給它。"""
    if os.path.exists(config.GOOGLE_SA_JSON):
        try:
            data = json.loads(open(config.GOOGLE_SA_JSON, encoding="utf-8").read())
            print(f"\n📋 把你的 Google Sheet「共用」給這個 email（編輯權限）：\n   {data.get('client_email')}")
        except Exception:  # noqa: BLE001
            pass


def main() -> None:
    send_test = "--send-test" in sys.argv
    print("=== PSMF-Coach 串接檢查 ===")
    for name, (icon, msg) in {
        "Gemini": check_gemini(),
        "Gmail ": check_gmail(send_test),
        "Sheet ": check_sheet(),
    }.items():
        print(f"{icon} {name}: {msg}")
    print_sa_email()


if __name__ == "__main__":
    main()
