"""
지원서 데이터 정규화 스크립트
잘못된 값(물음표, None 등)을 한글 기본값으로 치환합니다.
사용법: python scripts/normalize_applications.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from models import db, Application

VISION_BAD = {'None None', 'None', ''}
ADVANCE_BAD = {'???', '??', '?'}
ADVANCE_DEFAULT = "비희망"

SHIFT_MAP = {
    'day': '주간',
    'daytime': '주간',
    'night': '야간',
    '2shift': '2교대',
    '2 shift': '2교대',
    'two shift': '2교대',
}
POSTURE_MAP = {
    'good': '무관',
    'any': '무관',
    'sitting': '좌식',
    'standing': '입식',
}
BOOL_MAP = {
    'yes': '가능',
    'y': '가능',
    'true': '가능',
    'no': '불가능',
    'n': '불가능',
    'false': '불가능',
}

BAD_MARK = {'???', '??', '?'}
BAD_MARK_UTF = {'?', '??', '???'}

FILL_DEFAULTS = {
    'shift': '주간',
    'posture': '무관',
    'overtime': '불가능',
    'holiday': '불가능',
    'advance_pay': '비희망',
    'insurance_type': '3.3%',
}


def _normalize_text(val):
    if val is None:
        return None
    text = str(val).strip()
    if text in BAD_MARK or text in BAD_MARK_UTF:
        return ''
    return text


def _is_all_question_marks(val):
    if val is None:
        return False
    text = str(val).strip()
    return text != '' and set(text) == {'?'}


def _map_value(val, mapping):
    if val is None:
        return None
    if _is_all_question_marks(val):
        return None
    raw = _normalize_text(val)
    if raw == '':
        return None
    key = raw.lower()
    return mapping.get(key, val)


def normalize():
    with app.app_context():
        applications = Application.query.all()
        updated = 0

        for row in applications:
            changed = False

            # vision 정규화
            if row.vision is None or _normalize_text(row.vision) in VISION_BAD:
                if row.vision is not None:
                    row.vision = None
                    changed = True

            # advance_pay 정규화
            norm_adv = _normalize_text(row.advance_pay)
            if row.advance_pay is None or norm_adv in ADVANCE_BAD or norm_adv == '':
                if row.advance_pay != FILL_DEFAULTS['advance_pay']:
                    row.advance_pay = FILL_DEFAULTS['advance_pay']
                    changed = True

            # insurance_type 정규화
            norm_ins = _normalize_text(row.insurance_type)
            if row.insurance_type is None or norm_ins == '':
                row.insurance_type = FILL_DEFAULTS['insurance_type']
                changed = True
            elif norm_ins and norm_ins.startswith('?'):
                row.insurance_type = '4대보험'
                changed = True

            # shift, posture, overtime, holiday 정규화
            for field, mapping, default in [
                ('shift', SHIFT_MAP, FILL_DEFAULTS['shift']),
                ('posture', POSTURE_MAP, FILL_DEFAULTS['posture']),
                ('overtime', BOOL_MAP, FILL_DEFAULTS['overtime']),
                ('holiday', BOOL_MAP, FILL_DEFAULTS['holiday']),
            ]:
                old_val = getattr(row, field)
                new_val = _map_value(old_val, mapping)
                if new_val is None or _normalize_text(new_val) == '':
                    new_val = default
                if old_val != new_val:
                    setattr(row, field, new_val)
                    changed = True

            if changed:
                updated += 1

        db.session.commit()
        print(f"정규화 완료: {len(applications)}건 중 {updated}건 수정됨")


if __name__ == '__main__':
    normalize()
