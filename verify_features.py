import os
import sys

# 프로젝트 경로 추가
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)

from app import app
from models import db, Application
import logging

# 로거 설정 (콘솔 출력 확인용)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def verify():
    with app.test_client() as client:
        # 1. 지원서 제출 테스트 (CSRF 방지는 테스트 클라이언트 환경에서 기본적으로 세션/쿠키를 다루므로 통과 가능성 높음)
        # 만약 CSRF가 계속 막히면 app.config['WTF_CSRF_ENABLED'] = False 처리
        app.config['WTF_CSRF_ENABLED'] = False
        
        print("\n--- 1. 지원서 제출 및 알림 테스트 ---")
        test_data = {
            'name': '홍길동_테스트',
            'phone': '010-1234-5678',
            'email': 'test@example.com',
            'birth': '1990-01-01',
            'address': '서울시 테스트구',
            'agree': 'on'
        }
        response = client.post('/submit', data=test_data)
        print(f"제출 응답 코드: {response.status_code}")
        
        # 로그 파일 확인 (NotificationService의 Mock 로그가 찍혔는지)
        with open('logs/humetix.log', 'r', encoding='utf-8') as f:
            logs = f.read()
            if "[MOCK EMAIL]" in logs and "홍길동_테스트" in logs:
                print("✅ 알림 로그(Email) 확인됨!")
            else:
                print("❌ 알림 로그(Email) 확인 실패")
                
            if "[MOCK SMS]" in logs and "홍길동_테스트" in logs:
                print("✅ 알림 로그(SMS) 확인됨!")
            else:
                print("❌ 알림 로그(SMS) 확인 실패")

        # 2. 검색 기능 테스트
        print("\n--- 2. 검색 기능 테스트 ---")
        # 이름을 포함한 검색
        resp_search = client.get('/humetix_master_99?type=name&q=홍길동')
        if "홍길동_테스트" in resp_search.get_data(as_text=True):
            print("✅ 이름 검색 성공!")
        else:
            print("❌ 이름 검색 실패")

        # 존재하지 않는 검색어
        resp_search_no = client.get('/humetix_master_99?type=name&q=존재하지않는이름')
        if "홍길동_테스트" not in resp_search_no.get_data(as_text=True):
            print("✅ 필터링 동작 확인 (미검색 항목 제외)!")
        else:
            print("❌ 필터링 동작 실패")

        # 3. 메모 저장 테스트
        print("\n--- 3. 메모 저장 테스트 ---")
        app_obj = Application.query.filter_by(name='홍길동_테스트').first()
        if app_obj:
            app_id = app_obj.id
            memo_data = {'memo': '테스트용 메모입니다.'}
            resp_memo = client.post(f'/update_memo/{app_id}', data=memo_data)
            print(f"메모 저장 응답: {resp_memo.status_code}, {resp_memo.json}")
            
            # DB 재조회
            db.session.expire_all()
            updated_app = Application.query.get(app_id)
            if updated_app.memo == '테스트용 메모입니다.':
                print("✅ DB 메모 저장 성공!")
            else:
                print(f"❌ DB 메모 저장 실패 (저장된 값: {updated_app.memo})")
        else:
            print("❌ 테스트 대상 지원서를 찾을 수 없음")

if __name__ == "__main__":
    verify()
