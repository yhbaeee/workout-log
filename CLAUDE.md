# 오늘의 운동기록 (Streamlit)

날짜별로 부위(어깨·가슴·등·하체)를 고르고 기본 운동 후보와 한조바디 자세 영상을 보며 세트별 중량·횟수를 기록하는 한국어 웹앱. 교육용 개인 미니 프로젝트. GitHub: yhbaeee/workout-log (public), Streamlit Community Cloud 배포.

## 명령
- 실행: `streamlit run app.py` (로컬은 `.venv` 사용: `.venv\Scripts\python -m streamlit run app.py`)
- 테스트: `.venv\Scripts\python -m pytest -q` (record_utils 41개)
- 브라우저 점검: Playwright(chromium)는 개발용으로만 `.venv`에 설치. `requirements.txt`에는 `streamlit>=1.40`만 둔다.

## 구조
- `app.py`: UI와 세션 상태·콜백만. 검증·기록 변환 로직을 넣지 않는다.
- `record_utils.py`: Streamlit 비의존 순수 로직(검증, 추가/수정/삭제, JSON 내보내기·복원). 입력 리스트를 변경하지 않고 새 리스트를 반환. 오류는 `ValidationError`(사용자에게 보여도 되는 메시지).
- `data/exercises.json`: 운동 카탈로그 26개(어깨 7·가슴 7·등 6·하체 6; 부위/장비/중량 기준/영상). `data/demo_records.json`: 가상 데모(record_id는 `demo-` 접두사).
- `docs/video_research.md`: 영상 조사 근거. `docs/screenshots/`: Playwright 캡처.
- `_prev/`: 초기 버전 보관(수정 금지, Git 제외).

## 규칙
- 모든 UI 문구는 한국어. 오류 메시지에 내부 예외를 그대로 노출하지 않는다.
- 기록은 `st.session_state`에만 둔다. 전역 변수·`st.cache_*`에 사용자 기록을 저장하지 않는다. 장기 보관은 JSON 백업.
- 기록 필드: record_id, date(YYYY-MM-DD), exercise_id, weight_kg, reps, memo. 부위·운동명·중량 기준은 카탈로그에서 조회. 세트 번호는 같은 날짜·운동 내 저장 순서.
- 세트 입력 위젯 키는 `행 uid`와 저장마다 증가하는 `nonce`를 포함한다(행 삭제 시 값이 섞이지 않고 중복 저장이 막힌다). 인덱스 기반 키를 쓰지 않는다.
- 저장·수정·삭제·복원은 `on_click` 콜백에서 처리하고 결과는 `flash`로 표시한다.
- 입력칸 기본값은 비워 둔다(운동 처방처럼 보이는 기본값 금지). 상한: 중량 1000kg, 횟수 1000회, 메모 200자.
- 영상 정보(제목·채널·URL·ID·길이·시작 시각)는 실제로 확인한 것만 넣는다. 추측 금지, 미확인은 `null`. 한조바디가 아닌 채널로 임의 대체 금지. 영상이 없으면 '참고 영상 준비 중'.
- 앱 실행 중 유튜브 검색·크롤링·외부 API 호출 없음. 경로는 `Path(__file__)` 기준.
- 운동 효과·부상 판단, 개인별 중량 처방, 1RM·볼륨·칼로리 계산은 넣지 않는다.
- 새 의존성은 꼭 필요할 때만 추가.

## 점검 시 알아둘 점
- Streamlit은 접힌 expander 안의 위젯도 DOM에 렌더한다. Playwright에서는 `details[open]`로 범위를 좁혀 찾는다.
- 번들 chromium 헤드리스는 유튜브 영상이 검은 화면으로 나온다. 영상 캡처는 `p.chromium.launch(channel="chrome")`(설치된 Chrome)을 쓰면 썸네일·플레이어가 로드된다.
- 날짜 입력은 year/month/day spinbutton으로 나뉘어 있다. 각각 click 후 숫자를 입력하고 Escape 후 다른 곳을 클릭해 확정한다.
- 화면 캡처는 `docs/screenshots/`에 `2-1a`~`2-3c` 이름으로 두며(결과보고서 2.1~2.3 대응), 재생성 시 Pillow로 상단 헤더와 하단 여백을 자른다(개발용, requirements 제외).
- 모바일(390px)에서는 columns가 세로로 쌓인다. 가로 스크롤은 없음을 확인함.
- 새로고침하면 세션이 초기화되어 기록이 사라지는 것이 설계상 동작이다.

## 점검 이력 (2026-10-27)
- pytest 41개 통과(운동 26개 확장 후에도 통과). Playwright 12개 시나리오 통과(부위 전환, 세트 추가·삭제 값 유지, 더블클릭 중복 저장 방지, 삭제 대상, 백업 다운로드/복원, 잘못된 파일, 초기화, 모바일 폭).
- 발견·수정: 전체 초기화 후 동의 체크박스가 체크된 채 남던 문제(키 기반 위젯으로 변경), 업로더에 5MB 제한 안내가 없던 문제(라벨에 표기).
- 최종 점검(26개 운동, push 후 배포본 확인은 사용자가 수행): 최종 버전 화면 캡처 8장 생성, 영상 임베드 재생 화면 확인(Chrome).

## 배포
- Community Cloud: 저장소 `yhbaeee/workout-log`, 브랜치 `main`, 파일 `app.py`, Python 3.12 권장(로컬은 3.15.1).
- push하면 배포 앱이 재배포된다. 외부 공개·push는 사용자 확인 후 진행.
