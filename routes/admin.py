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

    col_widths = {
        "A": 10, "B": 10, "C": 12, "D": 28, "E": 12, "F": 28, "G": 12, "H": 28,
    }
    for col, width in col_widths.items():
        ws.column_dimensions[col].width = width

    header_fill = openpyxl.styles.PatternFill("solid", fgColor="1F4E78")
    header_font = Font(color="FFFFFF", bold=True)
    label_font = Font(bold=True)
    border = Border(
        left=Side(style="thin"), right=Side(style="thin"),
        top=Side(style="thin"), bottom=Side(style="thin")
    )

    def set_cell(r, c, value, bold=False):
        cell = ws.cell(row=r, column=c, value=value)
        if bold:
            cell.font = label_font
        cell.alignment = Alignment(vertical="center", wrap_text=True)
        cell.border = border
        return cell

    def merge_and_set(r1, c1, r2, c2, value, bold=False):
        ws.merge_cells(start_row=r1, start_column=c1, end_row=r2, end_column=c2)
        cell = ws.cell(row=r1, column=c1, value=value)
        if bold:
            cell.font = label_font
        cell.alignment = Alignment(vertical="center", wrap_text=True)
        cell.border = border
        for r in range(r1, r2 + 1):
            for c in range(c1, c2 + 1):
                ws.cell(row=r, column=c).border = border

    row = 1
    for app in apps:
        timestamp = app.timestamp.strftime('%Y-%m-%d %H:%M:%S') if app.timestamp else ""
        title = f"[{timestamp}] {app.name or ''}"

        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=8)
        title_cell = ws.cell(row=row, column=1, value=title)
        title_cell.fill = header_fill
        title_cell.font = header_font
        title_cell.alignment = Alignment(vertical="center")
        for c in range(1, 9):
            ws.cell(row=row, column=c).border = border
        ws.row_dimensions[row].height = 24

        # Photo box
        ws.merge_cells(start_row=row + 1, start_column=1, end_row=row + 9, end_column=2)
        photo_cell = ws.cell(row=row + 1, column=1, value="\uC0AC\uC9C4")
        photo_cell.alignment = Alignment(vertical="center", horizontal="center")
        for r in range(row + 1, row + 10):
            for c in range(1, 3):
                ws.cell(row=r, column=c).border = border

        # Basic info
        set_cell(row + 1, 3, "\uC774\uB984", bold=True)
        merge_and_set(row + 1, 4, row + 1, 8, app.name or "")
        set_cell(row + 2, 3, "\uC0DD\uB144\uC6D4\uC77C", bold=True)
        merge_and_set(row + 2, 4, row + 2, 8, app.birth.strftime('%Y-%m-%d') if app.birth else "")
        set_cell(row + 3, 3, "\uC5F0\uB77D\uCC98", bold=True)
        merge_and_set(row + 3, 4, row + 3, 8, app.phone or "")
        set_cell(row + 4, 3, "\uC774\uBA54\uC77C", bold=True)
        merge_and_set(row + 4, 4, row + 4, 8, app.email or "")
        set_cell(row + 5, 3, "\uC8FC\uC18C", bold=True)
        merge_and_set(row + 5, 4, row + 5, 8, app.address or "")

        # Body/size
        set_cell(row + 6, 3, "\uC2E0\uCCB4\uC815\uBCF4", bold=True)
        height_val = f"{app.height}cm" if app.height is not None else "-"
        weight_val = f"{app.weight}kg" if app.weight is not None else "-"
        merge_and_set(row + 6, 4, row + 6, 8, f"{height_val} / {weight_val}")

        set_cell(row + 7, 3, "\uC0C1\uC138\uC0AC\uC774\uC988", bold=True)
        vision = app.vision or "-"
        shoes = f"{app.shoes}" if app.shoes is not None else "-"
        tshirt = app.tshirt or "-"
        merge_and_set(row + 7, 4, row + 7, 8, f"\uC2DC\uB825:{vision} / \uC2E0\uBC1C:{shoes} / \uD2F0\uC154\uCE20:{tshirt}")

        # Work conditions
        set_cell(row + 8, 3, "\uADFC\uBB34\uC870\uAC74", bold=True)
        merge_and_set(
            row + 8, 4, row + 8, 8,
            f"\uD615\uD0DC:{app.shift or '-'} / \uBC29\uC2DD:{app.posture or '-'}"
        )
        set_cell(row + 9, 3, "\uAC00\uB2A5\uC5EC\uBD80", bold=True)
        merge_and_set(
            row + 9, 4, row + 9, 8,
            f"\uC794\uC5C5:{app.overtime or '-'} / \uD2B9\uADFC:{app.holiday or '-'}"
        )

        # Schedule / wish / status
        set_cell(row + 10, 3, "\uD76C\uB9DD\uC77C\uC815", bold=True)
        unknown = "\uBBF8\uC815"
        schedule = f"\uBA74\uC811:{app.interview_date.strftime('%Y-%m-%d') if app.interview_date else unknown} / \uC785\uC0AC:{app.start_date.strftime('%Y-%m-%d') if app.start_date else unknown}"
        merge_and_set(row + 10, 4, row + 10, 8, schedule)

        set_cell(row + 11, 3, "\uC0C1\uD0DC", bold=True)
        merge_and_set(row + 11, 4, row + 11, 8, app.status or "")

        # Career section
        set_cell(row + 12, 3, "\uACBD\uB825\uC0AC\uD56D", bold=True)
        careers = []
        for c in app.careers:
            period = f"{c.start.strftime('%Y-%m-%d') if c.start else ''}~{c.end.strftime('%Y-%m-%d') if c.end else ''}"
            careers.append(f"{c.company} | {period} | {c.role} | {c.reason}")
        merge_and_set(row + 12, 4, row + 14, 8, "\n".join(careers) if careers else "-")

        # Insert photo
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
                        ws.add_image(excel_img, f"A{row + 1}")
                except Exception:
                    pass

        for r in range(row + 1, row + 15):
            ws.row_dimensions[r].height = 20
        ws.row_dimensions[row + 1].height = 80
        ws.row_dimensions[row + 2].height = 20
        ws.row_dimensions[row + 12].height = 40

        row += 16

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
