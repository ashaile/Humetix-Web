#!/bin/bash
# Humetix 배포 스크립트
# 사용법: 서버에서 bash /var/www/recruit/deploy.sh
set -euo pipefail

echo "🚀 배포 시작..."

cd /var/www/recruit

echo "💾 DB 백업..."
BACKUP_DIR="/var/www/recruit/backup"
mkdir -p "$BACKUP_DIR"
DB_FILE="/var/www/recruit/humetix.db"
BACKUP_FILE="$BACKUP_DIR/humetix_$(date +%Y%m%d_%H%M%S).db"
if cp "$DB_FILE" "$BACKUP_FILE"; then
  echo "   백업 완료: $BACKUP_FILE"
  # 7일 이상 된 백업 자동 삭제
  find "$BACKUP_DIR" -name "humetix_*.db" -mtime +7 -delete
else
  echo "   백업 실패 — 배포 중단"
  exit 1
fi

echo "📥 최신 코드 받기..."
git config --global --add safe.directory /var/www/recruit
git pull origin main

echo "📦 라이브러리 설치..."
pip3 install -r requirements.txt -q

echo "🗄️ DB 마이그레이션..."
# 마이그레이션 통합 대응: 이전 revision이면 직접 alembic_version 갱신
CURRENT_REV=$(sqlite3 "$DB_FILE" "SELECT version_num FROM alembic_version LIMIT 1;" 2>/dev/null || echo "")
TARGET_REV="d5e6f7g8h9i0"
if [ -n "$CURRENT_REV" ] && [ "$CURRENT_REV" != "$TARGET_REV" ]; then
  echo "   마이그레이션 통합 반영 (${CURRENT_REV} → ${TARGET_REV})..."
  sqlite3 "$DB_FILE" "UPDATE alembic_version SET version_num='${TARGET_REV}';"
fi
FLASK_APP=app.py python3 -m flask db upgrade
echo "   마이그레이션 완료"

echo "🔒 권한 설정..."
chown -R www-data:www-data /var/www/recruit

echo "🔄 앱 재시작..."
systemctl restart humetix

echo "✅ 상태 확인..."
systemctl status humetix --no-pager

echo ""
echo "🎉 배포 완료!"
