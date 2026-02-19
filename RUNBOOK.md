# Humetix 운영 런북

> 서버: Ubuntu + Nginx + Gunicorn + Flask | 경로: `/var/www/recruit` | 서비스: `humetix`

---

## 1. 배포 직후 5분 체크리스트

```bash
# 1) 서비스 상태
systemctl status humetix --no-pager

# 2) Health check (DB 연결 포함)
curl -s http://localhost:5000/health | python3 -m json.tool
# 기대값: {"status":"healthy","database":"connected"}

# 3) Admin 로그인
curl -s -o /dev/null -w "%{http_code}" http://localhost:5000/login
# 기대값: 200

# 4) 핵심 기능 3개 — 공개 페이지 응답 확인
curl -s -o /dev/null -w "%{http_code}" http://localhost:5000/attendance   # 출퇴근
curl -s -o /dev/null -w "%{http_code}" http://localhost:5000/advance      # 선불금
curl -s -o /dev/null -w "%{http_code}" http://localhost:5000/apply        # 입사지원

# 5) 자동 스모크 테스트 (선택)
python3 /var/www/recruit/scripts/smoke_test.py --admin-password "$ADMIN_PASSWORD"

# 6) 최근 로그 에러 확인
grep -i "error\|traceback" /var/www/recruit/logs/humetix.log | tail -20
```

**PASS 기준:** health=200, login=200, 3개 페이지 모두 200, 로그에 Traceback 없음

---

## 2. 장애 유형별 대응

### 502 Bad Gateway (Nginx → Gunicorn 연결 실패)

```
증상: 브라우저에서 502, Nginx 에러 로그에 "connect() failed"
```

```bash
# Gunicorn 프로세스 확인
systemctl status humetix
ps aux | grep gunicorn

# 죽어있으면 재시작
sudo systemctl restart humetix

# 포트 점유 확인
ss -tlnp | grep 5000

# Nginx 설정 확인
sudo nginx -t && sudo systemctl reload nginx

# 그래도 안되면 — Gunicorn 직접 실행으로 에러 확인
cd /var/www/recruit
/usr/local/bin/gunicorn --workers 1 --bind 0.0.0.0:5000 app:app
```

### DB Migration 실패

```
증상: deploy.sh 실행 중 "flask db upgrade" 에서 에러
      또는 앱 시작 후 500 에러 + 로그에 "no such table" / "OperationalError"
```

```bash
# 현재 마이그레이션 버전 확인
cd /var/www/recruit
python3 -m flask db current

# 마이그레이션 히스토리 확인
python3 -m flask db history

# 충돌 시 — 한 단계씩 적용
python3 -m flask db upgrade +1

# 테이블 누락 긴급 복구 (Alembic 우회)
python3 fix_db.py

# DB 무결성 확인
sqlite3 humetix.db "PRAGMA integrity_check;"
sqlite3 humetix.db ".tables"
```

### 로그인 실패 (Admin)

```
증상: 올바른 비밀번호인데 로그인 안됨
      "Too many attempts" 메시지 / 세션 즉시 만료
```

```bash
# .env에서 ADMIN_PASSWORD 확인
grep ADMIN_PASSWORD /var/www/recruit/.env

# Rate limit 잠금 확인 및 해제 (SQLite)
sqlite3 /var/www/recruit/humetix.db \
  "SELECT ip, attempt_count, last_attempt FROM admin_login_attempts ORDER BY last_attempt DESC LIMIT 5;"

# 잠금 해제 — 해당 IP의 시도 기록 삭제
sqlite3 /var/www/recruit/humetix.db \
  "DELETE FROM admin_login_attempts WHERE ip='<blocked_ip>';"

# SECRET_KEY 변경 여부 확인 (변경 시 기존 세션 무효화됨)
grep SECRET_KEY /var/www/recruit/.env

# 세션 쿠키 문제 — SESSION_COOKIE_SECURE=1인데 HTTP 접속 시 쿠키 안 붙음
grep SESSION_COOKIE_SECURE /var/www/recruit/.env
```

### PDF 생성 실패 (`/admin/payslip/pdf`)

```
증상: PDF 다운로드 시 500 에러, 로그에 "TTFont" / "font" / "reportlab" 에러
```

```bash
# 한글 폰트 존재 확인 (Linux 경로)
ls -la /usr/share/fonts/truetype/nanum/NanumGothic.ttf

# 폰트 없으면 설치
sudo apt install -y fonts-nanum
fc-cache -fv

# reportlab 버전 확인
pip3 show reportlab

# PDF 생성 수동 테스트 — 급여 데이터 존재 여부 확인
sqlite3 /var/www/recruit/humetix.db \
  "SELECT COUNT(*) FROM payslips WHERE month='2026-02';"

# 로그에서 PDF 관련 에러 추출
grep -i "pdf\|font\|reportlab" /var/www/recruit/logs/humetix.log | tail -10
```

### Excel 생성 실패 (`/download_excel`, `/admin/attendance/excel`, `/admin/payslip/excel`)

```
증상: Excel 다운로드 시 500 에러
```

```bash
# 입사지원서 Excel 템플릿 존재 확인 (/download_excel에서 사용)
ls -la /var/www/recruit/templates/excel/입사지원서.xlsx

# openpyxl / Pillow 설치 확인
pip3 show openpyxl pillow pillow-heif

# 사진 포함 Excel 실패 시 — uploads 디렉토리 권한 확인
ls -la /var/www/recruit/uploads/

# HEIC 변환 실패 시 — pillow-heif 의존성
python3 -c "import pillow_heif; print('OK')"

# 로그 확인
grep -i "excel\|openpyxl\|workbook" /var/www/recruit/logs/humetix.log | tail -10
```

---

## 3. 롤백 절차

### 코드 롤백

```bash
cd /var/www/recruit

# 현재 커밋 확인
git log --oneline -5

# 직전 커밋으로 롤백
git checkout HEAD~1 -- .
# 또는 특정 커밋으로
git checkout <commit_hash> -- .

# 의존성 재설치 (requirements.txt 변경된 경우)
pip3 install -r requirements.txt -q

# 서비스 재시작
sudo systemctl restart humetix
```

### DB 롤백 (Migration)

```bash
cd /var/www/recruit

# 현재 버전 확인
python3 -m flask db current

# 한 단계 다운그레이드
python3 -m flask db downgrade -1

# 특정 버전으로 다운그레이드
python3 -m flask db downgrade <revision_id>
```

### DB 복구 불가 시 — 백업 복원

```bash
# 배포 전 백업이 있었다면
cp /var/www/recruit/backup/humetix_<timestamp>.db /var/www/recruit/humetix.db
chown www-data:www-data /var/www/recruit/humetix.db
sudo systemctl restart humetix
```

### 긴급 대응: deploy.sh에 백업 추가 (권장)

```bash
# deploy.sh 첫 줄에 추가해야 할 내용:
cp /var/www/recruit/humetix.db /var/www/recruit/backup/humetix_$(date +%Y%m%d_%H%M%S).db
```

---

## 4. 로그 위치 및 확인 명령어

| 로그 | 경로 / 명령어 |
|---|---|
| **앱 로그** | `/var/www/recruit/logs/humetix.log` (10MB x 5 rotation) |
| **앱 로그 실시간** | `tail -f /var/www/recruit/logs/humetix.log` |
| **systemd 로그** | `journalctl -u humetix -n 100 --no-pager` |
| **systemd 실시간** | `journalctl -u humetix -f` |
| **Nginx access** | `tail -f /var/log/nginx/access.log` |
| **Nginx error** | `tail -f /var/log/nginx/error.log` |
| **Gunicorn stderr** | `journalctl -u humetix -p err -n 50` |
| **DB 크기** | `ls -lh /var/www/recruit/humetix.db` |
| **디스크 용량** | `df -h /var/www/recruit` |
| **업로드 폴더 크기** | `du -sh /var/www/recruit/uploads/` |

### 자주 쓰는 디버깅 명령어

```bash
# 최근 에러만 추출
grep -E "ERROR|CRITICAL|Traceback" /var/www/recruit/logs/humetix.log | tail -30

# 특정 시간대 로그 (예: 오늘 14시대)
grep "2026-02-20 14:" /var/www/recruit/logs/humetix.log

# 5xx 응답 확인 (Nginx)
awk '$9 ~ /^5/' /var/log/nginx/access.log | tail -20

# Gunicorn 워커 수 확인
ps aux | grep gunicorn | grep -v grep | wc -l

# SQLite DB 잠금 확인
fuser /var/www/recruit/humetix.db
```
