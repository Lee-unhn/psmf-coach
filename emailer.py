"""P4：SMTP Gmail 週報。dry-run 時把 HTML 存檔不寄出。"""
from __future__ import annotations

import smtplib
import ssl
from email.mime.text import MIMEText

import config

LAST_REPORT = config.DATA_DIR / "last_report.html"
LAST_MENU = config.DATA_DIR / "last_menu.html"


def _send_html(subject: str, html: str, dry_run: bool = False) -> str:
    if dry_run or not config.GMAIL_APP_PASSWORD:
        return "dry-run" if dry_run else "未設 GMAIL_APP_PASSWORD"
    msg = MIMEText(html, "html", "utf-8")
    msg["Subject"] = subject
    msg["From"] = config.GMAIL_ADDRESS
    msg["To"] = config.REPORT_TO_EMAIL
    ctx = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ctx) as server:
        server.login(config.GMAIL_ADDRESS, config.GMAIL_APP_PASSWORD)
        server.send_message(msg)
    return "sent"


# --- 語意色票（每組: bg底色 / accent左色條·標題 / text內文）---
def _card(bg: str, accent: str, title_color: str, heading: str, body: str) -> str:
    return (f"<div style='background:{bg};border-left:4px solid {accent};border-radius:6px;"
            f"padding:12px 14px;margin:0 0 12px 0;'>"
            f"<div style='font-size:15px;font-weight:bold;color:{title_color};margin:0 0 8px 0;'>{heading}</div>"
            f"{body}</div>")


def _macro_row(label: str, tgt, ach, unit: str = "g", kind: str = "default") -> str:
    diff = round(ach - tgt, 1)
    tol = tgt * 0.10
    if kind == "protein":                       # 蛋白低於目標一律紅（保肌）；超標不罰
        ok = ach >= tgt - tol
        color, bg, mark = (("#2e7d32", "#e6f4ea", "✓") if ok else ("#c62828", "#fdecea", "▼"))
    else:
        if abs(diff) <= tol:
            color, bg, mark = "#2e7d32", "#e6f4ea", "✓"
        elif diff > 0:
            color, bg, mark = "#c62828", "#fdecea", "▲"
        else:
            color, bg, mark = "#d84315", "#fff3e0", "▼"
    sign = "" if mark == "✓" else f" {'+' if diff > 0 else ''}{diff}{unit}"
    return (f"<tr><td style='padding:6px 10px;color:#37474f'>{label}</td>"
            f"<td style='padding:6px 10px;color:#607d8b'>{tgt}{unit}</td>"
            f"<td style='padding:6px 10px;text-align:right'>"
            f"<span style='background:{bg};color:{color};font-weight:bold;padding:2px 8px;"
            f"border-radius:10px;white-space:nowrap'>{ach}{unit} {mark}{sign}</span></td></tr>")


def render_menu_html(menu_date: str, menu: dict, summary: str) -> str:
    import datetime as _dt
    try:
        wd = "一二三四五六日"[_dt.date.fromisoformat(menu_date).weekday()]
        date_line = f"{menu_date} (週{wd})"
    except Exception:  # noqa: BLE001
        date_line = menu_date

    t, a = menu["target"], menu["achieved"]
    phase = menu.get("phase", "A")
    dphase = menu.get("diet_phase", "")

    # Header（深靛 + Phase pill）
    header = (f"<div style='background:#1a237e;color:#fff;padding:14px 16px;border-radius:6px;margin:0 0 12px 0'>"
              f"<span style='font-size:18px;font-weight:bold'>PSMF · DAY {menu['day_index']}</span>"
              f"<span style='background:#3949ab;color:#fff;font-size:12px;font-weight:bold;"
              f"padding:2px 8px;border-radius:10px;margin-left:6px'>{dphase} · {phase}日</span><br>"
              f"<span style='font-size:13px;color:#c5cae9'>{date_line} · {menu['title']}</span></div>")

    # 教練提示（琥珀）
    tip = (_card("#fff8e1", "#f9a825", "#8a6d00", "💬 教練提示", menu['coach_tip'])
           if menu.get("coach_tip") else "")

    # 目標 vs 達成（淺藍）
    th = ("<tr style='background:#dde4f5'><th align=left style='padding:6px 10px;color:#1a237e;font-size:12px'>項目</th>"
          "<th align=left style='padding:6px 10px;color:#1a237e;font-size:12px'>目標</th>"
          "<th align=right style='padding:6px 10px;color:#1a237e;font-size:12px'>預計達成</th></tr>")
    rows = (_macro_row("熱量", t["kcal"], a["kcal"], " kcal")
            + _macro_row("蛋白", t["protein"], a["protein"], "g", "protein")
            + _macro_row("碳水", t["carb"], a["carb"])
            + _macro_row("脂肪", t["fat"], a["fat"])
            + f"<tr><td style='padding:6px 10px;color:#37474f'>水分</td>"
              f"<td colspan=2 style='padding:6px 10px;color:#37474f'>≥ {menu['water_l']}L · "
              f"{' / '.join(menu['water_times'])} 各 500ml</td></tr>")
    targets = _card("#eef2fb", "#3f51b5", "#1a237e", "今日目標 vs 預計達成",
                    f"<table style='border-collapse:collapse;font-size:14px;width:100%'>{th}{rows}</table>")


    # 三餐（暖橘，每餐一張卡）
    meals_html = ""
    for m in menu["meals"]:
        st = m["subtotal"]
        irows = ""
        for idx, i in enumerate(m["items"]):
            bg = "#ffffff" if idx % 2 == 0 else "#fff0e3"
            irows += (f"<div style='background:{bg};padding:8px 10px;border-bottom:1px solid #ffe0c4'>"
                      f"<div style='color:#3a3a3a;font-weight:bold;font-size:14px'>{i['item']}</div>"
                      f"<div style='color:#7a6555;font-size:12px;margin-top:3px'>"
                      f"{i['portion']}<br><b style='color:#3a3a3a'>{i['kcal']}</b> 大卡 · "
                      f"蛋白 {i['protein']}g · 碳水 {i['carb']}g · 脂肪 {i['fat']}g · <b>NT${i['cost']}</b></div></div>")
        subtotal = (f"<div style='background:#ffe5cc;color:#8a3b00;font-size:12px;font-weight:bold;"
                    f"padding:5px 8px;border-radius:4px;margin:0 0 8px 0'>"
                    f"小計 {st['kcal']} 大卡 · 蛋白 {st['protein']}g 碳水 {st['carb']}g 脂肪 {st['fat']}g · NT${st['cost']}</div>")
        body = subtotal + irows
        meals_html += _card("#fff5ec", "#fb8c00", "#b34a00", f"{m['name']} {m['time']}", body)

    # 補劑（紫，含等級點 + 斑馬紋 + 標價）
    srows = ""
    for idx, s in enumerate(menu["supplements"]):
        bg = "#ffffff" if idx % 2 == 0 else "#f0e9fb"
        srows += (f"<div style='background:{bg};padding:7px 10px;border-bottom:1px solid #e4d7f5'>"
                  f"<div style='color:#3a3a3a;font-weight:bold;font-size:14px'>{s.get('tier','')} {s['name']}</div>"
                  f"<div style='color:#6a5a8a;font-size:12px;margin-top:2px'>{s['timing']} · <b>NT${s['cost']}</b></div></div>")
    supp_body = (f"{srows}"
                 f"<div style='color:#6a5a8a;font-size:12px;margin-top:6px'>{menu['supp_timing_note']}</div>")
    supps = _card("#f3eefb", "#7e57c2", "#5e35b1", "💊 補充劑（🔴必需 🟠建議 🟢加分）", supp_body)

    # 記帳（綠，放大總額）
    cost = (f"<div style='background:#e8f5e9;border-left:4px solid #43a047;border-radius:6px;"
            f"padding:12px 14px;margin:0 0 12px 0'>"
            f"<span style='color:#1b5e20;font-weight:bold;font-size:14px'>💰 今日記帳</span><br>"
            f"<span style='color:#2e5e32;font-size:13px'>食材 NT${menu['food_cost']} + 補劑 NT${menu['supp_cost']} = </span>"
            f"<span style='color:#1b5e20;font-weight:bold;font-size:18px'>NT${menu['total_cost']}</span></div>")

    # 紅燈（紅，警示 + 內層即停框）
    flags = "".join(f"☐ {f}<br>" for f in menu["red_flags"])
    stop = (f"<div style='background:#ffd9d4;color:#7f1410;font-weight:bold;font-size:13px;"
            f"padding:8px 10px;border-radius:4px;margin-top:8px'>即停訊號 — {menu['stop_signals']}</div>")
    redflag = (f"<div style='background:#fdeceb;border-left:5px solid #d32f2f;border-radius:6px;"
               f"padding:12px 14px;margin:0 0 12px 0'>"
               f"<div style='font-size:15px;font-weight:bold;color:#b71c1c;margin:0 0 8px 0'>"
               f"🚨 紅燈自檢（任一勾選 → 立刻回填表單）</div>"
               f"<div style='font-size:13px;line-height:1.9;color:#5c1a16'>{flags}</div>{stop}</div>")

    # 提醒（藍灰）。回填按鈕只在有設 FORM_FILL_URL 時顯示。
    fill_btn = ""
    if config.FORM_FILL_URL:
        fill_btn = (f"<div style='text-align:center;margin-top:10px'>"
                    f"<a href='{config.FORM_FILL_URL}' style='display:inline-block;background:#1a237e;"
                    f"color:#fff;font-weight:bold;font-size:15px;text-decoration:none;"
                    f"padding:12px 22px;border-radius:8px'>📲 點我回填今日資料</a>"
                    f"<div style='color:#90a4ae;font-size:12px;margin-top:6px'>今晚 22:00 前填，明天菜單依此調整</div>"
                    f"</div>")
    rem_body = (f"<div style='font-size:13px;line-height:1.7;color:#37474f'>"
                f"🏋️ 訓練：{menu['training_note']}<br>"
                f"💧 水分：{' / '.join(menu['water_times'])} 各 500ml（共 ≥ {menu['water_l']}L）</div>"
                + fill_btn)
    reminders = _card("#eceff1", "#607d8b", "#37474f", "📋 提醒", rem_body)

    # 📚 今日醫學新知（從每週更新的研究 DB 挑一則權威論文）
    fnd = menu.get("daily_finding")
    finding = ""
    if fnd:
        yr = fnd.get("year") or "—"
        summ = (fnd.get("summary") or "").strip()
        summ = (summ[:220] + "…") if len(summ) > 220 else summ
        finding = (f"<div style='background:#e3f2fd;border-left:4px solid #1976d2;border-radius:6px;"
                   f"padding:12px 14px;margin:0 0 12px 0'>"
                   f"<div style='font-size:15px;font-weight:bold;color:#0d47a1;margin:0 0 6px 0'>"
                   f"📚 今日醫學新知</div>"
                   f"<a href='{fnd.get('url','')}' style='color:#0d47a1;font-weight:bold;font-size:14px;"
                   f"text-decoration:none'>{fnd.get('title','')}</a>"
                   f"<div style='color:#37474f;font-size:13px;margin-top:4px'>{summ}</div>"
                   f"<div style='color:#607d8b;font-size:12px;margin-top:4px'>"
                   f"來源：{fnd.get('source','')} · {yr} · <a href='{fnd.get('url','')}' "
                   f"style='color:#1976d2'>看原文</a></div></div>")

    footer = ("<div style='color:#90a4ae;font-size:12px;margin-top:16px'>"
              "本菜單為衛教資訊非醫療處方；電解質為每日必需。如有紅燈症狀請就醫。</div>")

    return (f"<html><body style='margin:0;padding:0;background:#f4f5f7'>"
            f"<div style='font-family:-apple-system,\"Helvetica Neue\",Arial,sans-serif;"
            f"max-width:600px;margin:0 auto;padding:14px;color:#222'>"
            f"{header}{tip}{targets}{meals_html}{supps}{cost}{finding}{redflag}{reminders}{footer}"
            f"</div></body></html>")


def send_menu(menu_date: str, menu: dict, summary: str, dry_run: bool = False) -> str:
    html = render_menu_html(menu_date, menu, summary)
    LAST_MENU.write_text(html, encoding="utf-8")
    status = _send_html(f"PSMF 明日菜單 {menu_date}", html, dry_run)
    print(f"[email] 菜單 → {status}")
    return status


def render_html(summary: dict, adjustments: list[dict]) -> str:
    rows = "".join(
        f"<tr><td>{a['field']}</td><td>{a['old_value']}</td>"
        f"<td>{a['new_value']}</td><td>{a['reason']}</td></tr>"
        for a in adjustments
    ) or "<tr><td colspan=4>本週無調整</td></tr>"

    papers = "".join(
        f"<li><a href='{p['url']}'>{p['title']}</a> "
        f"({p.get('year') or '—'}, {p['source']})<br><small>{p.get('summary','')}</small></li>"
        for p in summary.get("papers", [])
    ) or "<li>本週無新論文</li>"

    eta = (f"約 {summary['weeks_left_est']} 週" if summary["weeks_left_est"]
           else "速率不足，需檢視")
    plateau = "⚠️ 偵測到停滯" if summary["plateau"] else "正常下降"
    upcoming = "、".join(f"{d}:{e}" for d, e in summary["upcoming"]) or "無"

    nxt = (f"距 <b>{summary['next_phase']}</b> 還需減 {summary['to_gate_kg']} kg"
           if summary.get("next_phase") else "已在最終階段")
    phase_panel = (
        f"<div style='background:#ede7f6;border-left:5px solid #5e35b1;border-radius:8px;"
        f"padding:14px 16px;margin:0 0 14px 0'>"
        f"<div style='font-size:16px;font-weight:bold;color:#4527a0'>📈 現階段：{summary.get('phase','—')}</div>"
        f"<div style='color:#37474f;font-size:14px;margin-top:4px'>{summary.get('phase_desc','')}</div>"
        f"<div style='color:#37474f;font-size:14px;margin-top:6px'>"
        f"目標 ~{summary.get('phase_kcal','—')} kcal · 蛋白 {summary.get('phase_protein','—')}g｜{nxt}</div>"
        f"<div style='color:#6a4fb0;font-size:13px;margin-top:4px'>{summary.get('phase_note','')}</div></div>")

    # 🧠 自我學習偏好面板
    pr = summary.get("prefs", {}) or {}
    if pr.get("best_adhered") or pr.get("top_foods"):
        tops = "、".join(f"{n}({c})" for n, c in (pr.get("top_foods") or [])[:5]) or "—"
        prefs_panel = (
            f"<div style='background:#e0f2f1;border-left:5px solid #00897b;border-radius:8px;"
            f"padding:14px 16px;margin:0 0 14px 0'>"
            f"<div style='font-size:16px;font-weight:bold;color:#00695c'>🧠 系統學到的偏好</div>"
            f"<div style='color:#37474f;font-size:14px;margin-top:6px'>"
            f"最依從菜單：<b>{pr.get('best_adhered') or '資料不足'}</b>"
            f"（之後固體日會多排這種）｜最省：{pr.get('cheapest') or '—'}"
            f"｜平均花費 NT${pr.get('avg_cost') or '—'}/天</div>"
            f"<div style='color:#37474f;font-size:13px;margin-top:4px'>最常排品項：{tops}</div>"
            f"<div style='color:#80897e;font-size:12px;margin-top:4px'>（依 {pr.get('n_days',0)} 天歷史；越多越準）</div></div>")
    else:
        prefs_panel = ""

    return f"""<html><body style="font-family:sans-serif;max-width:680px">
<h2>PSMF 週報 — 第 {summary['week_no']} 週（{summary['today']}）</h2>
{phase_panel}
{prefs_panel}
<table border=1 cellpadding=6 style="border-collapse:collapse">
<tr><td>起始 → 目前</td><td>{summary['start_weight']} → <b>{summary['latest_weight']}</b> kg</td></tr>
<tr><td>已減</td><td><b>{summary['lost']} kg</b>（{summary['rate']} kg/週）</td></tr>
<tr><td>距目標 {config.GOAL_WEIGHT}kg</td><td>{summary['to_goal']} kg（預估 {eta}）</td></tr>
<tr><td>本週狀態</td><td>{plateau}</td></tr>
<tr><td>BMR / TDEE</td><td>{summary['bmr']} / <b>{summary['tdee']}</b> kcal（TDEE 來源：{summary.get('tdee_src','formula')}）</td></tr>
<tr><td>未來 7 天排定</td><td>{upcoming}</td></tr>
<tr><td>本週花費</td><td>NT${round(summary['week_cost']['total'])}（{summary['week_cost']['days']} 天）· 食材 NT${round(summary['week_cost']['food'])} + 補劑 NT${round(summary['week_cost']['supp'])}</td></tr>
<tr><td>累計花費</td><td>NT${round(summary['total_cost']['total'])}（{summary['total_cost']['days']} 天，日均 NT${round(summary['total_cost']['total']/max(summary['total_cost']['days'],1))}）</td></tr>
</table>

<h3>本週調整建議</h3>
<table border=1 cellpadding=6 style="border-collapse:collapse">
<tr><th>項目</th><th>原</th><th>調整為</th><th>理由</th></tr>
{rows}
</table>

<h3>最新研究情報</h3>
<ul>{papers}</ul>

<p style="color:#888;font-size:12px">本報告為衛教資訊非醫療處方。電解質為每日必需；如有不適請就醫。</p>
</body></html>"""


def send_report(subject: str, html: str, dry_run: bool = False) -> str:
    LAST_REPORT.write_text(html, encoding="utf-8")
    status = _send_html(subject, html, dry_run)
    print(f"[email] 週報 → {status}（HTML 存 {LAST_REPORT}）")
    return status
