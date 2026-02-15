# Humetix-Web

Humetix 입사지원 관리 시스템입니다. Flask 기반의 웹 애플리케이션으로, 지원서 접수, 관리자 조회, 엑셀 다운로드 기능을 제공합니다.

## 🛠 기술 스택
- **Backend**: Python 3.10+, Flask
- **Database**: SQLite, SQLAlchemy, Flask-Migrate
- **Server**: Gunicorn, Nginx (Reverse Proxy)
- **Frontend**: HTML5, Bootstrap 5

## 🚀 설치 및 실행 (Local Development)

### 1. 프로젝트 클론
```bash
git clone https://github.com/ashaile/Humetix-Web.git
cd Humetix-Web
```

### 2. 가상환경 생성 및 패키지 설치
```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. 환경변수 설정 (.env)
프로젝트 루트에 `.env` 파일을 생성하고 아래 내용을 작성하세요.
```ini
FLASK_APP=app.py
FLASK_ENV=development
SECRET_KEY=your_secret_key_here
ADMIN_PASSWORD=your_admin_password_here
```

### 4. 데이터베이스 초기화
```bash
flask db upgrade
```

### 5. 실행
```bash
python app.py
```
브라우저에서 `http://localhost:5000` 접속.

---

## 🔒 운영 서버 배포 (Production)

### 1. 환경 변수 설정
운영 서버의 `.env` 파일은 보안을 위해 `FLASK_ENV=production`으로 설정해야 합니다.
```ini
FLASK_ENV=production
SECRET_KEY=very_complex_random_string_do_not_share
ADMIN_PASSWORD=secure_admin_password
```

### 2. Gunicorn 실행
Gunicorn을 사용하여 애플리케이션을 실행합니다. (보통 systemd 서비스로 등록하여 관리)
```bash
gunicorn --workers 3 --bind 0.0.0.0:5000 app:app
```

### 3. 배포 스크립트 사용
```bash
./deploy.sh
```

---

## 📁 주요 디렉터리 구조
- `app.py`: 애플리케이션 진입점 및 설정
- `config.py`: 환경별(개발/운영) 설정 분리
- `models.py`: 데이터베이스 모델 (Application, Career)
- `routes/`: URL 라우트 처리 (auth, apply, admin)
- `templates/`: HTML 템플릿 파일
- `static/`: CSS, JS, 이미지 파일
- `migrations/`: DB 스키마 마이그레이션 파일

## 🧪 테스트 실행
```bash
pytest
```
