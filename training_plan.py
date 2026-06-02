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


def next_training_note(daily_logs: list[dict]) -> str:
    """daily_logs 最新在前。回傳隔日訓練建議。"""
    trained_last7 = sum(1 for d in daily_logs[:7] if d.get("trained"))
    trained_yesterday = bool(daily_logs and daily_logs[0].get("trained"))

    if trained_last7 >= config.TRAINING_DAYS_PER_WEEK or trained_yesterday:
        return "🚶 走路 8,000–10,000 步 + 充分休息（恢復日）。"

    session = _ROTATION[trained_last7 % len(_ROTATION)]
    moves = "；".join(HOME_SESSIONS[session])
    return f"🏋️ 重訓「{session}」：{moves}。組間休息 60–90 秒。"
