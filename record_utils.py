"""운동 기록 처리 로직 (Streamlit 비의존).

기록은 dict 리스트이며 필드는 record_id, date, exercise_id, weight_kg, reps, memo.
모든 함수는 입력 리스트를 변경하지 않고 새 리스트를 반환한다.
"""
import json
import math
import re
import uuid
from datetime import datetime
from pathlib import Path

APP_NAME = "오늘의 운동기록"
BACKUP_VERSION = 1
MAX_WEIGHT_KG = 1000
MAX_REPS = 1000
MAX_MEMO_LEN = 200
MAX_RECORDS = 20000

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class ValidationError(ValueError):
    """사용자에게 그대로 보여줘도 되는 검증 오류."""


def load_catalog(path):
    """exercises.json을 읽어 (부위 목록, {exercise_id: 운동 dict})를 반환."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return data["parts"], {e["id"]: e for e in data["exercises"]}


def exercises_by_part(catalog, part):
    return [e for e in catalog.values() if e["part"] == part]


def validate_date(value):
    if hasattr(value, "isoformat") and not isinstance(value, str):
        value = value.isoformat()
    if not isinstance(value, str) or not _DATE_RE.match(value):
        raise ValidationError("날짜는 YYYY-MM-DD 형식이어야 합니다.")
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        raise ValidationError("존재하지 않는 날짜입니다.") from None
    return value


def validate_weight(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError("중량은 숫자로 입력해 주세요.")
    value = float(value)
    if not math.isfinite(value):
        raise ValidationError("중량 값이 올바르지 않습니다.")
    if value < 0:
        raise ValidationError("중량은 0 이상이어야 합니다.")
    if value > MAX_WEIGHT_KG:
        raise ValidationError(f"중량은 {MAX_WEIGHT_KG}kg 이하로 입력해 주세요.")
    return value


def validate_reps(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError("반복 횟수는 숫자로 입력해 주세요.")
    if isinstance(value, float):
        if not math.isfinite(value) or not value.is_integer():
            raise ValidationError("반복 횟수는 정수여야 합니다.")
        value = int(value)
    if value < 1:
        raise ValidationError("반복 횟수는 1 이상이어야 합니다.")
    if value > MAX_REPS:
        raise ValidationError(f"반복 횟수는 {MAX_REPS}회 이하로 입력해 주세요.")
    return value


def validate_memo(value):
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValidationError("메모는 문자열이어야 합니다.")
    value = value.strip()
    if len(value) > MAX_MEMO_LEN:
        raise ValidationError(f"메모는 {MAX_MEMO_LEN}자 이하로 입력해 주세요.")
    return value


def make_record(day, exercise_id, weight_kg, reps, memo, catalog, record_id=None):
    """검증을 거친 기록 dict를 만든다. 실패하면 ValidationError."""
    if exercise_id not in catalog:
        raise ValidationError("존재하지 않는 운동입니다.")
    if record_id is not None and (not isinstance(record_id, str) or not record_id):
        raise ValidationError("기록 ID가 올바르지 않습니다.")
    return {
        "record_id": record_id or uuid.uuid4().hex,
        "date": validate_date(day),
        "exercise_id": exercise_id,
        "weight_kg": validate_weight(weight_kg),
        "reps": validate_reps(reps),
        "memo": validate_memo(memo),
    }


def add_records(records, new_records):
    """여러 세트를 한 번에 추가. 하나라도 ID가 겹치면 거부."""
    ids = {r["record_id"] for r in records}
    for r in new_records:
        if r["record_id"] in ids:
            raise ValidationError("이미 저장된 기록입니다.")
        ids.add(r["record_id"])
    if len(records) + len(new_records) > MAX_RECORDS:
        raise ValidationError("저장할 수 있는 기록 수를 넘었습니다.")
    return records + list(new_records)


def update_record(records, record_id, weight_kg, reps, memo, catalog):
    """중량·횟수·메모만 수정한다 (날짜·운동은 유지)."""
    for i, r in enumerate(records):
        if r["record_id"] == record_id:
            updated = make_record(
                r["date"], r["exercise_id"], weight_kg, reps, memo, catalog, record_id
            )
            return records[:i] + [updated] + records[i + 1:]
    raise ValidationError("수정할 기록을 찾을 수 없습니다.")


def delete_record(records, record_id):
    if not any(r["record_id"] == record_id for r in records):
        raise ValidationError("삭제할 기록을 찾을 수 없습니다.")
    return [r for r in records if r["record_id"] != record_id]


def records_on(records, day):
    return [r for r in records if r["date"] == day]


def group_by_exercise(day_records):
    """같은 날짜 기록을 운동별로 묶는다. 세트 번호는 저장 순서(1부터)."""
    groups = {}
    for r in day_records:
        groups.setdefault(r["exercise_id"], []).append(r)
    return groups


def export_json(records, now=None):
    now = now or datetime.now()
    payload = {
        "app": APP_NAME,
        "version": BACKUP_VERSION,
        "exported_at": now.isoformat(timespec="seconds"),
        "records": records,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _reject_constant(name):
    raise ValidationError("올바르지 않은 숫자 값이 포함되어 있습니다.")


def parse_backup(text, catalog):
    """백업 JSON 문자열을 검증해 기록 리스트를 반환. 실패하면 ValidationError."""
    try:
        data = json.loads(text, parse_constant=_reject_constant)
    except ValidationError:
        raise
    except (ValueError, RecursionError):
        raise ValidationError("JSON 파일을 읽을 수 없습니다.") from None
    if not isinstance(data, dict) or data.get("app") != APP_NAME:
        raise ValidationError("이 앱의 백업 파일이 아닙니다.")
    if data.get("version") != BACKUP_VERSION:
        raise ValidationError("지원하지 않는 백업 버전입니다.")
    raw = data.get("records")
    if not isinstance(raw, list):
        raise ValidationError("기록 목록이 없습니다.")
    if len(raw) > MAX_RECORDS:
        raise ValidationError("기록 수가 너무 많습니다.")
    records, seen = [], set()
    for item in raw:
        if not isinstance(item, dict):
            raise ValidationError("기록 형식이 올바르지 않습니다.")
        rec = make_record(
            item.get("date"),
            item.get("exercise_id"),
            item.get("weight_kg"),
            item.get("reps"),
            item.get("memo", ""),
            catalog,
            item.get("record_id"),
        )
        if rec["record_id"] in seen:
            raise ValidationError("중복된 기록 ID가 있습니다.")
        seen.add(rec["record_id"])
        records.append(rec)
    return records


def try_restore(current, text, catalog):
    """복원 시도. 성공하면 (새 기록, None), 실패하면 (기존 기록, 오류 메시지)."""
    try:
        return parse_backup(text, catalog), None
    except ValidationError as e:
        return current, str(e)


def is_demo(records):
    return any(r["record_id"].startswith("demo-") for r in records)
