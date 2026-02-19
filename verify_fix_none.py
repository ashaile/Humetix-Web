import sys
import os
from datetime import date
from app import app
from models import db, Employee, AttendanceRecord

# app = create_app()

with app.app_context():
    # 1. Setup Test Employee
    emp = Employee.query.filter_by(name='NoneTest').first()
    if not emp:
        emp = Employee(name='NoneTest', birth_date='999999')
        db.session.add(emp)
        db.session.commit()

    # 2. Insert record with None holiday_work_hours (simulating old data)
    # Using SQL directly or object manipulation to force None if model defaults to 0?
    # Model definition: holiday_work_hours = db.Column(db.Float, default=0.0) -> Wait, if it has default, why is it None?
    # Ah, existing records created BEFORE the column was added might be NULL in SQLite/Postgres if not filled.
    # We can force it.
    
    rec = AttendanceRecord(
        emp_name='NoneTest',
        birth_date='999999',
        work_date=date(2026, 1, 1),
        clock_in='09:00',
        clock_out='18:00',
        work_type='normal',
        total_work_hours=8.0,
        holiday_work_hours=None # Force None
    )
    db.session.add(rec)
    db.session.commit()
    
    print("Inserted record with holiday_work_hours=None")

    # 3. Test the failing logic
    today = date(2026, 1, 1)
    today_recs = [rec] # Simulate the query result
    
    try:
        total_holiday = round(sum((r.holiday_work_hours or 0) for r in today_recs), 1)
        print(f"Calculation success! Result: {total_holiday}")
    except TypeError as e:
        print(f"Calculation FAILED with TypeError: {e}")
    except Exception as e:
        print(f"Calculation FAILED with {e}")
    
    # Clean up
    db.session.delete(rec)
    db.session.commit()
