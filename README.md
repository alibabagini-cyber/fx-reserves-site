# 외환보유액 순위 사이트

한국은행이 2026-09-03부터 월간 보도자료에서 뺀 「주요국 외환보유액 순위표」를 IMF·각국 중앙은행 공개자료로 매월 재현하는 정적 사이트.

## 파이프라인
```
fetch_reserves.py   IMF IRFCL(IRFCL65) + 대만 CBC + 중국 SAFE + 사우디 SAMA → data/reserves_YYYY-MM.json, latest.json, direct_cache.json
fetch_companion.py  한국 2005~ 월별 구성, 40개국 2015~ 추이, 금 보유·시가환산 → korea_history / country_history / gold.json
backtest_bok.py     한은 마지막 순위표(2026-06말, 8/5 발표) 재현 → data/backtest_bok.json (12/12 일치, 2026-09-03)
build_site.py       data/ + content/*.md → site/ (104p: 순위·월별 아카이브·한국·국가별40·금·방법론·데이터·임베드·기자용·해설·EN)
update.sh           위 전부 + 스냅샷 + (--deploy) Cloudflare Pages
```
설정 `site.json`: site_name, base_url, adsense_pub, errata[].  키 필요 없음(모두 공개 API/페이지). SAMA는 openpyxl 필요.

## 방법론 요약
- 순위 = 같은 기준월 값끼리. 미발표국은 직전 월 값 + `*` 표시.
- 중국은 SAFE 헤드라인(금·SDR·RTP 제외), 사우디는 SAMA 직접, 대만은 CBC 보도자료 — 한은 표와 같은 방식.
- 금은 IMF 템플릿 시가. 한국·미국·싱가포르는 장부가 보고 → `/gold/`에서 시가환산 별도 제공.

## 증빙
- `raw/bok_official_reserves_jul2026_en.pdf` 한은 마지막 순위표 원본, `raw/snapshots/` 일별 수집 스냅샷, `probe/SOURCES.md` 소스 실측 기록, `docs/TRAFFIC_RESEARCH.md` 트래픽 리서치.
