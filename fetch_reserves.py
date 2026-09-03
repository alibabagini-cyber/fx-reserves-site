#!/usr/bin/env python3
"""외환보유액 국가별 순위 수집 — 한은 순위표 비공개(2026-09-03) 대체 루트.

소스
  1. IMF IRFCL (SDMX 2.1, 키 불필요)  : 회원국 전부, 월말 공식준비자산(IRFCL65)·금(IRFCL56)
  2. 대만 중앙은행(CBC) 보도자료      : IMF 비회원이라 IRFCL에 없음 → 보도자료 파싱
  3. 한국은행 보도자료(옵션)           : 한국 최신월은 IMF보다 2~4주 빠름 → 수동/ECOS 보강

출력: data/reserves_<YYYY-MM>.json, data/latest.json
"""
import csv, io, json, re, sys, urllib.request, datetime as dt
from pathlib import Path

IMF = "https://api.imf.org/external/sdmx/2.1/data/IMF.STA,IRFCL/{keys}.{ind}?startPeriod={start}&format=csv"
IND_TOTAL, IND_GOLD = "IRFCLDT1_IRFCL65_USD", "IRFCLDT1_IRFCL56_USD"
# 한은 구 순위표 + 상위 25개국 후보 (ISO3). 대만은 별도.
COUNTRIES = ("CHN JPN CHE IND RUS SAU HKG KOR SGP DEU BRA ITA FRA GBR MEX THA USA POL IDN ISR "
             "CZE TUR MYS PHL ESP NLD BEL SWE NOR DNK CAN AUS ZAF COL PER CHL EGY ARG ROU HUN").split()
NAMES = {"CHN":"중국","JPN":"일본","CHE":"스위스","IND":"인도","RUS":"러시아","SAU":"사우디아라비아","HKG":"홍콩",
         "KOR":"한국","SGP":"싱가포르","DEU":"독일","BRA":"브라질","ITA":"이탈리아","FRA":"프랑스","GBR":"영국",
         "MEX":"멕시코","THA":"태국","USA":"미국","POL":"폴란드","IDN":"인도네시아","ISR":"이스라엘","CZE":"체코",
         "TUR":"튀르키예","MYS":"말레이시아","PHL":"필리핀","ESP":"스페인","NLD":"네덜란드","BEL":"벨기에",
         "SWE":"스웨덴","NOR":"노르웨이","DNK":"덴마크","CAN":"캐나다","AUS":"호주","ZAF":"남아공","COL":"콜롬비아",
         "PER":"페루","CHL":"칠레","EGY":"이집트","ARG":"아르헨티나","ROU":"루마니아","HUN":"헝가리","TWN":"대만"}
CBC_LIST = "https://www.cbc.gov.tw/en/lp-448-2.html"  # 대만 CBC 보도자료 목록(영문)
# 한은 순위표 방식과 맞추기 위한 직접소스(정의·지연 차이): 중국=SAFE 헤드라인(금·SDR·RTP 제외, IMF 총액보다 ~370B 작음),
# 사우디=SAMA(IMF 2개월 지연). 각 함수는 최신월만 주므로 data/direct_cache.json 에 월별로 누적한다.
DIRECT = {"CHN": ("safe_china", "SAFE 외환보유액(금 제외)"), "SAU": ("sama_saudi", "SAMA Reserve Assets")}

def get(url, accept="text/csv", timeout=90):
    req = urllib.request.Request(url, headers={"Accept": accept, "User-Agent": "fx-reserves-site/0.1"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "ignore")

def imf(ind, start):
    rows = csv.DictReader(io.StringIO(get(IMF.format(keys="+".join(COUNTRIES), ind=ind, start=start))))
    out = {}
    for r in rows:
        if r["FREQUENCY"] == "M" and r["OBS_VALUE"]:
            out.setdefault(r["COUNTRY"], {})[r["TIME_PERIOD"].replace("-M", "-")] = float(r["OBS_VALUE"]) / 1e9
    return out

def taiwan(period=None):
    """CBC 영문 보도자료 목록에서 'Foreign Exchange Reserves as of the End of <Month YYYY>' 링크→본문의 US$ 금액.
    period 지정 시 그 달(없으면 그 이전 최신) 보도자료를 고른다."""
    found = []
    for pg in (1, 2, 3, 4):  # 페이지당 20건, 월 1건이라 4페이지≈6개월 커버
        html = get(f"https://www.cbc.gov.tw/en/lp-448-2-{pg}-20.html", accept="text/html")
        for m in re.finditer(r'href="(/en/cp-448-\d+-[0-9a-f]+-2\.html)"[^>]*>[^<]*Foreign Exchange Reserves as of the End of (\w+ \d{4})', html):
            per = dt.datetime.strptime(m.group(2), "%B %Y").strftime("%Y-%m")
            if period is None or per <= period:
                found.append((per, m.group(1)))
        if found and (period is None or max(found)[0] == period):
            break
    if not found:
        return None
    per, path = max(found)
    body = get("https://www.cbc.gov.tw" + path, accept="text/html")
    v = re.search(r'US\$\s*([\d,]+\.?\d*)\s*billion', body)
    return per, float(v.group(1).replace(",", "")), "https://www.cbc.gov.tw" + path

def main(period=None):
    start = (dt.date.today().replace(day=1) - dt.timedelta(days=120)).strftime("%Y-%m")
    total, gold = imf(IND_TOTAL, start), imf(IND_GOLD, start)
    # 기준월 = 한국·중국·일본이 모두 보고한 최신 월(미지정 시)
    if not period:
        common = set.intersection(*(set(total[c]) for c in ("KOR", "CHN", "JPN")))
        period = max(common)
    rows = []
    for c, d in total.items():
        per = period if period in d else max(k for k in d if k <= period)  # 지연국은 직전 월(as_of 표기)
        rows.append({"iso3": c, "name": NAMES.get(c, c), "usd_bn": round(d[per], 1), "usd_exact": round(d[per], 4), "as_of": per,
                     "gold_usd_bn": round(gold.get(c, {}).get(per, 0.0), 1), "source": "IMF IRFCL"})
    # 직접소스 덮어쓰기 (SAFE/SAMA) — 캐시 우선, 없으면 조회
    cache_p = Path(__file__).parent / "data" / "direct_cache.json"
    cache = json.loads(cache_p.read_text()) if cache_p.exists() else {}
    try:
        sys.path.insert(0, str(Path(__file__).parent / "probe")); import sources_direct
    except Exception:
        sources_direct = None
    for c, (fn, label) in DIRECT.items():
        if sources_direct and period not in cache.get(c, {}):
            got = getattr(sources_direct, fn)()
            if got:
                cache.setdefault(c, {})[got[0]] = [got[1], got[2]]
        avail = {k: v for k, v in cache.get(c, {}).items() if k <= period}
        if avail:
            k = max(avail); val, url = avail[k]
            for r in rows:
                if r["iso3"] == c:
                    r.update(usd_bn=val, usd_exact=val, as_of=k, source=f"{label} {url}")
    cache_p.parent.mkdir(exist_ok=True); cache_p.write_text(json.dumps(cache, ensure_ascii=False, indent=1))
    tw = taiwan(period)
    if tw:
        rows.append({"iso3": "TWN", "name": "대만", "usd_bn": tw[1], "usd_exact": tw[1], "as_of": tw[0], "gold_usd_bn": None,
                     "source": tw[2]})
    rows.sort(key=lambda r: -r["usd_exact"])  # 반올림 전 값으로 정렬(한국·싱가포르 427.9 동률 사례)
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    out = {"period": period, "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
           "note": "as_of<period 인 국가는 지연 보고(직전 월 값). 금은 시장가치(IMF 템플릿) — 한국은 장부가 보고.",
           "rows": rows}
    d = Path(__file__).parent / "data"; d.mkdir(exist_ok=True)
    (d / f"reserves_{period}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    lp = d / "latest.json"
    if not lp.exists() or json.loads(lp.read_text())["period"] <= period:  # 과거월 재생성이 latest를 덮지 않게
        lp.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    kor = next(r for r in rows if r["iso3"] == "KOR")
    print(f"{period}: {len(rows)}개국, 한국 {kor['rank']}위 ${kor['usd_bn']}B")
    for r in rows[:12]:
        print(f"{r['rank']:>2} {r['name']:<9} {r['usd_bn']:>8,.1f}B  as_of={r['as_of']}")

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
