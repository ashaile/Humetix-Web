import os
from flask import Blueprint, render_template, request, redirect, url_for, session, send_file, send_from_directory
from datetime import datetime
import openpyxl
from openpyxl import Workbook
from openpyxl.drawing.image import Image as ExcelImage
from openpyxl.styles import Font, Alignment, Border, Side
from models import db, Application

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
    
    query = Application.query
    
    if search_query:
        if search_type == 'name':
            query = query.filter(Application.name.contains(search_query))
        elif search_type == 'phone':
            query = query.filter(Application.phone.contains(search_query))
            
    apps = query.order_by(Application.timestamp.desc()).all()
    data = [app.to_dict() for app in apps]
    
    return render_template('admin.html', data=data, search_query=search_query, search_type=search_type)

@admin_bp.route('/update_memo/<app_id>', methods=['POST'])
def update_memo(app_id):
    if not session.get('is_admin'):
        return {"success": False, "message": "Unauthorized"}, 401
        
    app = Application.query.get(app_id)
    if not app:
        return {"success": False, "message": "Application not found"}, 404
        
    memo = request.form.get('memo', '')
    app.memo = memo
    db.session.commit()
    
    return {"success": True, "message": "Memo updated"}

@admin_bp.route('/delete_selected', methods=['POST'])
def delete_selected():
    if not session.get('is_admin'):
        return redirect(url_for('auth.login'))
        
    selected_ids = request.form.getlist('selected_ids')
    if not selected_ids:
        return "<script>alert('삭제할 항목을 선택해주세요.'); history.back();</script>"
    
    # 선택된 지원서 삭제
    for app_id in selected_ids:
        app = Application.query.get(app_id)
        if app:
            # 사진 파일 삭제
            if app.photo:
                try:
                    os.remove(os.path.join(UPLOAD_DIR, app.photo))
                except Exception as e:
                    logger.error(f"Error deleting photo {app.photo}: {e}")
            db.session.delete(app)
    
    db.session.commit()
    return redirect(url_for('admin.master_view'))

@admin_bp.route('/download_excel')
def download_excel():
    logger.info("Excel download requested")
    if not session.get('is_admin'):
        logger.warning("Unauthorized excel download attempt")
        return redirect(url_for('auth.login'))
    
    try:
        apps = Application.query.all()
        logger.info(f"Found {len(apps)} applications for excel")
        data = [app.to_dict() for app in apps]
        
        wb = Workbook()
        ws = wb.active
        ws.title = "지원자 목록"
        
        # 스타일 정의
        bold_font = Font(bold=True)
        center_align = Alignment(horizontal='center', vertical='center', wrap_text=True)
        border_style = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))
        
        row_idx = 1
        
        for entry in data:
            # 1. 지원자별 헤더
            ws.merge_cells(start_row=row_idx, start_column=1, end_row=row_idx, end_column=4)
            cell = ws.cell(row=row_idx, column=1, value=f"[{entry['timestamp']}] {entry['info']['name']}")
            cell.font = Font(bold=True, size=12, color="FFFFFF")
            cell.fill = openpyxl.styles.PatternFill(start_color="003057", end_color="003057", fill_type="solid")
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
                ("희망일정", f"면접:{entry['work_condition']['interview_date']} / 입사:{entry['work_condition']['start_date']}")
            ]
            
            current_data_row = row_idx
            for key, value in fields:
                ws.cell(row=current_data_row, column=3, value=key).font = bold_font
                ws.cell(row=current_data_row, column=3).border = border_style
                ws.cell(row=current_data_row, column=3).alignment = center_align
                ws.cell(row=current_data_row, column=4, value=value).border = border_style
                ws.cell(row=current_data_row, column=4).alignment = Alignment(wrap_text=True, vertical='center')
                current_data_row += 1
                
            # 4. 경력사항
            ws.cell(row=current_data_row, column=3, value="경력사항").font = bold_font
            ws.cell(row=current_data_row, column=3).border = border_style
            ws.cell(row=current_data_row, column=3).alignment = center_align
            
            career_text = ""
            if not entry['career']:
                career_text = "경력 없음"
            else:
                for c in entry['career']:
                    career_text += f"[{c['company']}] {c['start']}~{c['end']} / {c['role']} / {c['reason']}\n"
            
            ws.cell(row=current_data_row, column=4, value=career_text.strip()).border = border_style
            ws.cell(row=current_data_row, column=4).alignment = Alignment(wrap_text=True, vertical='center')
            current_data_row += 1
            
            # 5. 사진 삽입
            # Check for invalid merge range
            if photo_start_row > current_data_row - 1:
                logger.warning(f"Invalid merge range for {entry['info']['name']}: {photo_start_row} to {current_data_row-1}")
                # Adjust to avoid error allow single row?
                # Just skip merge if invalid
            else:
                ws.merge_cells(start_row=photo_start_row, start_column=1, end_row=current_data_row-1, end_column=2)
            
            img_cell = ws.cell(row=photo_start_row, column=1)
            img_cell.border = border_style
            
            if entry['photo']:
                try:
                    img_path = os.path.join(UPLOAD_DIR, entry['photo'])
                    if os.path.exists(img_path):
                        img = ExcelImage(img_path)
                        img.width = 150
                        img.height = 200
                        ws.add_image(img, f"A{photo_start_row}")
                    else:
                        img_cell.value = "이미지 파일 없음"
                        img_cell.alignment = center_align
                except Exception as e:
                    img_cell.value = f"이미지 오류: {str(e)}"
                    logger.error(f"Image error for {entry['photo']}: {e}")
            else:
                img_cell.value = "사진 없음"
                img_cell.alignment = center_align
                
            row_idx = current_data_row + 2

        # 컬럼 너비 조정
        ws.column_dimensions['A'].width = 10
        ws.column_dimensions['B'].width = 10
        ws.column_dimensions['C'].width = 15
        ws.column_dimensions['D'].width = 50

        # 메모리에 엑셀 파일 저장
        from io import BytesIO
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
        import traceback
        logger.error(traceback.format_exc())
        return f"Excel download failed: {str(e)}", 500
@admin_bp.route('/view_photo/<filename>')
def view_photo(filename):
    return send_from_directory(UPLOAD_DIR, filename)

@admin_bp.route('/clear_data', methods=['POST'])
def clear_data():
    if not session.get('is_admin'):
        return redirect(url_for('auth.login'))
    
    # 모든 지원서 삭제
    Application.query.delete()
    db.session.commit()
    
    # 업로드된 사진들도 삭제
    for f in os.listdir(UPLOAD_DIR):
        try:
            os.remove(os.path.join(UPLOAD_DIR, f))
        except Exception as e:
            logger.error(f"Error deleting file {f}: {e}")
        
    return redirect(url_for('admin.master_view'))
