"""用實測體重趨勢反推「有效 TDEE」（比公式準，隨每週量測自動更新）。

TDEE ≈ 期間平均攝取 + 體重變化換算的每日赤字（1kg 體組織 ≈ 7700 kcal）。
資料不足（點數 < 3 或跨距 < 14 天）→ 退回 Mifflin 公式（誠實標註）。
注意：用「計畫攝取」近似實際攝取（無實吃記錄）；前 2 週含水分故先不採信。
"""
from __future__ import annotations

from datetime import date as _date

import config

KCAL_PER_KG = 7700
MIN_POINTS = 3      # 每週量一次 → 至少 3 次（約 2 週）才採信
MIN_SPAN_DAYS = 14  # 跨距 ≥14 天，讓初期水分洗掉


def effective_tdee(conn, weight: float) -> tuple[int, str]:
    """回傳 (tdee, source)。source = 'measured(...)' 或 'formula'。"""
    formula = round(config.tdee(weight))
    rows = [dict(r) for r in conn.execute(
        "SELECT date, weight FROM body_metrics WHERE weight IS NOT NULL ORDER BY date").fetchall()]
    if len(rows) < MIN_POINTS:
        return formula, "formula"
    try:
        span = (_date.fromisoformat(rows[-1]["date"]) - _date.fromisoformat(rows[0]["date"])).days
    except Exception:  # noqa: BLE001
        return formula, "formula"
    if span < MIN_SPAN_DAYS:
        return formula, "formula"
    intakes = [r[0] for r in conn.execute(
        "SELECT kcal_target FROM menu_plan WHERE date >= ? AND date <= ? AND kcal_target IS NOT NULL",
        (rows[0]["date"], rows[-1]["date"])).fetchall()]
    if not intakes:
        return formula, "formula"
    avg_intake = sum(intakes) / len(intakes)
    dw = rows[0]["weight"] - rows[-1]["weight"]        # 減重(正)
    deficit_per_day = dw * KCAL_PER_KG / span
    tdee = round(avg_intake + deficit_per_day)
    tdee = max(1500, min(3500, tdee))                  # 防離譜雜訊
    return tdee, f"measured({span}天/{len(rows)}點)"
