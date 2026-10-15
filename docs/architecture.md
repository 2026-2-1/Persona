# 구조와 변경 영향

`cli.py` 또는 `monitor.py` → `runner.run_study` → BrowserSession → observe → Brain(FastLoop + SlowLoop + MemoryStore) → ActionExecutor → 새 observe와 evaluate → JSON/JSONL/PNG.

2026-10-15 구현: #39의 기록 계약, #41의 Fast 단계별 생성, #42의 Slow reflection/plan review, #43의 실행별 조율은 코드에 연결됐다. #40에서 새 기억은 미산정으로 저장하고 Slow가 공통 예산으로 1~10점 중요도를 산정해 원본과 변경 사건을 분리한다. #54에서 `MemoryStore.retrieve`의 mode로 Fast 계획·행동 결정과 Slow의 검색 순위를 구분한다. #55에서 현재 단계·Slow snapshot의 보호 ID를 `MemoryStore`에 전달하고 상한 제거·캐시 정리를 맡긴다. Brain은 stage 경계의 완료 결과를 provenance로 검사해 채택하고, plan review는 observation/plan/version이 정확히 일치하는 decision에만 전달한다. 세부 정책과 남은 평가 범위는 [설계 초안](plans/2026-10-14-brain-two-loops.md)에 기록했다.

| 영역 | 파일 | 책임·회귀 영향 |
|---|---|---|
| 계약 | schemas.py | 설정·관찰·행동·결정·메모리; 모든 소비 모듈 확인 |
| 관찰 | observation.py | DOM 요약과 current registry; 숨김 텍스트·동명이인 ID·화면 갱신 |
| 실행 | actions.py, browser.py, security.py | origin·대상 검증, 상태 안정화, 브라우저 자원 |
| 판단 | brain.py, fast_loop.py, slow_loop.py, llm.py | 실행별 두 루프·결과 채택, 모델 출력·후보·fallback·비용/예산; 평가기와 분리 |
| 기억 | memory.py, slow_loop.py | 근거 기억·비동기 snapshot; 직접 브라우저 실행 금지 |
| 실행 상태 | runner.py, storage.py | 종료 사유·원자료·요약·자원 종료 |
| 성공 평가 | evaluator.py | fixture 성공 조건; 실제 과업 evaluator 확장 대상 |
| persona | personas.py | seed·분포·생성 provenance; 일반 AI 대조 조건 분리 필요 |
| 결과 | review.py | 후보·설문·인터뷰·HTML; null 결과와 근거 누락 확인 |
| 근거 소비 | trace.py, reports.py | 단계·작업·원본 기억을 행동 관찰 ID로 연결하고 출력; 구버전 로그 누락 허용 |
| 화면 | monitor.py, dashboard/ | 작업 시작·상태·최신 화면·API 키 비노출 |

새 기능은 관찰/행동/평가/분석/UI 중 책임을 정하고 작은 모듈을 추가한다. 동일 변경에 전체 구조 재작성을 포함하지 않는다. 새 계약은 기존 로그도 읽을 수 있게 버전과 기본값을 정의한다.

Brain 로그의 읽기 경계는 `brain_trace.py`다. monitor가 선택 실행의 선택적 JSONL을 읽고 reports/dashboard가 같은 brain 자료를 소비한다. 이 경계는 원본 파일을 변경하거나 평가/사람 검토 상태를 생성하지 않는다. 생성기 schemas 버전과 구버전 소비는 [D 계약](tasks/d-brain-trace-viewer.md)을 따른다.
