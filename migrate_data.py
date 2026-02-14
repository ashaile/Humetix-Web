"""
기존 applications.json 데이터를 SQLite DB로 이전하는 스크립트
서버에서 1회만 실행: python3 migrate_data.py
"""
import os
import json
from app import app
from models import db, Application, Career

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'applications.json')

def migrate():
    with app.app_context():
        # DB 테이블 생성
        db.create_all()
        
        # JSON 파일이 없으면 종료
        if not os.path.exists(DATA_FILE):
            print("⚠️  applications.json 파일이 없습니다. 마이그레이션할 데이터가 없습니다.")
            print("✅ 빈 데이터베이스가 생성되었습니다.")
            return
        
        # JSON 데이터 로드
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if not data:
            print("⚠️  applications.json이 비어있습니다.")
            print("✅ 빈 데이터베이스가 생성되었습니다.")
            return
        
        # 이미 마이그레이션된 데이터가 있는지 확인
        existing = Application.query.count()
        if existing > 0:
            print(f"⚠️  DB에 이미 {existing}건의 데이터가 있습니다. 마이그레이션을 건너뜁니다.")
            return
        
        # 데이터 이전
        count = 0
        for entry in data:
            new_app = Application(
                id=entry['id'],
                timestamp=entry['timestamp'],
                photo=entry.get('photo', ''),
                name=entry['info']['name'],
                birth=entry['info'].get('birth', ''),
                phone=entry['info'].get('phone', ''),
                email=entry['info'].get('email', ''),
                address=entry['info'].get('address', ''),
                height=entry['body'].get('height', ''),
                weight=entry['body'].get('weight', ''),
                vision=entry['body'].get('vision', ''),
                shoes=entry['body'].get('shoes', ''),
                tshirt=entry['body'].get('tshirt', ''),
                shift=entry['work_condition'].get('shift', ''),
                posture=entry['work_condition'].get('posture', ''),
                overtime=entry['work_condition'].get('overtime', ''),
                holiday=entry['work_condition'].get('holiday', ''),
                interview_date=entry['work_condition'].get('interview_date', ''),
                start_date=entry['work_condition'].get('start_date', ''),
                agree=entry['work_condition'].get('agree', ''),
            )
            
            for c in entry.get('career', []):
                career = Career(
                    company=c.get('company', ''),
                    start=c.get('start', ''),
                    end=c.get('end', ''),
                    role=c.get('role', ''),
                    reason=c.get('reason', ''),
                )
                new_app.careers.append(career)
            
            db.session.add(new_app)
            count += 1
        
        db.session.commit()
        print(f"🎉 마이그레이션 완료! {count}건의 지원서를 DB로 이전했습니다.")
        print(f"💡 이제 applications.json은 백업용으로만 보관하세요.")

if __name__ == '__main__':
    migrate()
