# 현재 구현 상태

## 2026-10-19 prototype 통합 기준

기준 커밋은 `9095b3c7896d7080a39d59fb6492251491139fb6`이다. 팀원이 [#101](https://github.com/2026-2-1/Persona/pull/101)을 일반 merge로 병합하면서 #95~#99도 함께 병합 처리됐다. #100의 D 보완은 #101에 보존돼 #100은 대체 종료했고, 병합된 6개 원격 브랜치는 삭제했다. 이번 병합을 순차 squash로 기록하지 않는다. `main`은 이번 작업 대상이 아니다.

password 타입 정규화, Slow 민감 출력 저장 차단, GPU hover/select 정보 보존, 실제 취소의 최종 기록과 취소 재전파, 실패 재설문의 과거 성공 파일 제거 5건이 모두 들어 있다. 병합 후 전체 파일 tree는 준비한 #101 `fe94fe3`과 동일하다. [수정 이력](handoffs/2026-10-19-review-fixes.md), [최종 검증과 재현 절차](handoffs/2026-10-19-prototype-verification.md)를 따른다.

| 확인 범위 | 결과 |
| --- | --- |
| 병합 후 Ubuntu/Python 3.11 CI | 574 passed, doctor·Mock 통과 |
| 병합 후 Windows/Python 3.13 CI | 569 passed, POSIX SSH/agent 5 skipped, doctor·Mock 통과 |
| 이번 macOS 화면·검토·출력 집중 회귀 | 54 passed, 실제 Chromium/HTTP 사용 |
| 이번 macOS doctor | Python 3.13.13 / Playwright 1.55.0, 설정 오류 없음 |
| 실제 GPU 과업·공개 사이트·인간 판단 비교 | 이번 통합 검증 범위 밖, 후속 검증 |

원격 결과는 [prototype CI](https://github.com/2026-2-1/Persona/actions/runs/39208715049)에 있다. 필수 승인 1명, Ubuntu/Windows CI와 최신 대상 브랜치, 대화 해결, 관리자 적용 조건을 유지한다. 병합 여부·자동 검사·팀원 독립 재현은 각각 확인하며, #36은 독립 재현 전 자동 종료하지 않는다.

## 현재 실행 흐름

- Python 3.11+ / Playwright Chromium / Pydantic 기반 로컬 실행기다. Mock, OpenAI, Claude, Gemini, Jev+Gemini와 로컬 SSH 터널의 GPU Qwen 경로를 제공한다. 모든 제공자의 실제 모델 품질을 이번 CI로 검증한 것은 아니다.
- Fast Loop: 첫 perceive → plan → act, 이후 feedback/perceive 동시 실행 → plan → act. 이유 Thought·Plan·모든 행동 제안을 실행 전에 저장하고 첫 제안만 실행한다. [#83 계약](tasks/83-u-fast.md).
- Slow Loop: 첫 인식 뒤 실행별 단일 worker가 reflect → wonder → memory.update를 반복한다. 성찰과 생각은 공유 기억에 직접 저장한다. 새 실행에는 plan_review·stage 채택 게이트·1% draw가 없다. [#84 계약](tasks/84-u-slow.md).
- 기억: 기본 활성 64개, 설정 범위 10~64개. 미산정 기억을 우선 보존하고 낮은 중요도·동점 오래된 순으로 제거한다. 제거 뒤에도 seq는 단조 증가하며 전체 trace를 보존한다. U 검색·분리 GPU embedding·늦은 점수/벡터의 활성 ID 정합성은 [#85 계약](tasks/85-u-memory.md)을 따른다.
- 관찰: U DOM parser가 HTML과 semantic ID를 구성하고 제한 시간 내 DOM/network quiet를 기다린다. legacy 크기 상한 초과는 기록하며 원본 관찰을 조용히 자르지 않는다. password 값은 type 표기 대소문자와 무관하게 가린다. [#86 계약](tasks/86-u-observation.md).
- 행동: semantic ID 기반 click/type/raw type/hover/select/clear, 좌표 click, scroll, key, URL/history/reload, 탭 전환·열기·닫기를 실행한다. AI 경로에 allowed-origin·최신 observation/registry·capability gate를 붙이지 않으며 없는 대상·탭과 Playwright 실패는 도구 오류로 기록한다. scripted scenario의 별도 origin/read-only 경계는 유지한다. [#87 계약](tasks/87-u-actions.md).
- 종료·평가: AI terminate, 단계/시간/예산 제한, 중지, 모델/브라우저 오류는 종료 사유다. Brain/Slow 정리 뒤 브라우저가 열린 상태에서 새 최종 관찰을 저장하고 독립 평가를 한 번 한다. step 판정을 사후 성공으로 덮어쓰지 않으며 캡처/평가 실패는 unknown이다. [#89 계약](tasks/89-u-termination-evaluation.md).
- 설문: 질문지와 제거 기억을 포함한 전체 누적 trace를 모델에 전달한다. batch는 모든 browser 세션이 끝난 뒤 설문한다. 공통 예산·호출 usage와 출처를 기록하고 실패 시 과거 성공 답변을 최신 결과로 남기지 않는다. 답변은 `simulated_self_report`다. [#88 계약](tasks/88-u-survey.md).
- 호출 기록: `llm_calls.jsonl` v2는 로컬 요청·응답·검색 기억·시각과 method를 보존한다. 민감정보 의심 값은 치환하고 Slow 민감 출력은 단계/기억 저장 전에 차단한다. 대시보드 API·CLI 검토 HTML·네 형식 내보내기는 호출 전문을 제외한다. [#90 계약](tasks/90-u-transition-08.md).
- 요청/토큰 기본 상한은 무제한이다. 실행별 단계·시간·예산 제한과 사용자 stop을 지원한다. 실제 GPU 파일럿은 유한 요청/토큰/시간 예산을 먼저 정해야 한다.

## 검토와 대시보드

- D-01: 카드 ID·근거 버전·검토자 별칭·5종 판정·메모를 서버 JSONL에 저장한다. 서버 성공 확인 뒤 최신 판정을 표시하며 저장 실패·버전 충돌·중복 제출을 구분한다.
- D-02: 자동 갱신과 다른 실행 왕복에서 미저장 초안·포커스·선택을 유지한다. 지연 조회/저장 응답이 다른 실행이나 최신 판정을 덮어쓰지 않는다. 새로고침 후 미저장 초안 복원은 범위 밖이며 저장 판정은 유지된다.
- D-03: 현재/이전 근거 버전의 검토 이력, 실행 방식, Mock/합성/실사이트 출처를 표시한다. 출처가 없는 구형 기록은 unknown이며 사람 판정은 독립 verification을 바꾸지 않는다.
- D-04: 예정 분모·실행/취소/미실행 상태·중앙값 계산 대상·전체/부분 측정·누락 세션 수를 표시한다. 실제 0과 미확인, 대상 행동 없음을 구분하고 scripted 점검을 AI 비교에서 제외한다.
- D-05와 U 소비: 최종 평가의 observation 출처, 설문 답변, 매 반복 Wonder의 빈 응답·생각·저장 여부, 구형 Brain 8상태/채택·폐기·추첨을 구분한다. 카드와 Brain 기록을 JSON/CSV/Markdown/HTML로 내보낸다. [재현과 남은 팀 검증](tasks/d-review-export-verification.md).
- 설정은 목표 → 사용자 → 모델 → 실행의 4단계다. 키는 서버 프로세스 메모리에서 관리하고 브라우저 저장소·보고서에 넣지 않는다. 설정 도우미의 AI 추천은 사용자 적용을 거친다. 로컬 단색 UI와 모바일 한 열을 유지한다.

## GPU 연결과 실제 확인 범위

비공개 GPU 설정이 있는 dashboard는 SSH·Slurm 단일 할당·Qwen/분리 embedding·터널·health/probe를 준비하고 종료 시 자신이 소유한 작업만 반환한다. 수동 터널도 지원한다. macOS 키체인 비밀번호 또는 최초 등록한 SSH 키/agent 경로를 사용한다. [수명주기와 복구 안내](tasks/gpu-dashboard-lifecycle.md).

2026-10-18의 실제 확인 범위는 Qwen health, CUDA embedding 벡터, 소유 작업 반환이다. 현재 통합 코드의 실제 Qwen 생성→브라우저 과업→종료 설문 완주는 후속이다. Windows의 실제 SSH/Slurm과 비정상 종료·네트워크 단절 복구도 별도 확인한다. 이미 시작한 원격 HTTP의 취소가 원격 추론·과금 중단을 보장하지 않는다.

## 남은 검증과 연구

1. 다른 팀원의 새 환경 재현: 후보 → 근거 → 저장 → 새로고침 → 네 형식 결과 일치. #36에 OS·커밋·결과를 남긴다.
2. 실제 Qwen 파일럿: 유한 예산에서 Fast/Slow·embedding·독립 평가·질문지 설문 전체 경로를 확인한다.
3. 큰 페이지·긴 실행: 조각 요약 정보 손실, hover/select, 활성 기억 64개 초과, 긴 trace의 실제 context 한도를 확인한다.
4. 실제 중지·SSH 단절: 기록 보존, worker 합류, 소유 Slurm 작업 반환/복구를 확인한다.
5. 인간 평가와 비교: 2인 판정·합의, 개선 전후 재현, 모델/프롬프트/검색/Slow 조건의 통제 실험을 설계한다. 기업 데이터는 사용자 확인 기준 미수령 0건이다.

공개 데카트론의 과거 부분 점검은 지정 검색 결과와 러닝화 상세 이름·80,000원 상한에 한정한다. 홈페이지 검색 제출·색상·사이즈·재고·픽업·전체 네 과업의 성공은 검증하지 않았다. iframe/canvas/복잡한 shadow DOM/custom combobox의 범용 처리는 보장하지 않는다. Qwen 큰 화면 조각 요약은 U 원본 전체 HTML 입력과 다르므로 동등 성능을 주장하지 않는다.

ChatGPT 구독 OAuth, 근거 Q&A, 전체 서비스 큐/DB, 환경별 비교와 연구용 Slow off/빈도 제어는 후속이다. 과거 plan_review·1% 정책 실험안은 현재 U 기준에 맞춰 다시 합의한다. [개발 순서](roadmap.md), [연구 계획](research/2026-10-15-slow-loop-experiment-plan.md).

## 과거 구현과 검증 기록

날짜별 기록은 당시 커밋과 정책을 설명한다. 현재 완료 상태는 위 통합 기준을 따른다.

- [검증 누적 기록](verification.md)
- [10/19 검토 5건 수정과 준비 이력](handoffs/2026-10-19-review-fixes.md)
- [10/18 D/U 통합 검증](handoffs/2026-10-18-d-u-integration.md)
- [10/16 prototype 병합 기록](handoffs/2026-10-16-prototype-merge-queue.md)
- [10/14 D 진행과 회의 안건](meetings/2026-10-14-d-progress-and-decisions.md)
