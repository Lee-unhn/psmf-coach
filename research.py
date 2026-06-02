"""P2：抓最新健康論文/情報，存進 research_papers。

來源（皆免費、純標準庫 urllib）：
- Europe PMC REST（單一 JSON endpoint，最穩）
- PubMed E-utilities（esearch + esummary）
- Semantic Scholar Graph API（無金鑰會限流，失敗則略過）

每個來源獨立 try/except；任一壞掉不影響其他。離線時退回 DB 既有資料。
首次執行會 seed 我們規劃時找到的 5 篇基準論文，保證週報有內容。
"""
from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone

import db

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

_UA = {"User-Agent": "PSMF-Coach/1.0 (personal health tracker)"}
_TIMEOUT = 15

QUERIES = [
    "protein sparing modified fast obesity",
    "high protein very low calorie diet muscle preservation resistance training",
    "protein intake lean body mass energy deficit",
    "diet break refeed metabolic adaptation weight loss",
    "electrolyte sodium potassium magnesium low calorie diet safety",
]

# 規劃階段已驗證的基準論文（首次 seed）
SEED_PAPERS = [
    ("PubMed", "PSMF: Effective and Safe Rapid Weight Loss in Severely Obese Adolescents",
     "https://pubmed.ncbi.nlm.nih.gov/27335996/", 2016,
     "PSMF 對重度肥胖青少年短期安全有效，體重下降主來自脂肪。", 0.9),
    ("PMC", "VLCD: role of exercise and protein in preserving skeletal muscle mass",
     "https://pmc.ncbi.nlm.nih.gov/articles/PMC10552824/", 2023,
     "VLCD 期間蛋白補充(~1.1-1.3 g/kg)+阻力訓練可保留瘦體組織。", 0.95),
    ("PMC", "Resistance Training Prevents Muscle Loss Induced by Caloric Restriction",
     "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC5946208/", 2018,
     "重訓挽回約 93.5% 因熱量限制造成的瘦體組織流失（meta-analysis）。", 0.92),
    ("Nature", "Intermittent energy restriction improves weight loss efficiency (MATADOR)",
     "https://www.nature.com/articles/ijo2017206", 2017,
     "間歇限制組比連續組多減 50% 脂肪、靜息代謝下降減半、復胖較少。", 0.93),
    ("Virta", "Sodium/potassium/magnesium needs on low-carb/VLCD",
     "https://www.virtahealth.com/faq/sodium-potassium-magnesium-ketogenic-diet", 2024,
     "建議鈉 3-5g、鉀 3-4g、鎂 300-500mg；缺乏可誘發/惡化心律不整。", 0.88),
]


def _get_json(url: str) -> dict | None:
    try:
        req = urllib.request.Request(url, headers=_UA)
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        print(f"[research] 取用失敗 {url[:60]}... : {type(exc).__name__}")
        return None


def _relevance(title: str, year: int | None) -> float:
    score = 0.5
    low = title.lower()
    for kw in ("protein", "muscle", "psmf", "calorie", "fasting",
               "refeed", "electrolyte", "resistance", "weight loss"):
        if kw in low:
            score += 0.06
    if year and year >= 2023:
        score += 0.15
    return round(min(score, 1.0), 2)


def fetch_europepmc(query: str, n: int = 4) -> list[dict]:
    q = urllib.parse.quote(query)
    url = (f"https://www.ebi.ac.uk/europepmc/webservices/rest/search?"
           f"query={q}&format=json&pageSize={n}&sort=P_PDATE_D%20desc")
    data = _get_json(url)
    out = []
    for r in (data or {}).get("resultList", {}).get("result", []):
        doi = r.get("doi")
        link = (f"https://doi.org/{doi}" if doi
                else f"https://europepmc.org/article/{r.get('source')}/{r.get('id')}")
        year = int(r["pubYear"]) if r.get("pubYear", "").isdigit() else None
        title = r.get("title", "").rstrip(".")
        out.append({"source": "EuropePMC", "title": title, "url": link,
                    "year": year, "summary": (r.get("abstractText") or title)[:400],
                    "relevance_score": _relevance(title, year)})
    return out


def fetch_pubmed(query: str, n: int = 4) -> list[dict]:
    q = urllib.parse.quote(query)
    s = _get_json("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?"
                  f"db=pubmed&term={q}&retmode=json&retmax={n}&sort=date")
    ids = (s or {}).get("esearchresult", {}).get("idlist", [])
    if not ids:
        return []
    summ = _get_json("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?"
                     f"db=pubmed&id={','.join(ids)}&retmode=json")
    res = (summ or {}).get("result", {})
    out = []
    for pid in ids:
        item = res.get(pid)
        if not item:
            continue
        pub = item.get("pubdate", "")
        year = int(pub[:4]) if pub[:4].isdigit() else None
        title = item.get("title", "").rstrip(".")
        out.append({"source": "PubMed", "title": title,
                    "url": f"https://pubmed.ncbi.nlm.nih.gov/{pid}/",
                    "year": year, "summary": title,
                    "relevance_score": _relevance(title, year)})
    return out


def fetch_semantic_scholar(query: str, n: int = 4) -> list[dict]:
    q = urllib.parse.quote(query)
    url = ("https://api.semanticscholar.org/graph/v1/paper/search?"
           f"query={q}&limit={n}&fields=title,year,abstract,url")
    data = _get_json(url)
    out = []
    for r in (data or {}).get("data", []):
        title = (r.get("title") or "").rstrip(".")
        year = r.get("year")
        url_ = r.get("url") or ""
        if not url_:
            continue
        out.append({"source": "SemanticScholar", "title": title, "url": url_,
                    "year": year, "summary": (r.get("abstract") or title)[:400],
                    "relevance_score": _relevance(title, year)})
    return out


def _seed_if_empty(conn) -> None:
    cur = conn.execute("SELECT COUNT(*) AS c FROM research_papers")
    if cur.fetchone()["c"] > 0:
        return
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for src, title, url, year, summ, score in SEED_PAPERS:
        conn.execute(
            "INSERT OR IGNORE INTO research_papers "
            "(fetched_at, source, title, url, year, summary, relevance_score) "
            "VALUES (?,?,?,?,?,?,?)",
            (now, src, title, url, year, summ, score),
        )
    print(f"[research] seed {len(SEED_PAPERS)} 篇基準論文")


def collect_and_store() -> int:
    """抓所有來源、去重、存 DB。回傳本次新增筆數。"""
    db.init_db()
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    found: dict[str, dict] = {}
    for query in QUERIES:
        for fetch in (fetch_europepmc, fetch_pubmed, fetch_semantic_scholar):
            for paper in fetch(query):
                key = paper["url"].lower()
                if key not in found:
                    found[key] = paper

    added = 0
    with db.connect() as conn:
        _seed_if_empty(conn)
        for paper in found.values():
            cur = conn.execute(
                "INSERT OR IGNORE INTO research_papers "
                "(fetched_at, source, title, url, year, summary, relevance_score) "
                "VALUES (?,?,?,?,?,?,?)",
                (now, paper["source"], paper["title"], paper["url"],
                 paper["year"], paper["summary"], paper["relevance_score"]),
            )
            added += cur.rowcount
    print(f"[research] 線上抓到 {len(found)} 篇、新增 {added} 篇")
    return added


def top_recent(conn, n: int = 6) -> list[dict]:
    cur = conn.execute(
        "SELECT * FROM research_papers ORDER BY fetched_at DESC, relevance_score DESC LIMIT ?",
        (n,),
    )
    return [dict(r) for r in cur.fetchall()]


if __name__ == "__main__":
    collect_and_store()
