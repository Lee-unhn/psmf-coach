# PSMF-Coach · 個人化 PSMF 減脂教練系統

**English** · [中文說明見下 ↓](#中文說明)

Self-hosted PSMF (Protein-Sparing Modified Fast) diet-coaching automation. You log a
daily check-in (a local form, a Google Form, or a Google Sheet); it generates the next
day's full menu card and emails it to you. Every Sunday it pulls the latest papers +
trends, recomputes your TDEE, and emails a weekly report. Python · SQLite · free APIs.

> Author: **JasonLee** · Template — bring your own data (personal data lives in `data/`, gitignored).

## Architecture

```mermaid
flowchart LR
  classDef uin fill:#74c7ec,stroke:#1e66f5,color:#1e1e2e;
  classDef pipe fill:#f9e2af,stroke:#df8e1d,color:#1e1e2e;
  classDef model fill:#a6e3a1,stroke:#40a02b,color:#1e1e2e;
  classDef out fill:#f5c2e7,stroke:#ea76cb,color:#1e1e2e;
  classDef worker fill:#94e2d5,stroke:#179299,color:#1e1e2e;

  FORM([Daily check-in: form.py :8765 / Google Form / Sheet]):::uin
  SCHD[/schedule · daily 21:05/]:::worker
  SCHW[/schedule · Sunday 09:00/]:::worker
  SH[(Google Sheet check-in · gviz CSV)]:::model
  subgraph DAILY[Daily · daily_job.py]
    RE[/rule_engine · day-type/]:::pipe
    MG[/menu_generator · Gemini or template/]:::pipe
  end
  subgraph WEEKLY[Weekly · weekly_job.py]
    WA[/weekly_analysis · stall detect + TDEE recompute/]:::pipe
    RES[/research · PubMed / EuropePMC / Semantic Scholar/]:::pipe
    MD[/make_docs · HTML/]:::pipe
  end
  DB[(SQLite · db.py)]:::model
  GEM[(Gemini free)]:::model
  EM[emailer · SMTP]:::out
  DM[Daily menu email]:::out
  WR[Weekly report email]:::out
  DOC[docs: 18-week plan / shopping list]:::out

  FORM --> SH
  SCHD -.-> RE
  SH --> RE --> MG --> EM --> DM
  MG --> GEM
  RE --> DB
  SCHW -.-> WA
  WA --> RES --> MD --> EM --> WR
  WA --> DB
  MD --> DOC
```

## Quick start (no keys)
```powershell
cd psmf-coach
python init_baseline.py        # build DB + baseline row
python daily_job.py --dry-run  # generate next-day menu from sample data
```

## Modules
| File | Role |
|---|---|
| `config.py` / `db.py` | profile + targets + key loading / SQLite schema (8 tables) |
| `rule_engine.py` | decides next-day type (A / B / refeed / diet-break) from check-in + trend |
| `menu_generator.py` | next-day menu card (Gemini, template fallback) |
| `sheets.py` | Google Sheet read (gviz CSV, no service account) |
| `daily_job.py` | daily orchestration (21:05) → menu email |
| `weekly_analysis.py` / `research.py` / `weekly_job.py` | stall + TDEE recompute / paper fetch / weekly report email (Sun 09:00) |
| `make_docs.py` | 18-week plan + shopping list → `docs/` |
| `form.py` | local check-in form (`http://localhost:8765`) → instant menu |

Setup & keys: [SETUP.md](SETUP.md) · Full plan / evidence: [PSMF-COACH.md](PSMF-COACH.md)

---

## 中文說明

個人化 PSMF（蛋白質節約型減脂）教練系統。每天回填一次（本機表單／Google 表單／Google Sheet），
自動生成**隔日完整菜單卡**並 email 給你；每週日抓最新論文＋趨勢、重算 TDEE、寄**週報**。
Python · SQLite · 全免費 API。

### 功能
- **每日**（21:05）：讀回填 → `rule_engine` 判隔日日型 → `menu_generator`（Gemini／template）→ email 菜單卡（每餐 macros／價格、水分、補劑、紅燈自檢、訓練提示）。
- **每週日**（09:00）：`weekly_analysis` 偵測停滯／減速、重算 TDEE；`research` 抓 PubMed／EuropePMC 論文 → `make_docs` 出 HTML → email 週報。
- **回填三選一**：本機表單 `form.py`（手機同 WiFi 可連）／ Google 表單（隨地填）／ Google Sheet 手動。
- **金鑰**：Gemini（免費，429 自動退 template）、Gmail SMTP 寄信、Google Sheet（gviz CSV 唯讀）。皆放 `~/.claude/secrets/`，`verify_setup.py` 一鍵檢查（不印金鑰值）。

### 隱私
個人健康資料（體重、體脂、菜單紀錄）只存在本機 `data/`（已 gitignore），不進 repo。這是**範本**，請自帶資料。

### 安裝
見 [SETUP.md](SETUP.md)；完整計畫、營養目標、實證依據見 [PSMF-COACH.md](PSMF-COACH.md)。
