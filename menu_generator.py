"""隔日完整菜單生成。結構化菜單由食材庫 deterministic 組出（卡路里/價格不靠 LLM 幻覺）；
Gemini 只負責一句「教練提示」，缺 key 或額度用盡就省略。

回傳 (menu_dict, generated_by)。menu_dict 為 emailer.render_menu_html 吃的完整結構。
"""
from __future__ import annotations

import config
import foods
from foods import line_item, total
from rule_engine import Decision

# 各日型的餐點組合（time, meal_name, [(food_key, qty)]）。B 兩變體輪替增加變化。
_COMPOSITIONS: dict[str, list] = {
    "A": [  # 全乳清 + 精瘦蛋白（保留備用）
        ("07:00", "🌅 早餐", [("whey_2", 1)]),
        ("12:30", "🌞 午餐", [("whey_2", 1), ("broccoli", 1)]),
        ("19:00", "🌙 晚餐", [("whey_2", 1), ("tuna_can", 1), ("sousvide_chicken", 1), ("veg_boiled", 1)]),
    ],
    "B0": [  # Costco 雞胸 + 鮭魚：精瘦，僅留必需脂肪
        ("07:00", "🌅 早餐", [("whey_2", 1)]),
        ("12:30", "🌞 午餐", [("costco_chicken_250", 1), ("broccoli", 1)]),
        ("19:00", "🌙 晚餐", [("salmon_ready", 1), ("sousvide_chicken", 1), ("veg_boiled", 1), ("whey_2", 1), ("whey_1", 1)]),
    ],
    "B1": [  # 雞胸 + 鮪魚 + 蛋：最精瘦
        ("07:00", "🌅 早餐", [("whey_2", 1), ("tea_egg", 1)]),
        ("12:30", "🌞 午餐", [("costco_chicken_250", 1), ("broccoli", 1)]),
        ("19:00", "🌙 晚餐", [("tuna_can", 1), ("sousvide_chicken", 1), ("veg_boiled", 1), ("whey_2", 1), ("whey_1", 1)]),
    ],
    "refeed": [
        ("07:00", "🌅 早餐", [("whey_2", 1), ("oats_40", 1)]),
        ("12:30", "🌞 午餐", [("sousvide_chicken", 1), ("rice_bowl", 1), ("veg_boiled", 1), ("fruit", 1)]),
        ("19:00", "🌙 晚餐", [("salmon_ready", 1), ("sweet_potato", 1), ("broccoli", 1)]),
    ],
    "diet_break": [
        ("07:00", "🌅 早餐", [("eggs_2", 1), ("soy_milk", 1), ("oats_40", 1)]),
        ("12:30", "🌞 午餐", [("costco_chicken_250", 1), ("brown_rice", 1), ("veg_boiled", 1)]),
        ("19:00", "🌙 晚餐", [("salmon_ready", 1), ("sweet_potato", 1), ("broccoli", 1), ("fruit", 1)]),
    ],
}

_TITLES = {
    "A": "全乳清日 · 低脂",
    "B0": "鮭魚 + 雞胸 · 精瘦",
    "B1": "Costco 雞胸 + 鮪魚 + 蛋",
    "refeed": "碳水回補日",
    "diet_break": "飲食假期 · 維持熱量",
}


def _coach_tip(decision: Decision, context: str) -> str | None:
    if not config.GEMINI_API_KEY:
        return None
    try:
        from google import genai
        client = genai.Client(api_key=config.GEMINI_API_KEY)
        prompt = (f"你是 PSMF 減脂教練。根據情況用繁體中文寫 1 句（30 字內）今日提醒，"
                  f"語氣務實不浮誇。情況：{decision.reason}；{context}")
        return client.models.generate_content(
            model=config.GEMINI_MODEL, contents=prompt).text.strip()
    except Exception:  # noqa: BLE001
        return None


def _fill_macros(meals: list, target: dict) -> None:
    """精瘦蛋白底 + 依階段把碳水/脂肪補到目標（高階段才會補）。就地改 meals。"""
    ach = total([i for m in meals for i in m["items"]])
    extra = []
    carb_gap = target["carb"] - ach["carb"]
    while carb_gap > 25 and len(extra) < 6:
        key = "rice_bowl" if carb_gap > 45 else "sweet_potato"
        extra.append(key)
        carb_gap -= foods.FOODS[key]["carb"]
    fat_gap = target["fat"] - ach["fat"]
    while fat_gap > 9 and len(extra) < 9:
        key = "avocado_half" if fat_gap > 10 else "olive_oil_5"
        extra.append(key)
        fat_gap -= foods.FOODS[key]["fat"]
    if extra:
        items = [line_item(k, 1) for k in extra]
        meals.append({"time": "加餐", "name": "🍚 補碳/脂", "items": items, "subtotal": total(items)})


_TITLE_TO_KEY = {v: k for k, v in _TITLES.items()}


def generate_menu(decision: Decision, training_note: str, context: str = "",
                  day_index: int = 1, prefer_title: str | None = None) -> tuple[dict, str]:
    dt = decision.day_type
    comp_key = dt
    if dt == "B":
        # 自我學習：多數天用「最依從」的變體，其餘維持變化避免單調
        pref_key = _TITLE_TO_KEY.get(prefer_title) if prefer_title else None
        if pref_key in ("B0", "B1") and day_index % 3 != 0:
            comp_key = pref_key
        else:
            comp_key = "B0" if day_index % 2 == 0 else "B1"

    meals = []
    for time, name, parts in _COMPOSITIONS[comp_key]:
        items = [line_item(k, q) for k, q in parts]
        meals.append({"time": time, "name": name, "items": items, "subtotal": total(items)})

    target = {"kcal": round(decision.kcal_target), "protein": decision.protein_target,
              "carb": decision.carb_target, "fat": decision.fat_target}
    _fill_macros(meals, target)   # 高階段(CRUISE+)補碳水/脂肪到目標
    achieved = total([i for m in meals for i in m["items"]])

    tip = _coach_tip(decision, context)
    generated_by = "template+gemini-tip" if tip else "template"

    supplements = [{"name": n, "timing": t, "cost": c, "tier": tier}
                   for n, t, c, tier in config.SUPPLEMENT_PLAN]
    supp_cost = sum(s["cost"] for s in supplements)
    food_cost = achieved["cost"]
    total_cost = food_cost + supp_cost

    menu = {
        "day_index": day_index,
        "phase": dt,
        "diet_phase": decision.phase_name,
        "title": _TITLES.get(comp_key, ""),
        "target": target,
        "achieved": achieved,
        "water_l": config.WATER_L,
        "water_times": config.WATER_TIMES,
        "meals": meals,
        "supplements": supplements,
        "supp_timing_note": config.SUPP_TIMING_NOTE,
        "food_cost": food_cost,
        "supp_cost": supp_cost,
        "total_cost": total_cost,
        "red_flags": config.RED_FLAGS,
        "stop_signals": config.STOP_SIGNALS,
        "training_note": training_note,
        "reason": decision.reason,
        "coach_tip": tip,
        # 給 DB/CLI 用的精簡欄位
        "protein_g": achieved["protein"],
        "kcal": achieved["kcal"],
        "notes": (tip or decision.reason) + f"\n訓練：{training_note}",
    }
    return menu, generated_by
