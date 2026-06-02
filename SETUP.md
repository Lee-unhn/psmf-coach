# 安裝與串接指南

零金鑰也能跑 demo（`python daily_job.py --dry-run`）。要上線到 Gemini / Email / Google 表單才需要以下設定。設定後用 `python verify_setup.py` 檢查（不會印出任何金鑰）。

## 0. 環境

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env   # 編輯 .env
python init_baseline.py
```

## 1. Gemini（每日教練提示，可選）

1. https://aistudio.google.com/apikey 申請免費 API key。
2. `.env` 填 `GEMINI_API_KEY`。沒填則菜單用 template（仍完整可用）。
   > ⚠️ 隱私：填了之後你的近況摘要會送到 Google 生成提示。

## 2. Gmail 寄信（SMTP）

1. Google 帳戶 → 安全性 → 開「兩步驟驗證」→「應用程式密碼」產生 16 碼。
2. `.env` 填 `GMAIL_ADDRESS` + `GMAIL_APP_PASSWORD`（非登入密碼）。
3. 驗證寄測試信：`python verify_setup.py --send-test`。

## 3. Google 表單回填（隨地填，可選）

1. 建一張 Google 試算表 → 在試算表「工具 → 建立新表單」（回應會自動連回這張表）。
2. 表單加題目，**標題包含這些關鍵字即可**（程式靠關鍵字對應）：
   `體重`、`腰圍`、`重訓`(單選 有/沒有)、`飢餓`(刻度1-5)、`能量`(刻度1-5)、`依從`(刻度1-5)、`備註`、`電解質`(有/沒有)、`魚油`(有/沒有)、`維他命`(有/沒有)。
   日期不用問，程式用表單「時間戳記」當當日日期。
3. （可選）表單 設定 → 關閉「收集電子郵件地址」→ 填表更快。
4. 試算表右上「共用」→「知道連結的任何人 → 檢視」。
5. `.env` 填：
   - `SHEET_ID`＝試算表網址 `/d/` 後那段
   - `SHEET_LOG_TAB`＝回應分頁名（中文常見「表單回覆」）
   - `FORM_FILL_URL`＝表單填寫連結（會放進每日菜單 email 的按鈕）
6. `python verify_setup.py` 確認可讀。

> reader 用 gviz CSV 唯讀讀取（免 service account），中文題目自動對應、時間戳記自動轉日期。
> 若要「把菜單回寫到試算表」才需 service account JSON（放 `credentials/service_account.json`）。

## 4. 排程（Windows 工作排程器）

見 [README.md](README.md#-排程windows) 的 PowerShell 指令（每日 21:05 `daily_job.py` + 週日 09:00 `weekly_job.py`）。
本機表單開機自動啟動：`python install_autostart.py`。

## 5. 在地化

`foods.py`、`config.SUPPLEMENT_PLAN` 的品項/價格是台灣情境，請依你所在地調整。
