"""P1 每日任務（每天 21:05 排程）：

1. 從 Google Sheet 讀今日回填 → 寫入 body_metrics / daily_log
2. 讀近期趨勢 → 規則引擎決定隔日日型
3. 生成隔日菜單（Gemini 或 template）+ 家用訓練提示
4. 寫入 menu_plan + 回寫 Sheet「隔日菜單」分頁

用法：
  python daily_job.py            # 正式（讀 Sheet 或 mock）
  python daily_job.py --dry-run  # 用內建範例輸入跑全流程（不需任何金鑰）
"""
from __future__ import annotations

import json
import sys
from datetime import date, datetime, timedelta

import config
import db
import emailer
import phases
import sheets
from menu_generator import generate_menu
from rule_engine import decide_next_day
from training_plan import next_training_note

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def _to_int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _to_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def ingest_log(conn, log: dict) -> str:
    """把 Sheet 一列寫進 body_metrics + daily_log。回傳該列日期。"""
    log_date = str(log.get("date") or date.today().isoformat())
    db.upsert_body_metrics(conn, {
        "date": log_date,
        "weight": _to_float(log.get("weight")),
        "body_fat_pct": _to_float(log.get("body_fat_pct")),
        "fat_mass": _to_float(log.get("fat_mass")),
        "lbm": _to_float(log.get("lbm")),
        "visceral_fat": _to_float(log.get("visceral_fat")),
        "waist_cm": _to_float(log.get("waist_cm")),
    })
    db.upsert_daily_log(conn, {
        "date": log_date,
        "trained": 1 if str(log.get("trained")).lower() in ("1", "true", "yes", "y", "是", "on", "有") else 0,
        "hunger": _to_int(log.get("hunger")),
        "energy": _to_int(log.get("energy")),
        "adherence": _to_int(log.get("adherence")),
        "notes": log.get("notes", ""),
    })
    _ingest_supplements(conn, log_date, log)
    return log_date


def _yn(v) -> int:
    return 1 if str(v).lower() in ("1", "true", "yes", "y", "是", "v", "✓", "on", "有") else 0


def _ingest_supplements(conn, log_date: str, log: dict) -> None:
    """選填：Sheet 若有補劑欄位（na_mg/k_mg/mg_mg/multivit/fishoil/creatine）就記錄電解質依從。
    沒有這些欄位則略過（不強迫改 Sheet）。"""
    supp_keys = ("na_mg", "k_mg", "mg_mg", "multivit", "fishoil", "creatine")
    if not any(k in log for k in supp_keys):
        return
    db.upsert_supplement_log(conn, {
        "date": log_date,
        "sodium_mg": _to_float(log.get("na_mg")),
        "potassium_mg": _to_float(log.get("k_mg")),
        "magnesium_mg": _to_float(log.get("mg_mg")),
        "multivit": _yn(log.get("multivit")),
        "fishoil": _yn(log.get("fishoil")),
        "creatine": _yn(log.get("creatine")),
    })


def _seed_mock() -> None:
    """--dry-run 用：若無 mock_log.json 就塞一筆今日範例。"""
    if sheets.MOCK_LOG.exists():
        return
    sample = [{
        "date": date.today().isoformat(),
        "weight": 100.0, "body_fat_pct": 30.0, "fat_mass": 30.0,
        "lbm": 65.0, "visceral_fat": 15, "waist_cm": 95,
        "trained": "yes", "hunger": 3, "energy": 3, "adherence": 5,
        "notes": "demo sample",
    }]
    sheets.MOCK_LOG.write_text(json.dumps(sample, ensure_ascii=False, indent=2), encoding="utf-8")


def generate_for_date(target, dry_run: bool = False) -> dict:
    """為指定日期生成菜單 → 記帳 → email。用最新的 DB 數據（不依賴某筆回填的日期）。"""
    db.init_db()
    with db.connect() as conn:
        daily_logs = db.recent_daily_logs(conn, 7)
        body_metrics = db.recent_body_metrics(conn, 14)
        current_weight = db.latest_weight(conn) or config.START_WEIGHT

        day_index = (target - config.START_DATE).days + 1
        decision = decide_next_day(target, daily_logs, body_metrics, current_weight)
        block = phases.current_phase(current_weight)["block"]
        training_note = next_training_note(daily_logs, block)
        menu, generated_by = generate_menu(decision, training_note, f"體重 {current_weight}kg", day_index)
        menu["daily_finding"] = db.pick_daily_paper(conn, day_index)  # 每日一則權威新知

        db.upsert_menu_plan(conn, {
            "date": target.isoformat(), "day_type": decision.day_type,
            "kcal_target": decision.kcal_target, "protein_target": decision.protein_target,
            "menu_json": json.dumps(menu, ensure_ascii=False), "training_note": training_note,
            "reason": decision.reason, "generated_by": generated_by,
        })
        db.upsert_cost_log(conn, {
            "date": target.isoformat(), "food_cost": menu["food_cost"],
            "supplement_cost": menu["supp_cost"], "total_cost": menu["total_cost"],
        })

    summary = f"日型 {decision.day_type}｜{decision.reason}（by {generated_by}）"
    email_status = emailer.send_menu(target.isoformat(), menu, summary, dry_run=dry_run)
    return {"target": target, "day_index": day_index, "decision": decision,
            "menu": menu, "generated_by": generated_by, "summary": summary,
            "email_status": email_status, "training_note": training_note}


def process_log(log: dict, dry_run: bool = False) -> dict:
    """表單即時用：吃一筆回填 → 寫 DB → 生「該回填日 + 1」菜單 + email。"""
    db.init_db()
    with db.connect() as conn:
        log_date = ingest_log(conn, log)
    target = datetime.strptime(log_date, "%Y-%m-%d").date() + timedelta(days=1)
    return generate_for_date(target, dry_run=dry_run)


def run(dry_run: bool = False) -> None:
    """每日排程：有新回填就吃進 DB 更新數據，然後**固定寄「明天」菜單**（即使今天沒填也照寄）。"""
    db.init_db()
    provider = sheets.MockSheet() if dry_run else sheets.get_provider()
    if dry_run:
        _seed_mock()

    log = provider.read_today_log()
    if log:
        with db.connect() as conn:
            ingest_log(conn, log)
        print("✅ 已讀取最新回填並更新數據。")
    else:
        print("ℹ️ 今天沒新回填 → 用最新已知數據生成明天菜單。")

    target = date.today() + timedelta(days=1)
    r = generate_for_date(target, dry_run=dry_run)
    try:
        provider.write_menu(r["target"].isoformat(), r["menu"], r["summary"])
    except Exception as exc:  # noqa: BLE001
        print(f"[sheets] 回寫略過：{exc}")

    a = r["menu"]["achieved"]
    print(f"✅ 已寄 {r['target']} 菜單 DAY{r['day_index']} Phase{r['decision'].day_type}"
          f"（{r['generated_by']}）｜email={r['email_status']}")
    print(f"   達成 {a['kcal']} kcal / P{a['protein']} C{a['carb']} F{a['fat']} / NT${a['cost']}")
    if r["decision"].flag_for_weekly:
        print("   🔎 已標記給週日深度分析。")


if __name__ == "__main__":
    run(dry_run="--dry-run" in sys.argv)
