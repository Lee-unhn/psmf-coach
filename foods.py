"""食材資料庫（台灣超商/全聯/Costco 估值）。每項：kcal, protein, carb, fat, cost(NT$), portion, source。

菜單由 (food_key, qty) 組合，總量自動加總 → 卡片顯示「目標 vs 預計達成」。
數值為合理估計，實品包裝會有出入。
"""
from __future__ import annotations

FOODS: dict[str, dict] = {
    # 蛋白主力
    "whey_2":        {"name": "乳清蛋白 2 匙", "portion": "60g · 自備", "source": "自備",
                      "kcal": 240, "protein": 44, "carb": 6, "fat": 4, "cost": 50},
    "whey_1":        {"name": "乳清蛋白 1 匙", "portion": "30g · 自備", "source": "自備",
                      "kcal": 120, "protein": 22, "carb": 3, "fat": 2, "cost": 25},
    "salmon_ready":  {"name": "即食鮭魚", "portion": "1 片 ~100g", "source": "全聯",
                      "kcal": 180, "protein": 22, "carb": 0, "fat": 10, "cost": 85},
    "sousvide_chicken": {"name": "舒肥雞胸即食", "portion": "1 包 ~100g", "source": "7-11/全聯",
                      "kcal": 130, "protein": 24, "carb": 1, "fat": 3, "cost": 60},
    "costco_chicken_250": {"name": "Costco 雞胸肉", "portion": "250g · 氣炸/水煮", "source": "Costco",
                      "kcal": 275, "protein": 55, "carb": 0, "fat": 6, "cost": 60},
    "tuna_can":      {"name": "水煮鮪魚罐", "portion": "1 罐 ~100g", "source": "全聯/7-11",
                      "kcal": 90, "protein": 20, "carb": 0, "fat": 1, "cost": 45},
    "tea_egg":       {"name": "茶葉蛋", "portion": "1 顆", "source": "7-11",
                      "kcal": 70, "protein": 6, "carb": 1, "fat": 5, "cost": 13},
    "eggs_2":        {"name": "水煮蛋 2 顆", "portion": "2 顆", "source": "自備/超商",
                      "kcal": 140, "protein": 12, "carb": 1, "fat": 10, "cost": 20},
    "soy_milk":      {"name": "無糖豆漿", "portion": "450ml", "source": "全聯/7-11",
                      "kcal": 130, "protein": 13, "carb": 8, "fat": 5, "cost": 25},
    "yogurt_protein": {"name": "無糖高蛋白優格", "portion": "1 杯", "source": "全聯",
                      "kcal": 100, "protein": 10, "carb": 8, "fat": 3, "cost": 45},
    # 蔬菜
    "veg_boiled":    {"name": "自助餐燙青菜無油", "portion": "1 碟", "source": "自助餐/便當店",
                      "kcal": 50, "protein": 3, "carb": 8, "fat": 1, "cost": 35},
    "broccoli":      {"name": "花椰菜", "portion": "1 份 ~150g", "source": "Costco/全聯",
                      "kcal": 50, "protein": 4, "carb": 10, "fat": 0, "cost": 25},
    "salad":         {"name": "生菜沙拉(醬另計)", "portion": "1 盒", "source": "7-11",
                      "kcal": 60, "protein": 3, "carb": 9, "fat": 1, "cost": 45},
    # 必需脂肪
    "avocado_half":  {"name": "酪梨半顆", "portion": "半顆 ~80g", "source": "全聯",
                      "kcal": 120, "protein": 1.5, "carb": 6, "fat": 11, "cost": 30},
    "olive_oil_5":   {"name": "橄欖油 5ml", "portion": "5ml · 自帶", "source": "自備",
                      "kcal": 45, "protein": 0, "carb": 0, "fat": 5, "cost": 3},
    "almonds_10":    {"name": "杏仁果 10 顆", "portion": "10 顆 ~12g", "source": "全聯/7-11",
                      "kcal": 70, "protein": 2.5, "carb": 2, "fat": 6, "cost": 15},
    # 回補/假期碳水
    "oats_40":       {"name": "燕麥 40g", "portion": "40g", "source": "全聯/Costco",
                      "kcal": 150, "protein": 5, "carb": 27, "fat": 3, "cost": 10},
    "rice_bowl":     {"name": "白飯 1 碗", "portion": "~200g", "source": "自備/便當店",
                      "kcal": 280, "protein": 5, "carb": 62, "fat": 1, "cost": 15},
    "brown_rice":    {"name": "糙米飯 1 碗", "portion": "~200g", "source": "自備/便當店",
                      "kcal": 250, "protein": 6, "carb": 52, "fat": 2, "cost": 20},
    "sweet_potato":  {"name": "地瓜 1 條", "portion": "~150g", "source": "7-11/全聯",
                      "kcal": 130, "protein": 2, "carb": 30, "fat": 0, "cost": 20},
    "fruit":         {"name": "水果 1 份", "portion": "拳頭大", "source": "全聯",
                      "kcal": 60, "protein": 1, "carb": 15, "fat": 0, "cost": 20},
}

_MACROS = ("kcal", "protein", "carb", "fat", "cost")


def line_item(key: str, qty: float = 1) -> dict:
    """回傳一筆餐點項目（含份量、來源、營養、價格）。"""
    f = FOODS[key]
    suffix = f" ×{qty:g}" if qty != 1 else ""
    return {
        "item": f["name"] + suffix,
        "portion": f"{f['portion']} · {f['source']}",
        "kcal": round(f["kcal"] * qty),
        "protein": round(f["protein"] * qty, 1),
        "carb": round(f["carb"] * qty, 1),
        "fat": round(f["fat"] * qty, 1),
        "cost": round(f["cost"] * qty),
    }


def total(items: list[dict]) -> dict:
    return {m: round(sum(i[m] for i in items), 1) for m in _MACROS}
