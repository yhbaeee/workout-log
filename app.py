from datetime import date
from pathlib import Path

import streamlit as st

import record_utils as ru

BASE = Path(__file__).resolve().parent
PARTS, CATALOG = ru.load_catalog(BASE / "data" / "exercises.json")
DEMO_PATH = BASE / "data" / "demo_records.json"
INITIAL_ROWS = 3

st.set_page_config(page_title=ru.APP_NAME, page_icon="🏋️", layout="centered")


# ---------- 세션 상태 ----------
def init_state():
    ss = st.session_state
    ss.setdefault("records", [])
    ss.setdefault("uid", 0)
    ss.setdefault("rows", {})        # exercise_id -> [row uid, ...]
    ss.setdefault("nonce", {})       # exercise_id -> 저장 후 입력칸 초기화용 번호
    ss.setdefault("saved_nonces", set())
    ss.setdefault("flash", {})       # 영역 이름 -> (종류, 메시지)
    ss.setdefault("pending_delete", None)
    ss.setdefault("pending_restore", None)
    ss.setdefault("pending_demo", False)
    ss.setdefault("confirm_reset", False)
    ss.setdefault("uploader_n", 0)


def new_uid():
    st.session_state.uid += 1
    return st.session_state.uid


def rows_for(ex_id):
    ss = st.session_state
    if ex_id not in ss.rows:
        ss.rows[ex_id] = [new_uid() for _ in range(INITIAL_ROWS)]
    return ss.rows[ex_id]


def nonce_for(ex_id):
    return st.session_state.nonce.setdefault(ex_id, 0)


def flash(area, kind, msg):
    st.session_state.flash[area] = (kind, msg)


def show_flash(area):
    item = st.session_state.flash.pop(area, None)
    if item:
        getattr(st, item[0])(item[1])


# ---------- 콜백 ----------
def add_row(ex_id):
    rows_for(ex_id).append(new_uid())


def remove_row(ex_id, uid):
    rows = rows_for(ex_id)
    if len(rows) > 1:
        rows.remove(uid)


def save_sets(ex_id, day_key):
    ss = st.session_state
    nonce = nonce_for(ex_id)
    token = (ex_id, nonce)
    if token in ss.saved_nonces:  # 같은 입력창의 중복 저장 방지
        return
    new = []
    try:
        day = ru.validate_date(ss[day_key])
        for n, uid in enumerate(rows_for(ex_id), start=1):
            w = ss.get(f"w_{ex_id}_{nonce}_{uid}")
            r = ss.get(f"r_{ex_id}_{nonce}_{uid}")
            if w is None and r is None:
                continue
            if w is None or r is None:
                raise ru.ValidationError(f"{n}번째 입력 행의 중량과 횟수를 모두 입력해 주세요.")
            memo = ss.get(f"m_{ex_id}_{nonce}_{uid}", "")
            try:
                new.append(ru.make_record(day, ex_id, w, r, memo, CATALOG))
            except ru.ValidationError as e:
                raise ru.ValidationError(f"{n}번째 입력 행: {e}") from None
        if not new:
            raise ru.ValidationError("저장할 세트가 없습니다. 중량과 횟수를 입력해 주세요.")
        ss.records = ru.add_records(ss.records, new)
    except ru.ValidationError as e:
        flash(f"rec_{ex_id}", "error", str(e))
        return
    ss.saved_nonces.add(token)
    ss.nonce[ex_id] = nonce + 1
    ss.rows[ex_id] = [new_uid() for _ in range(INITIAL_ROWS)]
    flash(f"rec_{ex_id}", "success", f"{day} {CATALOG[ex_id]['name']} {len(new)}세트를 저장했습니다.")


def save_edit(record_id):
    ss = st.session_state
    try:
        ss.records = ru.update_record(
            ss.records,
            record_id,
            ss.get(f"ew_{record_id}"),
            ss.get(f"er_{record_id}"),
            ss.get(f"em_{record_id}", ""),
            CATALOG,
        )
        flash(f"edit_{record_id}", "success", "수정했습니다.")
    except ru.ValidationError as e:
        flash(f"edit_{record_id}", "error", str(e))


def ask_delete(record_id):
    st.session_state.pending_delete = record_id


def cancel_delete():
    st.session_state.pending_delete = None


def confirm_delete(record_id):
    ss = st.session_state
    try:
        ss.records = ru.delete_record(ss.records, record_id)
        flash("view", "success", "기록을 삭제했습니다.")
    except ru.ValidationError as e:
        flash("view", "error", str(e))
    ss.pending_delete = None


def apply_records(new_records, message):
    ss = st.session_state
    ss.records = new_records
    ss.pending_restore = None
    ss.pending_demo = False
    ss.pending_delete = None
    flash("backup", "success", message)


def load_demo():
    text = DEMO_PATH.read_text(encoding="utf-8")
    apply_records(ru.parse_backup(text, CATALOG), "가상 데모 기록을 불러왔습니다.")


def ask_demo():
    if st.session_state.records:
        st.session_state.pending_demo = True
    else:
        load_demo()


def cancel_demo():
    st.session_state.pending_demo = False


def do_restore():
    ss = st.session_state
    if ss.pending_restore is not None:
        apply_records(ss.pending_restore, "백업 파일로 기록을 복원했습니다.")
        ss.uploader_n += 1


def cancel_restore():
    st.session_state.pending_restore = None
    st.session_state.uploader_n += 1


def do_reset():
    apply_records([], "모든 기록을 삭제했습니다.")
    st.session_state.confirm_reset = False


# ---------- 화면 조각 ----------
def video_block(ex):
    v = ex.get("video")
    if not v or not v.get("url"):
        st.caption("참고 영상 준비 중")
        return
    start = v.get("start_sec") or 0
    if st.toggle("자세 영상 보기", key=f"vt_{ex['id']}"):
        try:
            st.video(v["url"], start_time=start)
        except Exception:
            st.warning("영상을 표시하지 못했습니다. 아래 버튼으로 유튜브에서 열어 주세요.")
    link = v["url"] + (f"&t={start}s" if start else "")
    st.link_button("유튜브에서 열기", link)
    dur = v.get("duration_sec")
    length = f"{dur // 60}:{dur % 60:02d}" if dur else "길이 미확인"
    st.caption(f"{v['channel']} · {v['title']} · {length}")


def input_rows(ex):
    ex_id = ex["id"]
    nonce = nonce_for(ex_id)
    rows = rows_for(ex_id)
    for n, uid in enumerate(rows, start=1):
        st.markdown(f"**{n}세트**")
        c1, c2 = st.columns(2)
        c1.number_input("중량(kg)", min_value=0.0, step=0.5, value=None,
                        key=f"w_{ex_id}_{nonce}_{uid}", format="%g")
        c2.number_input("반복 횟수", min_value=1, step=1, value=None,
                        key=f"r_{ex_id}_{nonce}_{uid}")
        st.text_input("메모 (선택)", key=f"m_{ex_id}_{nonce}_{uid}", max_chars=ru.MAX_MEMO_LEN)
        if len(rows) > 1:
            st.button("이 세트 삭제", key=f"rm_{ex_id}_{nonce}_{uid}",
                      on_click=remove_row, args=(ex_id, uid))
    st.button("＋ 세트 추가", key=f"add_{ex_id}_{nonce}", on_click=add_row, args=(ex_id,))


def exercise_card(ex, day_key):
    ex_id = ex["id"]
    with st.expander(f"{ex['name']} · {ex['equipment']}"):
        st.caption(f"중량 입력 기준: {ex['weight_basis']}")
        video_block(ex)
        st.divider()
        show_flash(f"rec_{ex_id}")
        input_rows(ex)
        st.button("저장", key=f"save_{ex_id}_{nonce_for(ex_id)}", type="primary",
                  on_click=save_sets, args=(ex_id, day_key))


# ---------- 탭 ----------
def tab_record():
    st.date_input("날짜", value=date.today(), key="record_day")
    part = st.radio("부위", PARTS, horizontal=True)
    st.subheader(f"{part} 기본 운동 후보")
    st.caption("운동을 열어 세트별 중량과 반복 횟수를 입력하세요. 칸은 비어 있는 상태로 시작합니다.")
    for ex in ru.exercises_by_part(CATALOG, part):
        exercise_card(ex, "record_day")


def tab_view():
    day = st.date_input("조회할 날짜", value=date.today(), key="view_day").isoformat()
    show_flash("view")
    day_records = ru.records_on(st.session_state.records, day)
    if not day_records:
        st.info("이 날짜에 저장된 기록이 없습니다.")
        return
    for ex_id, sets in ru.group_by_exercise(day_records).items():
        ex = CATALOG[ex_id]
        st.markdown(f"#### {ex['name']}  \n{ex['part']} · {ex['equipment']} · 총 {len(sets)}세트")
        for n, r in enumerate(sets, start=1):
            rid = r["record_id"]
            memo = f" · {r['memo']}" if r["memo"] else ""
            with st.expander(f"{n}세트 · {r['weight_kg']:g}kg × {r['reps']}회{memo}"):
                show_flash(f"edit_{rid}")
                c1, c2 = st.columns(2)
                c1.number_input("중량(kg)", min_value=0.0, step=0.5, value=r["weight_kg"],
                                key=f"ew_{rid}", format="%g")
                c2.number_input("반복 횟수", min_value=1, step=1, value=r["reps"], key=f"er_{rid}")
                st.text_input("메모", value=r["memo"], key=f"em_{rid}", max_chars=ru.MAX_MEMO_LEN)
                b1, b2 = st.columns(2)
                b1.button("수정 저장", key=f"es_{rid}", on_click=save_edit, args=(rid,))
                b2.button("삭제", key=f"ed_{rid}", on_click=ask_delete, args=(rid,))
                if st.session_state.pending_delete == rid:
                    st.warning(f"{n}세트 기록을 삭제할까요? 되돌릴 수 없습니다.")
                    d1, d2 = st.columns(2)
                    d1.button("삭제 확인", key=f"edc_{rid}", type="primary",
                              on_click=confirm_delete, args=(rid,))
                    d2.button("취소", key=f"edn_{rid}", on_click=cancel_delete)


def tab_backup():
    ss = st.session_state
    show_flash("backup")
    if ru.is_demo(ss.records):
        st.warning("현재 기록에 가상 데모 데이터가 포함되어 있습니다. 실제 기록이 아닙니다.")

    st.markdown("#### 백업 내려받기")
    st.caption(f"현재 기록 {len(ss.records)}세트")
    st.download_button("JSON 백업 다운로드", data=ru.export_json(ss.records),
                       file_name=f"workout_backup_{date.today().isoformat()}.json",
                       mime="application/json")

    st.markdown("#### 백업에서 복원")
    st.caption("복원하면 현재 기록이 모두 백업 파일의 기록으로 교체됩니다.")
    up = st.file_uploader("백업 JSON 파일", type=["json"], key=f"uploader_{ss.uploader_n}")
    if up is not None and ss.pending_restore is None:
        if up.size > 5_000_000:
            st.error("파일이 너무 큽니다.")
        else:
            try:
                text = up.getvalue().decode("utf-8")
            except UnicodeDecodeError:
                text = ""
            records, err = ru.try_restore(ss.records, text, CATALOG)
            if err:
                st.error(f"복원할 수 없습니다. 기존 기록은 그대로 유지됩니다. ({err})")
            elif ss.records:
                ss.pending_restore = records
                st.rerun()
            else:
                apply_records(records, "백업 파일로 기록을 복원했습니다.")
                ss.uploader_n += 1
                st.rerun()
    if ss.pending_restore is not None:
        st.warning(f"기존 {len(ss.records)}세트를 백업의 {len(ss.pending_restore)}세트로 교체할까요?")
        c1, c2 = st.columns(2)
        c1.button("교체 확인", type="primary", on_click=do_restore)
        c2.button("취소", key="cancel_restore", on_click=cancel_restore)

    st.markdown("#### 데모 기록")
    st.caption("실제 사용자 정보가 없는 가상의 운동 기록입니다.")
    st.button("데모 기록 불러오기", on_click=ask_demo)
    if ss.pending_demo:
        st.warning("기존 기록이 모두 가상 데모 기록으로 교체됩니다. 계속할까요?")
        c1, c2 = st.columns(2)
        c1.button("데모로 교체", type="primary", on_click=load_demo)
        c2.button("취소", key="cancel_demo", on_click=cancel_demo)

    st.markdown("#### 전체 기록 초기화")
    st.checkbox("모든 기록을 삭제하는 것에 동의합니다", key="confirm_reset")
    st.button("전체 초기화", disabled=not (ss.confirm_reset and ss.records), on_click=do_reset)


def main():
    init_state()
    st.title("🏋️ 오늘의 운동기록")
    st.caption("날짜와 부위를 고르고, 기본 운동 후보의 자세 영상을 참고하며 세트별 중량과 횟수를 기록하세요.")
    st.info("기록은 현재 세션에서 관리됩니다. 세션이 종료되거나 초기화되면 사라질 수 있으므로 "
            "사용 후 JSON 백업 파일을 저장해 주세요.")
    t1, t2, t3 = st.tabs(["기록하기", "기록 보기", "백업·복원"])
    with t1:
        tab_record()
    with t2:
        tab_view()
    with t3:
        tab_backup()
    st.divider()
    st.caption("참고 영상과 운동 목록은 일반적인 정보입니다. 개인 상태에 따른 운동 처방을 제공하지 않습니다.")


main()
