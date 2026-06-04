"""自我學習：從歷史自動學出菜單偏好（最依從 / 最省 / 最常排），回饋到隔日菜單選擇。

資料來源：
- `menu_plan`（每天排出的菜單 + 標題 + 品項）
- `daily_log.adherence`（依從度 1-5）
- `cost_log.total_cost`（每日花費）

註：系統不追蹤「實際吃下肚」（無 food_log），所以「最常吃」= 最常被排進菜單的品項。
資料越多越準；前 1–2 週樣本少僅供參考。
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict


def learn_preferences(conn, min_samples: int = 2) -> dict:
    rows = conn.execute(
        "SELECT mp.date, mp.menu_json, dl.adherence, cl.total_cost "
        "FROM menu_plan mp "
        "LEFT JOIN daily_log dl ON dl.date = mp.date "
        "LEFT JOIN cost_log cl ON cl.date = mp.date "
        "ORDER BY mp.date"
    ).fetchall()

    adh: dict[str, list] = defaultdict(list)
    cost: dict[str, list] = defaultdict(list)
    food_ctr: Counter = Counter()
    costs_all: list = []

    for r in rows:
        try:
            menu = json.loads(r["menu_json"])
        except Exception:  # noqa: BLE001
            continue
        title = menu.get("title") or "?"
        if r["adherence"] is not None:
            adh[title].append(r["adherence"])
        if r["total_cost"] is not None:
            cost[title].append(r["total_cost"])
            costs_all.append(r["total_cost"])
        for m in menu.get("meals", []):
            for it in m.get("items", []):
                name = str(it.get("item", "")).split(" ×")[0].strip()
                if name:
                    food_ctr[name] += 1

    adh_avg = {t: round(sum(v) / len(v), 1) for t, v in adh.items() if len(v) >= min_samples}
    cost_avg = {t: round(sum(v) / len(v)) for t, v in cost.items() if v}
    return {
        "n_days": len(rows),
        "adherence_by_menu": adh_avg,
        "cost_by_menu": cost_avg,
        "best_adhered": max(adh_avg, key=adh_avg.get) if adh_avg else None,
        "cheapest": min(cost_avg, key=cost_avg.get) if cost_avg else None,
        "avg_cost": round(sum(costs_all) / len(costs_all)) if costs_all else None,
        "top_foods": food_ctr.most_common(6),
    }
