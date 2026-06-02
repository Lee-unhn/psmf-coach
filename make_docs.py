"""P6：產出 18 週週曆 + 採購清單 markdown，寫到 docs/。

週曆依 rule_engine 的排定事件 + 預設 A/B 輪替推算；採購清單含每週消耗估算。
  python make_docs.py
"""
from __future__ import annotations

import sys
from datetime import timedelta

import config
from rule_engine import scheduled_event

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

DOCS = config.BASE_DIR / "docs"
DOCS.mkdir(exist_ok=True)


def _day_type(d) -> str:
    ev = scheduled_event(d)
    if ev:
        return ev
    days = (d - config.START_DATE).days
    return "B" if days % 3 == 2 else "A"


def build_calendar() -> str:
    rows = []
    total_days = config.PLAN_WEEKS * 7
    weekly_rate = round((config.START_WEIGHT - config.GOAL_WEIGHT) / config.PLAN_WEEKS, 2)
    for wk in range(config.PLAN_WEEKS):
        start = config.START_DATE + timedelta(days=wk * 7)
        end = start + timedelta(days=6)
        types = [_day_type(start + timedelta(days=i)) for i in range(7)]
        n_a, n_b = types.count("A"), types.count("B")
        refeeds = [start + timedelta(days=i) for i in range(7)
                   if scheduled_event(start + timedelta(days=i)) == "refeed"]
        is_break = any(scheduled_event(start + timedelta(days=i)) == "diet_break"
                       for i in range(7))

        if is_break:
            content = "🟦 **飲食假期**（吃到維持熱量 5–7 天）"
            note = "保肌 + 逆轉代謝下修 (MATADOR)"
            target_w = "持平"
        else:
            content = f"PSMF：{n_a} 全乳清日 + {n_b} 固體日"
            note = ("🔁 回補日 " + ", ".join(d.strftime("%m/%d") for d in refeeds)) if refeeds else "—"
            tw = config.START_WEIGHT - weekly_rate * (wk + 1)
            target_w = f"~{tw:.1f} kg"

        rows.append(f"| W{wk+1} | {start.strftime('%m/%d')}–{end.strftime('%m/%d')} "
                    f"| {content} | {note} | {target_w} |")

    return f"""# PSMF 18 週週曆

> 起始 {config.START_DATE.isoformat()} · {config.START_WEIGHT}kg → 目標 {config.GOAL_WEIGHT}kg
> 平均速率 {weekly_rate} kg/週（前段含水分較快、後段較慢屬正常）。
> A=全乳清日 / B=2乳清+1固體日 / 回補=碳水升至近維持 / 飲食假期=W{config.DIET_BREAK_WEEK} 維持熱量。
> 此為預設排程；每日實際菜單由系統依你回填動態微調。

| 週 | 日期 | 內容 | 重點 | 目標體重(指引) |
|---|---|---|---|---|
{chr(10).join(rows)}

> ⚠️ 目標體重僅為**指引**，非每週硬指標。落後就延長時間軸，不硬砍熱量。
> 飲食假期（W{config.DIET_BREAK_WEEK}）不可省略 — 是保肌與長期成功的關鍵。
"""


def build_shopping() -> str:
    scoops_per_week = 35
    tubs = round(scoops_per_week * 30 / 1000 / 7 * 7)  # ~1kg/週
    return f"""# PSMF 採購清單

> 可印出帶去買。份量為一週估算（依 A/B 輪替）。

## 🥤 常備 / 自備（每週）
| 品項 | 量 | 備註 |
|---|---|---|
| 乳清蛋白 | ~{scoops_per_week} 匙/週（約 1kg 罐/週） | 主食，挑高蛋白低糖 |
| 橄欖油 | 小瓶 | 每餐 5ml |

## 🛒 全聯 / 超商（每週）
| 品項 | 量 |
|---|---|
| 即食鮭魚 | 2–3 片 |
| 舒肥雞胸即食 | 3–4 包 |
| 酪梨 | 3–4 顆 |
| 杏仁果 | 1 包（分裝每次 10 顆） |
| 無糖豆漿 | 3 瓶 |
| 茶葉蛋 | 5–7 顆 |
| 水煮鮪魚罐 | 2–3 罐 |
| 生菜沙拉 / 燙青菜 | 每日 |

## 🏬 Costco（每 1–2 週）
| 品項 | 量 |
|---|---|
| 雞胸肉 | 1 大包（分裝冷凍，每份 250g） |
| 冷凍花椰菜 | 1 大包 |
| 冷凍三色蔬菜 | 1 大包 |
| 燕麥 | 1 包（回補/假期用） |

## 💊 補劑（每月一次補貨）
| 品項 | 月量 | 等級 |
|---|---|---|
| 電解質粉（含鈉/鉀/鎂） | 30 包 | 🔴 必需 |
| 甘胺酸鎂 400mg | 30 顆 | 🔴 |
| 綜合 B 群 | 30 顆 | 🔴 |
| 魚油 Omega-3 | 60 顆 | 🔴 必需脂肪 |
| 綜合維他命 | 30 份 | 🔴 |
| 維他命 D3 2000IU | 30 顆 | 🟠 |
| 洋車前子粉 | 1 罐 | 🟠 防便秘 |
| 肌酸（一水） | 1 罐 | 🟢 保力量 |

> 🔴 電解質是 PSMF 的「藥」等級必需品，最先補、不可斷貨。
"""


def main() -> None:
    cal = DOCS / "18週週曆.md"
    shop = DOCS / "採購清單.md"
    cal.write_text(build_calendar(), encoding="utf-8")
    shop.write_text(build_shopping(), encoding="utf-8")
    print(f"✅ 已產出：\n   {cal}\n   {shop}")


if __name__ == "__main__":
    main()
