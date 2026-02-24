"""전자계약서 서비스 — 토큰 생성, PDF 합성 (폰트 설정/이미지 필드/정렬 지원)."""

import base64
import json
import logging
import os
import secrets
from io import BytesIO

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTRACT_PDF_DIR = os.path.join(BASE_DIR, "uploads", "contracts")


def generate_sign_token():
    """고유 서명 URL 토큰 생성."""
    return secrets.token_urlsafe(32)


def _register_fonts():
    """한글 폰트(맑은 고딕) 일반/볼드 등록. 등록된 폰트 이름 딕셔너리를 반환한다.

    Returns:
        dict: {"normal": 폰트이름, "bold": 폰트이름} 형태.
              등록 실패 시 Helvetica 로 폴백.
    """
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    fonts = {"normal": "Helvetica", "bold": "Helvetica-Bold"}

    # 등록할 폰트 목록 [(파일경로, 등록이름, 역할)] — OS별 분기
    import platform
    if platform.system() == "Windows":
        font_candidates = [
            ("C:/Windows/Fonts/malgun.ttf", "malgun", "normal"),
            ("C:/Windows/Fonts/malgunbd.ttf", "malgunbd", "bold"),
        ]
    else:
        font_candidates = [
            ("/usr/share/fonts/truetype/nanum/NanumGothic.ttf", "NanumGothic", "normal"),
            ("/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf", "NanumGothicBold", "bold"),
        ]

    for font_path, fname, role in font_candidates:
        if os.path.exists(font_path):
            try:
                pdfmetrics.registerFont(TTFont(fname, font_path))
                if fonts[role] in ("Helvetica", "Helvetica-Bold"):
                    fonts[role] = fname
            except Exception:
                pass

    # 볼드 폰트가 없으면 일반 폰트로 대체
    if fonts["bold"] in ("Helvetica-Bold",) and fonts["normal"] != "Helvetica":
        fonts["bold"] = fonts["normal"]

    return fonts


def generate_final_pdf(contract, **kwargs):
    """모든 참여자의 필드값을 원본 PDF 위에 합성하여 최종 PDF를 생성한다.

    폰트 크기/볼드/이탤릭/정렬 등 필드별 서식 설정을 반영하며,
    참여자가 값을 입력하지 않은 필드에는 default_value를 사용한다.
    이미지 필드(file path 또는 base64)도 지원한다.

    Returns:
        str: 저장된 최종 PDF 파일 경로
    """
    import pypdf
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

    template = contract.template
    if not template or not os.path.exists(template.file_path):
        raise FileNotFoundError("서식 PDF를 찾을 수 없습니다.")

    # 폰트 등록
    fonts = _register_fonts()
    font_normal = fonts["normal"]
    font_bold = fonts["bold"]

    # 서식 필드 정의
    fields = template.fields

    # 모든 참여자의 필드값 수집 {field_idx: value}
    all_values = {}
    for participant in contract.participants:
        for fv in participant.field_values:
            idx = fv.get("field_idx")
            if idx is not None and fv.get("value"):
                all_values[idx] = fv.get("value", "")

    # 참여자가 값을 입력하지 않은 필드에 default_value 적용
    for i, field in enumerate(fields):
        if i not in all_values and field.get("default_value"):
            all_values[i] = field["default_value"]

    # 원본 PDF 열기
    with open(template.file_path, "rb") as f:
        reader = pypdf.PdfReader(f)
        writer = pypdf.PdfWriter()

        for page_num in range(len(reader.pages)):
            page = reader.pages[page_num]
            page_width = float(page.mediabox.width)
            page_height = float(page.mediabox.height)

            # 이 페이지에 해당하는 필드 필터
            page_fields = [
                (i, field) for i, field in enumerate(fields)
                if field.get("page", 1) == page_num + 1 and i in all_values
            ]

            if page_fields:
                # 오버레이 PDF 생성
                overlay_buf = BytesIO()
                c = canvas.Canvas(overlay_buf, pagesize=(page_width, page_height))

                for field_idx, field in page_fields:
                    value = all_values[field_idx]
                    if not value:
                        continue

                    ftype = field.get("type", "text")

                    # 좌표: % 비율 -> 실제 PDF 좌표로 변환
                    x = field.get("x_pct", 0) / 100 * page_width
                    y_from_top = field.get("y_pct", 0) / 100 * page_height
                    w = field.get("w_pct", 10) / 100 * page_width
                    h = field.get("h_pct", 3) / 100 * page_height
                    # PDF 좌표는 하단 기준
                    y = page_height - y_from_top - h

                    if ftype in ("text", "date"):
                        _draw_text_field(
                            c, field, value, x, y, w, h, font_normal, font_bold
                        )

                    elif ftype in ("signature", "stamp"):
                        # base64 이미지 -> PDF 위에 삽입
                        _draw_image(c, value, x, y, w, h, field_idx)

                    elif ftype == "image":
                        # 이미지 필드 (파일 경로 또는 base64)
                        _draw_image(c, value, x, y, w, h, field_idx)

                    elif ftype == "checkbox":
                        if value:
                            font_size = max(8, h * 0.7)
                            c.setFont(font_normal, font_size)
                            c.drawString(x + 2, y + h * 0.2, "V")

                c.save()
                overlay_buf.seek(0)

                # 합성
                overlay_reader = pypdf.PdfReader(overlay_buf)
                page.merge_page(overlay_reader.pages[0])

            writer.add_page(page)

    # 저장
    os.makedirs(CONTRACT_PDF_DIR, exist_ok=True)
    suffix = kwargs.get("suffix", "final")
    output_path = os.path.join(CONTRACT_PDF_DIR, f"contract_{contract.id}_{suffix}.pdf")
    with open(output_path, "wb") as out:
        writer.write(out)

    logger.info("PDF 생성: contract_id=%d, suffix=%s, path=%s", contract.id, suffix, output_path)
    return output_path


def _draw_text_field(c, field, value, x, y, w, h, font_normal, font_bold):
    """텍스트 필드를 캔버스에 그린다.

    필드 정의의 font_size, font_bold, font_italic, text_align 설정을 반영한다.

    Args:
        c: reportlab Canvas 객체
        field: 필드 정의 딕셔너리
        value: 렌더링할 텍스트 값
        x: PDF 좌표 x
        y: PDF 좌표 y (하단 기준)
        w: 필드 너비
        h: 필드 높이
        font_normal: 일반 폰트 이름
        font_bold: 볼드 폰트 이름
    """
    # 폰트 크기 결정 (필드 정의에 font_size가 있으면 사용, 없으면 높이 기반 자동 계산)
    font_size = field.get("font_size")
    if font_size:
        font_size = float(font_size)
    else:
        font_size = max(8, min(h * 0.6, 14))

    # 볼드/이탤릭 처리
    is_bold = field.get("font_bold", False)
    is_italic = field.get("font_italic", False)

    if is_bold:
        chosen_font = font_bold
    else:
        chosen_font = font_normal

    c.setFont(chosen_font, font_size)

    # 텍스트 y 위치 (수직 중앙 정렬)
    text_y = y + (h - font_size) / 2

    # 정렬 처리
    text_align = field.get("text_align", "left")
    text_value = str(value)

    if text_align == "center":
        c.drawCentredString(x + w / 2, text_y, text_value)
    elif text_align == "right":
        c.drawRightString(x + w, text_y, text_value)
    else:
        # 왼쪽 정렬 (기본값)
        c.drawString(x + 2, text_y, text_value)


def _draw_image(c, value, x, y, w, h, field_idx):
    """이미지를 캔버스에 그린다. base64 또는 파일 경로를 지원한다.

    Args:
        c: reportlab Canvas 객체
        value: 이미지 값 (base64 data URI 또는 파일 경로)
        x: PDF 좌표 x
        y: PDF 좌표 y (하단 기준)
        w: 필드 너비
        h: 필드 높이
        field_idx: 필드 인덱스 (오류 로깅용)
    """
    from reportlab.lib.utils import ImageReader

    try:
        if value.startswith("data:image"):
            # base64 이미지
            img_data = value.split(",", 1)[1]
            img_bytes = base64.b64decode(img_data)
            img_reader = ImageReader(BytesIO(img_bytes))
            c.drawImage(img_reader, x, y, width=w, height=h, mask="auto")
        elif os.path.exists(value):
            # 파일 경로
            c.drawImage(value, x, y, width=w, height=h, mask="auto")
        else:
            # uploads/ 하위 경로일 수 있으므로 BASE_DIR 기준으로도 시도
            abs_path = os.path.join(BASE_DIR, value.lstrip("/"))
            if os.path.exists(abs_path):
                c.drawImage(abs_path, x, y, width=w, height=h, mask="auto")
            else:
                logger.warning("이미지 파일을 찾을 수 없음 (field %d): %s", field_idx, value)
    except Exception as e:
        logger.warning("이미지 삽입 실패 (field %d): %s", field_idx, e)
