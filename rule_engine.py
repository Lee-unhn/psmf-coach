"""動態規則引擎：依「前一日回填 + 近期趨勢」決定隔日菜單。

階段由現體重自動決定（phases），熱量/碳水隨體重往上帶。輸出 Decision 餵給 menu_generator。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import config
import phases


@dataclass
class Decision:
    day_type: str          # 'B' | 'refeed' | 'diet_break'
    kcal_target: float
    protein_target: float
    carb_target: float
    fat_target: float
    phase_name: str
    reason: str
    flag_for_weekly: bool = False


def _mk(day_type: str, phase: dict, reason: str, flag: bool = False,
        maintenance: float | None = None) -> Decision:
    t = phases.day_target(phase, day_type)
    if day_type == "refeed" and maintenance:
        return Decision(day_type, round(maintenance * 0.95), phase["protein"], 180, 40, phase["name"], reason, flag)
    if day_type == "diet_break" and maintenance:
        return Decision(day_type, round(maintenance), phase["protein"], 200, 50, phase["name"], reason, flag)
    return Decision(day_type, t["kcal"], t["protein"], t["carb"], t["fat"], phase["name"], reason, flag)


def scheduled_event(target: date) -> str | None:
    days = (target - config.START_DATE).days
    if days < 0:
        return None
    db_start = (config.DIET_BREAK_WEEK - 1) * 7
    if db_start <= days < db_start + config.DIET_BREAK_DAYS:
        return "diet_break"
    if days > 0 and days % config.REFEED_INTERVAL_DAYS == 0:
        return "refeed"
    return None


def _avg(values: list) -> float | None:
    vals = [v for v in values if v is not None]
    return sum(vals) / len(vals) if vals else None


def _weight_stalled(body_metrics: list[dict]) -> bool:
    weights = [m["weight"] for m in body_metrics if m.get("weight") is not None]
    if len(weights) < 5:
        return False
    newest, oldest = weights[0], weights[-1]
    return (oldest - newest) < 0.2


def decide_next_day(target: date, daily_logs: list[dict],
                    body_metrics: list[dict], current_weight: float) -> Decision:
    """daily_logs / body_metrics 皆為最新在前 (DESC)。階段由現體重自動決定。"""
    maintenance = config.tdee(current_weight)
    phase = phases.current_phase(current_weight)

    event = scheduled_event(target)
    if event == "diet_break":
        return _mk("diet_break", phase,
                   "排定飲食假期：吃到維持熱量 5–7 天，保肌 + 逆轉代謝下修 (MATADOR)。",
                   maintenance=maintenance)
    if event == "refeed":
        return _mk("refeed", phase,
                   "排定碳水回補日：升碳水至近維持，補充肝醣 + 提升依從性。",
                   maintenance=maintenance)

    last3 = daily_logs[:3]
    avg_energy = _avg([d.get("energy") for d in last3])
    avg_hunger = _avg([d.get("hunger") for d in last3])
    if last3 and ((avg_energy is not None and avg_energy <= 2)
                  or (avg_hunger is not None and avg_hunger >= 4)):
        return _mk("B", phase,
                   f"[{phase['name']}] 近 3 日能量低/飢餓高 → 固體餐日 + 注意睡眠。")

    avg_adherence = _avg([d.get("adherence") for d in daily_logs[:7]])
    flag = bool(_weight_stalled(body_metrics) and avg_adherence and avg_adherence >= 4)
    stall = "（停滯，標記週日深析）" if flag else ""
    return _mk("B", phase, f"[{phase['name']}] {phase['desc']}。" + stall, flag=flag)
