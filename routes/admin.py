import os
import logging
import traceback
from io import BytesIO
from flask import Blueprint, render_template, request, redirect, url_for, session, send_file, send_from_directory, flash, jsonify
from datetime import datetime
from sqlalchemy.orm import joinedload
from PIL import Image as PILImage
import openpyxl
from openpyxl import Workbook
from openpyxl.drawing.image import Image as ExcelImage
from openpyxl.styles import Font, Alignment, Border, Side
from models import db, Application

from routes.auth import admin_required

# Logger 설정
logger = logging.getLogger(__name__)

admin_bp = Blueprint('admin', __name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOAD_DIR = os.path.join(BASE_DIR, 'uploads')

# 페이지네이션 상수
PER_PAGE = 10

# 엑셀 스타일 상수
EXCEL_HEADER_FONT = Font(bold=True, size=12, color="FFFFFF")
EXCEL_HEADER_FILL = openpyxl.styles.PatternFill(start_color="003057", end_color="003057", fill_type="solid")
EXCEL_BOLD_FONT = Font(bold=True)
EXCEL_CENTER_ALIGN = Alignment(horizontal='center', vertical='center', wrap_text=True)
EXCEL_WRAP_ALIGN = Alignment(wrap_text=True, vertical='center')
EXCEL_BORDER = Border(
    left=Side(style='thin'), right=Side(style='thin'),
    top=Side(style='thin'), bottom=Side(style='thin')
)
EXCEL_COL_WIDTHS = {'A': 10, 'B': 10, 'C': 15, 'D': 50}


def _build_filter_query(query, search_type, search_query, filters, start_date, end_date):
    """검색 및 필터 조건을 쿼리에 적용"""
    # 1. 기본 검색 (이름/연락처)
    if search_query:
        if search_type == 'name':
            query = query.filter(Application.name.contains(search_query))
        elif search_type == 'phone':
            query = query.filter(Application.phone.contains(search_query))

    # 2. 상세 필터 적용
    filter_fields = {
        'gender': Application.gender,
        'shift': Application.shift,
        'posture': Application.posture,
        'overtime': Application.overtime,
        'holiday': Application.holiday,
        'advance_pay': Application.advance_pay,
        'insurance_type': Application.insurance_type,
    }

    for key, column in filter_fields.items():
        if filters.get(key):
            query = query.filter(column == filters[key])

    if filters.get('agree'):
        is_agree = filters['agree'] == 'on'
        query = query.filter(Application.agree == is_agree)

    # 3. 날짜 범위 검색 (접수일 기준)
    if start_date:
        s_date = datetime.strptime(start_date, '%Y-%m-%d')
        query = query.filter(Application.timestamp >= s_date)

    if end_date:
        e_date = datetime.strptime(end_date, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
        query = query.filter(Application.timestamp <= e_date)

    return query


def _generate_excel_for_entry(ws, entry, row_idx):
    """단일 지원자의 엑셀 행을 생성"""
    # 1. 지원자별 헤더
    ws.merge_cells(start_row=row_idx, start_column=1, end_row=row_idx, end_column=4)
    cell = ws.cell(row=row_idx, column=1, value=f"[{entry['timestamp']}] {entry['info']['name']}")
    cell.font = EXCEL_HEADER_FONT
    cell.fill = EXCEL_HEADER_FILL
    cell.alignment = Alignment(vertical='center')
    row_idx += 1

    # 2. 사진 공간 확보
    photo_start_row = row_idx

    # 3. 데이터 입력
    fields = [
        ("이름", entry['info']['name']),
        ("생년월일", entry['info']['birth']),
        ("연락처", entry['info']['phone']),
        ("이메일", entry['info']['email']),
        ("주소", entry['info']['address']),
        ("신체정보", f"{entry['body']['height']}cm / {entry['body']['weight']}kg"),
        ("상세사이즈", f"시력:{entry['body']['vision']} / 신발:{entry['body']['shoes']} / 티셔츠:{entry['body']['tshirt']}"),
        ("근무조건", f"{entry['work_condition']['shift']} / {entry['work_condition']['posture']}"),
        ("가능여부", f"잔업:{entry['work_condition']['overtime']} / 특근:{entry['work_condition']['holiday']}"),
        ("희망일정", f"면접:{entry['work_condition']['interview_date']} / 입사:{entry['work_condition']['start_date']}"),
        ("상태", entry.get('status_display', '접수')),
    ]

    current_data_row = row_idx
    for key, value in fields:
        ws.cell(row=current_data_row, column=3, value=key).font = EXCEL_BOLD_FONT
        ws.cell(row=current_data_row, column=3).border = EXCEL_BORDER
        ws.cell(row=current_data_row, column=3).alignment = EXCEL_CENTER_ALIGN
        ws.cell(row=current_data_row, column=4, value=value).border = EXCEL_BORDER
        ws.cell(row=current_data_row, column=4).alignment = EXCEL_WRAP_ALIGN
        current_data_row += 1

    # 4. 경력사항
    ws.cell(row=current_data_row, column=3, value="경력사항").font = EXCEL_BOLD_FONT
    ws.cell(row=current_data_row, column=3).border = EXCEL_BORDER
    ws.cell(row=current_data_row, column=3).alignment = EXCEL_CENTER_ALIGN

    career_text = "경력 없음"
    if entry['career']:
        career_text = "\n".join(
            f"[{c['company']}] {c['start']}~{c['end']} / {c['role']} / {c['reason']}"
            for c in entry['career']
        )

    ws.cell(row=current_data_row, column=4, value=career_text).border = EXCEL_BORDER
    ws.cell(row=current_data_row, column=4).alignment = EXCEL_WRAP_ALIGN
    current_data_row += 1

    # 5. 사진 삽입
    if photo_start_row <= current_data_row - 1:
        ws.merge_cells(start_row=photo_start_row, start_column=1, end_row=current_data_row-1, end_column=2)

    img_cell = ws.cell(row=photo_start_row, column=1)
    img_cell.border = EXCEL_BORDER

    if entry['photo']:
        try:
            img_path = os.path.join(UPLOAD_DIR, entry['photo'])
            if os.path.exists(img_path):
                with PILImage.open(img_path) as pil_img:
                    pil_img.thumbnail((300, 400))
                    if pil_img.mode in ("RGBA", "P"):
                        pil_img = pil_img.convert("RGBA")
                    else:
                        pil_img = pil_img.convert("RGB")

                    img_io = BytesIO()
                    pil_img.save(img_io, format="PNG", optimize=True)
                    img_io.seek(0)

                    img = ExcelImage(img_io)
                    img.width = 150
                    img.height = 200
                    ws.add_image(img, f"A{photo_start_row}")
            else:
                img_cell.value = "이미지 파일 없음"
                img_cell.alignment = EXCEL_CENTER_ALIGN
        except Exception as e:
            img_cell.value = f"이미지 오류: {str(e)}"
            logger.error(f"Image error for {entry['photo']}: {e}")
    else:
        img_cell.value = "사진 없음"
        img_cell.alignment = EXCEL_CENTER_ALIGN

    return current_data_row + 2


@admin_bp.route('/humetix_master_99')
@admin_required
def master_view():
    search_type = request.args.get('type', 'name')
    search_query = request.args.get('q', '')

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

    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    query = Application.query.options(joinedload(Application.careers))
    query = _build_filter_query(query, search_type, search_query, filters, start_date, end_date)

    # 상태 필터
    if filters.get('status'):
        query = query.filter(Application.status == filters['status'])

    page = request.args.get('page', 1, type=int)
    pagination = query.order_by(Application.timestamp.desc()).paginate(
        page=page, per_page=PER_PAGE, error_out=False
    )

    data = [app.to_dict() for app in pagination.items]

    # 통계 데이터
    total_count = Application.query.count()
    from sqlalchemy import func
    status_counts = dict(
        db.session.query(Application.status, func.count(Application.id))
        .group_by(Application.status).all()
    )

    return render_template('admin.html',
        data=data, pagination=pagination,
        search_query=search_query, search_type=search_type,
        filters=filters, start_date=start_date, end_date=end_date,
        total_count=total_count, status_counts=status_counts
    )


@admin_bp.route('/update_memo/<app_id>', methods=['POST'])
@admin_required
def update_memo(app_id):
    app = Application.query.get(app_id)
    if not app:
        return jsonify({"success": False, "message": "Application not found"}), 404

    memo = request.form.get('memo', '')
    app.memo = memo
    db.session.commit()
    logger.info(f"Memo updated for application {app_id}")

    return jsonify({"success": True, "message": "Memo updated"})


@admin_bp.route('/update_status/<app_id>', methods=['POST'])
@admin_required
def update_status(app_id):
    """지원자 상태 변경"""
    app = Application.query.get(app_id)
    if not app:
        return jsonify({"success": False, "message": "Application not found"}), 404

    new_status = request.form.get('status', '')
    valid_statuses = ['접수', '서류심사', '면접예정', '합격', '불합격', '보류']
    if new_status not in valid_statuses:
        return jsonify({"success": False, "message": "Invalid status"}), 400

    old_status = app.status
    app.status = new_status
    db.session.commit()

    logger.info(f"Status changed for {app_id}: {old_status} -> {new_status}")
    return jsonify({"success": True, "message": f"상태가 '{new_status}'(으)로 변경되었습니다."})


@admin_bp.route('/delete_selected', methods=['POST'])
@admin_required
def delete_selected():
    selected_ids = request.form.getlist('selected_ids')
    if not selected_ids:
        flash('삭제할 항목을 선택해주세요.', 'warning')
        return redirect(url_for('admin.master_view'))

    # DB 먼저 삭제한 후 파일 삭제 (트랜잭션 정합성)
    photos_to_delete = []
    for app_id in selected_ids:
        app = Application.query.get(app_id)
        if app:
            if app.photo:
                photos_to_delete.append(app.photo)
            db.session.delete(app)

    try:
        db.session.commit()
        # DB 커밋 성공 후 파일 삭제
        for photo in photos_to_delete:
            try:
                photo_path = os.path.join(UPLOAD_DIR, photo)
                if os.path.exists(photo_path):
                    os.remove(photo_path)
            except Exception as e:
                logger.error(f"Error deleting photo {photo}: {e}")

        logger.info(f"Deleted {len(selected_ids)} applications: {selected_ids}")
        flash(f'{len(selected_ids)}건의 지원서가 삭제되었습니다.', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f"Delete failed: {e}")
        flash('삭제 중 오류가 발생했습니다.', 'danger')

    return redirect(url_for('admin.master_view'))


@admin_bp.route('/download_excel')
@admin_required
def download_excel():
    logger.info("Excel download requested")

    try:
        # 현재 필터 조건 가져오기
        search_type = request.args.get('type', 'name')
        search_query = request.args.get('q', '')
        filters = {
            'gender': request.args.get('gender'),
            'shift': request.args.get('shift'),
            'posture': request.args.get('posture'),
            'overtime': request.args.get('overtime'),
            'holiday': request.args.get('holiday'),
            'agree': request.args.get('agree'),
            'advance_pay': request.args.get('advance_pay'),
            'insurance_type': request.args.get('insurance_type'),
        }
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')

        # 필터를 적용한 쿼리 (N+1 방지)
        query = Application.query.options(joinedload(Application.careers))
        query = _build_filter_query(query, search_type, search_query, filters, start_date, end_date)
        apps = query.order_by(Application.timestamp.desc()).all()

        logger.info(f"Found {len(apps)} applications for excel")
        data = [app.to_dict() for app in apps]

        wb = Workbook()
        ws = wb.active
        ws.title = "지원자 목록"

        row_idx = 1
        for entry in data:
            row_idx = _generate_excel_for_entry(ws, entry, row_idx)

        # 컬럼 너비 조정
        for col, width in EXCEL_COL_WIDTHS.items():
            ws.column_dimensions[col].width = width

        output = BytesIO()
        wb.save(output)
        output.seek(0)

        logger.info("Excel file generated successfully")
        return send_file(
            output,
            as_attachment=True,
            download_name="applicants_export.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    except Exception as e:
        logger.error(f"Excel generation failed: {str(e)}")
        logger.error(traceback.format_exc())
        flash('엑셀 다운로드 중 오류가 발생했습니다.', 'danger')
        return redirect(url_for('admin.master_view'))


@admin_bp.route('/view_photo/<filename>')
@admin_required
def view_photo(filename):
    """사진 열람 (인증 필수)"""
    return send_from_directory(UPLOAD_DIR, filename)


@admin_bp.route('/clear_data', methods=['POST'])
@admin_required
def clear_data():
    confirm = request.form.get('confirm_text', '')
    if confirm != '전체삭제확인':
        flash('확인 텍스트가 일치하지 않습니다. "전체삭제확인"을 정확히 입력해주세요.', 'warning')
        return redirect(url_for('admin.master_view'))

    total_count = Application.query.count()
    logger.warning(f"CLEAR DATA requested - deleting {total_count} applications")

    # DB 먼저 삭제
    try:
        Application.query.delete()
        db.session.commit()

        # DB 성공 후 파일 삭제
        deleted_files = 0
        for f in os.listdir(UPLOAD_DIR):
            try:
                os.remove(os.path.join(UPLOAD_DIR, f))
                deleted_files += 1
            except Exception as e:
                logger.error(f"Error deleting file {f}: {e}")

        logger.warning(f"CLEAR DATA completed: {total_count} applications, {deleted_files} files deleted")
        flash(f'전체 데이터가 삭제되었습니다. ({total_count}건)', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f"Clear data failed: {e}")
        flash('데이터 삭제 중 오류가 발생했습니다.', 'danger')

    return redirect(url_for('admin.master_view'))


@admin_bp.route('/detail/<app_id>')
@admin_required
def detail_view(app_id):
    """지원서 상세 보기"""
    app = Application.query.options(joinedload(Application.careers)).get(app_id)
    if not app:
        flash('지원서를 찾을 수 없습니다.', 'warning')
        return redirect(url_for('admin.master_view'))
    return render_template('detail.html', entry=app.to_dict(), app_id=app_id)


@admin_bp.route('/edit/<app_id>', methods=['GET', 'POST'])
@admin_required
def edit_view(app_id):
    """지원서 수정"""
    app = Application.query.options(joinedload(Application.careers)).get(app_id)
    if not app:
        flash('지원서를 찾을 수 없습니다.', 'warning')
        return redirect(url_for('admin.master_view'))

    if request.method == 'POST':
        try:
            app.name = request.form.get('name', app.name)
            app.phone = request.form.get('phone', app.phone)
            app.email = request.form.get('email', app.email)
            app.address = request.form.get('address', app.address)
            app.gender = request.form.get('gender', app.gender)

            birth_str = request.form.get('birth')
            if birth_str:
                app.birth = datetime.strptime(birth_str, '%Y-%m-%d').date()

            height_str = request.form.get('height')
            if height_str:
                app.height = int(height_str)
            weight_str = request.form.get('weight')
            if weight_str:
                app.weight = int(weight_str)

            app.vision = request.form.get('vision', app.vision)
            shoes_str = request.form.get('shoes')
            if shoes_str:
                app.shoes = int(shoes_str)
            app.tshirt = request.form.get('tshirt', app.tshirt)

            app.shift = request.form.get('shift', app.shift)
            app.posture = request.form.get('posture', app.posture)
            app.overtime = request.form.get('overtime', app.overtime)
            app.holiday = request.form.get('holiday', app.holiday)

            interview_str = request.form.get('interview_date')
            if interview_str:
                app.interview_date = datetime.strptime(interview_str, '%Y-%m-%d').date()
            start_str = request.form.get('start_date')
            if start_str:
                app.start_date = datetime.strptime(start_str, '%Y-%m-%d').date()

            app.advance_pay = request.form.get('advance_pay', app.advance_pay)
            app.insurance_type = request.form.get('insurance_type', app.insurance_type)
            app.memo = request.form.get('memo', app.memo)

            db.session.commit()
            logger.info(f"Application {app_id} updated")
            flash('지원서가 수정되었습니다.', 'success')
            return redirect(url_for('admin.detail_view', app_id=app_id))
        except (ValueError, Exception) as e:
            db.session.rollback()
            logger.error(f"Edit failed for {app_id}: {e}")
            flash('수정 중 오류가 발생했습니다.', 'danger')

    return render_template('edit.html', entry=app.to_dict(), app_id=app_id)


@admin_bp.route('/stats')
@admin_required
def stats_api():
    """대시보드 통계 API"""
    from sqlalchemy import func

    total = Application.query.count()

    # 상태별 통계
    status_stats = dict(
        db.session.query(Application.status, func.count(Application.id))
        .group_by(Application.status).all()
    )

    # 성별 통계
    gender_stats = dict(
        db.session.query(Application.gender, func.count(Application.id))
        .filter(Application.gender.isnot(None))
        .group_by(Application.gender).all()
    )

    # 최근 7일간 일별 접수 통계
    from datetime import timedelta
    seven_days_ago = datetime.now() - timedelta(days=7)
    daily_stats = (
        db.session.query(
            func.date(Application.timestamp),
            func.count(Application.id)
        )
        .filter(Application.timestamp >= seven_days_ago)
        .group_by(func.date(Application.timestamp))
        .order_by(func.date(Application.timestamp))
        .all()
    )
    daily_data = {str(date): count for date, count in daily_stats}

    return jsonify({
        "total": total,
        "status": status_stats,
        "gender": gender_stats,
        "daily": daily_data,
    })
