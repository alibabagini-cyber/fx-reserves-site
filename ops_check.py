#!/usr/bin/env python3
"""무인 운영 점검. 실패 항목이 있으면 exit 1 + 요약(update.sh/크론이 TG로 보냄).
  --weekly : 이상 없어도 요약을 출력(월요일 주간 보고용)
점검: ①사이트 200 ②데이터 신선도(IMF 기준월이 오늘-2개월보다 오래되면 경고, 한은 ECOS는 -1개월)
     ③백테스트 12/12 ④정합성(한국 IMF vs ECOS 같은 달 0.5% 이내, 상위 15개국 m/m ±20% 초과=단위 의심)
     ⑤크론 로그 48h 이내 ⑥GitHub 이슈 미처리 수
"""
import json, sys, datetime as dt, subprocess, urllib.request
from pathlib import Path
R = Path(__file__).parent; D = R / "data"; BASE = json.loads((R / "site.json").read_text())["base_url"]
fails, info = [], []
def ym(d): return d.strftime("%Y-%m")
today = dt.date.today()

# ① 사이트
try:
    code = urllib.request.urlopen(urllib.request.Request(BASE + "/", headers={"User-Agent": "ops"}), timeout=20).status
    info.append(f"site {code}"); code == 200 or fails.append(f"site HTTP {code}")
except Exception as e: fails.append(f"site down: {e}")
# ② 신선도
latest = json.loads((D / "latest.json").read_text()); per = latest["period"]
lim = ym(today.replace(day=1) - dt.timedelta(days=62))
info.append(f"IMF 기준월 {per}"); per >= lim or fails.append(f"IMF 기준월 {per} 정체(기대 ≥{lim})")
bok = json.loads((D / "bok_latest.json").read_text())["months"]; bm = max(bok)
info.append(f"ECOS {bm}"); bm >= ym(today.replace(day=1) - dt.timedelta(days=32)) or fails.append(f"ECOS {bm} 정체")
# ③ 백테스트
bt = json.loads((D / "backtest_bok.json").read_text()); info.append(f"backtest {bt['hit']}/12"); bt["hit"] == 12 or fails.append(f"backtest {bt['hit']}/12")
# ④ 정합성
kor = next(r for r in latest["rows"] if r["iso3"] == "KOR")
if per in bok:
    d = abs(kor["usd_bn"] - bok[per]["total"]) / bok[per]["total"]
    d <= 0.005 or fails.append(f"한국 IMF {kor['usd_bn']} vs ECOS {bok[per]['total']} 차이 {d:.2%}")
months = sorted(p.stem[9:] for p in D.glob("reserves_*.json"))
if len(months) > 1:
    prev = {r["iso3"]: r for r in json.loads((D / f"reserves_{months[-2]}.json").read_text())["rows"]}
    for r in latest["rows"][:15]:
        p = prev.get(r["iso3"])
        if p and p["as_of"] != r["as_of"] and abs(r["usd_bn"] / p["usd_bn"] - 1) > 0.2:
            fails.append(f"{r['name']} m/m {r['usd_bn']/p['usd_bn']-1:+.0%} 단위 의심")
# ⑤ 크론 로그
logs = sorted((R / "logs").glob("update_*.log"))
if logs:
    age = (dt.datetime.now() - dt.datetime.fromtimestamp(logs[-1].stat().st_mtime)).total_seconds() / 3600
    info.append(f"cron {age:.0f}h ago"); age < 48 or fails.append(f"크론 {age:.0f}시간 미실행")
    tail = logs[-1].read_text()[-3000:]
    ("Traceback" in tail or "Error" in tail) and fails.append("크론 로그에 에러: " + [l for l in tail.splitlines() if "Error" in l or "Traceback" in l][-1][:120])
# ⑥ 이슈
try:
    n = json.loads(subprocess.run(["gh", "issue", "list", "-R", "alibabagini-cyber/fx-reserves-site", "--state", "open", "--json", "number,title"], capture_output=True, text=True, timeout=30).stdout or "[]")
    info.append(f"issues {len(n)}"); n and fails.append("미처리 이슈: " + "; ".join(f"#{i['number']} {i['title'][:40]}" for i in n[:3]))
except Exception: info.append("issues ?")

rk = f"한국 {kor['rank']}위 {kor['usd_bn']*10:,.0f}억 ({per}) · ECOS {bm} {bok[bm]['total']*10:,.1f}억"
summary = ("[외환보유액 사이트] " + ("⚠ " + " / ".join(fails) if fails else "정상") + f"\n{rk}\n" + " · ".join(info))
print(summary)
sys.exit(1 if fails else 0)
