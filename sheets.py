"""Google Sheet 回填介面。真實走 gspread + service account；缺金鑰時自動降級為本機 mock。

「每日回填」分頁欄位（第一列為標題）:
  date | weight | body_fat_pct | fat_mass | lbm | visceral_fat | waist_cm | trained | hunger | energy | adherence | notes
「隔日菜單」分頁：由程式寫入。
"""
from __future__ import annotations

import csv
import io
import json
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

import config

# Google 表單回應的中文題目標題 → 內部欄位。也相容舊手動分頁的英文標題。
_HEADER_MAP = {
    "date":      ["date", "日期"],
    "weight":    ["weight", "體重", "体重"],
    "waist_cm":  ["waist", "腰圍", "腰围"],
    "trained":   ["trained", "重訓", "訓練", "運動", "运动"],
    "hunger":    ["hunger", "飢餓", "饥饿", "饑餓"],
    "energy":    ["energy", "能量", "精神"],
    "adherence": ["adherence", "依從", "依从", "遵從"],
    "notes":     ["notes", "備註", "备注"],
    "supp_elec": ["電解質", "电解质"],
    "multivit":  ["維他命", "维他命", "綜合維", "multivit"],
    "fishoil":   ["魚油", "鱼油", "fishoil", "omega"],
    "creatine":  ["肌酸", "creatine"],
    "na_mg":     ["na_mg", "鈉"],
    "k_mg":      ["k_mg", "鉀"],
    "mg_mg":     ["mg_mg", "鎂"],
}
_YES = ("有", "yes", "y", "是", "on", "1", "true", "✓")


def _norm_date(s: str) -> str:
    """把 Google 時間戳記 / 各式日期字串正規化成 ISO YYYY-MM-DD。"""
    s = (s or "").strip()
    if not s:
        return date.today().isoformat()
    part = s.split(" ")[0].split("T")[0].replace(".", "/").replace("-", "/")
    p = [x for x in part.split("/") if x]
    try:
        if len(p[0]) == 4:                  # Y/M/D
            y, m, d = int(p[0]), int(p[1]), int(p[2])
        else:                                # M/D/Y（少見 locale）
            m, d, y = int(p[0]), int(p[1]), int(p[2])
        return f"{y:04d}-{m:02d}-{d:02d}"
    except Exception:                        # noqa: BLE001
        return date.today().isoformat()


def _normalize_row(raw: dict) -> dict:
    """把一列原始（form 中文題目 or 手動英文標題）對應成內部欄位。"""
    out: dict = {}
    ts = None
    for h, v in raw.items():
        if not h:
            continue
        hl = h.strip().lower()
        if "時間戳記" in h or "timestamp" in hl:
            ts = v
            continue
        for key, kws in _HEADER_MAP.items():
            if any(kw in hl for kw in kws):
                out[key] = v
                break
    # 電解質單一題（有/沒有）→ 展開成建議劑量供 supplement_log
    if str(out.pop("supp_elec", "")).strip().lower() in _YES:
        out.update({"na_mg": "4000", "k_mg": "3000", "mg_mg": "400"})
    if not str(out.get("date", "")).strip():
        out["date"] = _norm_date(ts)
    return out

MOCK_LOG = config.DATA_DIR / "mock_log.json"
MOCK_MENU = config.DATA_DIR / "mock_menu.json"


class MockSheet:
    """離線測試用：讀 data/mock_log.json，寫 data/mock_menu.json。"""

    def read_today_log(self) -> dict | None:
        if not MOCK_LOG.exists():
            return None
        rows = json.loads(MOCK_LOG.read_text(encoding="utf-8"))
        return rows[-1] if rows else None

    def write_menu(self, menu_date: str, menu: dict, summary: str) -> None:
        MOCK_MENU.write_text(
            json.dumps({"date": menu_date, "summary": summary, "menu": menu},
                       ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


class GoogleSheet:
    """gspread + service account。"""

    def __init__(self) -> None:
        import gspread  # 延遲匯入
        from google.oauth2.service_account import Credentials

        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        creds = Credentials.from_service_account_file(config.GOOGLE_SA_JSON, scopes=scopes)
        gc = gspread.authorize(creds)
        self._sh = gc.open_by_key(config.SHEET_ID)

    def read_today_log(self) -> dict | None:
        ws = self._sh.worksheet(config.SHEET_LOG_TAB)
        records = ws.get_all_records()
        return records[-1] if records else None

    def write_menu(self, menu_date: str, menu: dict, summary: str) -> None:
        ws = self._sh.worksheet(config.SHEET_MENU_TAB)
        lines = [f"【{menu_date} 隔日菜單】", summary, ""]
        for meal in menu.get("meals", []):
            lines.append(f"{meal['time']}：{'、'.join(meal['items'])}")
        lines.append("")
        lines.append(f"蛋白 {menu.get('protein_g')}g / 熱量 {menu.get('kcal')} kcal")
        lines.append(menu.get("notes", ""))
        ws.update_acell("A1", "\n".join(lines))


class CsvSheet:
    """讀 link-shared Sheet 的 gviz CSV（唯讀，免 service account）。菜單改走 email 推送。"""

    def __init__(self) -> None:
        tab = urllib.parse.quote(config.SHEET_LOG_TAB)
        self.url = (f"https://docs.google.com/spreadsheets/d/{config.SHEET_ID}"
                    f"/gviz/tq?tqx=out:csv&sheet={tab}")

    def read_today_log(self) -> dict | None:
        req = urllib.request.Request(self.url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=20) as r:
            text = r.read().decode("utf-8", "replace")
        rows = [_normalize_row(row) for row in csv.DictReader(io.StringIO(text))]
        # 有體重才算有效回填（form 必填、手動分頁也有）→ 取最新一筆
        valid = [r for r in rows if str(r.get("weight", "")).strip()]
        return valid[-1] if valid else None

    def write_menu(self, menu_date: str, menu: dict, summary: str) -> None:
        pass  # 唯讀來源；菜單由 emailer 推送


def get_provider():
    """優先序：有 service account → GoogleSheet（可回寫）；否則 SHEET_ID → CsvSheet（唯讀）；都無 → mock。"""
    if config.SHEET_ID and Path(config.GOOGLE_SA_JSON).exists():
        try:
            return GoogleSheet()
        except Exception as exc:  # noqa: BLE001
            print(f"[sheets] Google service account 失敗，改用 CSV：{exc}")
    if config.SHEET_ID:
        return CsvSheet()
    return MockSheet()
