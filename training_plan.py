"""家用器具（啞鈴 + 徒手）重訓計畫。VLCD 下走中低量、保肌優先。

3 個全身循環 A/B/C，目標每週 4 次；非訓練日走路 8–10k 步。
"""
from __future__ import annotations

import config

HOME_SESSIONS: dict[str, list[str]] = {
    "全身 A": [
        "啞鈴高腳杯深蹲 3×10",
        "啞鈴臥推/地板臥推 3×10",
        "啞鈴划船 3×12",
        "啞鈴羅馬尼亞硬舉 3×12",
        "棒式 3×40 秒",
    ],
    "全身 B": [
        "啞鈴分腿蹲 3×10/邊",
        "啞鈴站姿肩推 3×10",
        "啞鈴仰臥拉舉 3×12",
        "臀橋 3×15",
        "伏地挺身 3× 力竭",
    ],
    "全身 C": [
        "啞鈴硬舉 3×10",
        "上斜伏地挺身 3×12",
        "啞鈴二頭彎舉 + 推舉 3×12",
        "側棒式 3×30 秒/邊",
        "站姿提踵 3×20",
    ],
}
_ROTATION = list(HOME_SESSIONS)

# 訓練區塊（隨階段）：每週次數 + 焦點（借鏡 titan training-blocks）
_BLOCK = {
    0: (3, "動作學習 / 關節適應（重，RPE 6–7）"),
    1: (4, "肌肥大基礎（RPE 7–8）"),
    2: (4, "力量 + 體能（RPE 8，加間歇）"),
    3: (5, "表現 / 專項（2-a-day 可選）"),
}


def next_training_note(daily_logs: list[dict], block: int = 0) -> str:
    """daily_logs 最新在前；block 由現階段決定。回傳隔日訓練建議。"""
    days_target, focus = _BLOCK.get(block, _BLOCK[0])
    trained_last7 = sum(1 for d in daily_logs[:7] if d.get("trained"))
    trained_yesterday = bool(daily_logs and daily_logs[0].get("trained"))

    if trained_last7 >= days_target or trained_yesterday:
        return f"🚶 走路 8,000–10,000 步 + 充分休息（恢復日）。本區塊每週 {days_target} 練。"

    session = _ROTATION[trained_last7 % len(_ROTATION)]
    moves = "；".join(HOME_SESSIONS[session])
    return (f"🏋️ Block{block}·{focus}｜「{session}」：{moves}。組間休息 60–90 秒"
            f"（每週目標 {days_target} 練）。")
