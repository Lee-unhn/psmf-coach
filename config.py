"""PSMF-Coach 全域設定。

所有「個人資料」與「金鑰」都從 .env 讀取（見 .env.example），程式碼不含任何個資/secret。
沒有 .env 也能跑 demo（用下方通用預設值 + template/mock 模式）。
"""
from __future__ import annotations

import os
from datetime import date
from pathlib import Path

# --- 路徑 ---
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
CRED_DIR = BASE_DIR / "credentials"
DB_PATH = DATA_DIR / "psmf.db"
DATA_DIR.mkdir(exist_ok=True)
CRED_DIR.mkdir(exist_ok=True)


def _load_env(path: Path) -> None:
    """極簡 .env 載入器（免裝 python-dotenv）。空值跳過。"""
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        val = val.strip().strip('"').strip("'")
        if val:
            os.environ.setdefault(key.strip(), val)


_load_env(BASE_DIR / ".env")


def _f(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _i(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


# --- 使用者檔案（從 .env；下方為通用範例預設，請在 .env 覆蓋成你的數據）---
SEX = os.environ.get("SEX", "male")           # male / female
AGE = _i("AGE", 30)
HEIGHT_CM = _f("HEIGHT_CM", 175)
START_DATE = date.fromisoformat(os.environ.get("START_DATE", "2026-01-01"))
START_WEIGHT = _f("START_WEIGHT", 100.0)
START_BODY_FAT_PCT = _f("START_BODY_FAT_PCT", 35.0)
START_FAT_MASS = _f("START_FAT_MASS", 35.0)
START_LBM = _f("START_LBM", 65.0)
START_VISCERAL_FAT = _f("START_VISCERAL_FAT", 15.0)
GOAL_WEIGHT = _f("GOAL_WEIGHT", 75.0)
PLAN_WEEKS = _i("PLAN_WEEKS", 18)

# --- 營養目標 ---
PROTEIN_G_PER_DAY = _i("PROTEIN_G_PER_DAY", 180)
TDEE_ACTIVITY_FACTOR = _f("TDEE_ACTIVITY_FACTOR", 1.36)  # 久坐 + NEAT 走路
WHEY_SCOOP_PROTEIN_G = 24
WHEY_SCOOP_KCAL = 120

# 各日型每日目標（高蛋白精瘦 PSMF：蛋白拉高、碳水脂肪壓低；脂肪守 ~20g 底線防膽結石）
DAY_TARGETS = {
    "A":          {"kcal": 1000, "protein": 180, "carb": 30, "fat": 20},
    "B":          {"kcal": 1050, "protein": 180, "carb": 30, "fat": 28},
    "refeed":     {"kcal": 1900, "protein": 180, "carb": 170, "fat": 35},
    "diet_break": {"kcal": 2200, "protein": 180, "carb": 200, "fat": 45},
}
INTAKE_KCAL_TARGET = 1000
WATER_L = _f("WATER_L", 3.6)
WATER_TIMES = ["06:50", "09:00", "11:00", "14:00", "16:00", "18:00", "20:00"]

# --- 排程事件 ---
REFEED_INTERVAL_DAYS = _i("REFEED_INTERVAL_DAYS", 14)
DIET_BREAK_WEEK = _i("DIET_BREAK_WEEK", 9)
DIET_BREAK_DAYS = _i("DIET_BREAK_DAYS", 7)
TRAINING_DAYS_PER_WEEK = _i("TRAINING_DAYS_PER_WEEK", 4)

# --- 補劑時程（名稱, 時機, 每日成本, 等級）。成本為估計，請依當地調整 ---
SUPPLEMENT_PLAN = [
    ("電解質粉 1 包",        "起床後",         15, "🔴"),
    ("綜合 B 群 1 顆",       "早餐後",         5,  "🔴"),
    ("魚油 Omega-3 2 顆",    "早餐後",         10, "🔴"),
    ("維他命 D 2000IU 1 顆", "早餐後",         3,  "🟠"),
    ("甘胺酸鎂 400mg 1 顆",  "睡前",           5,  "🔴"),
    ("洋車前子粉 10g",       "睡前",           5,  "🟠"),
    ("肌酸 5g",              "訓練日任意時段", 5,  "🟢"),
]
SUPP_TIMING_NOTE = "電解質 + B群 + 維他命D + 魚油 = 起床後 / 早餐後 · 鎂 + 洋車前子 = 睡前"

RED_FLAGS = [
    "心悸 / 靜息心率比起點 +20 bpm",
    "暈眩 / 站起來眼前發黑 > 3 秒",
    "肌肉抽筋連續兩晚",
    "尿色深褐",
    "便祕 > 3 天 / 拉肚子 > 2 天",
    "情緒崩潰 / 嚴重失眠 3 天",
]
STOP_SIGNALS = "胸悶 / 右上腹劇痛 / 全身水腫 / 持續嘔吐 → 立刻停 PSMF 看醫生"

# --- 外部服務（全部從 .env；無預設個資/金鑰）---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
GMAIL_ADDRESS = os.environ.get("GMAIL_ADDRESS", "")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "").replace(" ", "")
REPORT_TO_EMAIL = os.environ.get("REPORT_TO_EMAIL", "") or GMAIL_ADDRESS
GOOGLE_SA_JSON = os.environ.get("GOOGLE_SA_JSON", str(CRED_DIR / "service_account.json"))
SHEET_ID = os.environ.get("SHEET_ID", "")
SHEET_LOG_TAB = os.environ.get("SHEET_LOG_TAB", "表單回覆")
SHEET_MENU_TAB = os.environ.get("SHEET_MENU_TAB", "隔日菜單")
FORM_FILL_URL = os.environ.get("FORM_FILL_URL", "")


def bmr_mifflin(weight_kg: float) -> float:
    """Mifflin-St Jeor BMR。"""
    s = 5 if SEX == "male" else -161
    return 10 * weight_kg + 6.25 * HEIGHT_CM - 5 * AGE + s


def tdee(weight_kg: float) -> float:
    return bmr_mifflin(weight_kg) * TDEE_ACTIVITY_FACTOR
