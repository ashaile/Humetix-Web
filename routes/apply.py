import logging
import os
import uuid
from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for

from models import Application, Career, Inquiry, db
from routes.utils import UPLOAD_DIR

logger = logging.getLogger(__name__)

apply_bp = Blueprint('apply', __name__)
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif', 'heic', 'heif', 'webp'}
ALLOWED_MIME_TYPES = {
    'image/jpeg',
    'image/png',
    'image/gif',
    'image/heic',
    'image/heif',
    'image/webp'
}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB


def allowed_file(filename):
    """허용된 파일 확장자 확인"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@apply_bp.route('/apply')
def apply_form():
    return render_template('apply.html')


@apply_bp.route('/submit', methods=['POST'])
def submit():
    try:
        file_now = datetime.now().strftime('%Y%m%d_%H%M%S')

        # 0. 필수 필드 서버사이드 검증
        name = request.form.get('name', '').strip()
        phone = request.form.get('phone', '').strip()
        agree = request.form.get('agree')
        if not name or not phone:
            flash('이름과 연락처는 필수 항목입니다.', 'error')
            return redirect(url_for('apply.apply_form'))
        if agree != 'on':
            flash('개인정보 수집·이용에 동의해주세요.', 'error')
            return redirect(url_for('apply.apply_form'))

        # 1. 신분증 사진 처리
        id_card = request.files.get('id_card')
        photo_filename = ""

        if id_card and id_card.filename != '':
            if not allowed_file(id_card.filename):
                flash('허용되지 않는 파일 형식입니다. (jpg, png, gif, heic, webp만 가능)', 'error')
                return redirect(url_for('apply.apply_form'))

            if id_card.mimetype and id_card.mimetype not in ALLOWED_MIME_TYPES:
                if id_card.mimetype != 'application/octet-stream':
                    flash('허용되지 않는 파일 형식입니다.', 'error')
                    return redirect(url_for('apply.apply_form'))

            id_card.seek(0, 2)
            file_size = id_card.tell()
            id_card.seek(0)
            if file_size > MAX_FILE_SIZE:
                flash('파일 크기가 5MB를 초과했습니다. 다른 파일을 선택해주세요.', 'error')
                return redirect(url_for('apply.apply_form'))

            # 매직 바이트 기반 이미지 검증(Pillow)
            try:
                from PIL import Image
                try:
                    from pillow_heif import register_heif_opener
                    register_heif_opener()
                except Exception:
                    pass

                img = Image.open(id_card)
                img.verify()  # 실제 이미지 파일인지 검증
                id_card.seek(0)

                img = Image.open(id_card)
                img_format = (img.format or '').upper()
                if img_format not in {'JPEG', 'PNG', 'GIF', 'WEBP', 'HEIC', 'HEIF'}:
                    flash('유효하지 않은 이미지 형식입니다.', 'error')
                    return redirect(url_for('apply.apply_form'))
                id_card.seek(0)
            except Exception:
                flash('유효하지 않은 이미지 파일입니다. (손상 또는 지원하지 않는 형식)', 'error')
                return redirect(url_for('apply.apply_form'))

            ext = os.path.splitext(id_card.filename)[1].lower()
            photo_name = f"{file_now}_id{ext}"
            photo_path = os.path.join(UPLOAD_DIR, photo_name)
            id_card.save(photo_path)
            photo_filename = photo_name

        # 2. DB 저장
        try:
            birth_date = datetime.strptime(request.form.get('birth'), '%Y-%m-%d').date() if request.form.get('birth') else None
            interview_date = datetime.strptime(request.form.get('interview_date'), '%Y-%m-%d').date() if request.form.get('interview_date') else None
            start_date_val = request.form.get('start_date')
            start_date = datetime.strptime(start_date_val, '%Y-%m-%d').date() if start_date_val else None

            height = int(request.form.get('height')) if request.form.get('height') else None
            weight = int(request.form.get('weight')) if request.form.get('weight') else None
            shoes = int(request.form.get('shoes')) if request.form.get('shoes') else None

            vision_type = request.form.get('vision_type')
            vision_value = request.form.get('vision_value')
            vision = None
            if vision_type or vision_value:
                vision = f"{vision_type or ''} {vision_value or ''}".strip()

            new_app = Application(
                id=str(uuid.uuid4()),
                # timestamp는 default로 자동 설정됨
                photo=photo_filename,
                name=name,
                agree=True,
                birth=birth_date,
                gender=request.form.get('gender'),
                phone=phone,
                email=request.form.get('email'),
                address=request.form.get('address'),
                height=height,
                weight=weight,
                vision=vision,
                shoes=shoes,
                tshirt=request.form.get('tshirt'),
                shift=request.form.get('shift'),
                posture=request.form.get('posture'),
                overtime=request.form.get('overtime'),
                holiday=request.form.get('holiday'),
                interview_date=interview_date,
                start_date=start_date,
                advance_pay=request.form.get('advance_pay', '비희망'),
                insurance_type=request.form.get('insurance_type', '3.3%'),
            )

            # 경력 사항
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

            # 3. 관리자 알림 발송 (이메일/SMS)
            from services.notification_service import NotificationService
            NotificationService.send_admin_notification(new_app.to_dict())

            flash('지원서가 접수되었습니다!', 'success')
            return redirect('/')

        except ValueError as ve:
            logger.error(f"Form validation error: {str(ve)}")
            flash('입력 형식이 올바르지 않습니다. 다시 확인해주세요.', 'error')
            return redirect(url_for('apply.apply_form'))

    except Exception as e:
        db.session.rollback()
        logger.error(f"Application submission error: {str(e)}", exc_info=True)

        return render_template(
            'error.html',
            error_code="500",
            error_message="지원서 접수 중 오류가 발생했습니다",
            error_description="잠시 후 다시 시도해주세요. 문제가 지속되면 관리자에게 문의 바랍니다."
        ), 500


@apply_bp.route('/contact_submit', methods=['POST'])
def contact_submit():
    company = request.form.get('company', '').strip()
    name = request.form.get('name', '').strip()
    phone = request.form.get('phone', '').strip()
    email = request.form.get('email', '').strip()
    message = request.form.get('message', '').strip()

    if not company or not name or not phone:
        flash('필수 항목을 입력해주세요.', 'error')
        return redirect('/#contact')

    try:
        inquiry = Inquiry(
            company=company,
            name=name,
            phone=phone,
            email=email,
            message=message
        )
        db.session.add(inquiry)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error(f"Contact submit error: {str(e)}", exc_info=True)
        flash('문의 접수 중 오류가 발생했습니다. 다시 시도해주세요.', 'error')
        return redirect('/#contact')

    flash('문의가 접수되었습니다. 빠른 시일 내에 연락드리겠습니다.', 'success')
    return redirect('/')
