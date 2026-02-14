from flask import Flask, render_template, request, send_from_directory
import os, shutil
from datetime import datetime

app = Flask(__name__)

# [중요] 현재 파일이 있는 폴더 위치를 자동으로 찾습니다.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, 'uploads')
DATA_FILE = os.path.join(BASE_DIR, 'data_html.txt')

# 업로드 폴더가 없으면 알아서 만듭니다.
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

# 1. 메인 홈페이지 (index.html) 보여주기
@app.route('/')
def home():
    return render_template('index.html')

# 2. 입사지원서 페이지 (apply.html) 보여주기
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
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    file_now = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    id_card = request.files.get('id_card')
    photo_html = "<span style='color:gray;'>[사진 없음]</span>"
    
    if id_card and id_card.filename != '':
        photo_name = f"{file_now}_id.jpg"
        id_card.save(os.path.join(UPLOAD_DIR, photo_name))
        
        photo_html = f'''
        <br>
        <a href="/view_photo/{photo_name}" target="_blank" style="text-decoration:none;">
            <img src="/view_photo/{photo_name}" 
                 style="max-width:300px; border-radius:10px; border:1px solid #ccc; margin-top:10px; cursor:pointer;"
                 title="클릭하면 원본 크기로 보입니다">
            <br><span style="font-size:0.8rem; color:#0056b3;">🔍 사진을 클릭하면 확대됩니다</span>
        </a><br>
        '''

    content = f"<div style='border-bottom:2px solid #003057; padding:20px 0; margin-bottom:20px;'>"
    content += f"<h3 style='color:#003057; margin-bottom:10px;'>[신규 지원서 - {now}]</h3>"
    
    content += f"<div style='background:#f9f9f9; padding:15px; border-radius:10px;'>"
    content += f"<b>1. 인적사항</b><br>"
    content += f"성함: {request.form.get('name')} / 생년월일: {request.form.get('birth')}<br>"
    content += f"연락처: <a href='tel:{request.form.get('phone')}'>{request.form.get('phone')}</a> / 이메일: <a href='mailto:{request.form.get('email')}'>{request.form.get('email')}</a><br>"
    content += f"주소: {request.form.get('address')}<br>"
    content += f"신분증 사진: {photo_html}<br>"
    content += f"</div><br>"

    content += f"<b>2. 경력사항</b><br>"
    content += f"● {request.form.get('company1')} ({request.form.get('exp_start1')}~{request.form.get('exp_end1')}) / {request.form.get('job_role1')} / {request.form.get('reason1')}<br>"
    
    if request.form.get('company2'):
        content += f"● {request.form.get('company2')} ({request.form.get('exp_start2')}~{request.form.get('exp_end2')}) / {request.form.get('job_role2')} / {request.form.get('reason2')}<br>"
    
    if request.form.get('company3'):
        content += f"● {request.form.get('company3')} ({request.form.get('exp_start3')}~{request.form.get('exp_end3')}) / {request.form.get('job_role3')} / {request.form.get('reason3')}<br>"
    
    content += f"<br><b>3. 신체 및 기타</b><br>"
    content += f"시력: {request.form.get('vision_type')}({request.form.get('vision_value')}) / 신발: {request.form.get('shoes')} / 티셔츠: {request.form.get('tshirt')}<br>"
    content += f"신체: {request.form.get('height')}cm, {request.form.get('weight')}kg<br>"
    
    content += f"조건: {request.form.get('shift')} / {request.form.get('posture')}<br>"
    content += f"추가근무: <b>잔업 {request.form.get('overtime')} / 특근 {request.form.get('holiday')}</b><br>"
    
    interview = request.form.get('interview_date') if request.form.get('interview_date') else "미지정"
    content += f"면접 희망일: <b style='color:#0056b3;'>{interview}</b><br>"
    content += f"입사 희망일: <b style='color:red;'>{request.form.get('start_date')}</b><br>"
    content += f"</div>"
    
    with open(DATA_FILE, 'a', encoding='utf-8') as f:
        f.write(content)
    
    return "<h1>지원서 접수 완료!</h1><script>setTimeout(function(){location.href='/';}, 2000);</script>"

# 5. 관리자 페이지
@app.route('/humetix_master_99')
def master_view():
    btn_html = '''
    <div style="background:#fff3cd; padding:20px; margin-bottom:30px; border-radius:10px; border:1px solid #ffeeba; text-align:center;">
        <h2 style="color:#003057;">관리자 페이지</h2>
        <p>지원서 내역을 확인하고 관리할 수 있습니다.</p>
        <button onclick="if(confirm('정말 모든 지원서와 사진 데이터를 영구 삭제하시겠습니까?\\n복구할 수 없습니다!')){location.href='/clear_data'}" 
        style="background:#dc3545; color:white; border:none; padding:15px 30px; border-radius:5px; cursor:pointer; font-weight:bold; font-size:1.1rem;">
        🗑️ 데이터 전체 초기화 (삭제)</button>
    </div>
    '''
    
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            lines = f.read()
        return f"<div style='font-family:sans-serif; padding:20px; max-width:800px; margin:0 auto;'>{btn_html}{lines}</div>"
    
    return f"<div style='font-family:sans-serif; padding:20px; text-align:center;'>{btn_html}<h3>현재 접수된 지원서가 없습니다.</h3></div>"

@app.route('/clear_data')
def clear_data():
    if os.path.exists(DATA_FILE):
        os.remove(DATA_FILE)
    if os.path.exists(UPLOAD_DIR):
        shutil.rmtree(UPLOAD_DIR)
        os.makedirs(UPLOAD_DIR)
    return """<script>alert('모든 데이터가 삭제되었습니다.'); location.href='/humetix_master_99';</script>"""

if __name__ == '__main__':
    # 내 컴퓨터에서 실행할 때 쓰는 설정
    app.run(host='0.0.0.0', port=5000, debug=True)