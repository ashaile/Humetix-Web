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
        try:
            birth_date = datetime.strptime(request.form.get('birth'), '%Y-%m-%d').date() if request.form.get('birth') else None
            interview_date = datetime.strptime(request.form.get('interview_date'), '%Y-%m-%d').date() if request.form.get('interview_date') else None
            start_date_val = request.form.get('start_date')
            start_date = datetime.strptime(start_date_val, '%Y-%m-%d').date() if start_date_val else None

            height = int(request.form.get('height')) if request.form.get('height') else None
            weight = int(request.form.get('weight')) if request.form.get('weight') else None
            shoes = int(request.form.get('shoes')) if request.form.get('shoes') else None
            
            agree = True if request.form.get('agree') == 'on' else False

            new_app = Application(
                id=str(uuid.uuid4()),
                # timestamp는 default로 자동 설정됨
                photo=photo_filename,
                name=request.form.get('name'),
                birth=birth_date,
                phone=request.form.get('phone'),
                email=request.form.get('email'),
                address=request.form.get('address'),
                height=height,
                weight=weight,
                vision=f"{request.form.get('vision_type')} {request.form.get('vision_value')}",
                shoes=shoes,
                tshirt=request.form.get('tshirt'),
                shift=request.form.get('shift'),
                posture=request.form.get('posture'),
                overtime=request.form.get('overtime'),
                holiday=request.form.get('holiday'),
                interview_date=interview_date,
                start_date=start_date,
                agree=agree,
                advance_pay=request.form.get('advance_pay', ''),
                insurance_type=request.form.get('insurance_type', '4대보험'),
            )
            
            # 경력사항
            for i in range(1, 4):
                company = request.form.get(f'company{i}')
                if company:
                    c_start = datetime.strptime(request.form.get(f'exp_start{i}'), '%Y-%m-%d').date() if request.form.get(f'exp_start{i}') else None
                    c_end = datetime.strptime(request.form.get(f'exp_end{i}'), '%Y-%m-%d').date() if request.form.get(f'exp_end{i}') else None
                    
                    career = Career(
                        company=company,
                        start=c_start,
                        end=c_end,
                        role=request.form.get(f'job_role{i}'),
                        reason=request.form.get(f'reason{i}'),
                    )
                    new_app.careers.append(career)
            
            db.session.add(new_app)
            db.session.commit()
            
            return "<h1>지원서 접수 완료!</h1><script>setTimeout(function(){location.href='/';}, 2000);</script>"
            
        except ValueError as ve:
             return f"<script>alert('입력 양식이 올바르지 않습니다: {str(ve)}'); history.back();</script>"
        
    except Exception as e:
        db.session.rollback()
        return f"<h1>오류 발생: {str(e)}</h1>"
