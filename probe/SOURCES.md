# FX 준비자산 소스 프로브 결과 (2026-09-03 실측)

모든 행은 실제 curl/python fetch로 검증됨(raw 응답 = `probe/*.html|*.xml|*.csv|*.xlsx`).
HTTPS만 사용. TradingEconomics/CEIC/MacroMicro 등 유료·스크래핑금지 소스는 사용하지 않음.

## 요약 테이블

| # | 항목 | URL | 방법 | 샘플 값 | as_of | HTTP |
|---|------|-----|------|---------|-------|------|
| 1 | China SAFE 외환보유액 | 목록: `https://www.safe.gov.cn/en/DataInterpretation/index.html`<br>기사(예): `https://www.safe.gov.cn/en/2026/0807/2449.html` | 목록 페이지 정규식으로 최신 "SAFE Releases Data on China's Foreign Exchange Reserve..." 링크 추출 → 기사 본문에서 `foreign exchange reserves totaled USD ([\d,]+\.?\d*)\s*(trillion\|billion)` | **USD 3,418.8bn** | 2026-07 | 200 |
| 2 | Saudi SAMA 준비자산 | 페이지: `https://www.sama.gov.sa/en-US/Statistics/Indices/Pages/reserve_assets.aspx`<br>xlsx(예): `.../D3/Reserve_Assets_Jul_2026.xlsx` | 페이지 내 SharePoint JSON에서 `"FileLeafRef":"([^"]+\.xlsx)"` 추출 → xlsx 다운로드 → openpyxl로 시트 "International Reserves", row3 "Official Reserves Assets"의 최신(가장 오른쪽) 열(SAR mn) → USD 페그(3.75) 환산 | **USD ~494.6bn**(SAR 1,854,565mn @3.75, 표기일 2026-06-26) | 2026-06 | 200(단, `--http1.1`+브라우저 UA 필수 — 기본 curl은 TLS 리셋됨, 아래 함정 참조) |
| 3 | Germany Bundesbank 준비자산 | 시리즈: `https://api.statistiken.bundesbank.de/rest/data/BBFI1/M.N.DE.W1.S121.S1.LE.A.FA.R.F._Z.X1._X.N?format=csv&lang=en`<br>환율: `https://api.statistiken.bundesbank.de/rest/data/BBEX3/M.USD.EUR.BB.AC.A01?format=csv&lang=en` | CSV 메타헤더(8행) 이후 `YYYY-MM,value,flag` 행 파싱. 시리즈 단위=EUR백만("unit multiplier: Millions"). EUR/USD는 별도 시리즈(ECB 월말 기준환율)로 곱해 USD환산 | **USD ~539.8bn**(2026-07, EUR 469,982mn × 1.1485) / 2026-06 기준 계산시 534.9bn(사용자 제시 IMF IRFCL 534.9와 거의 일치) | 2026-07(최신 공통월) | 200 |
| 4 | IMF IRFCL 월별 이력 심도 | `https://api.imf.org/external/sdmx/2.1/data/IMF.STA,IRFCL/{ISO3}.IRFCLDT1_IRFCL65_USD?startPeriod=1999-01&format=csv` (Accept: text/csv 헤더 필수 — 없으면 SDMX-ML XML로 반환) | CSV 파싱 후 FREQUENCY=='M' 행만 필터, TIME_PERIOD min/max | KOR: 2005-M01~2026-M07(259개월)<br>CHN: 2015-M06~2026-M07(134개월)<br>JPN: 2000-M04~2026-M07(316개월) | — | 200 |
| 5 | IMF COFER (준비통화 구성) | dataflow 확인: `https://api.imf.org/external/sdmx/2.1/dataflow/IMF.STA` (Accept 헤더 무시하고 XML 반환 — grep으로 `id="COFER"` 검색)<br>데이터: `https://api.imf.org/external/sdmx/2.1/data/IMF.STA,COFER,7.0.1/.?startPeriod=2025-Q1&format=csv` | dataflow id=`COFER`(version 7.0.1). World=`G001`, 지표=`AFXRA`(Allocated FX Reserve Assets), 통화=`CI_USD`, 변환=`SHRO_PT`(share %) 조합으로 필터 | **World USD share 57.13%** | 2026-Q1(최신 쿼터, 2025-Q1도 함께 수신) | 200 |
| 6 | World Bank API | `https://api.worldbank.org/v2/country/KOR/indicator/FI.RES.TOTL.MO?format=json&mrv=3` | 표준 JSON, `[1][0]` = 최신 연도 | **6.46개월(수입 대비)**, KOR | 2025(연간, 월단위 지표 아님 — "months of imports") | 200 |
| 7 | BOK 외환보유액 보도자료 | 상세뷰(예): `https://www.bok.or.kr/portal/bbs/B0000502/view.do?nttId=11062577&menuNo=201265` (2026년 6월말) | 상세뷰 HTML에서 PDF 첨부 정규식: `href="(/fileSrc/portal/[0-9a-f]{32}/\d+/[0-9a-f]{32}\.pdf)"` | 첨부 PDF 확인(값 파싱은 미실행, 링크만 검증) | 2026-06 | 200 |

## 항목별 상세 노트

### 1. China SAFE
- **작동하는 것**: `en/DataInterpretation/index.html` 목록 페이지는 정적 HTML로 최근 20건이 채워져 있음(제목+날짜+href). "Official Reserve Assets"(`en/OfficialReserveAssets/index.html`) 및 "Forex Reserves"(`en/ForexReserves/index.html`) 카테고리 인덱스는 **Thymeleaf 템플릿 미렌더링 placeholder만 있고 실제 목록(`list_conr` div)이 비어있음** — 이 두 경로는 목록용으로 못 씀.
- JSON/CSV 엔드포인트 없음. 순수 HTML 파싱 필요.
- 기사 본문은 안정적 문구: `China's foreign exchange reserves totaled USD X.XXX trillion` 또는 `USD X,XXX.X billion`(둘 다 관측됨, 정규식에 both 반영). `&#39;`(아포스트로피 HTML entity) 포함이라 문자 그대로 `China.s`로 정규식 처리.
- 값 검증: 2026-06(article `0707/2436.html`)=3,416.3bn — **사용자가 제시한 기대값(BOK 인용)과 정확히 일치**. 2026-07 최신값=3,418.8bn.

### 2. Saudi SAMA
- **함정**: 기본 curl(HTTP/2 협상, 기본 헤더)로 접속하면 TLS ClientHello 단계에서 `Connection reset by peer`(WAF 지문 차단으로 추정). `--http1.1` + 실제 브라우저 User-Agent 헤더를 강제하면 HTTP 200 성공(Python urllib은 기본이 HTTP/1.1이라 문제 없었음, 코드에서 확인됨).
- 페이지 자체는 SharePoint 문서 라이브러리 웹파트이며 다운로드 링크가 `<a href>`가 아니라 **페이지에 임베드된 JSON 블록**(`"FileLeafRef": "Reserve_Assets_Jul_2026.xlsx"`)에 있음 — HTML `href` grep으로는 못 찾고 JSON 문자열 정규식 필요.
- xlsx는 SAR **백만** 단위, 시트명 "International Reserves ", 헤더 row2=날짜(매월 26일 기준 스냅샷), row3="Official Reserves Assets"(총계), row4~8=금/SDR/IMF지분/외화준비금/기타 세부항목.
- USD 환산은 리얄 페그(3.75 고정) 적용 — SAMA가 발표하는 공식 USD 수치와 근사(사용자 기대값 493.9bn 대비 계산값 494.6bn, 오차 <0.2%).

### 3. Germany Bundesbank
- SDMX 시계열 키: `BBFI1.M.N.DE.W1.S121.S1.LE.A.FA.R.F._Z.X1._X.N` = "Reserve Assets (mthly.) - Total - Positions", **단위=EUR 백만**("unit multiplier: Millions", CSV 헤더에 명시). USD 환산 안 됨 — 별도 시리즈 필요.
- EUR/USD는 `BBEX3.M.USD.EUR.BB.AC.A01`(ECB 월말 기준환율, "End of month") 사용. Accept:text/csv 헤더 없으면 XML 반환(IMF와 동일 함정).
- 2026-06 기준 EUR 469,429mn × 1.1394 = USD 534.9bn — **사용자가 제시한 IMF IRFCL 비교값(534.9)과 소수점까지 일치**. BOK 인용치 536.3bn과는 ~1.4bn 차이(월평균 vs 월말 환율, 또는 BOK 자체 환산 방식 차이로 추정 — 원인 미확정, 추가 검증 필요).
- 대안: CSV 대신 `format=sdmx`(XML)도 가능하나 CSV가 더 가볍고 파싱 쉬움.

### 4. IMF IRFCL 이력 심도
- `Accept: text/csv` 헤더 필수(없으면 200 OK지만 SDMX-ML XML 반환 — 겉보기엔 성공이라 함정).
- 쿼리에 FREQUENCY 필터가 없으면 연간(A)·분기(Q)·월간(M) 데이터가 섞여 반환됨 — 클라이언트 측에서 `FREQUENCY=='M'` 필터링 필수.
- 국가별 월간 시작월이 다름(KOR 2005-01 시작 — 그 이전은 연간만 존재, JPN은 2000-04부터, CHN은 2015-06부터 — 그 이전은 비회원/미보고 추정).

### 5. IMF COFER
- dataflow 목록 자체도 Accept 헤더 무시하고 XML로 옴(`application/vnd.sdmx.structure+json` 요청해도 무시됨) — grep으로 `id="COFER"` 찾는 게 실전적.
- COFER 데이터 쿼리는 dimension 순서가 `COUNTRY.INDICATOR.FXR_CURRENCY.TYPE_OF_TRANSFORMATION`(4개 dim, wildcard `.` 로 전체 수신 가능). World 집계 코드는 `G001`(지역코드 G200=advanced economies, G110=emerging/developing 등도 있음 — COUNTRY 컬럼에서 관측).
- `TFXRA`=Total FX reserve assets(할당+미할당 합계), `AFXRA`=Allocated(통화별 구성 가능한 부분만), `UFXRA`=Unallocated. 통화별 비중(USD 57.13%)은 AFXRA 기준.

### 6. World Bank API
- 키 불필요, 즉시 작동. 단 **월별 데이터가 아니라 연간**("Total reserves in months of imports", IMF IRFCL 기반 세계은행 자체 지표) — 실시간 랭킹용으로는 부적합(최신값도 발표시차 큼, mrv=3으로 최근 3개 연도만 와도 최신이 전년도).

### 7. BOK 보도자료
- 상세뷰(`view.do?nttId=...`) 페이지에서 PDF·HWP 첨부 링크 패턴 확인:
  `/fileSrc/portal/{32자리hex}/{순번}/{32자리hex}.pdf` (HWP도 동일 패턴, 확장자만 다름)
- **미해결**: `list.do?menuNo=201265` 목록 페이지는 정적 HTML에 실제 게시물 목록이 없음(JS로 별도 로드되는 것으로 추정, AJAX 엔드포인트를 이 세션에서 특정 못함 — `ncloud/search` 계열 시도했으나 404). 현재는 **WebSearch로 최신 nttId를 찾는 방식**이 유일하게 검증된 경로(예: "2026년 6월말 외환보유액" 검색 → nttId=11062577 확보, 200 확인).
- 대안 후보(미검증, 다음 세션 시도 권장): ECOS(한국은행 경제통계시스템) API — 외환보유액은 ECOS 통계표 코드가 이미 존재할 가능성 높음(스킬 `bok-ecos-stats` 참조), 보도자료 스크래핑보다 안정적일 수 있음.

## 함정 모음 (재발 방지)
1. IMF API(`api.imf.org`)는 SDMX 계열 전부 — `Accept: text/csv` 헤더가 없으면 200 OK로 **XML을 csv 확장자에 담아 반환**(사일런트 실패). Bundesbank도 동일.
2. SAMA(`sama.gov.sa`)는 curl 기본 설정(HTTP/2 우선 협상)에서 TLS reset — `--http1.1`+브라우저 UA 강제, 또는 Python urllib(기본 HTTP/1.1) 사용.
3. SAFE 사이트의 카테고리 인덱스(`OfficialReserveAssets/`, `ForexReserves/`)는 Thymeleaf 미렌더링 placeholder — 실제 게시물 목록은 `DataInterpretation/index.html` 하나만 유효.
4. Bundesbank 리저브 시리즈는 EUR 단위 — USD 환산용 별도 환율 시리즈 fetch 필수(자동 환산 없음).

## 파일 목록 (probe/)
- `sources_direct.py` — 테스트 완료된 파이썬 모듈(3함수)
- 원본 응답: `safe_*.html`, `sama_reserve2.html`, `sama_jul2026.xlsx`, `bbk_*.xml/csv`, `*_irfcl.csv`, `cofer_test.csv`, `worldbank_kor.json`, `bok_view_202606.html`, `bok_list.html`, `dataflow_sta.json`
