import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import record_utils as ru  # noqa: E402

PARTS, CATALOG = ru.load_catalog(ROOT / "data" / "exercises.json")
EX = "bench_press"


def rec(day="2026-10-27", ex=EX, w=40, reps=10, memo="", rid=None):
    return ru.make_record(day, ex, w, reps, memo, CATALOG, rid)


def test_catalog_has_four_parts_with_3_to_4_exercises():
    assert PARTS == ["어깨", "가슴", "등", "하체"]
    for p in PARTS:
        assert 3 <= len(ru.exercises_by_part(CATALOG, p)) <= 4


def test_add_valid_record_and_zero_weight():
    records = ru.add_records([], [rec(), rec(w=0)])
    assert len(records) == 2
    assert records[1]["weight_kg"] == 0.0
    assert len({r["record_id"] for r in records}) == 2


def test_add_does_not_mutate_input():
    base = [rec()]
    ru.add_records(base, [rec()])
    assert len(base) == 1


@pytest.mark.parametrize("w", [-1, -0.5, float("nan"), float("inf"), "40", None, True])
def test_bad_weight_rejected(w):
    with pytest.raises(ru.ValidationError):
        rec(w=w)


@pytest.mark.parametrize("reps", [0, -3, 2.5, "10", None, True, float("nan")])
def test_bad_reps_rejected(reps):
    with pytest.raises(ru.ValidationError):
        rec(reps=reps)


@pytest.mark.parametrize("day", ["2026-13-01", "2026-02-30", "20261027", "2026/10/27", "", None, "2026-1-5"])
def test_bad_date_rejected(day):
    with pytest.raises(ru.ValidationError):
        rec(day=day)


def test_unknown_exercise_rejected():
    with pytest.raises(ru.ValidationError):
        rec(ex="no_such_exercise")


def test_update_and_delete_target_only_that_record():
    a, b, c = rec(rid="a"), rec(rid="b"), rec(rid="c")
    records = [a, b, c]
    updated = ru.update_record(records, "b", 50, 8, "메모", CATALOG)
    assert [r["record_id"] for r in updated] == ["a", "b", "c"]
    assert updated[1]["weight_kg"] == 50 and updated[1]["reps"] == 8
    assert updated[0] == a and updated[2] == c
    assert records[1] == b  # 원본 불변

    remaining = ru.delete_record(updated, "b")
    assert [r["record_id"] for r in remaining] == ["a", "c"]


def test_update_rejects_invalid_and_keeps_data():
    records = [rec(rid="a")]
    with pytest.raises(ru.ValidationError):
        ru.update_record(records, "a", -5, 8, "", CATALOG)
    assert records[0]["weight_kg"] == 40.0
    with pytest.raises(ru.ValidationError):
        ru.update_record(records, "zzz", 10, 8, "", CATALOG)


def test_delete_missing_record_raises():
    with pytest.raises(ru.ValidationError):
        ru.delete_record([rec(rid="a")], "nope")


def test_duplicate_record_id_rejected_on_add():
    with pytest.raises(ru.ValidationError):
        ru.add_records([rec(rid="a")], [rec(rid="a")])


def test_group_by_exercise_keeps_order():
    day = [rec(ex="bench_press", rid="1"), rec(ex="db_press", rid="2"), rec(ex="bench_press", rid="3")]
    groups = ru.group_by_exercise(day)
    assert [r["record_id"] for r in groups["bench_press"]] == ["1", "3"]


def test_export_then_restore_roundtrip():
    records = ru.add_records([], [rec(memo="한글 메모"), rec(day="2026-10-28", ex="squat", w=60.5, reps=5)])
    restored, err = ru.try_restore([], ru.export_json(records), CATALOG)
    assert err is None
    assert restored == records


def test_demo_file_is_valid_and_flagged():
    text = (ROOT / "data" / "demo_records.json").read_text(encoding="utf-8")
    records = ru.parse_backup(text, CATALOG)
    assert records and ru.is_demo(records)
    assert not ru.is_demo([rec()])


BAD_FILES = {
    "not json": "{broken",
    "wrong app": json.dumps({"app": "other", "version": 1, "records": []}),
    "wrong version": json.dumps({"app": ru.APP_NAME, "version": 99, "records": []}),
    "no records": json.dumps({"app": ru.APP_NAME, "version": 1}),
    "list root": "[]",
    "NaN weight": '{"app":"%s","version":1,"records":[{"record_id":"x","date":"2026-10-27","exercise_id":"bench_press","weight_kg":NaN,"reps":5}]}' % ru.APP_NAME,
    "bad exercise": json.dumps({"app": ru.APP_NAME, "version": 1, "records": [
        {"record_id": "x", "date": "2026-10-27", "exercise_id": "zzz", "weight_kg": 1, "reps": 1}]}),
    "dup ids": json.dumps({"app": ru.APP_NAME, "version": 1, "records": [
        {"record_id": "x", "date": "2026-10-27", "exercise_id": EX, "weight_kg": 1, "reps": 1},
        {"record_id": "x", "date": "2026-10-27", "exercise_id": EX, "weight_kg": 1, "reps": 1}]}),
    "non-dict item": json.dumps({"app": ru.APP_NAME, "version": 1, "records": [1]}),
}


@pytest.mark.parametrize("name", list(BAD_FILES))
def test_invalid_restore_keeps_existing_records(name):
    current = [rec(rid="keep")]
    result, err = ru.try_restore(current, BAD_FILES[name], CATALOG)
    assert err
    assert result is current
    assert result == [rec(rid="keep")] or result[0]["record_id"] == "keep"
