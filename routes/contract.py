"""전자계약서 관리 블루프린트 — Glosign 스타일."""

import json
import logging
import os
import secrets
from datetime import datetime
from io import BytesIO

from flask import (
    Blueprint,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from sqlalchemy import func, or_
from sqlalchemy.orm import joinedload
from werkzeug.utils import secure_filename

from models import (
    Contract,
    ContractAuditLog,
    ContractParticipant,
    ContractTemplate,
    Employee,
    db,
)
from routes.utils import BASE_DIR, require_admin
from services.contract_service import generate_final_pdf, generate_sign_token
from services.sms_service import send_contract_link

logger = logging.getLogger(__name__)

contract_bp = Blueprint("contract", __name__)

TEMPLATE_UPLOAD_DIR = os.path.join(BASE_DIR, "uploads", "templates")
CONTRACT_PDF_DIR = os.path.join(BASE_DIR, "uploads", "contracts")
FIELD_IMAGE_DIR = os.path.join(BASE_DIR, "uploads", "field_images")
ALLOWED_EXTENSIONS = {"pdf"}
ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "gif"}
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB


def _ensure_dirs():
    """업로드 디렉터리 생성."""
    os.makedirs(TEMPLATE_UPLOAD_DIR, exist_ok=True)
    os.makedirs(CONTRACT_PDF_DIR, exist_ok=True)
    os.makedirs(FIELD_IMAGE_DIR, exist_ok=True)


def _audit_log(contract_id, action, actor="관리자", detail="", ip=None):
    """감사 로그 헬퍼 — 세션에 추가만 하고 커밋은 호출측에서 담당."""
    log = ContractAuditLog(
        contract_id=contract_id,
        action=action,
        actor=actor,
        detail=detail,
        ip_address=ip,
    )
    db.session.add(log)


def _send_sign_sms(contract, participant):
    """pending 상태 참여자에게 서명 링크 SMS 발송 (연락처가 있는 경우)."""
    if participant.status != "pending" or not participant.phone:
        return
    try:
        sign_url = url_for(
            "contract.sign_page", token=participant.sign_token, _external=True
        )
        result = send_contract_link(
            to=participant.phone,
            worker_name=participant.name,
            contract_title=contract.title,
            sign_url=sign_url,
        )
        if result.get("success"):
            logger.info(f"[SMS] 서명링크 발송 성공: {participant.name} ({participant.phone})")
        else:
            logger.warning(f"[SMS] 서명링크 발송 실패: {participant.name} — {result.get('detail')}")
    except Exception as e:
        logger.error(f"[SMS] 발송 중 오류: {e}")


# ── 서식 관리 ──


@contract_bp.route("/admin/contract-templates")
@require_admin
def admin_templates():
    """서식 목록 페이지."""
    templates = ContractTemplate.query.filter_by(status="active").order_by(
        ContractTemplate.created_at.desc()
    ).all()
    return render_template("admin_templates.html", templates=templates)


@contract_bp.route("/api/contract-templates", methods=["POST"])
@require_admin
def create_template():
    """PDF 업로드 -> 서식 생성."""
    _ensure_dirs()

    if "file" not in request.files:
        return jsonify({"error": "파일을 선택해주세요."}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "파일을 선택해주세요."}), 400

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        return jsonify({"error": "PDF 파일만 업로드 가능합니다."}), 400

    name = request.form.get("name", "").strip()
    if not name:
        name = file.filename.rsplit(".", 1)[0]

    # 파일 저장
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = secure_filename(file.filename) or f"template_{timestamp}.pdf"
    filename = f"{timestamp}_{safe_name}"
    filepath = os.path.join(TEMPLATE_UPLOAD_DIR, filename)
    file.save(filepath)

    # 페이지 수 확인
    page_count = 1
    try:
        import pypdf
        with open(filepath, "rb") as f:
            reader = pypdf.PdfReader(f)
            page_count = len(reader.pages)
    except Exception:
        pass

    template = ContractTemplate(
        name=name,
        file_path=filepath,
        file_original_name=file.filename,
        page_count=page_count,
    )
    db.session.add(template)
    db.session.commit()

    return jsonify({
        "success": True,
        "template": template.to_dict(),
        "redirect": f"/admin/contract-templates/{template.id}/edit",
    }), 201


@contract_bp.route("/admin/contract-templates/<int:tid>/edit")
@require_admin
def edit_template(tid):
    """서식 에디터 페이지."""
    template = db.session.get(ContractTemplate, tid)
    if not template:
        return redirect(url_for("contract.admin_templates"))
    return render_template("admin_template_editor.html", template=template)


@contract_bp.route("/api/contract-templates/<int:tid>", methods=["PUT"])
@require_admin
def save_template(tid):
    """서식 필드 배치 저장."""
    template = db.session.get(ContractTemplate, tid)
    if not template:
        return jsonify({"error": "서식을 찾을 수 없습니다."}), 404

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "JSON body required"}), 400

    if "name" in data:
        template.name = str(data["name"]).strip()
    if "fields" in data:
        template.fields = data["fields"]
    if "roles" in data:
        template.roles = data["roles"]

    db.session.commit()
    return jsonify({"success": True, "template": template.to_dict()})


@contract_bp.route("/api/contract-templates/<int:tid>", methods=["DELETE"])
@require_admin
def delete_template(tid):
    """서식 삭제 (논리 삭제)."""
    template = db.session.get(ContractTemplate, tid)
    if not template:
        return jsonify({"error": "서식을 찾을 수 없습니다."}), 404
    template.status = "archived"
    db.session.commit()
    return jsonify({"success": True})


@contract_bp.route("/api/contract-templates/<int:tid>/replace", methods=["POST"])
@require_admin
def replace_template_file(tid):
    """서식 문서 교체 — PDF만 교체하고 기존 필드 좌표는 그대로 보존."""
    _ensure_dirs()
    template = db.session.get(ContractTemplate, tid)
    if not template:
        return jsonify({"error": "서식을 찾을 수 없습니다."}), 404

    if "file" not in request.files:
        return jsonify({"error": "파일을 선택해주세요."}), 400

    file = request.files["file"]
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        return jsonify({"error": "PDF 파일만 업로드 가능합니다."}), 400

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = secure_filename(file.filename) or f"template_{timestamp}.pdf"

    # 새 PDF 저장
    new_filename = f"{timestamp}_{safe_name}"
    new_filepath = os.path.join(TEMPLATE_UPLOAD_DIR, new_filename)
    file.save(new_filepath)

    try:
        import pypdf

        # 새 PDF 페이지 수 확인
        with open(new_filepath, "rb") as f:
            reader = pypdf.PdfReader(f)
            new_page_count = len(reader.pages)

        # 기존 필드 중 새 PDF 페이지 범위를 벗어나는 필드는 삭제 경고용으로 카운트
        existing_fields = template.fields
        kept_fields = [fld for fld in existing_fields if fld.get("page", 1) <= new_page_count]
        removed_count = len(existing_fields) - len(kept_fields)

        # 기존 PDF 백업 삭제 (선택) — 기존 파일 경로 저장
        old_file_path = template.file_path

        # 서식 업데이트: 새 PDF로 교체, 필드 보존
        template.file_path = new_filepath
        template.file_original_name = file.filename
        template.page_count = new_page_count
        template.fields = kept_fields
        db.session.commit()

        # 기존 PDF 파일 삭제 (새 파일과 다른 경우)
        if old_file_path and old_file_path != new_filepath and os.path.exists(old_file_path):
            try:
                os.remove(old_file_path)
            except OSError:
                pass

        msg = f"문서가 교체되었습니다. ({new_page_count}페이지)"
        if removed_count > 0:
            msg += f" 페이지 범위를 벗어난 필드 {removed_count}개가 제거되었습니다."

        return jsonify({
            "success": True,
            "message": msg,
            "template": template.to_dict(),
            "removed_fields": removed_count,
        })
    except Exception as e:
        # 실패 시 새 파일 정리
        try:
            os.remove(new_filepath)
        except OSError:
            pass
        logger.error("문서 교체 실패: %s", e)
        return jsonify({"error": f"문서 교체 실패: {str(e)}"}), 500


@contract_bp.route("/api/contract-templates/<int:tid>/pdf")
@require_admin
def template_pdf(tid):
    """원본 PDF 조회 (pdf.js 렌더링용)."""
    template = db.session.get(ContractTemplate, tid)
    if not template or not os.path.exists(template.file_path):
        return jsonify({"error": "파일을 찾을 수 없습니다."}), 404

    return send_file(
        template.file_path,
        mimetype="application/octet-stream",
        as_attachment=False,
    )


# ── 필드 이미지 업로드 ──


@contract_bp.route("/api/upload-field-image", methods=["POST"])
@require_admin
def upload_field_image():
    """필드 이미지 업로드 (서식 에디터에서 사용)."""
    _ensure_dirs()

    if "file" not in request.files:
        return jsonify({"error": "파일을 선택해주세요."}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "파일을 선택해주세요."}), 400

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        return jsonify({"error": "이미지 파일(jpg, png, gif)만 업로드 가능합니다."}), 400

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = secure_filename(file.filename) or f"field_image_{timestamp}.{ext}"
    filename = f"{timestamp}_{safe_name}"
    filepath = os.path.join(FIELD_IMAGE_DIR, filename)
    file.save(filepath)

    # 클라이언트에서 사용할 URL 경로 반환
    image_url = f"/uploads/field_images/{filename}"
    return jsonify({"success": True, "url": image_url}), 201


# ── 계약 관리 ──


@contract_bp.route("/admin/contracts")
@require_admin
def admin_contracts():
    """계약 목록 페이지 (검색/필터 지원)."""
    status_filter = request.args.get("status", "")
    q = request.args.get("q", "").strip()
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()

    query = Contract.query.options(
        joinedload(Contract.template),
        joinedload(Contract.employee),
        joinedload(Contract.participants),
    )

    # 상태 필터
    if status_filter:
        query = query.filter(Contract.status == status_filter)

    # 키워드 검색 (제목 또는 직원 이름)
    if q:
        query = query.outerjoin(Employee, Contract.employee_id == Employee.id).filter(
            or_(
                Contract.title.ilike(f"%{q}%"),
                Employee.name.ilike(f"%{q}%"),
            )
        )

    # 날짜 범위 필터
    if date_from:
        try:
            dt_from = datetime.strptime(date_from, "%Y-%m-%d")
            query = query.filter(Contract.created_at >= dt_from)
        except ValueError:
            pass
    if date_to:
        try:
            dt_to = datetime.strptime(date_to, "%Y-%m-%d")
            # 해당 날짜의 끝까지 포함
            dt_to = dt_to.replace(hour=23, minute=59, second=59)
            query = query.filter(Contract.created_at <= dt_to)
        except ValueError:
            pass

    contracts = query.order_by(Contract.created_at.desc()).all()

    templates = ContractTemplate.query.filter_by(status="active").order_by(
        ContractTemplate.name
    ).all()
    return render_template(
        "admin_contracts.html",
        contracts=contracts,
        templates=templates,
        status_filter=status_filter,
        q=q,
        date_from=date_from,
        date_to=date_to,
    )


@contract_bp.route("/admin/bulk-send")
@require_admin
def bulk_send_page():
    """대량전송 페이지."""
    templates = ContractTemplate.query.filter_by(status="active").order_by(
        ContractTemplate.id.desc()
    ).all()

    # batch_id 기반 그룹핑
    bulk_groups = (
        db.session.query(
            Contract.batch_id,
            Contract.title,
            Contract.template_id,
            func.count(Contract.id).label("total"),
            func.min(Contract.created_at).label("created_at"),
        )
        .filter(Contract.batch_id.isnot(None), Contract.batch_id != "")
        .group_by(Contract.batch_id, Contract.title, Contract.template_id)
        .order_by(func.min(Contract.created_at).desc())
        .all()
    )

    # 배치별 상태 카운트를 한 번의 쿼리로 조회
    batch_ids = [bg.batch_id for bg in bulk_groups]
    status_counts = {}
    if batch_ids:
        rows = (
            db.session.query(
                Contract.batch_id,
                Contract.status,
                func.count(Contract.id),
            )
            .filter(Contract.batch_id.in_(batch_ids))
            .group_by(Contract.batch_id, Contract.status)
            .all()
        )
        for bid, status, cnt in rows:
            status_counts.setdefault(bid, {})
            status_counts[bid][status] = cnt

    # 템플릿 ID → 이름 매핑 (한 번만 조회)
    tmpl_ids = {bg.template_id for bg in bulk_groups if bg.template_id}
    tmpl_map = {}
    if tmpl_ids:
        for t in ContractTemplate.query.filter(ContractTemplate.id.in_(tmpl_ids)).all():
            tmpl_map[t.id] = t.name

    bulk_history = []
    for bg in bulk_groups:
        counts = status_counts.get(bg.batch_id, {})
        signed_count = counts.get("completed", 0)
        pending_count = counts.get("pending", 0) + counts.get("in_progress", 0)
        bulk_history.append(
            {
                "batch_id": bg.batch_id,
                "title": bg.title,
                "template_name": tmpl_map.get(bg.template_id, "-"),
                "total": bg.total,
                "signed": signed_count,
                "pending": pending_count,
                "created_at": bg.created_at,
            }
        )

    return render_template(
        "admin_bulk_send.html", templates=templates, bulk_history=bulk_history
    )


@contract_bp.route("/admin/bulk-send/<batch_id>")
@require_admin
def bulk_send_detail(batch_id):
    """대량전송 배치 상세 페이지."""
    contracts = (
        Contract.query.options(
            joinedload(Contract.template),
            joinedload(Contract.participants),
        )
        .filter_by(batch_id=batch_id)
        .order_by(Contract.created_at.asc())
        .all()
    )

    if not contracts:
        return redirect(url_for("contract.bulk_send_page"))

    first = contracts[0]
    total = len(contracts)
    signed = sum(1 for c in contracts if c.status == "completed")
    pending = total - signed

    participant_list = []
    for idx, c in enumerate(contracts):
        # 모든 참여자 정보 수집
        parts = []
        for p in c.participants:
            parts.append({
                "id": p.id,
                "role_key": p.role_key,
                "name": p.name,
                "phone": p.phone or "",
                "status": p.status,
                "sign_token": p.sign_token,
                "signed_at": p.signed_at,
            })
        worker = next((p for p in c.participants if p.role_key == "worker"), None)
        participant_list.append(
            {
                "no": idx + 1,
                "contract_id": c.id,
                "participant_id": worker.id if worker else None,
                "name": worker.name if worker else (c.title or "-"),
                "phone": worker.phone if worker else "",
                "status": worker.status if worker else "pending",
                "signed_at": worker.signed_at if worker else None,
                "contract_status": c.status,
                "expires_at": c.expires_at,
                "is_expired": c.is_expired,
                "participants": parts,
            }
        )

    batch_info = {
        "batch_id": batch_id,
        "title": first.title,
        "template_name": first.template.name if first.template else "-",
        "created_at": first.created_at,
        "total": total,
        "signed": signed,
        "pending": pending,
    }

    return render_template(
        "admin_bulk_send_detail.html",
        batch_info=batch_info,
        participant_list=participant_list,
    )


@contract_bp.route("/admin/contracts/new")
@require_admin
def new_contract():
    """계약 생성 페이지."""
    template_id = request.args.get("template_id", type=int)
    template = db.session.get(ContractTemplate, template_id) if template_id else None
    templates = ContractTemplate.query.filter_by(status="active").order_by(
        ContractTemplate.name
    ).all()
    employees = Employee.query.filter_by(is_active=True).order_by(Employee.name).all()
    return render_template(
        "admin_contract_create.html",
        template=template,
        templates=templates,
        employees=employees,
    )


@contract_bp.route("/admin/contracts/<int:cid>")
@require_admin
def contract_detail(cid):
    """계약 상세 페이지."""
    contract = Contract.query.options(
        joinedload(Contract.template),
        joinedload(Contract.employee),
        joinedload(Contract.participants),
        joinedload(Contract.audit_logs),
    ).get(cid)
    if not contract:
        return redirect(url_for("contract.admin_contracts"))

    # 감사 로그를 최신순으로 정렬
    audit_logs = sorted(
        contract.audit_logs, key=lambda log: log.created_at or datetime.min, reverse=True
    )

    # 필드값에 라벨/타입 정보 보강 (상세 페이지에서 표시용)
    template_fields = contract.template.fields if contract.template else []
    for p in contract.participants:
        enriched_values = []
        for fv in p.field_values:
            idx = fv.get("field_idx")
            field_def = template_fields[idx] if idx is not None and idx < len(template_fields) else {}
            enriched_values.append({
                "field_idx": idx,
                "value": fv.get("value", ""),
                "label": field_def.get("label", f"필드 {idx}"),
                "type": field_def.get("type", "text"),
            })
        p._enriched_field_values = enriched_values

    return render_template(
        "admin_contract_detail.html",
        contract=contract,
        audit_logs=audit_logs,
    )


@contract_bp.route("/api/contracts", methods=["POST"])
@require_admin
def create_contract():
    """계약 생성 + 참여자 배정."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "JSON body required"}), 400

    template_id = data.get("template_id")
    template = db.session.get(ContractTemplate, template_id) if template_id else None
    if not template:
        return jsonify({"error": "서식을 선택해주세요."}), 400

    title = str(data.get("title", "")).strip()
    if not title:
        title = template.name

    # 만료일 처리 (ISO 형식 문자열)
    expires_at = None
    expires_at_str = data.get("expires_at", "")
    if expires_at_str:
        try:
            expires_at = datetime.fromisoformat(expires_at_str)
        except (ValueError, TypeError):
            pass

    # 예약발송 시각 처리
    scheduled_at = None
    scheduled_at_str = data.get("scheduled_at", "")
    if scheduled_at_str:
        try:
            scheduled_at = datetime.fromisoformat(scheduled_at_str)
        except (ValueError, TypeError):
            pass

    contract = Contract(
        template_id=template_id,
        title=title,
        employee_id=data.get("employee_id") or None,
        status="draft",
        expires_at=expires_at,
        scheduled_at=scheduled_at,
    )
    db.session.add(contract)
    db.session.flush()  # contract.id 확보

    # 참여자 생성
    participants_data = data.get("participants", [])
    for p in participants_data:
        participant = ContractParticipant(
            contract_id=contract.id,
            role_key=p.get("role_key", ""),
            name=str(p.get("name", "")).strip(),
            phone=str(p.get("phone", "")).strip(),
            sign_token=generate_sign_token(),
            field_values_json=json.dumps(p.get("field_values", []), ensure_ascii=False),
            status="signed" if p.get("pre_signed") else "pending",
            signed_at=datetime.now() if p.get("pre_signed") else None,
        )
        db.session.add(participant)

    # 전체 참여자 서명 여부 확인
    db.session.flush()
    _update_contract_status(contract)

    # 예약발송 여부에 따라 상태/발송 처리 분기
    is_scheduled = scheduled_at is not None and scheduled_at > datetime.now()

    if is_scheduled:
        contract.status = "scheduled"

    # 감사 로그: 계약 생성
    detail_msg = f"서식: {template.name}, 참여자 {len(participants_data)}명"
    if is_scheduled:
        detail_msg += f", 예약발송: {scheduled_at.strftime('%Y-%m-%d %H:%M')}"
    _audit_log(
        contract.id,
        "계약 생성",
        actor="관리자",
        detail=detail_msg,
        ip=request.remote_addr,
    )

    db.session.commit()

    # 예약발송이 아닌 경우에만 즉시 SMS 발송
    if not is_scheduled:
        for p in contract.participants:
            _send_sign_sms(contract, p)

    return jsonify({"success": True, "contract": contract.to_dict()}), 201


def _update_contract_status(contract):
    """참여자 서명 상태에 따라 계약 상태 업데이트."""
    if not contract.participants:
        return
    all_signed = all(p.status == "signed" for p in contract.participants)
    any_signed = any(p.status == "signed" for p in contract.participants)

    if all_signed:
        # 최종 PDF 생성
        try:
            pdf_path = generate_final_pdf(contract)
            contract.final_pdf_path = pdf_path
            contract.status = "completed"
            contract.completed_at = datetime.now()
            _audit_log(
                contract.id,
                "계약 완료",
                actor="시스템",
                detail="모든 참여자 서명 완료, 최종 PDF 생성",
            )
        except Exception as e:
            logger.error("최종 PDF 생성 실패: %s", e)
            contract.status = "in_progress"
            _audit_log(
                contract.id,
                "PDF 생성 실패",
                actor="시스템",
                detail=f"모든 서명 완료, PDF 생성 실패: {str(e)[:200]}",
            )
    elif any_signed:
        contract.status = "in_progress"
    else:
        contract.status = "pending"


@contract_bp.route("/api/contracts/<int:cid>", methods=["DELETE"])
@require_admin
def delete_contract(cid):
    """계약 취소."""
    contract = db.session.get(Contract, cid)
    if not contract:
        return jsonify({"error": "계약을 찾을 수 없습니다."}), 404
    contract.status = "cancelled"

    # 감사 로그: 계약 취소
    _audit_log(
        contract.id,
        "계약 취소",
        actor="관리자",
        detail="",
        ip=request.remote_addr,
    )

    db.session.commit()
    return jsonify({"success": True})


@contract_bp.route("/api/contracts/<int:cid>/hard-delete", methods=["DELETE"])
@require_admin
def hard_delete_contract(cid):
    """계약 완전 삭제 (DB에서 제거)."""
    contract = db.session.get(Contract, cid)
    if not contract:
        return jsonify({"error": "계약을 찾을 수 없습니다."}), 404

    # 최종 PDF 파일 삭제
    if contract.final_pdf_path and os.path.exists(contract.final_pdf_path):
        try:
            os.remove(contract.final_pdf_path)
        except OSError:
            pass

    # 감사 로그 삭제
    ContractAuditLog.query.filter_by(contract_id=cid).delete()
    # 참여자 삭제
    ContractParticipant.query.filter_by(contract_id=cid).delete()
    # 계약 삭제
    db.session.delete(contract)
    db.session.commit()
    return jsonify({"success": True})


@contract_bp.route("/api/contracts/<int:cid>/update-schedule", methods=["PUT"])
@require_admin
def update_contract_schedule(cid):
    """예약발송 시각 수정/취소."""
    contract = db.session.get(Contract, cid)
    if not contract:
        return jsonify({"error": "계약을 찾을 수 없습니다."}), 404

    if contract.status not in ("scheduled", "draft"):
        return jsonify({"error": "예약 상태가 아닌 계약은 수정할 수 없습니다."}), 400

    data = request.get_json(silent=True) or {}
    scheduled_at_str = data.get("scheduled_at", "")
    action = data.get("action", "update")  # "update" or "send_now" or "cancel"

    if action == "send_now":
        # 즉시 발송
        contract.status = "pending"
        contract.scheduled_at = None
        _audit_log(
            contract.id, "즉시 발송 전환", actor="관리자",
            detail="예약발송 → 즉시 발송으로 전환",
            ip=request.remote_addr,
        )
        db.session.commit()

        for p in contract.participants:
            _send_sign_sms(contract, p)

        return jsonify({"success": True, "message": "즉시 발송되었습니다."})

    if action == "cancel":
        # 예약 취소 (draft로 되돌림)
        contract.status = "draft"
        contract.scheduled_at = None
        _audit_log(
            contract.id, "예약 취소", actor="관리자",
            detail="예약발송이 취소되었습니다.",
            ip=request.remote_addr,
        )
        db.session.commit()
        return jsonify({"success": True, "message": "예약이 취소되었습니다."})

    # 예약 시각 변경
    if scheduled_at_str:
        try:
            new_scheduled = datetime.fromisoformat(scheduled_at_str)
            contract.scheduled_at = new_scheduled
            contract.status = "scheduled"
            _audit_log(
                contract.id, "예약 시각 변경", actor="관리자",
                detail=f"변경: {new_scheduled.strftime('%Y-%m-%d %H:%M')}",
                ip=request.remote_addr,
            )
        except (ValueError, TypeError):
            return jsonify({"error": "잘못된 날짜 형식입니다."}), 400
    else:
        return jsonify({"error": "예약 시각을 입력해주세요."}), 400

    db.session.commit()
    return jsonify({
        "success": True,
        "scheduled_at": contract.scheduled_at.strftime("%Y-%m-%d %H:%M") if contract.scheduled_at else None,
    })


@contract_bp.route("/api/contracts/<int:cid>/update-expiry", methods=["PUT"])
@require_admin
def update_contract_expiry(cid):
    """계약 만료일 수정/연장/제거."""
    contract = db.session.get(Contract, cid)
    if not contract:
        return jsonify({"error": "계약을 찾을 수 없습니다."}), 404

    data = request.get_json(silent=True) or {}
    expires_at_str = data.get("expires_at", "")

    if expires_at_str:
        try:
            contract.expires_at = datetime.fromisoformat(expires_at_str)
        except (ValueError, TypeError):
            return jsonify({"error": "잘못된 날짜 형식입니다."}), 400
    else:
        contract.expires_at = None  # 만료일 제거 (무기한)

    _audit_log(
        contract.id,
        "만료일 변경",
        actor="관리자",
        detail=f"만료일: {contract.expires_at or '무기한'}",
        ip=request.remote_addr,
    )

    db.session.commit()
    return jsonify({"success": True, "expires_at": contract.expires_at.strftime("%Y-%m-%d %H:%M") if contract.expires_at else None})


@contract_bp.route("/api/contracts/batch/<batch_id>/update-expiry", methods=["PUT"])
@require_admin
def batch_update_expiry(batch_id):
    """배치 내 미완료 계약 전체 만료일 일괄 수정."""
    data = request.get_json(silent=True) or {}
    expires_at_str = data.get("expires_at", "")

    new_expires = None
    if expires_at_str:
        try:
            new_expires = datetime.fromisoformat(expires_at_str)
        except (ValueError, TypeError):
            return jsonify({"error": "잘못된 날짜 형식입니다."}), 400

    contracts = Contract.query.filter_by(batch_id=batch_id).all()
    if not contracts:
        return jsonify({"error": "배치를 찾을 수 없습니다."}), 404

    updated = 0
    for c in contracts:
        if c.status != "completed":
            c.expires_at = new_expires
            _audit_log(
                c.id, "만료일 일괄변경", actor="관리자",
                detail=f"만료일: {new_expires or '무기한'} (배치 일괄)",
                ip=request.remote_addr,
            )
            updated += 1

    db.session.commit()
    return jsonify({
        "success": True,
        "updated": updated,
        "expires_at": new_expires.strftime("%Y-%m-%d %H:%M") if new_expires else None,
    })


@contract_bp.route("/api/contracts/bulk-create", methods=["POST"])
@require_admin
def bulk_create_contract():
    """대량 전송: 같은 서식으로 여러 사람에게 계약 생성."""
    data = request.get_json(silent=True) or {}
    template_id = data.get("template_id")
    template = db.session.get(ContractTemplate, template_id) if template_id else None
    if not template:
        return jsonify({"error": "서식을 찾을 수 없습니다."}), 400

    worker_name = str(data.get("worker_name", "")).strip()
    if not worker_name:
        return jsonify({"error": "수신자 이름을 입력해주세요."}), 400

    employer_name = str(data.get("employer_name", "")).strip()
    employer_phone = str(data.get("employer_phone", "")).strip()

    title = str(data.get("title", "")).strip() or template.name
    expires_at = None
    expires_at_str = data.get("expires_at", "")
    if expires_at_str:
        try:
            expires_at = datetime.fromisoformat(expires_at_str)
        except (ValueError, TypeError):
            pass

    # 예약발송 시각 처리
    scheduled_at = None
    scheduled_at_str = data.get("scheduled_at", "")
    if scheduled_at_str:
        try:
            scheduled_at = datetime.fromisoformat(scheduled_at_str)
        except (ValueError, TypeError):
            pass

    is_scheduled = scheduled_at is not None and scheduled_at > datetime.now()
    batch_id = str(data.get("batch_id", "")).strip() or None

    contract = Contract(
        template_id=template_id,
        title=title,
        status="scheduled" if is_scheduled else "pending",
        expires_at=expires_at,
        scheduled_at=scheduled_at,
        batch_id=batch_id,
    )
    db.session.add(contract)
    db.session.flush()

    # 서식의 역할 정보에서 참여자 생성
    roles = template.roles or []
    for role in roles:
        role_key = role.get("key", "")
        if role_key == "worker":
            participant = ContractParticipant(
                contract_id=contract.id,
                role_key="worker",
                name=worker_name,
                phone=str(data.get("worker_phone", "")).strip(),
                sign_token=generate_sign_token(),
                status="pending",
            )
        else:
            # employer 등 기타 역할: 전달된 관리자 정보 사용
            participant = ContractParticipant(
                contract_id=contract.id,
                role_key=role_key,
                name=employer_name or role.get("label", role_key),
                phone=employer_phone,
                sign_token=generate_sign_token(),
                status="pending",
            )
        db.session.add(participant)

    detail_msg = f"서식: {template.name}, 근로자: {worker_name}"
    if is_scheduled:
        detail_msg += f", 예약발송: {scheduled_at.strftime('%Y-%m-%d %H:%M')}"
    _audit_log(
        contract.id,
        "대량 전송 생성",
        actor="관리자",
        detail=detail_msg,
        ip=request.remote_addr,
    )

    db.session.commit()

    # 예약발송이 아닌 경우에만 즉시 SMS 발송
    if not is_scheduled:
        for p in contract.participants:
            _send_sign_sms(contract, p)

    return jsonify({"success": True, "contract": contract.to_dict()}), 201


@contract_bp.route("/admin/contracts/<int:cid>/pdf")
@require_admin
def contract_pdf(cid):
    """계약 PDF 다운로드."""
    contract = db.session.get(Contract, cid)
    if not contract:
        return jsonify({"error": "계약을 찾을 수 없습니다."}), 404

    if contract.final_pdf_path and os.path.exists(contract.final_pdf_path):
        return send_file(
            contract.final_pdf_path,
            mimetype="application/pdf",
            as_attachment=True,
            download_name=f"계약서_{contract.title}.pdf",
        )

    # 아직 완료되지 않은 경우 원본 서식 PDF 반환
    if contract.template and os.path.exists(contract.template.file_path):
        return send_file(contract.template.file_path, mimetype="application/pdf")

    return jsonify({"error": "PDF를 찾을 수 없습니다."}), 404


@contract_bp.route("/admin/contracts/<int:cid>/view-pdf")
@require_admin
def contract_view_pdf(cid):
    """계약 PDF 브라우저 내 열람 (인라인) — 현재까지 입력된 필드값 반영."""
    contract = (
        db.session.query(Contract)
        .options(joinedload(Contract.template), joinedload(Contract.participants))
        .get(cid)
    )
    if not contract:
        return jsonify({"error": "계약을 찾을 수 없습니다."}), 404

    # 완료된 계약: 최종 PDF
    if contract.final_pdf_path and os.path.exists(contract.final_pdf_path):
        return send_file(
            contract.final_pdf_path,
            mimetype="application/pdf",
            as_attachment=False,
        )

    # 미완료 계약: 현재까지 입력된 필드값으로 미리보기 PDF 생성
    if contract.template and os.path.exists(contract.template.file_path):
        # 참여자 중 누구라도 필드값을 입력했는지 확인
        has_values = any(
            p.field_values for p in contract.participants if p.field_values
        )
        if has_values:
            try:
                from services.contract_service import generate_final_pdf
                preview_path = generate_final_pdf(contract, suffix="preview")
                resp = send_file(
                    preview_path,
                    mimetype="application/pdf",
                    as_attachment=False,
                )
                # 미리보기 임시파일 삭제 예약 (응답 후)
                @resp.call_on_close
                def _cleanup():
                    try:
                        if preview_path and os.path.exists(preview_path):
                            os.remove(preview_path)
                    except OSError:
                        pass
                return resp
            except Exception as e:
                logger.warning("미리보기 PDF 생성 실패, 원본 반환: %s", e)

        return send_file(
            contract.template.file_path,
            mimetype="application/pdf",
            as_attachment=False,
        )

    return jsonify({"error": "PDF를 찾을 수 없습니다."}), 404


@contract_bp.route(
    "/api/contracts/<int:cid>/participants/<int:pid>/resend-sms",
    methods=["POST"],
)
@require_admin
def resend_sms(cid, pid):
    """참여자에게 서명 링크 SMS 재전송."""
    contract = db.session.get(Contract, cid)
    if not contract:
        return jsonify({"error": "계약을 찾을 수 없습니다."}), 404

    participant = ContractParticipant.query.filter_by(
        id=pid, contract_id=cid
    ).first()
    if not participant:
        return jsonify({"error": "참여자를 찾을 수 없습니다."}), 404

    if participant.status == "signed":
        return jsonify({"error": "이미 서명이 완료된 참여자입니다."}), 400

    if not participant.phone:
        return jsonify({"error": "연락처가 등록되지 않은 참여자입니다."}), 400

    _send_sign_sms(contract, participant)

    _audit_log(
        cid,
        "SMS 재전송",
        actor="관리자",
        detail=f"참여자: {participant.name} ({participant.phone})",
        ip=request.remote_addr,
    )
    db.session.commit()

    return jsonify(
        {
            "success": True,
            "message": f"{participant.name}에게 SMS를 재전송했습니다.",
        }
    )


# ── 업로드된 필드 이미지 서빙 ──


@contract_bp.route("/uploads/field_images/<filename>")
def serve_field_image(filename):
    """업로드된 필드 이미지 서빙 (서명 페이지에서도 접근 가능)."""
    safe = secure_filename(filename)
    if not safe or safe != filename:
        return jsonify({"error": "잘못된 파일명"}), 400

    # 허용 확장자 검사로 이미지 외 파일 노출 방지
    ext = safe.rsplit(".", 1)[-1].lower() if "." in safe else ""
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        return jsonify({"error": "허용되지 않은 파일 형식"}), 403

    filepath = os.path.join(FIELD_IMAGE_DIR, safe)
    # 경로 탈출 방지 (심볼릭 링크 등)
    if not os.path.realpath(filepath).startswith(os.path.realpath(FIELD_IMAGE_DIR)):
        return jsonify({"error": "잘못된 파일명"}), 400
    if not os.path.exists(filepath):
        return jsonify({"error": "파일을 찾을 수 없습니다."}), 404

    mime_map = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "gif": "image/gif"}
    return send_file(filepath, mimetype=mime_map.get(ext, "application/octet-stream"))


# ── 서명용 공개 PDF ──


@contract_bp.route("/api/sign-pdf/<token>")
def sign_template_pdf(token):
    """서명 페이지에서 원본 PDF를 조회 (공개, 토큰 기반 인증).

    IDM 등 다운로드 매니저가 application/pdf를 가로채는 것을 방지하기 위해
    octet-stream으로 전송. 프론트에서 fetch → ArrayBuffer → pdf.js 렌더링.
    """
    participant = ContractParticipant.query.filter_by(sign_token=token).first()
    if not participant:
        return jsonify({"error": "잘못된 링크입니다."}), 404

    contract = participant.contract
    template = contract.template
    if not template or not os.path.exists(template.file_path):
        return jsonify({"error": "파일을 찾을 수 없습니다."}), 404

    return send_file(
        template.file_path,
        mimetype="application/octet-stream",
        as_attachment=False,
    )


# ── 감사 로그 API ──


@contract_bp.route("/api/contracts/<int:cid>/audit-logs")
@require_admin
def contract_audit_logs(cid):
    """계약 감사 로그 조회."""
    contract = db.session.get(Contract, cid)
    if not contract:
        return jsonify({"error": "계약을 찾을 수 없습니다."}), 404

    logs = ContractAuditLog.query.filter_by(contract_id=cid).order_by(
        ContractAuditLog.created_at.desc()
    ).all()
    return jsonify({"success": True, "logs": [log.to_dict() for log in logs]})


# ── 서명 토큰 재생성 ──


@contract_bp.route(
    "/api/contracts/<int:cid>/participants/<int:pid>/regenerate-token",
    methods=["POST"],
)
@require_admin
def regenerate_token(cid, pid):
    """참여자 서명 토큰 재생성."""
    participant = ContractParticipant.query.filter_by(
        id=pid, contract_id=cid
    ).first()
    if not participant:
        return jsonify({"error": "참여자를 찾을 수 없습니다."}), 404

    old_token = participant.sign_token
    participant.sign_token = generate_sign_token()

    # 감사 로그: 토큰 재생성
    _audit_log(
        cid,
        "토큰 재생성",
        actor="관리자",
        detail=f"참여자: {participant.name} (역할: {participant.role_key})",
        ip=request.remote_addr,
    )

    db.session.commit()
    return jsonify({
        "success": True,
        "participant": participant.to_dict(),
    })


# ── 서명 (공개) ──


@contract_bp.route("/sign/<token>")
def sign_page(token):
    """직원 서명 페이지."""
    participant = ContractParticipant.query.filter_by(sign_token=token).first()
    if not participant:
        return render_template(
            "error.html",
            error_code="404",
            error_message="잘못된 링크입니다",
            error_description="서명 링크가 유효하지 않습니다.",
        ), 404

    contract = participant.contract

    # 만료 확인
    if contract.is_expired:
        return render_template(
            "error.html",
            error_code="410",
            error_message="만료된 계약",
            error_description="이 계약의 서명 기한이 만료되었습니다.",
        ), 410

    if contract.status == "cancelled":
        return render_template(
            "error.html",
            error_code="410",
            error_message="취소된 계약",
            error_description="이 계약은 취소되었습니다.",
        ), 410

    # 다른 참여자의 필드값 수집 (이미 서명한 참여자의 값만)
    other_values = {}
    for p in contract.participants:
        if p.id != participant.id and p.status == "signed":
            for fv in p.field_values:
                idx = fv.get("field_idx")
                if idx is not None and fv.get("value"):
                    other_values[idx] = fv["value"]

    # PDF를 base64로 인코딩하여 HTML에 직접 임베드 (IDM 우회)
    import base64

    pdf_base64 = ""
    template = contract.template

    # 서명 완료 + 최종 PDF가 있으면 최종 PDF 표시
    if participant.status == "signed" and contract.final_pdf_path and os.path.exists(
        contract.final_pdf_path
    ):
        with open(contract.final_pdf_path, "rb") as f:
            pdf_base64 = base64.b64encode(f.read()).decode("ascii")
    elif template and os.path.exists(template.file_path):
        with open(template.file_path, "rb") as f:
            pdf_base64 = base64.b64encode(f.read()).decode("ascii")

    render_kwargs = dict(
        participant=participant,
        contract=contract,
        template=template,
        other_values=other_values,
        pdf_base64=pdf_base64,
    )

    if participant.status == "signed":
        return render_template(
            "contract_sign.html", already_signed=True, **render_kwargs
        )

    return render_template(
        "contract_sign.html", already_signed=False, **render_kwargs
    )


@contract_bp.route("/api/sign/<token>", methods=["POST"])
def submit_sign(token):
    """서명 제출."""
    participant = ContractParticipant.query.filter_by(sign_token=token).first()
    if not participant:
        return jsonify({"error": "잘못된 링크입니다."}), 404

    if participant.status == "signed":
        return jsonify({"error": "이미 서명하셨습니다."}), 400

    contract = participant.contract

    # 만료 확인
    if contract.is_expired:
        return jsonify({"error": "서명 기한이 만료된 계약입니다."}), 400

    if contract.status == "cancelled":
        return jsonify({"error": "취소된 계약입니다."}), 400

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "JSON body required"}), 400

    # field_values 검증
    field_values = data.get("field_values", [])
    if not isinstance(field_values, list):
        return jsonify({"error": "field_values must be a list"}), 400
    if len(field_values) > 200:
        return jsonify({"error": "필드 수가 너무 많습니다."}), 400
    # 전체 크기 제한 (1MB)
    import json as _json
    if len(_json.dumps(field_values, ensure_ascii=False)) > 1_000_000:
        return jsonify({"error": "데이터 크기가 너무 큽니다."}), 400
    for fv in field_values:
        if not isinstance(fv, dict):
            return jsonify({"error": "field_values 항목이 올바르지 않습니다."}), 400

    participant.field_values = field_values
    participant.status = "signed"
    participant.signed_at = datetime.now()
    participant.sign_ip = request.remote_addr

    # 감사 로그: 서명 완료
    _audit_log(
        contract.id,
        "서명 완료",
        actor=participant.name,
        detail=f"역할: {participant.role_key}",
        ip=request.remote_addr,
    )

    _update_contract_status(contract)
    db.session.commit()

    return jsonify({"success": True, "message": "서명이 완료되었습니다."})


@contract_bp.route("/sign/<token>/download")
def download_signed_pdf(token):
    """서명 완료된 계약서 PDF 다운로드."""
    participant = ContractParticipant.query.filter_by(sign_token=token).first()
    if not participant or participant.status != "signed":
        return "잘못된 요청입니다.", 404

    contract = participant.contract
    if not contract.final_pdf_path or not os.path.exists(contract.final_pdf_path):
        return "완성된 계약서가 아직 준비되지 않았습니다.", 404

    return send_file(
        contract.final_pdf_path,
        as_attachment=True,
        download_name=f"{contract.title}_계약서.pdf",
    )
