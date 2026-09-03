#!/usr/bin/env python3
"""외환보유액 개별 국가 소스 직접 조회 — probe 결과물.

각 함수는 (period 'YYYY-MM', usd_bn float, source_url str) 또는 실패 시 None 을 반환한다.
전부 실제 fetch 로 검증됨(2026-09-03, SOURCES.md 참조). HTTPS만 사용, 무료 공식 소스만.

의존: 표준 라이브러리 + openpyxl(SAMA xlsx 파싱, `pip install openpyxl` 필요).
"""
import csv
import io
import re
import urllib.request
import datetime as dt

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"


def _get(url, accept=None, timeout=30):
    headers = {"User-Agent": UA}
    if accept:
        headers["Accept"] = accept
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


# ---------------------------------------------------------------------------
# 1. China SAFE — headline "foreign exchange reserves" (excludes gold)
# ---------------------------------------------------------------------------
SAFE_LIST_URL = "https://www.safe.gov.cn/en/DataInterpretation/index.html"
SAFE_TITLE_RE = re.compile(
    r'<a href="(/en/\d{4}/\d{4}/\d+\.html)"[^>]*>\s*(SAFE Releases Data on China.s Foreign Exchange Reserve[s]? at the End of (\w+ \d{4}))'
)
SAFE_VALUE_RE = re.compile(
    r"foreign exchange reserves totaled USD\s*([\d,]+\.?\d*)\s*(trillion|billion)"
)


def safe_china():
    try:
        html = _get(SAFE_LIST_URL, accept="text/html").decode("utf-8", "ignore")
        m = SAFE_TITLE_RE.search(html)
        if not m:
            return None
        href, _, month_year = m.groups()
        article_url = "https://www.safe.gov.cn" + href
        body = _get(article_url, accept="text/html").decode("utf-8", "ignore")
        vm = SAFE_VALUE_RE.search(body)
        if not vm:
            return None
        val, unit = vm.groups()
        usd_bn = float(val.replace(",", "")) * (1000 if unit == "trillion" else 1)
        period = dt.datetime.strptime(month_year, "%B %Y").strftime("%Y-%m")
        return period, round(usd_bn, 1), article_url
    except Exception:
        return None


# ---------------------------------------------------------------------------
# 2. Saudi SAMA — "Official Reserves Assets" (SAR mn, converted @ peg 3.75)
# ---------------------------------------------------------------------------
SAMA_PAGE_URL = "https://www.sama.gov.sa/en-US/Statistics/Indices/Pages/reserve_assets.aspx"
SAMA_FILE_RE = re.compile(r'"FileLeafRef":\s*"([^"]+\.xlsx)"')
SAMA_PEG = 3.75  # SAR per USD, official fixed peg


def sama_saudi():
    try:
        html = _get(SAMA_PAGE_URL, accept="text/html").decode("utf-8", "ignore")
        m = SAMA_FILE_RE.search(html)
        if not m:
            return None
        fname = m.group(1)
        xlsx_url = f"https://www.sama.gov.sa/en-US/Statistics/Indices/D3/{fname}"
        data = _get(xlsx_url)
        import openpyxl

        wb = openpyxl.load_workbook(io.BytesIO(data), data_only=True)
        ws = wb.worksheets[0]
        last_col, last_date = None, None
        for c in range(2, ws.max_column + 1):
            v = ws.cell(row=2, column=c).value
            if isinstance(v, dt.datetime):
                last_col, last_date = c, v
        if last_col is None:
            return None
        sar_mn = ws.cell(row=3, column=last_col).value  # row 3 = "Official Reserves Assets"
        usd_bn = sar_mn / SAMA_PEG / 1000
        period = last_date.strftime("%Y-%m")
        return period, round(usd_bn, 1), xlsx_url
    except Exception:
        return None


# ---------------------------------------------------------------------------
# 3. Germany Bundesbank — Reserve Assets (EUR mn) converted @ EUR/USD EOM rate
# ---------------------------------------------------------------------------
BBK_RESERVES_URL = (
    "https://api.statistiken.bundesbank.de/rest/data/BBFI1/"
    "M.N.DE.W1.S121.S1.LE.A.FA.R.F._Z.X1._X.N?format=csv&lang=en"
)
BBK_EURUSD_URL = (
    "https://api.statistiken.bundesbank.de/rest/data/BBEX3/"
    "M.USD.EUR.BB.AC.A01?format=csv&lang=en"
)


def _parse_bbk_csv(raw):
    """BBK CSV: metadata header lines, then 'YYYY-MM,value,flag' data rows."""
    out = {}
    reader = csv.reader(io.StringIO(raw.decode("utf-8-sig", "ignore")))
    for row in reader:
        if len(row) >= 2 and re.match(r"^\d{4}-\d{2}$", row[0]):
            try:
                out[row[0]] = float(row[1])
            except ValueError:
                pass
    return out


def bundesbank_germany():
    try:
        reserves = _parse_bbk_csv(_get(BBK_RESERVES_URL, accept="text/csv"))
        fx = _parse_bbk_csv(_get(BBK_EURUSD_URL, accept="text/csv"))
        common = sorted(set(reserves) & set(fx))
        if not common:
            return None
        period = common[-1]
        eur_mn = reserves[period]
        rate = fx[period]  # EUR 1 = USD rate, end-of-month
        usd_bn = eur_mn * rate / 1000
        return period, round(usd_bn, 1), BBK_RESERVES_URL
    except Exception:
        return None


if __name__ == "__main__":
    for name, fn in (("safe_china", safe_china), ("sama_saudi", sama_saudi), ("bundesbank_germany", bundesbank_germany)):
        r = fn()
        print(f"{name}: {r}")
