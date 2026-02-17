#!/bin/bash
# Humetix 배포 스크립트
# 사용법: 서버에서 bash /var/www/recruit/deploy.sh

set -e  # 에러 발생 시 즉시 중단

echo "배포 시작..."

cd /var/www/recruit

echo "최신 코드 받기..."
git config --global --add safe.directory /var/www/recruit
git pull origin main

echo "라이브러리 설치..."
pip3 install -r requirements.txt -q

echo "DB 마이그레이션..."
python3 -m flask db upgrade || { echo "마이그레이션 실패! 배포를 중단합니다."; exit 1; }

echo "권한 설정..."
chown -R www-data:www-data /var/www/recruit

echo "앱 재시작..."
systemctl restart humetix

echo "상태 확인..."
sleep 2
systemctl status humetix --no-pager

# 헬스 체크
echo "헬스 체크..."
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:5000/health 2>/dev/null || echo "000")
if [ "$HTTP_STATUS" = "200" ]; then
    echo "헬스 체크 성공 (HTTP $HTTP_STATUS)"
else
    echo "헬스 체크 실패 (HTTP $HTTP_STATUS)"
    exit 1
fi

echo ""
echo "배포 완료!"
