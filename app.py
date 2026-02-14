from flask import Flask, render_template, request, send_from_directory, session, redirect, url_for
import os, shutil
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'humetix_secret_key_1234' # 세션 보안을 위한 키 (실제 운영시 변경 권장)

# 경로 설정
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, 'uploads')
DATA_FILE = os.path.join(BASE_DIR, 'data_html.txt')
EXCEL_FILE = os.path.join(BASE_DIR, 'data.xlsx')

# 관리자 비밀번호 설정
ADMIN_PASSWORD = "3326" 

if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

# 1. 메인 홈페이지
@app.route('/')
def home():
    return render_template('index.html')

# 2. 입사지원서 페이지
@app.route('/apply')
def apply_page():
    return render_template('apply.html')

# 3. 사진 보여주기 기능
@app.route('/view_photo/<filename>')
def view_photo(filename):
    return send_from_directory(UPLOAD_DIR, filename)

# 4. 지원서 제출 처리
@app.route('/submit', methods=['POST'])
def submit():
    try:
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        file_now = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # 1. 신분증 사진 처리
        id_card = request.files.get('id_card')
        photo_html = "<span style='color:gray;'>[사진 없음]</span>"
        photo_filename = ""
        
        if id_card and id_card.filename != '':
            photo_name = f"{file_now}_id.jpg"
            id_card.save(os.path.join(UPLOAD_DIR, photo_name))
            photo_filename = photo_name
            photo_html = f'''
            <br>
            <a href="/view_photo/{photo_name}" target="_blank">
                <img src="/view_photo/{photo_name}" style="max-width:300px; border-radius:10px; margin-top:10px;">
            </a>
            '''

        # 2. 엑셀 저장 (openpyxl 사용)
        import openpyxl
        from openpyxl import Workbook
        
        if not os.path.exists(EXCEL_FILE):
            wb = Workbook()
            ws = wb.active
            ws.append(['접수일시', '이름', '생년월일', '연락처', '이메일', '주소', '파일명', '경력1', '경력2', '희망근무', '출근가능일'])
        else:
            wb = openpyxl.load_workbook(EXCEL_FILE)
            ws = wb.active
            
        ws.append([
            now,
            request.form.get('name'),
            request.form.get('birth'),
            request.form.get('phone'),
            request.form.get('email'),
            request.form.get('address'),
            photo_filename,
            f"{request.form.get('company1')}/{request.form.get('job_role1')}" if request.form.get('company1') else "",
            f"{request.form.get('company2')}/{request.form.get('job_role2')}" if request.form.get('company2') else "",
            f"{request.form.get('shift')}",
            request.form.get('start_date')
        ])
        wb.save(EXCEL_FILE)

        # 3. HTML 파일 저장 (기존 방식 유지)
        content = f"<div style='border-bottom:2px solid #003057; padding:20px 0; margin-bottom:20px;'>"
        content += f"<h3 style='color:#003057; margin-bottom:10px;'>[신규 지원서 - {now}]</h3>"
        
        content += f"<div style='background:#f9f9f9; padding:15px; border-radius:10px;'>"
        content += f"<b>1. 인적사항</b><br>"
        content += f"성함: {request.form.get('name')} / 생년월일: {request.form.get('birth')}<br>"
        content += f"연락처: {request.form.get('phone')} / 주소: {request.form.get('address')}<br>"
        content += f"신분증 사진: {photo_html}<br>"
        content += f"</div><br>"

        content += f"<b>2. 경력사항</b><br>"
        content += f"● {request.form.get('company1')} / {request.form.get('job_role1')} / {request.form.get('reason1')}<br>"
        
        if request.form.get('company2'):
            content += f"● {request.form.get('company2')} / {request.form.get('job_role2')} / {request.form.get('reason2')}<br>"

        content += f"<br><b>3. 근무조건</b><br>"
        content += f"근무형태: {request.form.get('shift')} / 희망일: {request.form.get('start_date')}<br>"
        
        agree_check = request.form.get('agree')
        if agree_check == 'on':
            content += f"<br><div style='color:blue; font-weight:bold;'>✅ 개인정보 수집 동의 및 허위사실 확인 서약 완료</div>"
        else:
            content += f"<br><div style='color:red;'>❌ 동의하지 않음 (오류)</div>"
            
        content += f"</div>"
        
        with open(DATA_FILE, 'a', encoding='utf-8') as f:
            f.write(content)
        
        return "<h1>지원서 접수 완료!</h1><script>setTimeout(function(){location.href='/';}, 2000);</script>"
        
    except Exception as e:
        return f"<h1>오류 발생: {str(e)}</h1>"

# 5. 관리자 로그인 페이지
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        password = request.form.get('password')
        if password == ADMIN_PASSWORD:
            session['is_admin'] = True
            return redirect(url_for('master_view'))
        else:
            return "<script>alert('비밀번호가 틀렸습니다.'); history.back();</script>"
    return render_template('login.html')

# 6. 관리자 메인 페이지 (보안 적용)
@app.route('/humetix_master_99')
def master_view():
    if not session.get('is_admin'):
        return redirect(url_for('login'))
        
    btn_html = '''
    <div style="background:#fff3cd; padding:20px; margin-bottom:30px; text-align:center;">
        <h2 style="color:#003057;">관리자 페이지</h2>
        <div style="margin-bottom:15px;">
            <button onclick="location.href='/download_excel'" 
            style="background:#28a745; color:white; border:none; padding:10px 20px; cursor:pointer; margin-right:10px;">
            📊 엑셀 다운로드</button>
            <button onclick="if(confirm('전체 삭제하시겠습니까?')){location.href='/clear_data'}" 
            style="background:#dc3545; color:white; border:none; padding:10px 20px; cursor:pointer;">
            🗑️ 데이터 초기화</button>
        </div>
        <a href="/logout" style="color:gray; text-decoration:underline;">로그아웃</a>
    </div>
    '''
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            lines = f.read()
        return f"<div style='padding:20px; max-width:800px; margin:0 auto;'>{btn_html}{lines}</div>"
    return f"<div style='padding:20px; max-width:800px; margin:0 auto;'>{btn_html}<h3 style='text-align:center;'>데이터 없음</h3></div>"

@app.route('/logout')
def logout():
    session.pop('is_admin', None)
    return redirect(url_for('home'))

@app.route('/download_excel')
def download_excel():
    if not session.get('is_admin'):
        return redirect(url_for('login'))
    if os.path.exists(EXCEL_FILE):
        return send_from_directory(BASE_DIR, 'data.xlsx', as_attachment=True)
    return "<script>alert('엑셀 파일이 없습니다.'); history.back();</script>"

@app.route('/clear_data')
def clear_data():
    if not session.get('is_admin'):
        return redirect(url_for('login'))
        
    if os.path.exists(DATA_FILE): os.remove(DATA_FILE)
    if os.path.exists(EXCEL_FILE): os.remove(EXCEL_FILE) # 엑셀도 삭제
    if os.path.exists(UPLOAD_DIR):
        shutil.rmtree(UPLOAD_DIR)
        os.makedirs(UPLOAD_DIR)
    return "<script>location.href='/humetix_master_99';</script>"

if __name__ == '__main__':
    # SSL 인증서 경로 (서버에 파일이 확인됨)
    cert_path = '/etc/letsencrypt/live/humetix.com/fullchain.pem'
    key_path = '/etc/letsencrypt/live/humetix.com/privkey.pem'

    if os.path.exists(cert_path) and os.path.exists(key_path):
        # 인증서가 있으면 HTTPS (443 포트) 실행
        app.run(host='0.0.0.0', port=443, ssl_context=(cert_path, key_path))
    else:
        # 인증서가 없으면 HTTP (80 포트) 실행 (안전장치)
        app.run(host='0.0.0.0', port=80, debug=True)