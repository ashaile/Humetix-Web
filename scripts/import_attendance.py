"""
카카오톡 근태 메시지 벌크 임포트 스크립트

카카오톡 대화내보내기 .txt 파일을 직접 읽어 근태 레코드를 일괄 등록합니다.

사용법:
  # 1) 첫 실행 — 매핑 파일 자동 생성 (birth_date 미입력 직원 안내 후 종료)
  python scripts/import_attendance.py "C:/path/to/KakaoTalkChats.txt" --year 2026

  # 2) data/employee_mapping.json 에서 birth_date 채운 후 dry-run
  python scripts/import_attendance.py "C:/path/to/KakaoTalkChats.txt" --year 2026 --dry-run

  # 3) 실제 임포트
  python scripts/import_attendance.py "C:/path/to/KakaoTalkChats.txt" --year 2026
"""
import argparse
import io
import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import date, datetime

# Windows 콘솔 한글 출력 보정
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Flask 앱 컨텍스트 설정 (migrate_to_mysql.py 패턴)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app  # noqa: E402
from models import db, Employee, AttendanceRecord  # noqa: E402
from services.attendance_service import (  # noqa: E402
    calc_work_hours,
    _get_cfg,
    _effective_day_type,
    TIME_REQUIRED_TYPES,
)

# ---------------------------------------------------------------------------
# 데이터 구조
# ---------------------------------------------------------------------------

@dataclass
class ParsedRecord:
    month: int
    day: int
    name: str
    clock_in: str | None = None
    clock_out: str | None = None
    work_type: str = "normal"
    reported_overtime: float | None = None
    raw_text: str = ""


@dataclass
class ImportResult:
    employees_existing: list = field(default_factory=list)
    employees_created: list = field(default_factory=list)
    records_created: int = 0
    records_skipped_dup: int = 0
    overtime_mismatches: list = field(default_factory=list)

# ---------------------------------------------------------------------------
# 카카오톡 대화내보내기 파싱
# ---------------------------------------------------------------------------

# 카톡 메시지 헤더: "2026년 2월 1일 오전 5:04, 닉네임 : 내용"
KAKAO_MSG_HEADER = re.compile(
    r"^\d{4}년 \d{1,2}월 \d{1,2}일 오[전후] \d{1,2}:\d{2},\s+.+\s+:\s+"
)

# 카톡 날짜만 있는 줄: "2026년 2월 1일 오전 5:04"
KAKAO_DATE_ONLY = re.compile(
    r"^\d{4}년 \d{1,2}월 \d{1,2}일 오[전후] \d{1,2}:\d{2}$"
)

# 시스템 메시지 (들어왔습니다/나갔습니다/삭제/사진 등)
KAKAO_SYSTEM = re.compile(
    r"님이 (들어왔습니다|나갔습니다)|삭제된 메시지입니다|사진$|동영상$|이모티콘$"
)

# 근무 기록 패턴: "M/D 이름 HH:MM출 HH:MM퇴 [잔업N시간] [(특근)]"
# 공백 없는 경우도 처리: "2/2장성배07:30출17:30퇴"
RECORD_PATTERN = re.compile(
    r"(\d{1,2})/(\d{1,2})\s*"                # 날짜 M/D
    r"([가-힣a-zA-Z]+)"                       # 이름
    r"\s*"                                     # 선택적 공백
    r"(\d{1,2})[;:](\d{2})\s*출\s*"          # 출근 (;도 허용)
    r"(\d{1,2})[;:](\d{2})\s*퇴"             # 퇴근 (;도 허용)
)

# 잔업 패턴: "잔업 1.5시간" or "잔업1.5시간"
OVERTIME_PATTERN = re.compile(r"잔업\s*(\d+(?:\.\d+)?)\s*시간")

# 특수 유형: "M/D 이름 연차" or "M/D 이름 비가동휴무"
SPECIAL_PATTERN = re.compile(
    r"(\d{1,2})/(\d{1,2})\s*"
    r"([가-힣a-zA-Z]+)"
    r"\s+"
    r"(연차|결근|조퇴|휴무|비가동휴무)"
)

KAKAO_WORK_TYPE_MAP = {
    "연차": "annual",
    "결근": "absent",
    "조퇴": "early",
    "휴무": "holiday",
    "비가동휴무": "holiday",
}


def normalize_time(h: str, m: str) -> str:
    """시간 정규화 -> 'HH:MM'"""
    return f"{int(h):02d}:{m}"


def infer_work_type(clock_in: str) -> str:
    """출근 시간으로 주간/야간 자동 판별. 15시 이후 또는 06시 이전 출근 = night"""
    hour = int(clock_in.split(":")[0])
    if hour >= 15 or hour < 6:
        return "night"
    return "normal"


def extract_records_from_text(text: str) -> list[ParsedRecord]:
    """메시지 텍스트에서 모든 근태 기록을 추출."""
    results = []

    # 일반 근무 기록 찾기
    for m in RECORD_PATTERN.finditer(text):
        month, day = int(m.group(1)), int(m.group(2))
        name = m.group(3).strip()
        clock_in = normalize_time(m.group(4), m.group(5))
        clock_out = normalize_time(m.group(6), m.group(7))

        # 이 매치 이후~다음 날짜 패턴 사이의 텍스트에서 잔업 찾기
        after_text = text[m.end():]
        # 다음 날짜 패턴 전까지만 잔업 검색
        next_date = re.search(r"\d{1,2}/\d{1,2}", after_text)
        search_area = after_text[:next_date.start()] if next_date else after_text
        ot_match = OVERTIME_PATTERN.search(search_area)
        reported_ot = float(ot_match.group(1)) if ot_match else None

        results.append(ParsedRecord(
            month=month, day=day, name=name,
            clock_in=clock_in, clock_out=clock_out,
            work_type=infer_work_type(clock_in),
            reported_overtime=reported_ot,
            raw_text=m.group(0).strip(),
        ))

    # 특수 유형 찾기 (일반 기록에 매치되지 않은 것만)
    matched_positions = set()
    for m in RECORD_PATTERN.finditer(text):
        matched_positions.update(range(m.start(), m.end()))

    for m in SPECIAL_PATTERN.finditer(text):
        if m.start() in matched_positions:
            continue
        month, day = int(m.group(1)), int(m.group(2))
        name = m.group(3).strip()
        wt = KAKAO_WORK_TYPE_MAP[m.group(4)]
        results.append(ParsedRecord(
            month=month, day=day, name=name,
            work_type=wt,
            raw_text=m.group(0).strip(),
        ))

    return results


def parse_kakao_file(filepath: str):
    """카카오톡 내보내기 파일 파싱. (records, skipped_system_count) 반환."""
    records: list[ParsedRecord] = []
    skipped_system = 0

    with open(filepath, encoding="utf-8-sig") as f:
        lines = f.readlines()

    # 1단계: 메시지 단위로 합치기 (줄바꿈 연속 메시지 처리)
    messages: list[str] = []
    current_msg = ""

    for line in lines:
        stripped = line.rstrip("\n\r")

        # 날짜만 있는 줄 → 건너뛰기
        if KAKAO_DATE_ONLY.match(stripped.strip()):
            if current_msg:
                messages.append(current_msg)
                current_msg = ""
            continue

        # 새 메시지 헤더 시작
        if KAKAO_MSG_HEADER.match(stripped):
            if current_msg:
                messages.append(current_msg)
            current_msg = stripped
        else:
            # 이전 메시지의 연속 줄
            current_msg += " " + stripped.strip() if current_msg else stripped.strip()

    if current_msg:
        messages.append(current_msg)

    # 2단계: 각 메시지에서 근태 기록 추출
    for msg in messages:
        # 시스템 메시지 건너뛰기
        if KAKAO_SYSTEM.search(msg):
            skipped_system += 1
            continue

        # 메시지 헤더 제거 → 실제 내용만 추출
        header_match = KAKAO_MSG_HEADER.match(msg)
        if header_match:
            content = msg[header_match.end():]
        else:
            content = msg

        if not content.strip():
            continue

        extracted = extract_records_from_text(content)
        records.extend(extracted)

    return records, skipped_system

# ---------------------------------------------------------------------------
# 직원 매핑 파일 관리
# ---------------------------------------------------------------------------

def load_or_create_mapping(mapping_path: str, names: list[str], default_work_type: str):
    """매핑 JSON 파일을 로드하거나, 없으면 자동 생성."""
    mapping: dict = {}

    if os.path.exists(mapping_path):
        with open(mapping_path, encoding="utf-8") as f:
            mapping = json.load(f)

    changed = False

    for name in names:
        if name in mapping:
            continue

        # DB에서 이름으로 검색 (동명이인이 아닌 경우 자동 매핑)
        employees = Employee.query.filter_by(name=name, is_active=True).all()
        if len(employees) == 1:
            mapping[name] = {
                "birth_date": employees[0].birth_date,
                "work_type": employees[0].work_type,
            }
        else:
            mapping[name] = {
                "birth_date": "",
                "work_type": default_work_type,
            }
        changed = True

    if changed:
        os.makedirs(os.path.dirname(mapping_path) or ".", exist_ok=True)
        with open(mapping_path, "w", encoding="utf-8") as f:
            json.dump(mapping, f, ensure_ascii=False, indent=2)

    return mapping

# ---------------------------------------------------------------------------
# 직원 조회/등록
# ---------------------------------------------------------------------------

def get_or_create_employee(name: str, birth_date: str, work_type: str):
    """DB에서 직원 조회, 없으면 생성. (employee, is_new) 반환."""
    emp = Employee.query.filter_by(name=name, birth_date=birth_date).first()
    if emp:
        if not emp.is_active:
            emp.is_active = True
        return emp, False

    emp = Employee(
        name=name,
        birth_date=birth_date,
        work_type=work_type,
        is_active=True,
    )
    db.session.add(emp)
    db.session.flush()
    return emp, True

# ---------------------------------------------------------------------------
# 근태 레코드 생성
# ---------------------------------------------------------------------------

def create_attendance_record(employee, work_date, clock_in, clock_out, work_type, cfg):
    """단일 근태 레코드 생성. (record_or_None, status) 반환."""
    exists = AttendanceRecord.query.filter_by(
        employee_id=employee.id,
        work_date=work_date,
    ).first()
    if exists:
        return None, "duplicate"

    total_hours = ot_hours = night_hours = holiday_hours = 0.0

    if work_type in TIME_REQUIRED_TYPES and clock_in and clock_out:
        day_type = _effective_day_type(work_date, cfg)
        total_hours, ot_hours, night_hours, holiday_hours = calc_work_hours(
            clock_in, clock_out, cfg,
            work_date=work_date,
            calendar_day_type=day_type,
        )

    record = AttendanceRecord(
        employee_id=employee.id,
        birth_date=employee.birth_date,
        emp_name=employee.name,
        dept="",
        work_date=work_date,
        clock_in=clock_in,
        clock_out=clock_out,
        work_type=work_type,
        total_work_hours=total_hours,
        overtime_hours=ot_hours,
        night_hours=night_hours,
        holiday_work_hours=holiday_hours,
    )
    db.session.add(record)
    return record, "created"

# ---------------------------------------------------------------------------
# 메인 임포트 로직
# ---------------------------------------------------------------------------

def import_records(records, mapping, cfg, default_work_type, year, dry_run):
    """전체 레코드 처리. ImportResult 반환."""
    result = ImportResult()
    seen_employees = set()

    for rec in records:
        info = mapping.get(rec.name)
        if not info or not info.get("birth_date"):
            continue

        birth_date = info["birth_date"]
        wt = info.get("work_type", default_work_type)

        # 직원 조회/등록
        emp_key = (rec.name, birth_date)
        if emp_key not in seen_employees:
            emp, is_new = get_or_create_employee(rec.name, birth_date, wt)
            if is_new:
                result.employees_created.append(rec.name)
            else:
                result.employees_existing.append(rec.name)
            seen_employees.add(emp_key)
        else:
            emp = Employee.query.filter_by(name=rec.name, birth_date=birth_date).first()

        # 근태 레코드 생성
        try:
            work_date = date(year, rec.month, rec.day)
        except ValueError:
            continue

        att_rec, status = create_attendance_record(
            emp, work_date, rec.clock_in, rec.clock_out, rec.work_type, cfg,
        )

        if status == "created":
            result.records_created += 1

            # 잔업시간 불일치 체크
            if rec.reported_overtime is not None and att_rec:
                calc_ot = att_rec.overtime_hours
                if abs(calc_ot - rec.reported_overtime) > 0.01:
                    result.overtime_mismatches.append(
                        f"  {rec.month}/{rec.day} {rec.name}: "
                        f"카톡 {rec.reported_overtime}h vs 계산 {calc_ot}h"
                    )
        elif status == "duplicate":
            result.records_skipped_dup += 1

    if not dry_run:
        db.session.commit()
    else:
        db.session.rollback()

    return result

# ---------------------------------------------------------------------------
# 출력
# ---------------------------------------------------------------------------

def print_summary(records, skipped_system, result, dry_run):
    mode = "[DRY-RUN] " if dry_run else ""
    print(f"\n{'='*50}")
    print(f" {mode}카카오톡 근태 임포트 결과")
    print(f"{'='*50}")

    print(f"\n[파싱]")
    print(f"  근태 기록: {len(records)}건")
    print(f"  시스템 메시지 건너뜀: {skipped_system}건")

    print(f"\n[직원]")
    print(f"  기존: {len(result.employees_existing)}명")
    print(f"  신규 등록: {len(result.employees_created)}명")
    if result.employees_created:
        print(f"    -> {', '.join(result.employees_created)}")

    print(f"\n[근태 레코드]")
    print(f"  신규 생성: {result.records_created}건")
    print(f"  중복 건너뜀: {result.records_skipped_dup}건")

    if result.overtime_mismatches:
        print(f"\n[잔업시간 불일치 경고] {len(result.overtime_mismatches)}건")
        for msg in result.overtime_mismatches:
            print(msg)

    if dry_run:
        print(f"\n* DRY-RUN 모드: DB에 저장되지 않았습니다.")
        print(f"  실제 임포트: --dry-run 옵션을 제거하고 다시 실행하세요.")

    print()

# ---------------------------------------------------------------------------
# 진입점
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="카카오톡 근태 메시지 벌크 임포트",
    )
    parser.add_argument("input_file", help="카카오톡 대화내보내기 .txt 파일 경로")
    parser.add_argument(
        "--year", type=int, default=datetime.now().year,
        help="근무 연도 (기본: 현재 연도)",
    )
    parser.add_argument(
        "--mapping", default="data/employee_mapping.json",
        help="직원 매핑 JSON 파일 경로 (기본: data/employee_mapping.json)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="실제 DB에 저장하지 않고 시뮬레이션만 수행",
    )
    parser.add_argument(
        "--work-type", default="weekly", choices=["weekly", "shift"],
        help="신규 등록 직원의 기본 근무 유형 (기본: weekly)",
    )
    args = parser.parse_args()

    if not os.path.exists(args.input_file):
        print(f"[오류] 파일을 찾을 수 없습니다: {args.input_file}")
        sys.exit(1)

    with app.app_context():
        # 1. 카카오톡 파일 파싱
        records, skipped_system = parse_kakao_file(args.input_file)
        if not records:
            print("[오류] 파싱된 근태 기록이 없습니다.")
            sys.exit(1)

        print(f"[파싱 완료] 근태 기록 {len(records)}건 / 시스템 메시지 {skipped_system}건 건너뜀")

        # 2. 이름 목록 추출
        names = sorted(set(r.name for r in records))
        print(f"[직원] {len(names)}명 감지: {', '.join(names)}")

        # 3. 매핑 파일 로드/생성
        mapping = load_or_create_mapping(args.mapping, names, args.work_type)

        # 4. 미입력 birth_date 확인
        missing = [n for n in names if not mapping.get(n, {}).get("birth_date")]
        if missing:
            print(f"\n[!] 다음 직원의 생년월일이 매핑 파일에 없습니다:")
            for n in missing:
                print(f"    - {n}")
            print(f"\n    매핑 파일을 수정하세요: {os.path.abspath(args.mapping)}")
            print(f"    각 직원의 \"birth_date\"에 YYMMDD 형식을 입력한 후 다시 실행하세요.")
            print(f"    예: \"birth_date\": \"950101\"")
            sys.exit(1)

        # 5. 임포트
        cfg = _get_cfg()
        result = import_records(
            records, mapping, cfg, args.work_type, args.year, args.dry_run,
        )

        # 6. 결과 출력
        print_summary(records, skipped_system, result, args.dry_run)


if __name__ == "__main__":
    main()
