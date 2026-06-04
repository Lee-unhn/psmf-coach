"""階段制度（借鏡 titan-coach）：隨體重自動升階，熱量/碳水隨體重往上帶。

門檻相對 GOAL_WEIGHT 自動適配任何使用者：
ATTACK(>目標+17) → CRUISE(目標+10..17) → STABILIZE(目標+3..10) → MAINTAIN(≤目標+3)。
"""
from __future__ import annotations

import config

_g = config.GOAL_WEIGHT
PHASES = [
    {"name": "ATTACK",    "weight_min": _g + 17, "protein": 180, "carb": 30,  "fat": 25,
     "block": 0, "desc": "積極減脂（高蛋白精瘦）"},
    {"name": "CRUISE",    "weight_min": _g + 10, "protein": 170, "carb": 90,  "fat": 45,
     "block": 1, "desc": "中度赤字，加回部分碳水"},
    {"name": "STABILIZE", "weight_min": _g + 3,  "protein": 160, "carb": 140, "fat": 55,
     "block": 2, "desc": "和緩赤字，正常三餐，拉訓練強度"},
    {"name": "MAINTAIN",  "weight_min": 0,       "protein": 150, "carb": 200, "fat": 70,
     "block": 3, "desc": "維持／逆向飲食，趨向目標體重"},
]


def kcal_of(protein: float, carb: float, fat: float) -> int:
    return round(protein * 4 + carb * 4 + fat * 9)


def current_phase(weight: float) -> dict:
    for p in PHASES:
        if weight > p["weight_min"]:
            return p
    return PHASES[-1]


def next_phase(phase: dict) -> dict | None:
    i = PHASES.index(phase)
    return PHASES[i + 1] if i + 1 < len(PHASES) else None


def day_target(phase: dict, day_type: str = "B") -> dict:
    p, c, f = phase["protein"], phase["carb"], phase["fat"]
    return {"protein": p, "carb": c, "fat": f, "kcal": kcal_of(p, c, f)}


def gate_status(weight: float, avg_adherence, avg_energy) -> dict:
    p = current_phase(weight)
    nxt = next_phase(p)
    struggling = ((avg_adherence is not None and avg_adherence < 3)
                  or (avg_energy is not None and avg_energy < 2))
    if not nxt:
        return {"phase": p, "next": None, "to_gate_kg": 0.0,
                "struggling": struggling, "note": "已在最終階段（維持）。"}
    to_gate = round(max(0.0, weight - nxt["weight_min"]), 1)
    note = f"距 {nxt['name']}（≤{nxt['weight_min']}kg）還需減 {to_gate} kg。"
    if struggling:
        note += " ⚠️ 近期依從/能量偏低 → 先穩住，別再加激進度。"
    return {"phase": p, "next": nxt, "to_gate_kg": to_gate,
            "struggling": struggling, "note": note}
