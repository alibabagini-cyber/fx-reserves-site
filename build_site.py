#!/usr/bin/env python3
"""정적 사이트 생성기. data/*.json → site/ (순수 HTML+인라인 SVG, 외부 JS 0).

페이지
  /                         순위표(기준월) + 한국 타일 + 캘린더
  /ranking/YYYY-MM/         월별 아카이브(롱테일)
  /korea/                   한국 시계열·구성
  /country/<iso3>/          국가별 40p
  /gold/                    금 보유·시가환산 순위
  /methodology/             방법론·백테스트·정정로그
  /data/                    다운로드(CSV/JSON)+인용문구
  /embed/ranking.html       iframe 위젯
  /articles/<slug>/         content/*.md
  /en/                      영문 미러(순위·국가)
  rss.xml sitemap.xml robots.txt
"""
import csv, io, json, re, html, datetime as dt
from pathlib import Path

ROOT = Path(__file__).parent
DATA, SITE, CONTENT = ROOT / "data", ROOT / "site", ROOT / "content"
CFG = json.loads((ROOT / "site.json").read_text()) if (ROOT / "site.json").exists() else {}
BASE = CFG.get("base_url", "https://example.org")
NAME = CFG.get("site_name", "외환보유액 순위")
EN = {"CHN":"China","JPN":"Japan","CHE":"Switzerland","IND":"India","RUS":"Russia","SAU":"Saudi Arabia","HKG":"Hong Kong",
      "KOR":"South Korea","SGP":"Singapore","DEU":"Germany","BRA":"Brazil","ITA":"Italy","FRA":"France","GBR":"United Kingdom",
      "MEX":"Mexico","THA":"Thailand","USA":"United States","POL":"Poland","IDN":"Indonesia","ISR":"Israel","CZE":"Czechia",
      "TUR":"Türkiye","MYS":"Malaysia","PHL":"Philippines","ESP":"Spain","NLD":"Netherlands","BEL":"Belgium","SWE":"Sweden",
      "NOR":"Norway","DNK":"Denmark","CAN":"Canada","AUS":"Australia","ZAF":"South Africa","COL":"Colombia","PER":"Peru",
      "CHL":"Chile","EGY":"Egypt","ARG":"Argentina","ROU":"Romania","HUN":"Hungary","TWN":"Taiwan"}

CSS = """
:root{--fg:#1b1b1b;--mut:#666;--bg:#fff;--line:#e5e5e5;--acc:#0b57d0;--hi:#fff7e0}
*{box-sizing:border-box}body{margin:0;font:16px/1.6 -apple-system,"Malgun Gothic","Apple SD Gothic Neo",sans-serif;color:var(--fg);background:var(--bg)}
a{color:var(--acc);text-decoration:none}a:hover{text-decoration:underline}
header{border-bottom:1px solid var(--line)}header .in{max-width:1040px;margin:0 auto;padding:12px 16px;display:flex;gap:18px;align-items:center;flex-wrap:wrap}
header .brand{font-weight:700;font-size:18px;color:var(--fg)}header nav a{color:var(--mut);font-size:14px;margin-right:12px}
main{max-width:1040px;margin:0 auto;padding:20px 16px}h1{font-size:26px;margin:8px 0 4px}h2{font-size:20px;margin:32px 0 10px}
.sub{color:var(--mut);font-size:14px;margin:0 0 18px}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin:18px 0}
.tile{border:1px solid var(--line);border-radius:10px;padding:14px 16px}.tile b{display:block;font-size:28px;line-height:1.2}.tile span{color:var(--mut);font-size:13px}
table{border-collapse:collapse;width:100%;font-size:15px}th,td{padding:7px 8px;border-bottom:1px solid var(--line);text-align:right;white-space:nowrap}
th:nth-child(2),td:nth-child(2){text-align:left}th{color:var(--mut);font-weight:600;font-size:13px}tr.kor{background:var(--hi);font-weight:700}
.wrap{overflow-x:auto}.up{color:#0a7d3a}.dn{color:#c0392b}.note{font-size:13px;color:var(--mut);margin-top:8px}
.ad{min-height:90px;margin:24px 0;border:1px dashed var(--line);border-radius:8px;display:flex;align-items:center;justify-content:center;color:#bbb;font-size:12px}
footer{border-top:1px solid var(--line);margin-top:48px}footer .in{max-width:1040px;margin:0 auto;padding:18px 16px;font-size:13px;color:var(--mut)}
svg.chart{width:100%;height:auto;max-height:340px}.grid2{display:grid;grid-template-columns:1fr 1fr;gap:20px}@media(max-width:720px){.grid2{grid-template-columns:1fr}}
pre{background:#f6f6f6;padding:10px;border-radius:6px;overflow-x:auto;font-size:13px}.btn{display:inline-block;border:1px solid var(--acc);border-radius:6px;padding:6px 12px;margin:4px 6px 4px 0;font-size:14px}
article p{margin:0 0 14px}article h2{margin-top:26px}.tag{font-size:12px;background:#eef3ff;color:var(--acc);padding:2px 8px;border-radius:10px}
"""

def esc(s): return html.escape(str(s))
def kper(p): y, m = p.split("-"); return f"{y}년 {int(m)}월말"
def eper(p): return dt.date(int(p[:4]), int(p[5:]), 1).strftime("End of %B %Y")
def fmt(v, d=1): return f"{v:,.{d}f}" if v is not None else "—"
def delta(v, d=1):
    if v is None: return ""
    if abs(v) < 0.5 * 10 ** -d: v = 0.0  # "-0.0" 방지
    c = "up" if v > 0 else "dn" if v < 0 else ""
    return f'<span class="{c}">{v:+,.{d}f}</span>' if v else f'<span>{0:.{d}f}</span>'

def page(title, body, desc="", path="/", lang="ko", jsonld=None, canonical=None):
    nav = ('<a href="/">순위</a><a href="/korea/">한국</a><a href="/gold/">금</a><a href="/country/">국가별</a>'
           '<a href="/articles/">해설</a><a href="/data/">데이터</a><a href="/methodology/">방법론</a><a href="/en/">EN</a>'
           if lang == "ko" else '<a href="/en/">Ranking</a><a href="/en/country/">Countries</a><a href="/data/">Data</a><a href="/methodology/">Methodology (KO)</a><a href="/">한국어</a>')
    ld = f'<script type="application/ld+json">{json.dumps(jsonld, ensure_ascii=False)}</script>' if jsonld else ""
    # 계정 연동 슬롯(site.json): 서치콘솔·서치어드바이저 소유확인 메타, 애드센스 스크립트 — 값 비면 출력 안 함
    ld += "".join(f'<meta name="{n}" content="{esc(CFG[k])}">' for k, n in (("google_verify", "google-site-verification"), ("naver_verify", "naver-site-verification")) if CFG.get(k))
    if CFG.get("adsense_pub"):
        ld += f'<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client={esc(CFG["adsense_pub"])}" crossorigin="anonymous"></script>'
    foot = ("자료: IMF IRFCL(SDMX), 대만 CBC, 중국 SAFE, 사우디 SAMA, 한국은행. 각 수치의 기준월·출처는 표 안에 표기. "
            "본 사이트는 공식 통계를 재집계한 독립 자료이며 한국은행·IMF와 무관합니다. "
            '<a href="/methodology/">방법론</a> · <a href="/methodology/#errata">정정로그</a> · <a href="/about/">소개</a> · <a href="/privacy/">개인정보</a>'
            if lang == "ko" else
            'Sources: IMF IRFCL (SDMX), CBC Taiwan, SAFE China, SAMA, Bank of Korea. Independent compilation, not affiliated with any central bank or the IMF. '
            '<a href="/methodology/">Methodology (KO)</a> · <a href="/about/">About</a> · <a href="/privacy/">Privacy</a>')
    return f"""<!doctype html><html lang="{lang}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title><meta name="description" content="{esc(desc)}"><link rel="canonical" href="{BASE}{canonical or path}">
<link rel="alternate" type="application/rss+xml" title="{esc(NAME)}" href="{BASE}/rss.xml"><style>{CSS}</style>{ld}</head>
<body><header><div class="in"><a class="brand" href="{'/' if lang=='ko' else '/en/'}">{esc(NAME)}</a><nav>{nav}</nav></div></header>
<main>{body}</main><footer><div class="in">{foot}<br>© {dt.date.today().year} {esc(NAME)}</div></footer></body></html>"""

def write(path, content):
    p = SITE / path.strip("/")
    if path.endswith("/") or not p.suffix: p = p / "index.html"
    p.parent.mkdir(parents=True, exist_ok=True); p.write_text(content, encoding="utf-8")
    URLS.append("/" + str(p.relative_to(SITE)).replace("index.html", ""))
URLS = []

# ---------- 차트 (인라인 SVG) ----------
def line_chart(series, w=800, h=300, ylabel="", labels=None):
    """series=[(period, value)...] 단일 시계열."""
    if not series: return ""
    vals = [v for _, v in series]; lo, hi = min(vals), max(vals); pad = (hi - lo) * 0.08 or 1
    lo -= pad; hi += pad; L, R, T, B = 60, 16, 14, 30
    def x(i): return L + (w - L - R) * i / max(1, len(series) - 1)
    def y(v): return T + (h - T - B) * (hi - v) / (hi - lo)
    pts = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, (_, v) in enumerate(series))
    g = ""
    for k in range(5):
        v = lo + (hi - lo) * k / 4; yy = y(v)
        g += f'<line x1="{L}" y1="{yy:.1f}" x2="{w-R}" y2="{yy:.1f}" stroke="#eee"/><text x="{L-6}" y="{yy+4:.1f}" font-size="11" text-anchor="end" fill="#888">{v:,.0f}</text>'
    step = max(1, len(series) // 8)
    for i in range(0, len(series), step):
        g += f'<text x="{x(i):.1f}" y="{h-8}" font-size="11" text-anchor="middle" fill="#888">{series[i][0][:7]}</text>'
    return (f'<svg class="chart" viewBox="0 0 {w} {h}" role="img" aria-label="{esc(ylabel)}">{g}'
            f'<polyline fill="none" stroke="#0b57d0" stroke-width="2" points="{pts}"/></svg>')

def bar_chart(items, w=800, h=None, unit="B"):
    """items=[(label, value)] 가로 막대."""
    h = h or 22 * len(items) + 10; mx = max(v for _, v in items) or 1
    g = ""
    for i, (lab, v) in enumerate(items):
        yy = 5 + i * 22; bw = (w - 260) * v / mx
        g += (f'<text x="150" y="{yy+15}" font-size="12" text-anchor="end">{esc(lab)}</text>'
              f'<rect x="160" y="{yy+3}" width="{bw:.1f}" height="16" fill="{"#e0a800" if lab in ("한국","South Korea") else "#0b57d0"}"/>'
              f'<text x="{165+bw:.1f}" y="{yy+15}" font-size="12" fill="#444">{v:,.1f}{unit}</text>')
    return f'<svg class="chart" viewBox="0 0 {w} {h}" style="max-height:none">{g}</svg>'

# ---------- 로드 ----------
def load():
    latest = json.loads((DATA / "latest.json").read_text())
    kh = json.loads((DATA / "korea_history.json").read_text())
    ch = json.loads((DATA / "country_history.json").read_text())
    gold = json.loads((DATA / "gold.json").read_text())
    months = sorted(p.stem.replace("reserves_", "") for p in DATA.glob("reserves_*.json"))
    prev = None
    if len(months) >= 2:
        prev = json.loads((DATA / f"reserves_{months[-2]}.json").read_text())
    bt = json.loads((DATA / "backtest_bok.json").read_text()) if (DATA / "backtest_bok.json").exists() else None
    global BOK, KLONG
    BOK = json.loads((DATA / "bok_latest.json").read_text())["months"] if (DATA / "bok_latest.json").exists() else {}
    KLONG = json.loads((DATA / "korea_long.json").read_text()) if (DATA / "korea_long.json").exists() else {}
    return latest, kh, ch, gold, months, prev, bt
BOK, KLONG = {}, {}

def flash_block(per):
    """한은 발표가 순위 기준월보다 앞서 있으면 속보 타일(순위 미확정 명시)."""
    if not BOK or max(BOK) <= per: return ""
    m = max(BOK); cur = BOK[m]["total"]; pv = BOK.get(sorted(BOK)[-2], {}).get("total") if len(BOK) > 1 else None
    return (f'<div class="tile" style="border-color:#e0a800"><span>속보 · 한국 {kper(m)} (한은 ECOS)</span><b>{fmt(cur*10,1)}억달러</b>'
            f'<span>전월비 {delta((cur-pv)*10,1) if pv else "—"}억달러 · {kper(m)} 세계 순위는 각국 발표가 모이는 대로 확정</span></div>')

def ranking_table(rows, prev_rows=None, lang="ko", limit=None):
    pm = {r["iso3"]: r for r in (prev_rows or [])}
    out = ['<div class="wrap"><table><thead><tr><th>#</th><th>' + ("국가" if lang == "ko" else "Country") + '</th><th>' +
           ("외환보유액(억달러)" if lang == "ko" else "Reserves (USD bn)") + '</th><th>' + ("전월비" if lang == "ko" else "m/m") +
           '</th><th>' + ("기준월" if lang == "ko" else "As of") + '</th><th>' + ("출처" if lang == "ko" else "Source") + '</th></tr></thead><tbody>']
    for r in rows[:limit] if limit else rows:
        name = r["name"] if lang == "ko" else EN.get(r["iso3"], r["iso3"])
        ex = r.get("usd_exact", r["usd_bn"]); v = ex * 10 if lang == "ko" else ex
        d = (ex - pm[r["iso3"]].get("usd_exact", pm[r["iso3"]]["usd_bn"])) if r["iso3"] in pm and pm[r["iso3"]]["as_of"] != r["as_of"] else None
        d = d * 10 if (d is not None and lang == "ko") else d
        src = next((k for k in ("IMF", "CBC", "SAFE", "SAMA") if k.lower() in r["source"].lower()), esc(r["source"])[:8])
        href = f"/country/{r['iso3'].lower()}/" if lang == "ko" else f"/en/country/{r['iso3'].lower()}/"
        lag = "" if r["as_of"] == rows[0]["as_of"] else " *"
        out.append(f'<tr class="{"kor" if r["iso3"]=="KOR" else ""}"><td>{r["rank"]}</td><td><a href="{href}">{esc(name)}</a></td>'
                   f'<td>{fmt(v, 1)}</td><td>{delta(d, 1 if lang=="en" else 0)}</td><td>{r["as_of"]}{lag}</td><td>{src}</td></tr>')
    out.append("</tbody></table></div>")
    return "".join(out)

# ---------- 페이지 ----------
def build_home(latest, prev, kh, months):
    rows = latest["rows"]; per = latest["period"]; kor = next(r for r in rows if r["iso3"] == "KOR")
    pk = next((r for r in prev["rows"] if r["iso3"] == "KOR"), None) if prev else None
    kh_prev = kh[-2]["total"] if len(kh) > 1 else None
    lag = [r["name"] for r in rows if r["as_of"] != per]
    tiles = f"""<div class="tiles">{flash_block(per)}
<div class="tile"><span>한국 세계 순위 ({kper(per)})</span><b>{kor['rank']}위</b><span>{'전월 ' + str(pk['rank']) + '위' if pk else '40개국+대만 기준'}</span></div>
<div class="tile"><span>한국 외환보유액</span><b>{fmt(kor['usd_bn']*10,0)}억달러</b><span>전월비 {delta((kor['usd_bn']-kh_prev)*10, 0) if kh_prev else '—'}억달러</span></div>
<div class="tile"><span>1위와 격차</span><b>{fmt((rows[0]['usd_bn']-kor['usd_bn'])/1000,2)}조달러</b><span>{esc(rows[0]['name'])} {fmt(rows[0]['usd_bn']*10,0)}억달러</span></div>
</div>"""
    body = f"""<h1>세계 외환보유액 순위 — {kper(per)}</h1>
<p class="sub">IMF 국제준비자산 템플릿(IRFCL) + 각국 중앙은행 발표를 매월 재집계. 한국은행이 2026년 9월부터 순위표 공개를 중단해 독립적으로 집계합니다.
갱신 {latest['generated_at'][:10]} · <a href="/methodology/">방법론</a> · <a href="/data/">CSV 받기</a> · <a href="/embed/">표 퍼가기</a></p>
{tiles}
{ranking_table(rows, prev['rows'] if prev else None)}
<p class="note">* 표시 국가는 해당 월 미발표로 직전 월 값(사우디 등 2개월 지연 보고). 금은 IMF 템플릿 기준 시가 평가(한국·미국·싱가포르는 장부가 보고 — <a href="/gold/">금 시가환산 순위</a> 참고). 억달러 = 10억달러 × 10.</p>
<div class="ad">광고</div>
<h2>한국 외환보유액 추이 (2005~, 10억달러)</h2>
{line_chart([(r['period'], r['total']) for r in kh], ylabel='한국 외환보유액')}
<p><a href="/korea/">한국 상세(구성·월별 표) →</a></p>
<h2>월별 아카이브</h2><p>{' · '.join(f'<a href="/ranking/{m}/">{kper(m)}</a>' for m in reversed(months))}</p>
<h2>다음 갱신</h2><p>한국은행 월간 발표(매월 초 영업일 3~5일째 06:00) 당일 한국 수치 반영, IMF·각국 중앙은행 제출이 모이는 월 중순에 같은 기준월 순위 확정. <a href="/rss.xml">RSS</a>로 갱신 알림.</p>"""
    ld = {"@context": "https://schema.org", "@type": "Dataset", "name": f"세계 외환보유액 순위 {per}", "description": "IMF IRFCL 및 각국 중앙은행 발표 기반 국가별 외환보유액 월별 순위",
          "url": BASE + "/", "license": "https://creativecommons.org/licenses/by/4.0/", "temporalCoverage": per, "creator": {"@type": "Organization", "name": NAME},
          "distribution": [{"@type": "DataDownload", "encodingFormat": "text/csv", "contentUrl": f"{BASE}/data/reserves_{per}.csv"}]}
    write("/", page(f"세계 외환보유액 순위 {kper(per)} — 한국 {kor['rank']}위 | {NAME}", body,
                    f"{kper(per)} 세계 외환보유액 순위. 한국 {kor['rank']}위 {fmt(kor['usd_bn']*10,0)}억달러. IMF·각국 중앙은행 자료 재집계, 매월 갱신.", "/", jsonld=ld))

def build_archive(months):
    for m in months:
        d = json.loads((DATA / f"reserves_{m}.json").read_text()); kor = next(r for r in d["rows"] if r["iso3"] == "KOR")
        body = f'<h1>세계 외환보유액 순위 {kper(m)}</h1><p class="sub">한국 {kor["rank"]}위 · {fmt(kor["usd_bn"]*10,0)}억달러 · 생성 {d["generated_at"][:10]}</p>{ranking_table(d["rows"])}<p class="note">{esc(d["note"])}</p><div class="ad">광고</div>'
        write(f"/ranking/{m}/", page(f"{kper(m)} 세계 외환보유액 순위 | {NAME}", body, f"{kper(m)} 국가별 외환보유액 순위표(IMF 기준). 한국 {kor['rank']}위.", f"/ranking/{m}/"))

def build_korea(kh, latest):
    last = kh[-1]; per = last["period"]; kor = next(r for r in latest["rows"] if r["iso3"] == "KOR")
    comp = [("유가증권", last["securities"]), ("예치금", last["deposits"]), ("SDR", last["sdr"]), ("IMF포지션·기타", last["imf_pos_other"]), ("금(장부가)", last["gold"])]
    tbl = "".join(f'<tr><td>{r["period"]}</td><td>{fmt(r["total"]*10,0)}</td><td>{delta((r["total"]-kh[i-1]["total"])*10) if i>0 else ""}</td><td>{fmt(r["securities"]*10,0)}</td><td>{fmt(r["deposits"]*10,0)}</td><td>{fmt(r["sdr"]*10,0)}</td><td>{fmt(r["gold"]*10,0)}</td></tr>'
                  for i, r in list(enumerate(kh))[-24:][::-1])
    yoy = next((r["total"] for r in kh if r["period"] == f"{int(per[:4])-1}{per[4:]}"), None)
    body = f"""<h1>한국 외환보유액 — {kper(per)} {fmt(last['total']*10,0)}억달러</h1>{('<div class="tiles">' + flash_block(per) + '</div>') if flash_block(per) else ''}
<p class="sub">세계 {kor['rank']}위 · 전년동월비 {delta((last['total']-yoy)*10) if yoy else '—'}억달러 · 자료 IMF IRFCL(한국은행 제출분, 한은 발표와 동일)</p>
<div class="grid2"><div><h2>구성 (10억달러)</h2>{bar_chart(comp)}<p class="note">한국은 금을 매입 당시 장부가(온스당 약 $1,427)로 계상. 시가 환산 시 약 {fmt(last['gold']*10,0)}억 → <a href="/gold/">금 페이지</a>.</p></div>
<div><h2>{'1971년' if KLONG else '2005년'} 이후 추이</h2>{line_chart(sorted(KLONG.items()) if KLONG else [(r['period'], r['total']) for r in kh])}
<p class="note">{('1997년 12월 ' + fmt(KLONG['1997-12']*10,0) + '억달러(외환위기) → 2008년 11월 ' + fmt(KLONG['2008-11']*10,0) + '억달러(금융위기) → ' + kper(max(KLONG)) + ' ' + fmt(KLONG[max(KLONG)]*10,0) + '억달러. 자료 한국은행 ECOS 732Y001.') if KLONG else ''}</p></div></div>
<div class="ad">광고</div>
<h2>최근 24개월 (억달러)</h2><div class="wrap"><table><thead><tr><th>기준월</th><th>총액</th><th>전월비</th><th>유가증권</th><th>예치금</th><th>SDR</th><th>금</th></tr></thead><tbody>{tbl}</tbody></table></div>
<p><a class="btn" href="/data/korea_history.csv">전체 월별 CSV</a><a class="btn" href="/data/korea_history.json">JSON</a></p>"""
    write("/korea/", page(f"한국 외환보유액 {kper(per)} {fmt(last['total']*10,0)}억달러 · 세계 {kor['rank']}위 | {NAME}", body,
                          f"한국 외환보유액 월별 추이(2005~)와 구성(유가증권·예치금·SDR·금·IMF포지션). {kper(per)} {fmt(last['total']*10,0)}억달러, 세계 {kor['rank']}위.", "/korea/"))

def build_countries(latest, ch, gold, lang="ko"):
    rows = latest["rows"]; gm = {r["iso3"]: r for r in gold["rows"]}
    pre = "" if lang == "ko" else "/en"
    idx = []
    for r in rows:
        c = r["iso3"]; name = r["name"] if lang == "ko" else EN.get(c, c); hist = ch.get(c, [])
        g = gm.get(c); y5 = next((v for p, v in hist if p == f"{int(r['as_of'][:4])-5}{r['as_of'][4:]}"), None)
        if lang == "ko":
            body = f"""<h1>{esc(name)} 외환보유액 — {kper(r['as_of'])} {fmt(r['usd_bn']*10,0)}억달러</h1>
<p class="sub">세계 {r['rank']}위 · 5년 전 대비 {delta((r['usd_bn']-y5)*10) if y5 else '—'}억달러 · 출처 {esc(r['source'])}</p>
<div class="tiles"><div class="tile"><span>순위</span><b>{r['rank']}위</b></div><div class="tile"><span>외환보유액</span><b>{fmt(r['usd_bn']*10,0)}억달러</b></div>
<div class="tile"><span>금 보유</span><b>{fmt(g['tonnes'],0)+'t' if g else '—'}</b><span>{('시가 '+fmt(g['gold_mkt_usd_bn']*10,0)+'억달러') if g and g['gold_mkt_usd_bn'] else ''}</span></div></div>
<h2>2015년 이후 추이 (10억달러)</h2>{line_chart(hist) if hist else '<p class="note">IMF 시계열 없음(비회원국).</p>'}
<div class="ad">광고</div><p><a href="/">전체 순위 →</a> · <a href="/data/">데이터 받기</a></p>"""
            write(f"/country/{c.lower()}/", page(f"{name} 외환보유액 {kper(r['as_of'])} · 세계 {r['rank']}위 | {NAME}", body, f"{name} 외환보유액 {fmt(r['usd_bn']*10,0)}억달러, 세계 {r['rank']}위. 2015년 이후 월별 추이와 금 보유량.", f"/country/{c.lower()}/"))
        else:
            body = f"""<h1>{esc(name)} Foreign Exchange Reserves — {eper(r['as_of'])}: ${fmt(r['usd_bn'])} bn</h1>
<p class="sub">Rank #{r['rank']} worldwide · 5-year change {delta(r['usd_bn']-y5) if y5 else '—'} bn · Source {esc(r['source'])}</p>
<h2>Since 2015 (USD bn)</h2>{line_chart(hist) if hist else '<p class="note">No IMF series (non-member).</p>'}<div class="ad">ad</div><p><a href="/en/">Full ranking →</a></p>"""
            write(f"/en/country/{c.lower()}/", page(f"{name} Foreign Exchange Reserves {eper(r['as_of'])} — Rank #{r['rank']} | {NAME}", body, f"{name} foreign exchange reserves ${fmt(r['usd_bn'])} billion, ranked #{r['rank']}. Monthly series since 2015 from IMF data.", f"/en/country/{c.lower()}/", lang="en"))
        idx.append(f'<li><a href="{pre}/country/{c.lower()}/">{esc(name)}</a> — {r["rank"]}{"위" if lang=="ko" else ""} · {fmt(r["usd_bn"]*10,0)+"억달러" if lang=="ko" else "$"+fmt(r["usd_bn"])+" bn"}</li>')
    t = "국가별 외환보유액" if lang == "ko" else "Foreign Exchange Reserves by Country"
    write(f"{pre}/country/", page(f"{t} | {NAME}", f"<h1>{t}</h1><ul>{''.join(idx)}</ul>", t, f"{pre}/country/", lang=lang))

def build_gold(gold, latest):
    per = gold["period"]; rows = gold["rows"]; rk = {r["iso3"]: r for r in latest["rows"]}
    mk = sorted([r for r in rows if r["total_gold_mkt"]], key=lambda r: -r["total_gold_mkt"])
    kor = next(r for r in rows if r["iso3"] == "KOR"); kor_mk = next(i for i, r in enumerate(mk, 1) if r["iso3"] == "KOR")
    t1 = "".join(f'<tr class="{"kor" if r["iso3"]=="KOR" else ""}"><td>{r["gold_rank"]}</td><td>{esc(r["name"])}</td><td>{fmt(r["tonnes"],0)}</td><td>{fmt(r["gold_mkt_usd_bn"]*10,0)}</td><td>{fmt(r["gold_usd_bn"]*10,0)}{" (장부가)" if r["book_value"] else ""}</td><td>{fmt(r["gold_mkt_usd_bn"]/r["total_gold_mkt"]*100,1)}%</td></tr>' for r in rows[:25])
    t2 = "".join(f'<tr class="{"kor" if r["iso3"]=="KOR" else ""}"><td>{i}</td><td>{esc(r["name"])}</td><td>{fmt(r["total_gold_mkt"]*10,0)}</td><td>{fmt(r["total"]*10,0)}</td><td>{rk[r["iso3"]]["rank"] if r["iso3"] in rk else "—"}</td></tr>' for i, r in enumerate(mk[:20], 1))
    body = f"""<h1>금 보유량 순위와 금 시가환산 외환보유액 — {kper(per)}</h1>
<p class="sub">IMF 템플릿 보고 금 온스 × 시가보고국 내재 금가격(중앙값 ${gold['market_px_usd_oz']:,}/oz, {gold['n_market_reporters']}개국). 한국은 {fmt(kor['tonnes'],1)}t를 장부가 {fmt(kor['gold_usd_bn']*10,0)}억달러로 계상 → 시가 {fmt(kor['gold_mkt_usd_bn']*10,0)}억달러.</p>
<div class="tiles"><div class="tile"><span>한국 금 보유</span><b>{fmt(kor['tonnes'],1)}t</b><span>금 보유 순위 {kor['gold_rank']}위</span></div>
<div class="tile"><span>금 시가환산 시 한국 총액</span><b>{fmt(kor['total_gold_mkt']*10,0)}억달러</b><span>시가환산 순위 {kor_mk}위</span></div>
<div class="tile"><span>내재 금가격</span><b>${gold['market_px_usd_oz']:,}</b><span>/oz, 시가보고국 중앙값</span></div></div>
<h2>금 보유량 순위 (상위 25)</h2><div class="wrap"><table><thead><tr><th>#</th><th>국가</th><th>톤</th><th>시가(억달러)</th><th>보고액(억달러)</th><th>총보유액 중 금 비중</th></tr></thead><tbody>{t1}</tbody></table></div>
<div class="ad">광고</div>
<h2>금 시가환산 외환보유액 순위 (상위 20)</h2><p class="note">미국은 금을 온스당 $42.22 법정가로 계상해 공식 총액이 낮게 잡힙니다. 시가로 바꾸면 순위가 달라집니다.</p>
<div class="wrap"><table><thead><tr><th>#</th><th>국가</th><th>시가환산 총액(억달러)</th><th>공식 총액</th><th>공식 순위</th></tr></thead><tbody>{t2}</tbody></table></div>
<p class="note">브라질 등 온스 단위 오보고 국가는 제외. 한은이 "금 시세로 순위가 널뛴다"고 한 현상을 그대로 보여주는 표입니다.</p>"""
    write("/gold/", page(f"금 보유량 순위·금 시가환산 외환보유액 {kper(per)} | {NAME}", body, f"국가별 중앙은행 금 보유량 순위와 금 시가환산 외환보유액 순위. 한국 {fmt(kor['tonnes'],1)}t, 시가환산 시 {fmt(kor['total_gold_mkt']*10,0)}억달러.", "/gold/"))

def build_methodology(bt, latest):
    btbl = ""
    if bt:
        btbl = "<div class='wrap'><table><thead><tr><th>#</th><th>국가</th><th>한은 표(10억달러)</th><th>본 사이트</th><th>차이</th><th>출처</th></tr></thead><tbody>" + "".join(
            f'<tr><td>{r["rank"]}</td><td>{esc(r["name"])}</td><td>{fmt(r["bok"])}</td><td>{fmt(r["ours"])}</td><td>{delta(r["diff"]) if r["diff"] is not None else "—"}</td><td>{esc(r["source"])}</td></tr>' for r in bt["rows"]) + "</tbody></table></div>" + f"<p class='note'>{esc(bt['summary'])}</p>"
    body = f"""<h1>방법론 · 검증 · 정정</h1>
<h2>집계 방식</h2>
<p>순위 본체는 IMF 국제준비자산·외화유동성 템플릿(IRFCL)의 <code>Official reserve assets</code>(IRFCLDT1_IRFCL65_USD, 월말, 미달러)입니다. IMF 회원국 40개국을 대상으로 하고, IMF 비회원인 대만은 중앙은행(CBC) 월간 보도자료 값을 씁니다.
중국은 국가외환관리국(SAFE)이 발표하는 외환보유액 헤드라인(금·SDR·IMF포지션 제외)을 쓰는데, 한국은행이 순위표에 쓰던 방식과 같습니다. 사우디는 IMF 제출이 두 달 늦어 SAMA 발표를 직접 씁니다.</p>
<p>같은 기준월 값끼리만 순위를 매깁니다. 아직 발표하지 않은 국가는 직전 월 값을 넣고 표에 <b>*</b>로 표시합니다. 한국의 당월 수치가 먼저 나와도, 다른 나라 수치가 모이기 전에는 순위를 확정하지 않습니다.</p>
<h2>한국은행 마지막 순위표 재현 (2026년 6월말 기준, 8월 5일 발표)</h2>
<p>한국은행이 마지막으로 공개한 표를 위 방식으로 재현한 결과입니다. 이 표가 본 사이트 집계의 검증 기준입니다.</p>{btbl}
<h2>출처 URL</h2><ul>
<li>IMF IRFCL SDMX: <code>https://api.imf.org/external/sdmx/2.1/data/IMF.STA,IRFCL/…</code> (공개, 키 없음)</li>
<li>대만 CBC: <code>https://www.cbc.gov.tw/en/lp-448-2.html</code> Foreign Exchange Reserves 보도자료</li>
<li>한국은행 보도자료 "월말 외환보유액" · 중국 SAFE Official Reserve Assets · 사우디 SAMA Monthly Statistics</li></ul>
<h2>재현</h2><p>수집·집계 코드와 원본 파일(raw)은 공개 저장소 <a href="{CFG.get('repo_url','#')}">{esc(CFG.get('repo_url','(준비 중)'))}</a>에 두고, 매일 수집 원본을 스냅샷으로 보관합니다. 누구나 같은 명령으로 같은 표를 얻을 수 있습니다.</p>
<pre>python3 fetch_reserves.py      # IMF + CBC → data/reserves_YYYY-MM.json
python3 backtest_bok.py        # 한은 6월표 대조
python3 build_site.py          # site/</pre>
<h2 id="errata">정정 로그</h2><ul id="errata-list">{''.join(f'<li>{esc(e)}</li>' for e in CFG.get('errata', [])) or '<li>없음 (개설 2026-09-03)</li>'}</ul>
<h2>이 사이트가 아닌 것</h2><p>한국은행·IMF의 공식 발표가 아닙니다. 순위는 각국 보고 시점·평가 방식(특히 금 시가)에 따라 흔들리며, 대외건전성 지표로 쓰기에는 <a href="/articles/">해설</a>에서 다루는 단기외채 대비 비율 등이 더 적합합니다.</p>"""
    write("/methodology/", page(f"방법론·검증·정정 | {NAME}", body, "외환보유액 순위 집계 방법, 한국은행 마지막 순위표 재현 검증, 출처 URL, 정정 로그.", "/methodology/"))

def build_data(latest, kh, months):
    per = latest["period"]; dd = SITE / "data"; dd.mkdir(parents=True, exist_ok=True)
    for m in months:
        d = json.loads((DATA / f"reserves_{m}.json").read_text())
        buf = io.StringIO(); w = csv.writer(buf); w.writerow(["rank", "iso3", "name", "usd_bn", "as_of", "gold_usd_bn", "source"])
        for r in d["rows"]: w.writerow([r["rank"], r["iso3"], r["name"], r["usd_bn"], r["as_of"], r["gold_usd_bn"], r["source"]])
        (dd / f"reserves_{m}.csv").write_text(buf.getvalue(), encoding="utf-8-sig"); (dd / f"reserves_{m}.json").write_text(json.dumps(d, ensure_ascii=False))
    buf = io.StringIO(); w = csv.writer(buf); w.writerow(list(kh[0].keys()))
    for r in kh: w.writerow(list(r.values()))
    (dd / "korea_history.csv").write_text(buf.getvalue(), encoding="utf-8-sig"); (dd / "korea_history.json").write_text(json.dumps(kh, ensure_ascii=False))
    for f in ("gold.json", "country_history.json"): (dd / f).write_text((DATA / f).read_text())
    cite = f"{NAME}, 「세계 외환보유액 순위 {kper(per)}」, IMF IRFCL·각국 중앙은행 자료 재집계, {BASE}/ranking/{per}/ (접속 {dt.date.today()})"
    body = f"""<h1>데이터 다운로드</h1><p class="sub">CC BY 4.0 — 출처만 밝히면 기사·블로그·논문에 자유롭게 쓸 수 있습니다.</p>
<h2>월별 순위표</h2><ul>{''.join(f'<li>{kper(m)} — <a href="/data/reserves_{m}.csv">CSV</a> · <a href="/data/reserves_{m}.json">JSON</a></li>' for m in reversed(months))}</ul>
<h2>한국 월별 시계열 (2005~)</h2><p><a class="btn" href="/data/korea_history.csv">CSV</a><a class="btn" href="/data/korea_history.json">JSON</a></p>
<h2>기타</h2><p><a class="btn" href="/data/gold.json">금 보유·시가환산 JSON</a><a class="btn" href="/data/country_history.json">40개국 2015~ 월별 JSON</a></p>
<h2>인용 문구</h2><pre>{esc(cite)}</pre>
<h2>기자·연구자용</h2><p>매월 순위 확정 시 <a href="/rss.xml">RSS</a>에 요약(한국 순위·금액·전월비·상위 10)이 올라갑니다. 표를 그대로 넣으려면 <a href="/embed/">퍼가기</a>.</p>"""
    write("/data/", page(f"데이터 다운로드 | {NAME}", body, "국가별 외환보유액 월별 순위 CSV/JSON, 한국 2005년 이후 월별 시계열, 금 보유 데이터. CC BY 4.0.", "/data/"))

def build_embed(latest):
    per = latest["period"]; t = ranking_table(latest["rows"], limit=12)
    mini = f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>{CSS}body{{font-size:14px}}main{{padding:8px}}</style></head>
<body><main><b>세계 외환보유액 순위 {kper(per)}</b>{t}<p class="note">자료 IMF·각국 중앙은행 · <a href="{BASE}/ranking/{per}/" target="_blank">{esc(NAME)}</a></p></main></body></html>"""
    (SITE / "embed").mkdir(parents=True, exist_ok=True); (SITE / "embed" / "ranking.html").write_text(mini, encoding="utf-8")
    code = f'<iframe src="{BASE}/embed/ranking.html" width="100%" height="520" style="border:1px solid #e5e5e5;border-radius:8px" loading="lazy" title="세계 외환보유액 순위"></iframe>\n<p>자료: <a href="{BASE}/">{NAME}</a></p>'
    body = f"""<h1>순위표 퍼가기</h1><p class="sub">아래 코드를 블로그·기사 본문에 붙이면 매월 자동으로 최신 표가 표시됩니다. 출처 링크는 유지해 주세요.</p><pre>{esc(code)}</pre><h2>미리보기</h2>{code}"""
    write("/embed/", page(f"순위표 퍼가기(임베드) | {NAME}", body, "세계 외환보유액 순위표 iframe 임베드 코드.", "/embed/"))

def md_to_html(md):
    out, para = [], []
    def flush():
        if para: out.append("<p>" + " ".join(para) + "</p>"); para.clear()
    for line in md.splitlines():
        if line.startswith("## "): flush(); out.append(f"<h2>{esc(line[3:])}</h2>")
        elif line.startswith("- "): flush(); out.append(f"<ul><li>{esc(line[2:])}</li></ul>")
        elif line.strip() == "": flush()
        else: para.append(re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', esc(line)))
    flush(); return "".join(out).replace("</ul><ul>", "")

def build_articles():
    items = []
    for f in sorted(CONTENT.glob("*.md")) if CONTENT.exists() else []:
        txt = f.read_text(encoding="utf-8"); m = re.match(r"---\n(.*?)\n---\n(.*)", txt, re.S)
        meta = dict(l.split(":", 1) for l in m.group(1).splitlines() if ":" in l) if m else {}
        meta = {k.strip(): v.strip() for k, v in meta.items()}; body_md = m.group(2) if m else txt
        slug = meta.get("slug", f.stem); title = meta.get("title", f.stem); desc = meta.get("description", "")
        body = f'<article><h1>{esc(title)}</h1><p class="sub">{esc(meta.get("date",""))} · <span class="tag">해설</span></p>{md_to_html(body_md)}<div class="ad">광고</div><p><a href="/">현재 순위표 →</a></p></article>'
        write(f"/articles/{slug}/", page(f"{title} | {NAME}", body, desc, f"/articles/{slug}/"))
        items.append((slug, title, desc, meta.get("date", "")))
    lst = "".join(f'<li><a href="/articles/{s}/">{esc(t)}</a><br><span class="note">{esc(d)}</span></li>' for s, t, d, _ in items) or "<li>준비 중</li>"
    write("/articles/", page(f"해설 | {NAME}", f"<h1>외환보유액 해설</h1><ul>{lst}</ul>", "외환보유액의 뜻, 구성, 적정 규모, 순위의 한계 등 해설.", "/articles/"))
    return items

def build_en(latest, prev):
    rows = latest["rows"]; per = latest["period"]; kor = next(r for r in rows if r["iso3"] == "KOR")
    body = f"""<h1>Foreign Exchange Reserves by Country — {eper(per)}</h1>
<p class="sub">Monthly ranking compiled from the IMF International Reserves template (IRFCL) and central-bank releases (Taiwan CBC, China SAFE, Saudi SAMA). Updated {latest['generated_at'][:10]}. <a href="/data/">Download CSV</a></p>
{ranking_table(rows, prev['rows'] if prev else None, lang='en')}
<p class="note">* Latest month not yet reported; previous month shown. Gold at market value per IMF template except book-value reporters (Korea, US, Singapore) — see gold-adjusted view (KO). Korea ranks #{kor['rank']}.</p><div class="ad">ad</div>"""
    write("/en/", page(f"Foreign Exchange Reserves by Country {eper(per)} | {NAME}", body, f"List of countries by foreign exchange reserves, {eper(per)}, from IMF and central bank data. Monthly update.", "/en/", lang="en"))

def build_press(latest, prev, kh):
    """기자용 월간 요약 + SVG 카드 + SNS 포스트 초안(발송은 사람)."""
    rows = latest["rows"]; per = latest["period"]; kor = next(r for r in rows if r["iso3"] == "KOR")
    pm = {r["iso3"]: r for r in prev["rows"]} if prev else {}
    movers = sorted([(r, r["usd_bn"] - pm[r["iso3"]]["usd_bn"]) for r in rows if r["iso3"] in pm and pm[r["iso3"]]["as_of"] != r["as_of"]], key=lambda t: -abs(t[1]))[:5]
    rank_chg = [(r, pm[r["iso3"]]["rank"] - r["rank"]) for r in rows[:15] if r["iso3"] in pm and pm[r["iso3"]]["rank"] != r["rank"]]
    kprev = kh[-2]["total"] if len(kh) > 1 else None
    lead = (f"{kper(per)} 세계 외환보유액 순위에서 한국은 {fmt(kor['usd_bn']*10,0)}억달러로 {kor['rank']}위다"
            + (f"(전월 {pm['KOR']['rank']}위)" if 'KOR' in pm else "") + f". 전월 대비 {fmt((kor['usd_bn']-kprev)*10,0) if kprev else '—'}억달러 변동. "
            f"1위 {rows[0]['name']} {fmt(rows[0]['usd_bn']*10,0)}억달러, 한국 바로 위 {rows[kor['rank']-2]['name']} {fmt(rows[kor['rank']-2]['usd_bn']*10,0)}억달러, 바로 아래 {rows[kor['rank']]['name']} {fmt(rows[kor['rank']]['usd_bn']*10,0)}억달러.")
    mv = "".join(f"<li>{esc(r['name'])} {delta(d*10)}억달러 → {fmt(r['usd_bn']*10,0)}억달러 ({r['rank']}위)</li>" for r, d in movers) or "<li>전월 비교 데이터 없음</li>"
    rc = "".join(f"<li>{esc(r['name'])} {pm[r['iso3']]['rank']}위 → {r['rank']}위</li>" for r, _ in rank_chg) or "<li>상위 15개국 순위 변동 없음</li>"
    body = f"""<h1>기자용 요약 — 세계 외환보유액 순위 {kper(per)}</h1><p class="sub">인용 시 출처 "{esc(NAME)}, IMF·각국 중앙은행 자료 재집계" 표기. 확정 여부: {'확정' if all(r['as_of']==per for r in rows[:12]) else '잠정(일부 국가 직전 월 값)'}</p>
<h2>리드</h2><p>{lead}</p><h2>전월 대비 변동 큰 국가</h2><ul>{mv}</ul><h2>상위 15개국 순위 변동</h2><ul>{rc}</ul>
<h2>상위 12</h2>{ranking_table(rows, prev['rows'] if prev else None, limit=12)}
<p><a class="btn" href="/data/reserves_{per}.csv">CSV</a><a class="btn" href="/embed/">표 퍼가기</a><a class="btn" href="/embed/card_{per}.svg">이미지 카드(SVG)</a></p>"""
    write(f"/press/{per}/", page(f"기자용 요약 {kper(per)} 세계 외환보유액 순위 | {NAME}", body, lead[:150], f"/press/{per}/"))
    write("/press/", page(f"기자용 요약 | {NAME}", f"<h1>기자용 월간 요약</h1><ul><li><a href='/press/{per}/'>{kper(per)}</a></li></ul>", "월간 요약 목록", "/press/"))
    # SVG 카드 (img 태그로 퍼갈 수 있는 정적 이미지)
    items = [(r["name"], r["usd_bn"]) for r in rows[:15]]
    card = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 {22*15+70}" font-family="Malgun Gothic,Apple SD Gothic Neo,sans-serif"><rect width="100%" height="100%" fill="#fff"/>'
            f'<text x="16" y="28" font-size="18" font-weight="700">세계 외환보유액 순위 {kper(per)} (10억달러)</text><g transform="translate(0,40)">'
            + bar_chart(items).split(">", 1)[1].rsplit("</svg>", 1)[0] + f'</g><text x="16" y="{22*15+62}" font-size="11" fill="#888">자료 IMF IRFCL·각국 중앙은행 · {BASE}</text></svg>')
    (SITE / "embed").mkdir(parents=True, exist_ok=True); (SITE / "embed" / f"card_{per}.svg").write_text(card, encoding="utf-8")
    (SITE / "embed" / "card_latest.svg").write_text(card, encoding="utf-8")
    post = (f"[{kper(per)} 세계 외환보유액 순위] 한국 {kor['rank']}위 {fmt(kor['usd_bn']*10,0)}억달러"
            + (f" (전월 {pm['KOR']['rank']}위)" if 'KOR' in pm else "") + "\n" + "\n".join(f"{r['rank']}. {r['name']} {fmt(r['usd_bn']*10,0)}" for r in rows[:10])
            + f"\n자료 IMF·각국 중앙은행 재집계 → {BASE}/ranking/{per}/\n#외환보유액 #외환보유액순위")
    (DATA / f"post_{per}.txt").write_text(post, encoding="utf-8")

def build_static(latest, months, articles):
    per = latest["period"]; kor = next(r for r in latest["rows"] if r["iso3"] == "KOR"); top = ", ".join(f"{r['rank']}.{r['name']} {fmt(r['usd_bn']*10,0)}" for r in latest["rows"][:10])
    items = [(f"{BASE}/ranking/{m}/", f"세계 외환보유액 순위 {kper(m)}", "") for m in reversed(months)]
    items[0] = (items[0][0], items[0][1] + f" — 한국 {kor['rank']}위 {fmt(kor['usd_bn']*10,0)}억달러", f"상위 10(억달러): {top}")
    items += [(f"{BASE}/articles/{s}/", t, d) for s, t, d, _ in articles]
    rss = f'<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>{esc(NAME)}</title><link>{BASE}/</link><description>IMF·중앙은행 자료 기반 세계 외환보유액 월별 순위</description>' + "".join(
        f"<item><title>{esc(t)}</title><link>{u}</link><guid>{u}</guid><description>{esc(d)}</description></item>" for u, t, d in items) + "</channel></rss>"
    (SITE / "rss.xml").write_text(rss, encoding="utf-8")
    (SITE / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + "".join(f"<url><loc>{BASE}{u}</loc></url>" for u in sorted(set(URLS))) + "</urlset>", encoding="utf-8")
    (SITE / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {BASE}/sitemap.xml\n")
    if CFG.get("adsense_pub"): (SITE / "ads.txt").write_text(f"google.com, {CFG['adsense_pub']}, DIRECT, f08c47fec0942fa0\n")
    for slug, title, txt in [("about", "소개", CFG.get("about_html", "<p>한국은행이 2026년 9월 순위표 공개를 중단한 뒤, IMF와 각국 중앙은행이 공개하는 원자료로 같은 표를 매월 만들어 올립니다. 운영자 연락처는 사이트 설정에서 지정합니다.</p>")),
                             ("privacy", "개인정보 처리방침", "<p>이 사이트는 회원가입이나 개인정보 입력을 받지 않습니다. 광고(Google AdSense)와 접속 통계에 쿠키가 사용될 수 있으며, 브라우저 설정으로 거부할 수 있습니다. Google의 광고 쿠키 사용에 관한 내용은 <a href='https://policies.google.com/technologies/ads'>Google 광고 정책</a>을 참고하세요.</p>"),
                             ("contact", "문의", CFG.get("contact_html", "<p>정정 요청·데이터 문의: 사이트 설정의 연락처.</p>"))]:
        write(f"/{slug}/", page(f"{title} | {NAME}", f"<h1>{title}</h1>{txt}", title, f"/{slug}/"))

def main():
    latest, kh, ch, gold, months, prev, bt = load()
    build_home(latest, prev, kh, months); build_archive(months); build_korea(kh, latest)
    build_countries(latest, ch, gold, "ko"); build_countries(latest, ch, gold, "en"); build_gold(gold, latest)
    build_methodology(bt, latest); build_data(latest, kh, months); build_embed(latest); arts = build_articles(); build_en(latest, prev); build_press(latest, prev, kh)
    build_static(latest, months, arts)
    print(f"site/: {len(set(URLS))} 페이지, 기준월 {latest['period']}, 글 {len(arts)}편")

if __name__ == "__main__":
    main()
