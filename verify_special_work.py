import sys
import os
from datetime import date
import sys
import os
from datetime import date
from app import app
from models import db, Employee, AttendanceRecord

# app = create_app() # removed

with app.app_context():
    # 1. Setup Test Employee
    emp = Employee.query.filter_by(name='테스트직원').first()
    if not emp:
        emp = Employee(name='테스트직원', birth_date='900101')
        db.session.add(emp)
        db.session.commit()
        print(f"Created test employee: {emp.name}")
    else:
        print(f"Using existing employee: {emp.name}")

    # 2. Define Test Cases
    test_cases = [
        # (Date, Type, Expected Holiday Hours)
        (date(2026, 5, 4), 'normal', 0.0),   # Monday (Normal)
        (date(2026, 5, 2), 'normal', 8.0),   # Saturday (Weekend -> Special)
        (date(2026, 5, 5), 'normal', 8.0),   # Tuesday (Holiday -> Special)
        (date(2026, 5, 6), 'normal', 0.0),   # Wednesday (Normal)
    ]

    # Clean up previous test records
    AttendanceRecord.query.filter_by(emp_name='테스트직원').delete()
    db.session.commit()

    print("\n--- Running Verification ---")
    
    from routes.attendance import calc_work_hours, _get_cfg
    cfg = _get_cfg()
    print(f"Config Loaded. Holidays: {len(cfg['PUBLIC_HOLIDAYS_2026'])}")

    for d, w_type, expected_holiday in test_cases:
        clock_in = '09:00'
        clock_out = '18:00' # 9 hours - 1h break = 8h work
        
        # Calculate Logic directly
        total, ot, night, holiday = calc_work_hours(clock_in, clock_out, w_type, cfg, work_date=d)
        
        print(f"Date: {d} ({d.strftime('%A')})")
        print(f"  Input: {clock_in}~{clock_out}")
        print(f"  Result: Total={total}, OT={ot}, Night={night}, Holiday={holiday}")
        
        if holiday == expected_holiday:
            print("  ✅ PASS")
        else:
            print(f"  ❌ FAIL (Expected {expected_holiday}, Got {holiday})")

        # Save to DB to check model
        rec = AttendanceRecord(
            emp_name='테스트직원',
            birth_date='900101',
            work_date=d,
            clock_in=clock_in,
            clock_out=clock_out,
            work_type=w_type,
            total_work_hours=total,
            overtime_hours=ot,
            night_hours=night,
            holiday_work_hours=holiday
        )
        db.session.add(rec)
    
    db.session.commit()
    print("\n--- DB Saved Records ---")
    recs = AttendanceRecord.query.filter_by(emp_name='테스트직원').order_by(AttendanceRecord.work_date).all()
    for r in recs:
        print(f"{r.work_date}: H={r.holiday_work_hours}")

