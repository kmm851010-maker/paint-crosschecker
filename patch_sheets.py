
content = open('utils/sheets.py', encoding='utf-8').read()

# ── 1. 헬퍼 함수 추가 (업무현황 섹션 앞에) ──
HELPER = """
def _work_sheet_name(d) -> str:
    if isinstance(d, str):
        ym = d[:7]
    else:
        ym = d.strftime("%Y-%m")
    return "업무현황_" + ym

_WORK_HEADERS = ["날짜", "항목", "1근", "2근", "3근", "주간", "야간", "합계", "월누계"]

def _parse_work_row(row):
    return {
        "s1":          int(float(row[2])) if len(row) > 2 and row[2] else 0,
        "s2":          int(float(row[3])) if len(row) > 3 and row[3] else 0,
        "s3":          int(float(row[4])) if len(row) > 4 and row[4] else 0,
        "day":         int(float(row[5])) if len(row) > 5 and row[5] else 0,
        "night":       int(float(row[6])) if len(row) > 6 and row[6] else 0,
        "month_total": int(float(row[8])) if len(row) > 8 and row[8] else 0,
    }

def _read_work_sheet(sheet_name, date_str=None, month_prefix=None):
    try:
        sp = _retry(_get_spreadsheet)
        titles = {ws.title for ws in sp.worksheets()}
        if sheet_name not in titles:
            return []
        ws = sp.worksheet(sheet_name)
        rows = ws.get_all_values()[1:]
        if date_str:
            return [r for r in rows if r and r[0] == date_str]
        if month_prefix:
            return [r for r in rows if r and r[0].startswith(month_prefix)]
        return rows
    except Exception:
        return []

"""

# 업무현황 섹션 주석 앞에 삽입
MARKER = "\n# \u2500\u2500 \uc5c5\ubb34\ud604\ud669 \u2500\u2500"
content = content.replace(MARKER, HELPER + MARKER, 1)

# ── 2. save_work_items: 월별 시트 사용 ──
content = content.replace(
    'ws = _get_or_create_sheet("\uc5c5\ubb34\ud604\ud669", ["\ub0a0\uc9dc", "\ud56d\ubaa9", "1\uadfc", "2\uadfc", "3\uadfc", "\uc8fc\uac04", "\uc57c\uac04", "\ud569\uacc4", "\uc6d4\ub204\uacc4"])',
    'ws = _get_or_create_sheet(_work_sheet_name(selected_date), _WORK_HEADERS)'
)

# ── 3. load_work_items ──
OLD3 = (
    'def load_work_items(selected_date):\n'
    '    try:\n'
    '        ws = _get_or_create_sheet("\uc5c5\ubb34\ud604\ud669")\n'
    '        date_str = selected_date.strftime("%Y-%m-%d")\n'
    '        all_data = ws.get_all_values()\n'
    '        items = {}\n'
    '        for row in all_data[1:]:\n'
    '            if row and row[0] == date_str:\n'
    '                try:\n'
    '                    items[row[1]] = {\n'
    '                        "s1": int(float(row[2])) if row[2] else 0,\n'
    '                        "s2": int(float(row[3])) if row[3] else 0,\n'
    '                        "s3": int(float(row[4])) if row[4] else 0,\n'
    '                        "day": int(float(row[5])) if row[5] else 0,\n'
    '                        "night": int(float(row[6])) if row[6] else 0,\n'
    '                        "month_total": int(float(row[8])) if len(row) > 8 and row[8] else 0,\n'
    '                    }\n'
    '                except (ValueError, IndexError):\n'
    '                    pass\n'
    '        return items if items else None\n'
    '    except Exception:\n'
    '        return None'
)
NEW3 = (
    'def load_work_items(selected_date):\n'
    '    try:\n'
    '        date_str = selected_date.strftime("%Y-%m-%d")\n'
    '        rows = _read_work_sheet(_work_sheet_name(selected_date), date_str=date_str)\n'
    '        if not rows:\n'
    '            rows = _read_work_sheet("\uc5c5\ubb34\ud604\ud669", date_str=date_str)\n'
    '        items = {}\n'
    '        for row in rows:\n'
    '            try:\n'
    '                items[row[1]] = _parse_work_row(row)\n'
    '            except (ValueError, IndexError):\n'
    '                pass\n'
    '        return items if items else None\n'
    '    except Exception:\n'
    '        return None'
)
content = content.replace(OLD3, NEW3)

# ── 4. get_monthly_totals ──
OLD4 = (
    'def get_monthly_totals(selected_date):\n'
    '    """\ud574\ub2f9 \uc6d4 \ub204\uacc4\ub97c \ubc18\ud658\ud569\ub2c8\ub2e4. \uc120\ud0dd \ub0a0\uc9dc\ub294 \uc81c\uc678 (\uc774\uc911 \ud569\uc0b0 \ubc29\uc9c0)."""\n'
    '    try:\n'
    '        ws = _get_or_create_sheet("\uc5c5\ubb34\ud604\ud669")\n'
    '        month_prefix = selected_date.replace(day=1).strftime("%Y-%m-")\n'
    '        today_str = selected_date.strftime("%Y-%m-%d")\n'
    '        all_data = ws.get_all_values()\n'
    '        monthly = {}\n'
    '        for row in all_data[1:]:\n'
    '            if row and row[0].startswith(month_prefix) and row[0] != today_str:\n'
    '                name = row[1]\n'
    '                try:\n'
    '                    monthly[name] = monthly.get(name, 0) + (int(float(row[7])) if row[7] else 0)\n'
    '                except (ValueError, IndexError):\n'
    '                    pass\n'
    '        return monthly\n'
    '    except Exception:\n'
    '        return {}'
)
NEW4 = (
    'def get_monthly_totals(selected_date):\n'
    '    """\ud574\ub2f9 \uc6d4 \ub204\uacc4 \ubc18\ud658. \uc6d4\ubcc4+\ub808\uac70\uc2dc \uc2dc\ud2b8 \ud569\uc0b0. \uc120\ud0dd \ub0a0\uc9dc \uc81c\uc678."""\n'
    '    try:\n'
    '        month_prefix = selected_date.replace(day=1).strftime("%Y-%m-")\n'
    '        today_str = selected_date.strftime("%Y-%m-%d")\n'
    '        all_rows = (\n'
    '            _read_work_sheet(_work_sheet_name(selected_date), month_prefix=month_prefix)\n'
    '            + _read_work_sheet("\uc5c5\ubb34\ud604\ud669", month_prefix=month_prefix)\n'
    '        )\n'
    '        monthly = {}\n'
    '        seen = set()\n'
    '        for row in all_rows:\n'
    '            if not row or row[0] == today_str:\n'
    '                continue\n'
    '            key = (row[0], row[1] if len(row) > 1 else "")\n'
    '            if key in seen:\n'
    '                continue\n'
    '            seen.add(key)\n'
    '            name = row[1] if len(row) > 1 else ""\n'
    '            try:\n'
    '                monthly[name] = monthly.get(name, 0) + (int(float(row[7])) if len(row) > 7 and row[7] else 0)\n'
    '            except (ValueError, IndexError):\n'
    '                pass\n'
    '        return monthly\n'
    '    except Exception:\n'
    '        return {}'
)
content = content.replace(OLD4, NEW4)

# ── 5. has_saved_data ──
OLD5 = (
    'def has_saved_data(selected_date):\n'
    '    try:\n'
    '        ws = _get_or_create_sheet("\uc5c5\ubb34\ud604\ud669")\n'
    '        date_str = selected_date.strftime("%Y-%m-%d")\n'
    '        all_data = ws.get_all_values()\n'
    '        return any(row[0] == date_str for row in all_data[1:] if row)\n'
    '    except Exception:\n'
    '        return False'
)
NEW5 = (
    'def has_saved_data(selected_date):\n'
    '    try:\n'
    '        date_str = selected_date.strftime("%Y-%m-%d")\n'
    '        if _read_work_sheet(_work_sheet_name(selected_date), date_str=date_str):\n'
    '            return True\n'
    '        return bool(_read_work_sheet("\uc5c5\ubb34\ud604\ud669", date_str=date_str))\n'
    '    except Exception:\n'
    '        return False'
)
content = content.replace(OLD5, NEW5)

# ── 6. load_monthly_data ──
OLD6 = (
    '        ws_work = _retry(lambda: _get_or_create_sheet("\uc5c5\ubb34\ud604\ud669"))\n'
    '        for row in ws_work.get_all_values()[1:]:\n'
    '            if row and row[0].startswith(month_prefix):\n'
    '                d = row[0]\n'
    '                try:\n'
    '                    _work_dicts.setdefault(d, {})[row[1]] = {\n'
    '                        "name": row[1],\n'
    '                        "s1": int(float(row[2])) if len(row) > 2 and row[2] else 0,\n'
    '                        "s2": int(float(row[3])) if len(row) > 3 and row[3] else 0,\n'
    '                        "s3": int(float(row[4])) if len(row) > 4 and row[4] else 0,\n'
    '                        "day": int(float(row[5])) if len(row) > 5 and row[5] else 0,\n'
    '                        "night": int(float(row[6])) if len(row) > 6 and row[6] else 0,\n'
    '                        "month_total": int(float(row[8])) if len(row) > 8 and row[8] else 0,\n'
    '                    }\n'
    '                except (ValueError, IndexError):\n'
    '                    pass'
)
NEW6 = (
    '        _sheet_nm = "업무현황_{:04d}-{:02d}".format(year, month)\n'
    '        all_rows = (\n'
    '            _read_work_sheet(_sheet_nm, month_prefix=month_prefix)\n'
    '            + _read_work_sheet("\uc5c5\ubb34\ud604\ud669", month_prefix=month_prefix)\n'
    '        )\n'
    '        _seen_wk = set()\n'
    '        for row in all_rows:\n'
    '            if not row or not row[0].startswith(month_prefix):\n'
    '                continue\n'
    '            d = row[0]\n'
    '            name = row[1] if len(row) > 1 else ""\n'
    '            key = (d, name)\n'
    '            if key in _seen_wk:\n'
    '                continue\n'
    '            _seen_wk.add(key)\n'
    '            try:\n'
    '                item = _parse_work_row(row)\n'
    '                item["name"] = name\n'
    '                _work_dicts.setdefault(d, {})[name] = item\n'
    '            except (ValueError, IndexError):\n'
    '                pass'
)
content = content.replace(OLD6, NEW6)

open('utils/sheets.py', 'w', encoding='utf-8').write(content)

checks = [
    ('_work_sheet_name', '_work_sheet_name' in content),
    ('_parse_work_row', '_parse_work_row' in content),
    ('_read_work_sheet', '_read_work_sheet' in content),
    ('월별 save', '_work_sheet_name(selected_date), _WORK_HEADERS' in content),
    ('레거시 load', 'date_str=date_str' in content),
    ('monthly totals seen', 'seen = set()' in content),
    ('load_monthly _seen_wk', '_seen_wk' in content),
]
for name, ok in checks:
    print(f'{"OK" if ok else "FAIL"}: {name}')
