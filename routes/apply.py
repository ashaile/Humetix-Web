import os
import uuid
from flask import Blueprint, render_template, request
from werkzeug.utils import secure_filename
from datetime import datetime
from models import db, Application, Career

apply_bp = Blueprint('apply', __name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOAD_DIR = os.path.join(BASE_DIR, 'uploads')
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif', 'heic', 'heif', 'webp'}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB

def allowed_file(filename):
    """허용된 파일 확장자인지 확인"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@apply_bp.route('/apply')
def apply_form():
    return render_template('apply.html')

@apply_bp.route('/submit', methods=['POST'])
def submit():
    try:
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        file_now = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # 1. 신분증 사진 처리
        id_card = request.files.get('id_card')
        photo_filename = ""
        
        if id_card and id_card.filename != '':
            if not allowed_file(id_card.filename):
                return "<script>alert('허용되지 않는 파일 형식입니다. (jpg, png, gif, heic, webp만 가능)'); history.back();</script>"
            
            id_card.seek(0, 2)
            file_size = id_card.tell()
            id_card.seek(0)
            if file_size > MAX_FILE_SIZE:
                return "<script>alert('파일 크기가 5MB를 초과합니다. 더 작은 파일을 선택해주세요.'); history.back();</script>"
            
            ext = os.path.splitext(id_card.filename)[1].lower()
            photo_name = f"{file_now}_id{ext}"
            photo_path = os.path.join(UPLOAD_DIR, photo_name)
            id_card.save(photo_path)
            photo_filename = photo_name

        # 2. DB에 저장
        new_app = Application(
            id=str(uuid.uuid4()),
            timestamp=now,
            photo=photo_filename,
            name=request.form.get('name'),
            birth=request.form.get('birth'),
            phone=request.form.get('phone'),
            email=request.form.get('email'),
            address=request.form.get('address'),
            height=request.form.get('height'),
            weight=request.form.get('weight'),
            vision=f"{request.form.get('vision_type')} {request.form.get('vision_value')}",
            shoes=request.form.get('shoes'),
            tshirt=request.form.get('tshirt'),
            shift=request.form.get('shift'),
            posture=request.form.get('posture'),
            overtime=request.form.get('overtime'),
            holiday=request.form.get('holiday'),
            interview_date=request.form.get('interview_date'),
            start_date=request.form.get('start_date'),
            agree=request.form.get('agree'),
            advance_pay=request.form.get('advance_pay', ''),
            insurance_type=request.form.get('insurance_type', '4대보험'),
        )
        
        # 경력사항
        for i in range(1, 4):
            company = request.form.get(f'company{i}')
            if company:
                career = Career(
                    company=company,
                    start=request.form.get(f'exp_start{i}'),
                    end=request.form.get(f'exp_end{i}'),
                    role=request.form.get(f'job_role{i}'),
                    reason=request.form.get(f'reason{i}'),
                )
                new_app.careers.append(career)
        
        db.session.add(new_app)
        db.session.commit()
        
        return "<h1>지원서 접수 완료!</h1><script>setTimeout(function(){location.href='/';}, 2000);</script>"
        
    except Exception as e:
        db.session.rollback()
        return f"<h1>오류 발생: {str(e)}</h1>"
