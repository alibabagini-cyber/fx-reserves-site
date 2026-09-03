#!/usr/bin/env python3
"""한국은행 ECOS 732Y001(외환보유액) — 한국 최신월 속보 + 1971~ 장기 시계열.

키: 환경변수 ECOS_API_KEY(.env) 없으면 공개 'sample' 키(호출당 최대 10행) 사용.
출력 data/bok_latest.json (최근 2개월 구성), data/korea_long.json (1971-01~ 합계, 캐시 누적)
검증 2026-09-03: 202608 합계 442,281,314천달러 = 한은 보도자료 4,422.8억달러.
"""
import json, os, urllib.request, datetime as dt
from pathlib import Path

D = Path(__file__).parent / "data"
ENV = Path(__file__).parent / ".env"
KEY = os.environ.get("ECOS_API_KEY") or (dict(l.split("=", 1) for l in ENV.read_text().splitlines() if "=" in l).get("ECOS_API_KEY") if ENV.exists() else None) or "sample"
ITEMS = {"01": "gold", "02": "sdr", "03": "imf_pos", "04": "fx", "99": "total"}

def ecos(stat, start, end, item="", n=10):
    url = f"https://ecos.bok.or.kr/api/StatisticSearch/{KEY}/json/kr/1/{n}/{stat}/M/{start}/{end}" + (f"/{item}" if item else "")
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "fx-reserves-site/0.1"}), timeout=30) as r:
        d = json.load(r)
    if "StatisticSearch" not in d:
        raise RuntimeError(d.get("RESULT"))
    return d["StatisticSearch"]["row"]

def latest():
    end = dt.date.today().strftime("%Y%m"); start = (dt.date.today().replace(day=1) - dt.timedelta(days=40)).strftime("%Y%m")
    rows = ecos("732Y001", start, end)
    by = {}
    for r in rows:
        by.setdefault(r["TIME"], {})[ITEMS[r["ITEM_CODE1"]]] = round(float(r["DATA_VALUE"]) / 1e6, 3)  # 천달러 → 10억달러
    months = sorted(by)
    out = {"source": "한국은행 ECOS 732Y001", "fetched_at": dt.datetime.now().isoformat(timespec="seconds"),
           "months": {m[:4] + "-" + m[4:]: by[m] for m in months}}
    D.mkdir(exist_ok=True); (D / "bok_latest.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    m = months[-1]; cur = by[m]["total"]; pv = by[months[-2]]["total"] if len(months) > 1 else None
    base = json.loads((Path(__file__).parent / "site.json").read_text()).get("base_url", "")
    (D / f"post_flash_{m[:4]}-{m[4:]}.txt").write_text(  # D-0 SNS 초안(발송은 사람)
        f"[속보] {m[:4]}년 {int(m[4:])}월말 한국 외환보유액 {cur*10:,.1f}억달러" + (f" (전월비 {(cur-pv)*10:+,.1f}억)" if pv else "") +
        f"\n구성: 외환 {by[m]['fx']*10:,.0f} · SDR {by[m]['sdr']*10:,.0f} · IMF포지션 {by[m]['imf_pos']*10:,.0f} · 금 {by[m]['gold']*10:,.0f}(장부가)"
        f"\n세계 순위는 각국 발표가 모이면 확정 → {base}/korea/\n#외환보유액 #한국은행", encoding="utf-8")
    return out

def long_series():
    p = D / "korea_long.json"; have = json.loads(p.read_text()) if p.exists() else {}
    y = 1971
    while y <= dt.date.today().year:
        s, e = f"{y}01", f"{y}12"
        if all(f"{y}-{m:02d}" in have for m in range(1, 13)) and y < dt.date.today().year:
            y += 1; continue
        try:
            rows = ecos("732Y001", s, e, "99", 12)
        except RuntimeError:                       # sample 키는 10행 제한 → 반기 2회
            rows = ecos("732Y001", s, f"{y}06", "99", 6) + ecos("732Y001", f"{y}07", e, "99", 6)
        for r in rows:
            have[r["TIME"][:4] + "-" + r["TIME"][4:]] = round(float(r["DATA_VALUE"]) / 1e6, 3)
        y += 1
    p.write_text(json.dumps(dict(sorted(have.items())), ensure_ascii=False))
    return have

if __name__ == "__main__":
    o = latest(); m = max(o["months"]); print(f"ECOS 최신 {m}: 합계 {o['months'][m]['total']}B  키={'sample' if KEY=='sample' else 'env'}")
    h = long_series(); ks = sorted(h); print(f"장기 시계열 {ks[0]}~{ks[-1]} {len(h)}행, 1997-12={h.get('1997-12')}B, 2008-11={h.get('2008-11')}B")
