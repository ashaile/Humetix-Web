import logging
import re
from datetime import datetime

from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for
from sqlalchemy.exc import IntegrityError

from models import AdvanceRequest, AttendanceRecord, Employee, Payslip, db

logger = logging.getLogger(__name__)

employee_bp = Blueprint("employee", __name__)

ALLOWED_EMPLOYEE_WORK_TYPES = {"weekly", "shift"}


def _parse_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)


@employee_bp.route("/admin/employees")
def admin_employees():
    if not session.get("is_admin"):
        return redirect(url_for("auth.login"))

    employees = Employee.query.order_by(Employee.name).all()
    return render_template("admin_employee.html", employees=employees)


@employee_bp.route("/api/employees", methods=["POST"])
def create_employee():
    if not session.get("is_admin"):
        return jsonify({"error": "권한이 없습니다."}), 401

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "JSON body required"}), 400

    name = str(data.get("name", "")).strip()
    birth_date = str(data.get("birth_date", "")).strip()
    hire_date_str = str(data.get("hire_date", "")).strip()
    work_type = str(data.get("work_type", "weekly")).strip() or "weekly"

    if not name:
        return jsonify({"error": "이름을 입력해주세요."}), 400
    if not re.fullmatch(r"\d{6}", birth_date):
        return jsonify({"error": "생년월일은 YYMMDD 6자리 숫자여야 합니다."}), 400
    if work_type not in ALLOWED_EMPLOYEE_WORK_TYPES:
        return jsonify({"error": f"work_type must be one of {sorted(ALLOWED_EMPLOYEE_WORK_TYPES)}"}), 400

    hire_date = None
    if hire_date_str:
        try:
            hire_date = datetime.strptime(hire_date_str, "%Y-%m-%d").date()
        except ValueError:
            return jsonify({"error": "hire_date format must be YYYY-MM-DD"}), 400

    existing = Employee.query.filter_by(name=name, birth_date=birth_date).first()
    if existing:
        return jsonify({"error": f"{name}({birth_date}) 직원이 이미 등록되어 있습니다."}), 409

    try:
        employee = Employee(
            name=name,
            birth_date=birth_date,
            hire_date=hire_date,
            work_type=work_type,
            is_active=True,
        )
        db.session.add(employee)
        db.session.commit()
        return jsonify({"success": True, "employee": employee.to_dict()}), 201
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "직원 중복 등록이 차단되었습니다."}), 409
    except Exception as exc:
        db.session.rollback()
        logger.error("Employee create error: %s", exc)
        return jsonify({"error": "서버 오류가 발생했습니다."}), 500


@employee_bp.route("/api/employees/<int:emp_id>", methods=["PUT"])
def update_employee(emp_id):
    if not session.get("is_admin"):
        return jsonify({"error": "권한이 없습니다."}), 401

    employee = db.session.get(Employee, emp_id)
    if not employee:
        return jsonify({"error": "직원을 찾을 수 없습니다."}), 404

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "JSON body required"}), 400

    try:
        if "name" in data:
            new_name = str(data["name"]).strip()
            if not new_name:
                return jsonify({"error": "이름은 비어 있을 수 없습니다."}), 400
            employee.name = new_name

        if "birth_date" in data:
            new_birth = str(data["birth_date"]).strip()
            if not re.fullmatch(r"\d{6}", new_birth):
                return jsonify({"error": "생년월일은 YYMMDD 6자리 숫자여야 합니다."}), 400
            employee.birth_date = new_birth

        if "work_type" in data:
            work_type = str(data["work_type"]).strip()
            if work_type not in ALLOWED_EMPLOYEE_WORK_TYPES:
                return jsonify({"error": f"work_type must be one of {sorted(ALLOWED_EMPLOYEE_WORK_TYPES)}"}), 400
            employee.work_type = work_type

        if "is_active" in data:
            employee.is_active = _parse_bool(data["is_active"])

        if "hire_date" in data:
            raw = str(data["hire_date"] or "").strip()
            employee.hire_date = datetime.strptime(raw, "%Y-%m-%d").date() if raw else None

        if "resign_date" in data:
            raw = str(data["resign_date"] or "").strip()
            employee.resign_date = datetime.strptime(raw, "%Y-%m-%d").date() if raw else None

        duplicate = Employee.query.filter(
            Employee.id != employee.id,
            Employee.name == employee.name,
            Employee.birth_date == employee.birth_date,
        ).first()
        if duplicate:
            return jsonify({"error": "동일 이름/생년월일 직원이 이미 존재합니다."}), 409

        db.session.commit()
        return jsonify({"success": True, "employee": employee.to_dict()})
    except ValueError:
        db.session.rollback()
        return jsonify({"error": "날짜 형식은 YYYY-MM-DD 이어야 합니다."}), 400
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "직원 정보 중복으로 수정에 실패했습니다."}), 409
    except Exception as exc:
        db.session.rollback()
        logger.error("Employee update error: %s", exc)
        return jsonify({"error": "서버 오류가 발생했습니다."}), 500


@employee_bp.route("/api/employees/<int:emp_id>", methods=["DELETE"])
def delete_employee(emp_id):
    if not session.get("is_admin"):
        return jsonify({"error": "권한이 없습니다."}), 401

    employee = db.session.get(Employee, emp_id)
    if not employee:
        return jsonify({"error": "직원을 찾을 수 없습니다."}), 404

    attendance_count = AttendanceRecord.query.filter_by(employee_id=emp_id).count()
    advance_count = AdvanceRequest.query.filter_by(employee_id=emp_id).count()
    payslip_count = Payslip.query.filter_by(employee_id=emp_id).count()
    if attendance_count or advance_count or payslip_count:
        return jsonify(
            {
                "error": "연결된 근태/가불/급여 데이터가 있어 삭제할 수 없습니다. is_active=false(퇴사 처리)를 사용하세요.",
            }
        ), 409

    try:
        db.session.delete(employee)
        db.session.commit()
        return jsonify({"success": True})
    except Exception as exc:
        db.session.rollback()
        logger.error("Employee delete error: %s", exc)
        return jsonify({"error": "서버 오류가 발생했습니다."}), 500


@employee_bp.route("/api/employees/verify", methods=["POST"])
def verify_employee():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "JSON body required"}), 400

    name = str(data.get("name", "")).strip()
    birth_date = str(data.get("birth_date", "")).strip()

    if not name or not re.fullmatch(r"\d{6}", birth_date):
        return jsonify({"verified": False, "error": "이름과 생년월일(YYMMDD)을 입력하세요."}), 400

    employee = Employee.query.filter_by(name=name, birth_date=birth_date, is_active=True).first()
    if employee:
        return jsonify({"verified": True, "employee": employee.to_dict()})

    return jsonify({"verified": False, "error": "등록된 재직 직원이 아닙니다."})
