#!/usr/bin/env python3
"""동반 데이터 수집 (IMF IRFCL, 키 불필요).

산출
  data/korea_history.json   : 한국 2000-01~ 월별 총액·구성(증권/예치금/금/SDR/IMF포지션+기타)
  data/country_history.json : 후보국 2015-01~ 월별 총액(IRFCL65) — 국가별 페이지 추이용
  data/gold.json            : 국가별 금 보유량(온스·톤)·평가액, 시가보고국 내재 금가격, 한국 시가환산액, 금 시가 순위
"""
import csv, io, json, urllib.request, datetime as dt
from pathlib import Path
from fetch_reserves import COUNTRIES, NAMES, IMF, get

OZ_PER_TONNE = 32150.7466
CODES = {  # IRFCL Section I 구성 (2026-09-03 한국 7월분으로 검증: 401.8+4.8+15.7+3.1+2.5=427.9)
    "total": "IRFCLDT1_IRFCL65_USD",
    "fx": "IRFCLDT1_IRFCLCDCFC_USD",          # 외화자산(증권+예치금)
    "securities": "IRFCLDT1_IRFCL32_USD",
    "gold": "IRFCLDT1_IRFCL56_USD",
    "gold_oz": "IRFCLDT1_IRFCL56V_FTO",      # 트로이온스(원값, 한국 3.36e6oz=104.4t 검증)
    "sdr": "IRFCLDT1_IRFCL65_DIC_XDR_USD",
    "imf_pos": "IRFCLDT1_IRFCL57_USD",
    "other": "IRFCLDT1_IRFCL58_USD",
}
INV = {v: k for k, v in CODES.items()}

def pull(keys, inds, start):
    url = IMF.format(keys="+".join(keys), ind="+".join(inds), start=start)
    out = {}  # (country, period) -> {field: value}
    for r in csv.DictReader(io.StringIO(get(url))):
        if r["FREQUENCY"] != "M" or not r["OBS_VALUE"]:
            continue
        per = r["TIME_PERIOD"].replace("-M", "-")
        f = INV[r["INDICATOR"]]
        v = float(r["OBS_VALUE"])
        out.setdefault((r["COUNTRY"], per), {})[f] = v if f == "gold_oz" else v / 1e9
    return out

def korea_history():
    d = pull(["KOR"], list(CODES.values()), "2000-01")
    rows = []
    for (c, per), f in sorted(d.items()):
        if "total" not in f:
            continue
        fx, sec = f.get("fx"), f.get("securities")
        rows.append({"period": per, "total": round(f["total"], 3),
                     "securities": round(sec, 3) if sec is not None else None,
                     "deposits": round(fx - sec, 3) if fx is not None and sec is not None else None,
                     "gold": round(f.get("gold", 0), 3), "sdr": round(f.get("sdr", 0), 3),
                     "imf_pos_other": round(f.get("imf_pos", 0) + f.get("other", 0), 3)})
    return rows

def country_history():
    d = pull(COUNTRIES, [CODES["total"]], "2015-01")
    out = {}
    for (c, per), f in sorted(d.items()):
        out.setdefault(c, []).append([per, round(f["total"], 1)])
    return out

def gold_table(period):
    d = pull(COUNTRIES, [CODES["total"], CODES["gold"], CODES["gold_oz"]], period)
    rows, implied = [], []
    for (c, per), f in d.items():
        if per != period or "gold" not in f or not f.get("gold_oz"):
            continue
        oz = f["gold_oz"]
        px = f["gold"] * 1e9 / oz
        if oz / OZ_PER_TONNE > 9000:  # 단위 오보고(예: 브라질 172,446t) — 제외
            continue
        rows.append({"iso3": c, "name": NAMES.get(c, c), "gold_usd_bn": round(f["gold"], 1),
                     "tonnes": round(oz / OZ_PER_TONNE, 1), "implied_px": round(px), "total": round(f["total"], 1)})
        implied.append(px)
    top = sorted(implied)[len(implied) // 2:]  # 상위 절반 중앙값 = 시가 보고국 내재가격 (장부가국: 미국 $42·한국 $1,427·싱가포르 $891)
    mkt_px = sorted(top)[len(top) // 2] if top else None
    implied = [px for px in implied if px > 0.6 * mkt_px] if mkt_px else []
    for r in rows:
        r["book_value"] = r["implied_px"] < 0.6 * mkt_px if mkt_px else None
        r["gold_mkt_usd_bn"] = round(r["tonnes"] * OZ_PER_TONNE * mkt_px / 1e9, 1) if mkt_px else None
        r["total_gold_mkt"] = round(r["total"] - r["gold_usd_bn"] + r["gold_mkt_usd_bn"], 1) if mkt_px else None
        r["total_ex_gold"] = round(r["total"] - r["gold_usd_bn"], 1)
    rows.sort(key=lambda r: -r["gold_mkt_usd_bn"])
    for i, r in enumerate(rows, 1):
        r["gold_rank"] = i
    return {"period": period, "market_px_usd_oz": round(mkt_px) if mkt_px else None,
            "n_market_reporters": len(implied), "rows": rows}

def main():
    d = Path(__file__).parent / "data"; d.mkdir(exist_ok=True)
    kh = korea_history()
    (d / "korea_history.json").write_text(json.dumps(kh, ensure_ascii=False))
    print(f"korea_history: {kh[0]['period']}~{kh[-1]['period']} {len(kh)}행, 최신 {kh[-1]}")
    ch = country_history()
    (d / "country_history.json").write_text(json.dumps(ch, ensure_ascii=False))
    print(f"country_history: {len(ch)}개국, 예) JPN 최신 {ch['JPN'][-1]}")
    period = kh[-1]["period"]
    g = gold_table(period)
    (d / "gold.json").write_text(json.dumps(g, ensure_ascii=False, indent=1))
    kor = next(r for r in g["rows"] if r["iso3"] == "KOR")
    print(f"gold {period}: 내재 시가 ${g['market_px_usd_oz']}/oz (시가보고 {g['n_market_reporters']}국), "
          f"한국 {kor['tonnes']}t 장부 {kor['gold_usd_bn']}B → 시가 {kor['gold_mkt_usd_bn']}B, 총액 시가환산 {kor['total_gold_mkt']}B")
    for r in g["rows"][:5]:
        print(f"  금{r['gold_rank']} {r['name']:<8}{r['tonnes']:>8}t  {r['gold_mkt_usd_bn']:>7}B")

if __name__ == "__main__":
    main()
