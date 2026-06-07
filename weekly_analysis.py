"""P3：週趨勢分析 + BMR/TDEE 重算 + 調整建議。

吃 body_metrics / daily_log / research_papers，產生 summary 與 adjustments，
寫入 weekly_report + plan_adjustments。Gemini 可選（產敘事），無金鑰用規則。
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

import config
import db
import metabolism
import phases
import preferences
import research
from rule_engine import scheduled_event, _avg


def _week_no(today: date) -> int:
    return (today - config.START_DATE).days // 7 + 1


def build_summary(conn, today: date) -> dict:
    metrics = sorted(
        [dict(r) for r in conn.execute(
            "SELECT * FROM body_metrics WHERE weight IS NOT NULL ORDER BY date").fetchall()],
        key=lambda m: m["date"],
    )
    week_no = _week_no(today)
    start_w = config.START_WEIGHT
    latest_w = metrics[-1]["weight"] if metrics else start_w
    lost = start_w - latest_w
    weeks_elapsed = max((today - config.START_DATE).days / 7, 0.1)
    rate = lost / weeks_elapsed                       # kg/週
    to_goal = latest_w - config.GOAL_WEIGHT
    weeks_left_est = (to_goal / rate) if rate > 0.05 else None

    # 近 14 天停滯偵測
    recent14 = [m for m in metrics
                if m["date"] >= (today - timedelta(days=14)).isoformat()]
    plateau = (len(recent14) >= 3
               and (recent14[0]["weight"] - recent14[-1]["weight"]) < 0.3)

    bmr = config.bmr_mifflin(latest_w)
    tdee, tdee_src = metabolism.effective_tdee(conn, latest_w)

    # 接下來 7 天的排定事件
    upcoming = []
    for i in range(1, 8):
        ev = scheduled_event(today + timedelta(days=i))
        if ev:
            upcoming.append(((today + timedelta(days=i)).isoformat(), ev))

    with_papers = research.top_recent(conn, 6)

    week_start = (today - timedelta(days=7)).isoformat()
    week_cost = db.cost_since(conn, week_start)
    total_cost = db.cost_since(conn, config.START_DATE.isoformat())

    # 階段狀態（借鏡 titan）：現階段 + 距下一階段門檻 + 依從/能量閘門
    logs7 = db.recent_daily_logs(conn, 7)
    avg_adh = _avg([d.get("adherence") for d in logs7])
    avg_en = _avg([d.get("energy") for d in logs7])
    gate = phases.gate_status(latest_w, avg_adh, avg_en)
    phase_target = phases.day_target(gate["phase"], "B")
    prefs = preferences.learn_preferences(conn)   # 自我學習偏好

    return {
        "prefs": prefs,
        "phase": gate["phase"]["name"], "phase_desc": gate["phase"]["desc"],
        "phase_kcal": phase_target["kcal"], "phase_protein": phase_target["protein"],
        "next_phase": gate["next"]["name"] if gate["next"] else None,
        "to_gate_kg": gate["to_gate_kg"], "phase_note": gate["note"],
        "week_no": week_no, "today": today.isoformat(),
        "start_weight": start_w, "latest_weight": round(latest_w, 1),
        "lost": round(lost, 1), "rate": round(rate, 2),
        "to_goal": round(to_goal, 1),
        "weeks_left_est": round(weeks_left_est, 1) if weeks_left_est else None,
        "bmr": round(bmr), "tdee": round(tdee), "tdee_src": tdee_src,
        "plateau": plateau, "upcoming": upcoming,
        "papers": with_papers,
        "week_cost": week_cost, "total_cost": total_cost,
    }


def build_adjustments(summary: dict) -> list[dict]:
    """純規則調整建議；每項可附證據。"""
    adj = []
    # 1. 每週重算 TDEE（measured=實測反推；formula=資料不足退回公式）
    src = summary.get("tdee_src", "formula")
    basis = "實測體重趨勢反推" if src.startswith("measured") else "資料不足，暫用 Mifflin 公式"
    adj.append({
        "field": "tdee", "old_value": str(round(config.tdee(config.START_WEIGHT))),
        "new_value": f"{summary['tdee']}（{basis}）",
        "reason": f"TDEE 估計法：{src}。" + ("等 ≥3 次每週量測、跨距≥14 天才切換成實測。" if src == "formula" else "已用真實數據反推。"),
    })
    # 2. 停滯處理
    if summary["plateau"]:
        adj.append({
            "field": "plateau_action", "old_value": "PSMF 持續",
            "new_value": "插入碳水回補日 / 評估飲食假期",
            "reason": "近 14 天體重停滯。優先回補而非再砍熱量（已近 PSMF 下限 850kcal）。",
        })
    # 3. 減速過快保護
    if summary["rate"] > 1.9:
        adj.append({
            "field": "rate_guard", "old_value": f"{summary['rate']}kg/週",
            "new_value": "增加固體餐日 / 確認蛋白達 150g",
            "reason": "減速過快，保護肌肉與電解質，避免膽結石風險。",
        })
    # 4. 進度落後則建議延長
    if summary["weeks_left_est"] and summary["week_no"] + summary["weeks_left_est"] > config.PLAN_WEEKS + 2:
        adj.append({
            "field": "timeline", "old_value": f"{config.PLAN_WEEKS} 週",
            "new_value": f"預估約 {summary['week_no'] + summary['weeks_left_est']:.0f} 週",
            "reason": "依目前速率，建議延長時間軸而非硬壓熱量。",
        })
    return adj


def persist(conn, summary: dict, adjustments: list[dict], email_status: str) -> None:
    now = datetime.now().isoformat(timespec="seconds")
    conn.execute(
        "INSERT OR REPLACE INTO weekly_report "
        "(week_no, sent_at, summary, adjustments, email_status) VALUES (?,?,?,?,?)",
        (summary["week_no"], now,
         f"W{summary['week_no']}: 已減 {summary['lost']}kg / 距目標 {summary['to_goal']}kg / 速率 {summary['rate']}kg/週",
         "; ".join(a["field"] for a in adjustments), email_status),
    )
    for a in adjustments:
        conn.execute(
            "INSERT INTO plan_adjustments (date, field, old_value, new_value, reason, evidence_paper_id) "
            "VALUES (?,?,?,?,?,?)",
            (summary["today"], a["field"], a["old_value"], a["new_value"], a["reason"], None),
        )
