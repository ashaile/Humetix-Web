import os
import uuid
import logging
from flask import Blueprint, render_template, request, redirect, url_for, flash
from werkzeug.utils import secure_filename
from datetime import datetime
from PIL import Image
from models import db, Application, Career

# Logger 설정
logger = logging.getLogger(__name__)

apply_bp = Blueprint('apply', __name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOAD_DIR = os.path.join(BASE_DIR, 'uploads')
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif', 'heic', 'heif', 'webp'}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB

def allowed_file(filename):
    """허용된 파일 확장자인지 확인"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def _validate_required_fields(form):
    """필수 입력값 검증"""
    required = ['name', 'phone']
    for field in required:
        if not form.get(field, '').strip():
            return False, f'{field} 항목은 필수 입력입니다.'
    return True, ''

@apply_bp.route('/apply')
def apply_form():
    return render_template('apply.html')

@apply_bp.route('/submit', methods=['POST'])
def submit():
    try:
        file_now = datetime.now().strftime('%Y%m%d_%H%M%S')

        # 0. 필수 입력값 검증
        valid, msg = _validate_required_fields(request.form)
        if not valid:
            flash(msg, 'danger')
            return redirect(url_for('apply.apply_form'))

        # 1. 신분증 사진 처리
        id_card = request.files.get('id_card')
        photo_filename = ""

        if id_card and id_card.filename != '':
            if not allowed_file(id_card.filename):
                flash('허용되지 않는 파일 형식입니다. (jpg, png, gif, heic, webp만 가능)', 'danger')
                return redirect(url_for('apply.apply_form'))

            id_card.seek(0, 2)
            file_size = id_card.tell()
            id_card.seek(0)
            if file_size > MAX_FILE_SIZE:
                flash('파일 크기가 5MB를 초과합니다. 더 작은 파일을 선택해주세요.', 'danger')
                return redirect(url_for('apply.apply_form'))

            # 매직 바이트 검사 (Pillow)
            try:
                img = Image.open(id_card)
                img.verify()
                id_card.seek(0)
            except Exception:
                flash('유효하지 않은 이미지 파일입니다. (손상되었거나 가짜 이미지)', 'danger')
                return redirect(url_for('apply.apply_form'))

            # secure_filename 적용
            original_name = secure_filename(id_card.filename)
            ext = os.path.splitext(original_name)[1].lower()
            if not ext:
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

            agree = request.form.get('agree') == 'on'

            new_app = Application(
                id=str(uuid.uuid4()),
                photo=photo_filename,
                name=request.form.get('name'),
                birth=birth_date,
                gender=request.form.get('gender'),
                phone=request.form.get('phone'),
                email=request.form.get('email'),
                address=request.form.get('address'),
                height=height,
                weight=weight,
                vision=f"{request.form.get('vision_type', '')} {request.form.get('vision_value', '')}".strip(),
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
                status='접수',
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
            logger.info(f"New application submitted: {new_app.id} ({new_app.name})")

            # 3. 관리자 알림 발송 (비동기)
            import threading
            from services.notification_service import NotificationService
            app_data = new_app.to_dict()
            threading.Thread(
                target=NotificationService.send_admin_notification,
                args=(app_data,),
                daemon=True
            ).start()

            return render_template('submit_success.html', name=new_app.name)

        except ValueError as ve:
            logger.error(f"Form validation error: {str(ve)}")
            flash('입력 양식이 올바르지 않습니다. 다시 확인해 주세요.', 'danger')
            return redirect(url_for('apply.apply_form'))

    except Exception as e:
        db.session.rollback()
        logger.error(f"Application submission error: {str(e)}", exc_info=True)
        return render_template('error.html',
                             error_code="500",
                             error_message="지원서 접수 중 오류가 발생했습니다",
                             error_description="잠시 후 다시 시도해주세요. 문제가 지속되면 담당자에게 문의 바랍니다."), 500
