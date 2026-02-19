import os
from flask import Blueprint, render_template, request, redirect, url_for, session, send_file, send_from_directory, jsonify
from io import BytesIO
from datetime import datetime
import openpyxl
from openpyxl import Workbook
from openpyxl.drawing.image import Image as ExcelImage
from openpyxl.styles import Font, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from PIL import Image as PILImage
from models import db, Application, Inquiry
from sqlalchemy.orm import joinedload

import logging

# Logger 설정
logger = logging.getLogger(__name__)

admin_bp = Blueprint('admin', __name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOAD_DIR = os.path.join(BASE_DIR, 'uploads')

def build_filtered_query(args):
    search_type = args.get('type', 'name')
    search_query = args.get('q', '')

    filters = {
        'gender': args.get('gender'),
        'shift': args.get('shift'),
        'posture': args.get('posture'),
        'overtime': args.get('overtime'),
        'holiday': args.get('holiday'),
        'agree': args.get('agree'),
        'advance_pay': args.get('advance_pay'),
        'insurance_type': args.get('insurance_type'),
        'status': args.get('status'),
    }

    start_date = args.get('start_date')
    end_date = args.get('end_date')

    query = Application.query.options(joinedload(Application.careers))

    if search_query:
        if search_type == 'name':
            query = query.filter(Application.name.contains(search_query))
        elif search_type == 'phone':
            query = query.filter(Application.phone.contains(search_query))

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
    if filters['agree']:
        is_agree = True if filters['agree'] == 'on' else False
        query = query.filter(Application.agree == is_agree)
    if filters['advance_pay']:
        query = query.filter(Application.advance_pay == filters['advance_pay'])
    if filters['insurance_type']:
        query = query.filter(Application.insurance_type == filters['insurance_type'])
    if filters['status']:
        query = query.filter(Application.status == filters['status'])

    if start_date:
        s_date = datetime.strptime(start_date, '%Y-%m-%d')
        query = query.filter(Application.timestamp >= s_date)
    if end_date:
        e_date = datetime.strptime(end_date, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
        query = query.filter(Application.timestamp <= e_date)

    return query, filters, search_query, start_date, end_date

@admin_bp.route('/humetix_master_99')
def master_view():
    if not session.get('is_admin'):
        return redirect(url_for('auth.login'))

    query, filters, search_query, start_date, end_date = build_filtered_query(request.args)

    page = request.args.get('page', 1, type=int)
    per_page = 10
    pagination = query.order_by(Application.timestamp.desc()).paginate(page=page, per_page=per_page, error_out=False)

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
        status_options=status_options,
        query_string=request.query_string.decode()
    )


@admin_bp.route('/download_excel')
def download_excel():
    if not session.get('is_admin'):
        return redirect(url_for('auth.login'))

    query, _, _, _, _ = build_filtered_query(request.args)
    apps = query.order_by(Application.timestamp.desc()).all()

    wb = Workbook()
    ws = wb.active
    ws.title = "\uC9C0\uC6D0\uC11C"

    headers = [
        "\uC544\uC774\uB514", "\uC811\uC218\uC77C", "\uC131\uBA85", "\uC5F0\uB77D\uCC98", "\uC774\uBA54\uC77C", "\uC8FC\uC18C",
        "\uC2E0\uCCB4", "\uC2DC\uB825", "\uC0AC\uC774\uC988", "\uADFC\uBB34", "\uC77C\uC815", "\uD76C\uB9DD",
        "\uC0C1\uD0DC", "\uBA54\uBAA8", "\uC0AC\uC9C4"
    ]
    ws.append(headers)

    header_font = Font(bold=True)
    for cell in ws[1]:
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(headers))}1"

    photo_col = get_column_letter(len(headers))

    for row_idx, app in enumerate(apps, start=2):
        height_val = f"{app.height}cm" if app.height is not None else "-"
        weight_val = f"{app.weight}kg" if app.weight is not None else "-"
        body = f"{height_val} / {weight_val}"

        size = f"\uC2E0\uBC1C:{app.shoes if app.shoes is not None else '-'} / \uD2F0\uC154\uCE20:{app.tshirt or '-'}"

        work = "\n".join([
            f"\uD615\uD0DC:{app.shift or '-'}",
            f"\uBC29\uC2DD:{app.posture or '-'}",
            f"\uC794\uC5C5:{app.overtime or '-'}",
            f"\uD2B9\uADFC:{app.holiday or '-'}",
        ])

        schedule = "\n".join([
            f"\uBA74\uC811:{app.interview_date.strftime('%Y-%m-%d') if app.interview_date else '\uBBF8\uC815'}",
            f"\uC785\uC0AC:{app.start_date.strftime('%Y-%m-%d') if app.start_date else '\uBBF8\uC815'}",
        ])

        wish = "\n".join([
            f"\uAC00\uBD88:{app.advance_pay or '-'}",
            f"\uAE09\uC5EC:{app.insurance_type or '-'}",
        ])

        ws.append([
            app.id,
            app.timestamp.strftime('%Y-%m-%d %H:%M:%S') if app.timestamp else "",
            app.name or "",
            app.phone or "",
            app.email or "",
            app.address or "",
            body,
            app.vision or "",
            size,
            work,
            schedule,
            wish,
            app.status or "",
            app.memo or "",
            "",
        ])

        for col_idx in range(1, len(headers) + 1):
            cell = ws.cell(row=row_idx, column=col_idx)
            cell.alignment = Alignment(wrap_text=True, vertical="top")

        if app.photo:
            photo_path = os.path.join(UPLOAD_DIR, app.photo)
            if os.path.exists(photo_path):
                try:
                    try:
                        from pillow_heif import register_heif_opener
                        register_heif_opener()
                    except Exception:
                        pass
                    with PILImage.open(photo_path) as img:
                        if img.mode not in ('RGB',):
                            img = img.convert('RGB')
                        img.thumbnail((120, 160))
                        from io import BytesIO as _BytesIO
                        img_stream = _BytesIO()
                        img.save(img_stream, format='PNG')
                        img_stream.seek(0)
                        excel_img = ExcelImage(img_stream)
                        ws.add_image(excel_img, f"{photo_col}{row_idx}")
                        ws.row_dimensions[row_idx].height = max(ws.row_dimensions[row_idx].height or 0, img.height * 0.75)
                except Exception:
                    pass

    col_widths = {
        "A": 38,  # ID
        "B": 18,  # 접수일
        "C": 10,  # 성명
        "D": 16,  # 연락처
        "E": 24,  # 이메일
        "F": 28,  # 주소
        "G": 16,  # 신체
        "H": 12,  # 시력
        "I": 18,  # 사이즈
        "J": 22,  # 근무
        "K": 22,  # 일정
        "L": 18,  # 희망
        "M": 10,  # 상태
        "N": 30,  # 메모
        "O": 12,  # 사진
    }
    for col, width in col_widths.items():
        ws.column_dimensions[col].width = width

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return send_file(
        buf,
        as_attachment=True,
        download_name="humetix_applications.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


@admin_bp.route('/update_memo/<app_id>', methods=['POST'])
def update_memo(app_id):
    if not session.get('is_admin'):
        return jsonify({"success": False, "message": "\uAD8C\uD55C\uC774 \uC5C6\uC2B5\uB2C8\uB2E4."}), 401

    app = Application.query.get(app_id)
    if not app:
        return jsonify({"success": False, "message": "\uC9C0\uC6D0\uC11C\uB97C \uCC3E\uC744 \uC218 \uC5C6\uC2B5\uB2C8\uB2E4."}), 404

    app.memo = request.form.get('memo', '')
    db.session.commit()
    return jsonify({"success": True})


@admin_bp.route('/update_status/<app_id>', methods=['POST'])
def update_status(app_id):
    if not session.get('is_admin'):
        return jsonify({"success": False, "message": "\uAD8C\uD55C\uC774 \uC5C6\uC2B5\uB2C8\uB2E4."}), 401

    app = Application.query.get(app_id)
    if not app:
        return jsonify({"success": False, "message": "\uC9C0\uC6D0\uC11C\uB97C \uCC3E\uC744 \uC218 \uC5C6\uC2B5\uB2C8\uB2E4."}), 404

    status_val = request.form.get('status', '')
    allowed = {'new', 'review', 'interview', 'offer', 'hired', 'rejected'}
    if status_val not in allowed:
        return jsonify({"success": False, "message": "\uC720\uD6A8\uD558\uC9C0 \uC54A\uC740 \uC0C1\uD0DC\uC785\uB2C8\uB2E4."}), 400

    app.status = status_val
    db.session.commit()
    return jsonify({"success": True})

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


@admin_bp.route('/delete_selected', methods=['POST'])
def delete_selected():
    if not session.get('is_admin'):
        return redirect(url_for('auth.login'))

    selected_ids = request.form.getlist('selected_ids')
    if not selected_ids:
        return redirect(url_for('admin.master_view'))

    apps = Application.query.filter(Application.id.in_(selected_ids)).all()
    for app in apps:
        if app.photo:
            try:
                os.remove(os.path.join(UPLOAD_DIR, app.photo))
            except Exception as e:
                logger.error(f"Error deleting photo {app.photo}: {e}")
        db.session.delete(app)
    db.session.commit()

    return redirect(url_for('admin.master_view'))
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
