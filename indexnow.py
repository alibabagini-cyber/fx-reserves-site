#!/usr/bin/env python3
"""IndexNow 제출 — Bing·네이버·Yandex가 수신(네이버 2022년 참여). 키 파일은 build_site.py가 site/<key>.txt 로 게시.
사용: python3 indexnow.py [최대 URL 수]  (sitemap.xml의 URL을 제출, 하루 1회면 충분)"""
import json, re, sys, urllib.request
from pathlib import Path
R = Path(__file__).parent; cfg = json.loads((R / "site.json").read_text()); base = cfg["base_url"]; key = cfg["indexnow_key"]
urls = re.findall(r"<loc>([^<]+)</loc>", (R / "site" / "sitemap.xml").read_text())[: int(sys.argv[1]) if len(sys.argv) > 1 else 500]
body = json.dumps({"host": base.split("//")[1], "key": key, "keyLocation": f"{base}/{key}.txt", "urlList": urls}).encode()
req = urllib.request.Request("https://api.indexnow.org/indexnow", data=body, headers={"Content-Type": "application/json; charset=utf-8"})
try:
    with urllib.request.urlopen(req, timeout=30) as r: print("indexnow", r.status, len(urls), "urls")
except urllib.error.HTTPError as e: print("indexnow HTTP", e.code, e.read()[:200])
