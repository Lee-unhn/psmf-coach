"""動態規則引擎：依「前一日回填 + 近期趨勢」決定隔日日型。

對應 PSMF-COACH.md §7.3 流程圖。輸出 Decision，餵給 menu_generator。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import config


@dataclass
class Decision:
    day_type: str          # 'A' | 'B' | 'refeed' | 'diet_break'
    kcal_target: float
    protein_target: float
    reason: str
    flag_for_weekly: bool = False


def scheduled_event(target: date) -> str | None:
    """回傳 'diet_break' / 'refeed' / None。"""
    days = (target - config.START_DATE).days
    if days < 0:
        return None
    # 第 9 週飲食假期：week N 涵蓋 days [(N-1)*7, (N-1)*7 + 6]
    db_start = (config.DIET_BREAK_WEEK - 1) * 7
    if db_start <= days < db_start + config.DIET_BREAK_DAYS:
        return "diet_break"
    if days > 0 and days % config.REFEED_INTERVAL_DAYS == 0:
        return "refeed"
    return None


def _avg(values: list[float]) -> float | None:
    vals = [v for v in values if v is not None]
    return sum(vals) / len(vals) if vals else None


def _weight_stalled(body_metrics: list[dict]) -> bool:
    """近 ~7 日體重沒有下降趨勢（最新 vs 最舊差 < 0.2kg）。"""
    weights = [m["weight"] for m in body_metrics if m.get("weight") is not None]
    if len(weights) < 5:
        return False
    newest, oldest = weights[0], weights[-1]   # DESC 排序
    return (oldest - newest) < 0.2


def decide_next_day(
    target: date,
    daily_logs: list[dict],
    body_metrics: list[dict],
    current_weight: float,
) -> Decision:
    """daily_logs / body_metrics 皆為最新在前 (DESC)。"""
    maintenance = config.tdee(current_weight)

    event = scheduled_event(target)
    if event == "diet_break":
        return Decision(
            "diet_break", round(maintenance), config.PROTEIN_G_PER_DAY,
            "排定飲食假期：吃到維持熱量 5–7 天，保肌 + 逆轉代謝下修 (MATADOR)。",
        )
    if event == "refeed":
        return Decision(
            "refeed", round(maintenance * 0.95), config.PROTEIN_G_PER_DAY,
            "排定碳水回補日：升碳水至近維持，補充肝醣 + 提升依從性。",
        )

    last3 = daily_logs[:3]
    avg_energy = _avg([d.get("energy") for d in last3])
    avg_hunger = _avg([d.get("hunger") for d in last3])
    if last3 and ((avg_energy is not None and avg_energy <= 2)
                  or (avg_hunger is not None and avg_hunger >= 4)):
        return Decision(
            "B", config.DAY_TARGETS["B"]["kcal"], config.PROTEIN_G_PER_DAY,
            f"近 3 日能量低/飢餓高 (energy≈{avg_energy}, hunger≈{avg_hunger}) "
            "→ 固體餐日 + 熱量上緣 + 注意睡眠。",
        )

    avg_adherence = _avg([d.get("adherence") for d in daily_logs[:7]])
    if _weight_stalled(body_metrics) and avg_adherence and avg_adherence >= 4:
        return Decision(
            "A", config.DAY_TARGETS["A"]["kcal"], config.PROTEIN_G_PER_DAY,
            "體重停滯但依從佳 → 維持缺口，標記給週日深度分析（可能需回補或重算 TDEE）。",
            flag_for_weekly=True,
        )

    # 預設輪替：每第 3 天走固體 B 日，其餘全乳清 A 日
    days = (target - config.START_DATE).days
    if days % 3 == 2:
        return Decision(
            "B", config.DAY_TARGETS["B"]["kcal"], config.PROTEIN_G_PER_DAY,
            "輪替：固體餐日（2 乳清 + 1 雞胸餐）。",
        )
    return Decision(
        "A", config.DAY_TARGETS["A"]["kcal"], config.PROTEIN_G_PER_DAY,
        "輪替：全乳清日。",
    )
