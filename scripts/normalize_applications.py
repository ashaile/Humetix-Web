import sqlite3

DB_PATH = 'humetix.db'

VISION_BAD = {'None None', 'None', ''}
ADVANCE_BAD = {'???', '??', '?'}
ADVANCE_DEFAULT = "비희망"

SHIFT_MAP = {
    'day': '??',
    'daytime': '??',
    'night': '??',
    '2shift': '2??',
    '2 shift': '2??',
    'two shift': '2??',
}
POSTURE_MAP = {
    'good': '??',
    'any': '??',
    'sitting': '??',
    'standing': '??',
}
BOOL_MAP = {
    'yes': '??',
    'y': '??',
    'true': '??',
    'no': '???',
    'n': '???',
    'false': '???',
}


BAD_MARK = {'???', '??', '?'}
BAD_MARK_UTF = {'?', '??', '???'}

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


FILL_DEFAULTS = {
    'shift': '??',
    'posture': '??',
    'overtime': '???',
    'holiday': '???',
    'advance_pay': '???',
    'insurance_type': '3.3%',
}


def normalize():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""SELECT id, vision, advance_pay, insurance_type, shift, posture, overtime, holiday
                   FROM applications""")
    rows = cur.fetchall()

    for app_id, vision, advance_pay, insurance_type, shift, posture, overtime, holiday in rows:
        new_vision = vision
        if vision is None or _normalize_text(vision) in VISION_BAD:
            new_vision = None

        new_advance = advance_pay
        if advance_pay is None or _normalize_text(advance_pay) in ADVANCE_BAD or _normalize_text(advance_pay) == '':
            new_advance = FILL_DEFAULTS['advance_pay']

        new_insurance = insurance_type
        if insurance_type is None or _normalize_text(insurance_type) == '':
            new_insurance = FILL_DEFAULTS['insurance_type']
        elif _normalize_text(insurance_type).startswith('?'):
            new_insurance = '4???'

        new_shift = _map_value(shift, SHIFT_MAP)
        if new_shift is None or _normalize_text(new_shift) == '':
            new_shift = FILL_DEFAULTS['shift']
        new_posture = _map_value(posture, POSTURE_MAP)
        if new_posture is None or _normalize_text(new_posture) == '':
            new_posture = FILL_DEFAULTS['posture']
        new_overtime = _map_value(overtime, BOOL_MAP)
        if new_overtime is None or _normalize_text(new_overtime) == '':
            new_overtime = FILL_DEFAULTS['overtime']
        new_holiday = _map_value(holiday, BOOL_MAP)
        if new_holiday is None or _normalize_text(new_holiday) == '':
            new_holiday = FILL_DEFAULTS['holiday']

        if (new_vision != vision or new_advance != advance_pay or new_insurance != insurance_type or
                new_shift != shift or new_posture != posture or new_overtime != overtime or new_holiday != holiday):
            cur.execute(
                """UPDATE applications
                   SET vision = ?, advance_pay = ?, insurance_type = ?,
                       shift = ?, posture = ?, overtime = ?, holiday = ?
                   WHERE id = ?""",
                (new_vision, new_advance, new_insurance,
                 new_shift, new_posture, new_overtime, new_holiday, app_id)
            )

    conn.commit()
    conn.close()


if __name__ == '__main__':
    normalize()
