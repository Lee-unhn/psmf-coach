"""P0：建表 + 寫入 2026-06-02 基線數據。可重複執行（INSERT OR REPLACE）。"""
from __future__ import annotations

import sys

import config
import db

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def main() -> None:
    db.init_db()
    with db.connect() as conn:
        db.upsert_body_metrics(conn, {
            "date": config.START_DATE.isoformat(),
            "weight": config.START_WEIGHT,
            "body_fat_pct": config.START_BODY_FAT_PCT,
            "fat_mass": config.START_FAT_MASS,
            "lbm": config.START_LBM,
            "visceral_fat": config.START_VISCERAL_FAT,
            "waist_cm": None,
        })
    bmr = config.bmr_mifflin(config.START_WEIGHT)
    tdee = config.tdee(config.START_WEIGHT)
    print("✅ DB 初始化完成：", config.DB_PATH)
    print(f"   基線 {config.START_WEIGHT}kg → 目標 {config.GOAL_WEIGHT}kg / {config.PLAN_WEEKS} 週")
    print(f"   BMR {bmr:.0f} kcal / TDEE {tdee:.0f} kcal / 攝取目標 {config.INTAKE_KCAL_TARGET} kcal")
    print(f"   蛋白目標 {config.PROTEIN_G_PER_DAY} g/天")


if __name__ == "__main__":
    main()
