#!/bin/bash
# Humetix 배포 스크립트
# 사용법: 서버에서 bash /var/www/recruit/deploy.sh

echo "🚀 배포 시작..."

cd /var/www/recruit

echo "📥 최신 코드 받기..."
git pull origin main

echo "📦 라이브러리 설치..."
pip3 install -r requirements.txt -q

echo "🗄️ DB 마이그레이션..."
python3 -m flask db upgrade

echo "🔒 권한 설정..."
chown -R www-data:www-data /var/www/recruit

echo "🔄 앱 재시작..."
systemctl restart humetix

echo "✅ 상태 확인..."
systemctl status humetix --no-pager

echo ""
echo "🎉 배포 완료!"
