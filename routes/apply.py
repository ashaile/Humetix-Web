import os
import uuid
from flask import Blueprint, render_template, request
from werkzeug.utils import secure_filename
from datetime import datetime
from models import db, Application, Career, Inquiry

apply_bp = Blueprint('apply', __name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOAD_DIR = os.path.join(BASE_DIR, 'uploads')
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
    """?덉슜???뚯씪 ?뺤옣?먯씤吏 ?뺤씤"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@apply_bp.route('/apply')
def apply_form():
    return render_template('apply.html')

@apply_bp.route('/submit', methods=['POST'])
def submit():
    try:
        file_now = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # 1. ?좊텇利??ъ쭊 泥섎━
        id_card = request.files.get('id_card')
        photo_filename = ""
        
        if id_card and id_card.filename != '':
            if not allowed_file(id_card.filename):
                return "<script>alert('?덉슜?섏? ?딅뒗 ?뚯씪 ?뺤떇?낅땲?? (jpg, png, gif, heic, webp留?媛??'); history.back();</script>"

            if id_card.mimetype not in ALLOWED_MIME_TYPES:
                return "<script>alert('허용되지 않는 파일 형식입니다.'); history.back();</script>"
            
            id_card.seek(0, 2)
            file_size = id_card.tell()
            id_card.seek(0)
            if file_size > MAX_FILE_SIZE:
                return "<script>alert('?뚯씪 ?ш린媛 5MB瑜?珥덇낵?⑸땲?? ???묒? ?뚯씪???좏깮?댁＜?몄슂.'); history.back();</script>"
            
            # 留ㅼ쭅 諛붿씠??寃??(Pillow)
            try:
                from PIL import Image
                img = Image.open(id_card)
                img.verify()  # ?ㅼ젣 ?대?吏 ?뚯씪?몄? 寃利?
                id_card.seek(0)  # 寃利????뚯씪 ?ъ씤??珥덇린??
                img = Image.open(id_card)
                img_format = (img.format or '').upper()
                if img_format not in {'JPEG', 'PNG', 'GIF', 'WEBP', 'HEIC', 'HEIF'}:
                    return "<script>alert('유효하지 않은 이미지 형식입니다.'); history.back();</script>"
                id_card.seek(0)
            except Exception:
                return "<script>alert('?좏슚?섏? ?딆? ?대?吏 ?뚯씪?낅땲?? (?먯긽?섏뿀嫄곕굹 媛吏??대?吏)'); history.back();</script>"
            
            ext = os.path.splitext(id_card.filename)[1].lower()
            photo_name = f"{file_now}_id{ext}"
            photo_path = os.path.join(UPLOAD_DIR, photo_name)
            id_card.save(photo_path)
            photo_filename = photo_name

        # 2. DB?????
        try:
            birth_date = datetime.strptime(request.form.get('birth'), '%Y-%m-%d').date() if request.form.get('birth') else None
            interview_date = datetime.strptime(request.form.get('interview_date'), '%Y-%m-%d').date() if request.form.get('interview_date') else None
            start_date_val = request.form.get('start_date')
            start_date = datetime.strptime(start_date_val, '%Y-%m-%d').date() if start_date_val else None

            height = int(request.form.get('height')) if request.form.get('height') else None
            weight = int(request.form.get('weight')) if request.form.get('weight') else None
            shoes = int(request.form.get('shoes')) if request.form.get('shoes') else None
            
            agree = True if request.form.get('agree') == 'on' else False

            # 중복 지원 검증 (연락처/이메일)
            phone_val = request.form.get('phone')
            email_val = request.form.get('email')
            if phone_val and Application.query.filter(Application.phone == phone_val).first():
                return "<script>alert('이미 등록된 연락처입니다. 중복 지원은 제한됩니다.'); history.back();</script>"
            if email_val and Application.query.filter(Application.email == email_val).first():
                return "<script>alert('이미 등록된 이메일입니다. 중복 지원은 제한됩니다.'); history.back();</script>"

            new_app = Application(
                id=str(uuid.uuid4()),
                # timestamp??default濡??먮룞 ?ㅼ젙??
                photo=photo_filename,
                name=request.form.get('name'),
                birth=birth_date,
                gender=request.form.get('gender'), # ?깅퀎 ???
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
                insurance_type=request.form.get('insurance_type', '4?蹂댄뿕'),
            )
            
            # 寃쎈젰?ы빆
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
            
            # 3. 愿由ъ옄 ?뚮┝ 諛쒖넚 (?대찓??SMS)
            from services.notification_service import NotificationService
            NotificationService.send_admin_notification(new_app.to_dict())
            
            return "<h1>吏?먯꽌 ?묒닔 ?꾨즺!</h1><script>setTimeout(function(){location.href='/';}, 2000);</script>"
            
        except ValueError as ve:
             # XSS 諛⑹?瑜??꾪빐 ?먮윭 硫붿떆吏 吏곸젒 ?몄텧 ?먯젣
             import logging
             logger = logging.getLogger(__name__)
             logger.error(f"Form validation error: {str(ve)}")
             return "<script>alert('?낅젰 ?묒떇???щ컮瑜댁? ?딆뒿?덈떎. ?ㅼ떆 ?뺤씤??二쇱꽭??'); history.back();</script>"
        
    except Exception as e:
        db.session.rollback()
        # ?곸꽭 ?먮윭???쒕쾭 濡쒓렇?먮쭔 湲곕줉
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Application submission error: {str(e)}", exc_info=True)
        
        # ?ъ슜?먯뿉寃뚮뒗 ?쇰컲?곸씤 硫붿떆吏 ?쒖떆
        return render_template('error.html', 
                             error_code="500", 
                             error_message="吏?먯꽌 ?묒닔 以??ㅻ쪟媛 諛쒖깮?덉뒿?덈떎", 
                             error_description="?좎떆 ???ㅼ떆 ?쒕룄?댁＜?몄슂. 臾몄젣媛 吏?띾릺硫??대떦?먯뿉寃?臾몄쓽 諛붾엻?덈떎."), 500

@apply_bp.route('/contact_submit', methods=['POST'])
def contact_submit():
    company = request.form.get('company', '').strip()
    name = request.form.get('name', '').strip()
    phone = request.form.get('phone', '').strip()
    email = request.form.get('email', '').strip()
    message = request.form.get('message', '').strip()

    if not company or not name or not phone:
        return "<script>alert('필수 항목을 입력해주세요.'); history.back();</script>"

    inquiry = Inquiry(
        company=company,
        name=name,
        phone=phone,
        email=email,
        message=message
    )
    db.session.add(inquiry)
    db.session.commit()

    return "<script>alert('문의가 접수되었습니다. 빠른 시일 내에 연락드리겠습니다.'); location.href='/'</script>"
