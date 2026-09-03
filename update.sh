#!/usr/bin/env bash
# 월간 갱신 파이프라인: 수집 → 백테스트 → 빌드 → (옵션) Cloudflare Pages 배포
# 사용: ./update.sh [--deploy]   크론: 매일 09:10 (IMF·CBC·SAFE 갱신 감지형 — 기준월이 바뀔 때만 새 스냅샷)
set -euo pipefail
cd "$(dirname "$0")"
LOG=logs/update_$(date +%Y%m%d).log; mkdir -p logs raw/snapshots
{
  echo "== $(date -Is) start"
  before=$(python3 -c "import json;print(json.load(open('data/latest.json'))['period'])" 2>/dev/null || echo none)
  bok_before=$(python3 -c "import json;print(max(json.load(open('data/bok_latest.json'))['months']))" 2>/dev/null || echo none)
  python3 fetch_reserves.py
  python3 fetch_companion.py
  python3 fetch_bok.py
  python3 backtest_bok.py | tail -1
  after=$(python3 -c "import json;print(json.load(open('data/latest.json'))['period'])")
  cp data/latest.json "raw/snapshots/latest_$(date +%Y%m%d).json"   # 수집 원본 스냅샷(재현성)
  python3 build_site.py
  bok_after=$(python3 -c "import json;print(max(json.load(open('data/bok_latest.json'))['months']))" 2>/dev/null || echo none)
  if [ "$bok_before" != "$bok_after" ]; then
    echo "BOK NEW MONTH $bok_before -> $bok_after"
    [ -x ~/.claude/notify_tg.sh ] && ~/.claude/notify_tg.sh "[외환보유액 사이트] 한은 ${bok_after}월말 발표 감지(속보 타일 반영). SNS 초안 data/post_flash_${bok_after}.txt" || true
  fi
  if [ "$before" != "$after" ]; then
    echo "NEW PERIOD $before -> $after"
    [ -x ~/.claude/notify_tg.sh ] && ~/.claude/notify_tg.sh "[외환보유액 사이트] 기준월 갱신 $before→$after. 포스트 초안 data/post_$after.txt" || true
  fi
  if [ "${1:-}" = "--deploy" ]; then
    set -a; . ~/.secrets/cf_pages.env; set +a
    npx --yes wrangler@3 pages deploy site --project-name "${CF_PAGES_PROJECT:-fx-reserves}" --branch main --commit-dirty=true 2>&1 | tail -3
    sleep 20; python3 indexnow.py 200   # Bing·네이버 IndexNow 제출
  fi
  # 공개 repo에 일일 데이터 스냅샷 반영(변경 있을 때만)
  if [ -n "$(git status --porcelain data content site.json 2>/dev/null)" ]; then
    git add data content site.json && git -c user.name=akkan -c user.email=alibabagini@gmail.com commit -qm "data: $(date +%F) 갱신 (기준월 $after, 한은 $bok_after)" && git push -q origin main && echo "pushed"
  fi
  echo "== $(date -Is) done"
} >> "$LOG" 2>&1
tail -4 "$LOG"
