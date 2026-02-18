import os
from flask import Blueprint, render_template, request, redirect, url_for, session, send_file, send_from_directory
from io import BytesIO
from datetime import datetime
import openpyxl
from openpyxl import Workbook
from openpyxl.drawing.image import Image as ExcelImage
from openpyxl.styles import Font, Alignment, Border, Side
from PIL import Image as PILImage
from models import db, Application, Inquiry
from sqlalchemy.orm import joinedload

import logging

# Logger 설정
logger = logging.getLogger(__name__)

admin_bp = Blueprint('admin', __name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOAD_DIR = os.path.join(BASE_DIR, 'uploads')

@admin_bp.route('/humetix_master_99')
def master_view():
    if not session.get('is_admin'):
        return redirect(url_for('auth.login'))
    
    search_type = request.args.get('type', 'name')
    search_query = request.args.get('q', '')
    
    # 상세 필터 파라미터 받기
    filters = {
        'gender': request.args.get('gender'),
        'shift': request.args.get('shift'),
        'posture': request.args.get('posture'),
        'overtime': request.args.get('overtime'),
        'holiday': request.args.get('holiday'),
        'agree': request.args.get('agree'),
        'advance_pay': request.args.get('advance_pay'),
        'insurance_type': request.args.get('insurance_type'),
        'status': request.args.get('status'),
    }
    
    # 날짜 필터
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    query = Application.query.options(joinedload(Application.careers))
    
    # 1. 기본 검색 (이름/연락처)
    if search_query:
        if search_type == 'name':
            query = query.filter(Application.name.contains(search_query))
        elif search_type == 'phone':
            query = query.filter(Application.phone.contains(search_query))
            
    # 2. 상세 필터 적용
    if filters['gender']:
        query = query.filter(Application.gender == filters['gender'])
        
    if filters['shift']:
        query = query.filter(Application.shift == filters['shift'])
        
    if filters['posture']:
        query = query.filter(Application.posture == filters['posture'])
        
    if filters['overtime']:
        query = query.filter(Application.overtime == filters['overtime'])
        
    if filters['holiday']:
        query = query.filter(Application.holiday == filters['holiday'])

    if filters['agree']: # 정보제공 동의 여부 (on/off)
        is_agree = True if filters['agree'] == 'on' else False
        query = query.filter(Application.agree == is_agree)
        
    if filters['advance_pay']:
        query = query.filter(Application.advance_pay == filters['advance_pay'])
        
    if filters['insurance_type']:
        query = query.filter(Application.insurance_type == filters['insurance_type'])

    if filters['status']:
        query = query.filter(Application.status == filters['status'])
    
    # 3. 날짜 범위 검색 (접수일 기준)
    if start_date:
        s_date = datetime.strptime(start_date, '%Y-%m-%d')
        query = query.filter(Application.timestamp >= s_date)
        
    if end_date:
        e_date = datetime.strptime(end_date, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
        query = query.filter(Application.timestamp <= e_date)
            
    # 4. 페이지네이션 적용 (10개씩)
    page = request.args.get('page', 1, type=int)
    per_page = 10
    pagination = query.order_by(Application.timestamp.desc()).paginate(page=page, per_page=per_page, error_out=False)
    
    # 현재 페이지의 데이터만 딕셔너리로 변환
    data = [app.to_dict() for app in pagination.items]

    status_options = ['new', 'review', 'interview', 'offer', 'hired', 'rejected']
    return render_template(
        'admin.html',
        data=data,
        pagination=pagination,
        filters=filters,
        search_query=search_query,
        start_date=start_date,
        end_date=end_date,
        status_options=status_options
    )


@admin_bp.route('/inquiries/delete', methods=['POST'])
def delete_inquiries():
    if not session.get('is_admin'):
        return redirect(url_for('auth.login'))

    selected_ids = request.form.getlist('selected_ids')
    if not selected_ids:
        return redirect(url_for('admin.inquiries'))

    for inquiry_id in selected_ids:
        item = Inquiry.query.get(inquiry_id)
        if item:
            db.session.delete(item)
    db.session.commit()

    return redirect(url_for('admin.inquiries'))


@admin_bp.route('/inquiries/update/<int:inquiry_id>', methods=['POST'])
def update_inquiry(inquiry_id):
    if not session.get('is_admin'):
        return redirect(url_for('auth.login'))

    item = Inquiry.query.get(inquiry_id)
    if not item:
        return redirect(url_for('admin.inquiries'))

    item.status = request.form.get('status', item.status)
    item.assignee = request.form.get('assignee', item.assignee)
    item.admin_memo = request.form.get('admin_memo', item.admin_memo)
    db.session.commit()

    return redirect(url_for('admin.inquiries'))
@admin_bp.route('/view_photo/<filename>')
def view_photo(filename):
    file_path = os.path.join(UPLOAD_DIR, filename)
    if not os.path.exists(file_path):
        return "Not Found", 404

    ext = os.path.splitext(filename)[1].lower()
    if ext in {'.heic', '.heif'}:
        try:
            from pillow_heif import register_heif_opener
            register_heif_opener()
            with PILImage.open(file_path) as img:
                if img.mode not in ('RGB',):
                    img = img.convert('RGB')
                buf = BytesIO()
                img.save(buf, format='JPEG', quality=85)
                buf.seek(0)
            return send_file(buf, mimetype='image/jpeg', download_name=f"{os.path.splitext(filename)[0]}.jpg")
        except Exception as e:
            logger.error(f"HEIC preview failed for {filename}: {e}")
            return "Unsupported image", 415

    return send_from_directory(UPLOAD_DIR, filename)

@admin_bp.route('/clear_data', methods=['POST'])
def clear_data():
    if not session.get('is_admin'):
        return redirect(url_for('auth.login'))
    
    # 모든 지원서 삭제 (ORM 캐스케이드 적용) + 사진 정리
    apps = Application.query.all()
    referenced_photos = set()
    for app in apps:
        if app.photo:
            referenced_photos.add(app.photo)
            try:
                os.remove(os.path.join(UPLOAD_DIR, app.photo))
            except Exception as e:
                logger.error(f"Error deleting photo {app.photo}: {e}")
        db.session.delete(app)
    db.session.commit()
    
    # 남아있는 업로드 파일 정리 (DB에 없는 파일)
    for f in os.listdir(UPLOAD_DIR):
        if f not in referenced_photos:
            try:
                os.remove(os.path.join(UPLOAD_DIR, f))
            except Exception as e:
                logger.error(f"Error deleting leftover file {f}: {e}")
        
    return redirect(url_for('admin.master_view'))
