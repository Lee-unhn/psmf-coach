"""本機回填表單（零依賴，stdlib http.server）。

手機或電腦開瀏覽器填今日資料 → 直接寫 DB → 立即生成並 email 隔日菜單卡。

用法：
  python form.py           # 啟動，預設 0.0.0.0:8765
電腦：http://localhost:8765
手機（同一 WiFi）：http://<電腦區網IP>:8765   （啟動時會印出來）
  ※ 首次手機連線若不通，多半是 Windows 防火牆擋了，允許 python 的輸入連線即可。
按 Ctrl+C 結束。
"""
from __future__ import annotations

import html
import http.server
import os
import socket
import sys
import urllib.parse
from datetime import date

import config
import daily_job

# pythonw（無視窗）下 stdout/stderr 為 None，print() 會炸 → 導向 devnull 才能常駐
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PORT = 8765


def _scale(name: str, label: str) -> str:
    opts = "".join(f"<option value='{i}'>{i}</option>" for i in range(1, 6))
    return (f"<label>{label}</label>"
            f"<select name='{name}'><option value=''>—</option>{opts}</select>")


def form_html(msg: str = "") -> str:
    today = date.today().isoformat()
    supp_rows = "".join(
        f"<label class='chk'><input type='checkbox' name='{k}' checked> {lbl}</label>"
        for k, lbl in (("supp_elec", "電解質（鈉/鉀/鎂）"), ("multivit", "綜合維他命"),
                       ("fishoil", "魚油"), ("creatine", "肌酸"))
    )
    return f"""<!doctype html><html lang='zh-Hant'><head><meta charset='utf-8'>
<meta name='viewport' content='width=device-width,initial-scale=1'>
<title>PSMF 每日回填</title>
<style>
 body{{font-family:-apple-system,"Helvetica Neue",Arial,sans-serif;background:#f4f5f7;margin:0;padding:16px;color:#222}}
 .card{{max-width:480px;margin:0 auto;background:#fff;border-radius:10px;padding:18px;box-shadow:0 1px 4px rgba(0,0,0,.1)}}
 h1{{font-size:18px;color:#1a237e;margin:0 0 4px}} .sub{{color:#888;font-size:13px;margin:0 0 16px}}
 label{{display:block;font-weight:bold;font-size:14px;margin:14px 0 4px;color:#37474f}}
 input[type=number],input[type=date],input[type=text],select{{
   width:100%;box-sizing:border-box;padding:10px;font-size:16px;border:1px solid #cfd8dc;border-radius:6px}}
 .chk{{display:block;font-weight:normal;margin:6px 0;font-size:15px}}
 .chk input{{width:auto;margin-right:8px;transform:scale(1.3)}}
 .row{{display:flex;gap:10px}} .row>div{{flex:1}}
 button{{width:100%;margin-top:20px;padding:14px;font-size:17px;font-weight:bold;color:#fff;
   background:#1a237e;border:0;border-radius:8px}}
 .msg{{background:#e8f5e9;color:#1b5e20;padding:10px;border-radius:6px;margin-bottom:12px;font-size:14px}}
 .hint{{color:#90a4ae;font-size:12px;margin-top:2px;font-weight:normal}}
</style></head><body><div class='card'>
<h1>PSMF 每日回填</h1>
<p class='sub'>填完按送出 → 立刻收到明天的菜單 email</p>
{f"<div class='msg'>{msg}</div>" if msg else ""}
<form method='post' action='/submit'>
 <label>日期</label><input type='date' name='date' value='{today}'>
 <div class='row'>
   <div><label>體重 (kg)</label><input type='number' step='0.1' name='weight' required inputmode='decimal'></div>
   <div><label>腰圍 (cm)</label><input type='number' step='0.1' name='waist_cm' inputmode='decimal'></div>
 </div>
 <label class='chk'><input type='checkbox' name='trained'> 今天有重訓</label>
 <div class='row'>
   <div>{_scale("hunger", "飢餓 1-5")}</div>
   <div>{_scale("energy", "能量 1-5")}</div>
   <div>{_scale("adherence", "依從 1-5")}</div>
 </div>
 <div class='hint'>1=最低 5=最高</div>
 <label>備註</label><input type='text' name='notes' placeholder='睡眠、心情、特殊狀況…'>
 <label>今日補劑（有吃就打勾）</label>
 {supp_rows}
 <button type='submit'>送出並生成明日菜單</button>
</form></div></body></html>"""


def confirm_html(r: dict) -> str:
    a = r["menu"]["achieved"]
    mailed = "已寄到你的信箱 📧" if r["email_status"] == "sent" else f"（email: {r['email_status']}）"
    return f"""<!doctype html><html lang='zh-Hant'><head><meta charset='utf-8'>
<meta name='viewport' content='width=device-width,initial-scale=1'><title>已送出</title>
<style>body{{font-family:-apple-system,Arial,sans-serif;background:#f4f5f7;padding:20px;color:#222}}
.card{{max-width:480px;margin:0 auto;background:#fff;border-radius:10px;padding:20px}}
h1{{color:#1b5e20;font-size:20px}} a{{display:inline-block;margin-top:16px;color:#1a237e}}</style>
</head><body><div class='card'>
<h1>✅ 已記錄</h1>
<p>明日菜單 <b>DAY {r['day_index']} · Phase {r['decision'].day_type}</b>（{r['menu']['title']}）已生成，{mailed}</p>
<p style='color:#555;font-size:14px'>達成 {a['kcal']} 大卡 · 蛋白 {a['protein']}g · 花費 NT${r['menu']['total_cost']}<br>
{html.escape(r['decision'].reason)}</p>
<a href='/'>← 再填一筆</a>
</div></body></html>"""


class Handler(http.server.BaseHTTPRequestHandler):
    def _send(self, body: str, code: int = 200) -> None:
        data = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        if self.path.split("?")[0] in ("/", "/index.html"):
            self._send(form_html())
        else:
            self._send("<h1>404</h1>", 404)

    def do_POST(self) -> None:
        if self.path != "/submit":
            self._send("<h1>404</h1>", 404)
            return
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length).decode("utf-8")
        data = {k: v[0] for k, v in urllib.parse.parse_qs(raw).items()}
        # 電解質勾選 → 寫入建議劑量供 supplement_log 記錄
        if data.pop("supp_elec", None):
            data.update({"na_mg": "4000", "k_mg": "3000", "mg_mg": "400"})
        try:
            r = daily_job.process_log(data)
            self._send(confirm_html(r))
        except Exception as exc:  # noqa: BLE001
            self._send(form_html(f"⚠️ 出錯：{html.escape(str(exc))}"), 500)

    def log_message(self, *args) -> None:  # 靜音 access log
        pass


def _lan_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:  # noqa: BLE001
        return "127.0.0.1"


def main() -> None:
    server = http.server.ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    msg = (f"PSMF 回填表單已啟動：\n  電腦： http://localhost:{PORT}\n"
           f"  手機（同 WiFi）： http://{_lan_ip()}:{PORT}\n按 Ctrl+C 結束。")
    print(msg)
    # 檔案標記：headless 啟動也能確認有跑（含實際 URL）
    (config.DATA_DIR / "form_running.txt").write_text(msg, encoding="utf-8")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止。")


if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001 — headless 啟動失敗時留 log 可查
        import traceback
        (config.DATA_DIR / "form_crash.log").write_text(traceback.format_exc(), encoding="utf-8")
        raise
