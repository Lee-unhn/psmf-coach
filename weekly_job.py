"""每週日 09:00 排程：抓論文 → 週趨勢分析 → 寄 Email 週報。

用法：
  python weekly_job.py            # 正式（嘗試抓論文 + 寄信）
  python weekly_job.py --dry-run  # 不寄信，HTML 存 data/last_report.html
"""
from __future__ import annotations

import sys
from datetime import date

import db
import emailer
import research
import weekly_analysis

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def run(dry_run: bool = False, today: date | None = None) -> None:
    today = today or date.today()
    db.init_db()

    # P2：抓最新論文（離線失敗會自動退回 DB 既有 / seed）
    research.collect_and_store()

    # P3：分析
    with db.connect() as conn:
        summary = weekly_analysis.build_summary(conn, today)
        adjustments = weekly_analysis.build_adjustments(summary)

        # P4：寄信
        html = emailer.render_html(summary, adjustments)
        status = emailer.send_report(
            f"PSMF 週報 W{summary['week_no']} — 已減 {summary['lost']}kg", html, dry_run)

        weekly_analysis.persist(conn, summary, adjustments, status)

    print(f"✅ 週報 W{summary['week_no']}：已減 {summary['lost']}kg / "
          f"距目標 {summary['to_goal']}kg / 速率 {summary['rate']}kg/週")
    print(f"   調整 {len(adjustments)} 項；論文 {len(summary['papers'])} 篇；email={status}")
    for a in adjustments:
        print(f"   - {a['field']}: {a['new_value']}（{a['reason']}）")


if __name__ == "__main__":
    run(dry_run="--dry-run" in sys.argv)
