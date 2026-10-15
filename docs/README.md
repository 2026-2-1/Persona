# 문서 안내

AI와 개발자는 아래 순서로 읽는다. 완료 상태의 기준은 현재 코드와 실제 검증 결과이며, 기획 문서의 제안은 구현 완료를 뜻하지 않는다.

| 문서 | 목적 |
|---|---|
| [최신 PR 통합 검증](handoffs/2026-10-16-latest-pr-integration.md) | #79 + #78 후속 + D/C 통합·403개 검사·실제 화면/네 형식 출력·남은 범위 |
| [10/15 GitHub 확인](handoffs/2026-10-15-latest-github-review.md) | 통합 전 원격 #66/#71~#79 구현·preview 차이·분기 확인 이력 |
| [연구·데이터 회의 안건](meetings/2026-10-15-research-and-data-agenda.md) | Slow 정의·실험 조건·데이터·Novelty·담당/기한 결정표 |
| [Slow 실행·검색 실험 계획](research/2026-10-15-slow-loop-experiment-plan.md) | 빈도와 검색 정책의 단계별 비교·실제 입력 소비·예산·평가 분리 |
| [제출 초안 3항목](research/2026-10-15-project-submission-draft.md) | 기업 데이터 미수령 0건·시스템 구조도/구현 범위·핵심 논문 주제 |
| [관련 연구·Novelty 근거](research/2026-10-15-novelty-evidence.md) | 원문 기반 선행과 차별화 후보·주장 한계 |
| [D 진행 현황과 회의 안건](meetings/2026-10-14-d-progress-and-decisions.md) | D-01~D-04 결과·D-05·통합/추가 수정·회의 결정표 |
| [디자인 기준](design.md) | 사용자 제공 UI 스타일 |
| [모델·설정 도우미](tasks/setup-guide.md) | 발급 안내·모델 선택·추천 적용·호출 한도 |
| [C 담당 검토·집계](tasks/c-review-data.md) | 공통 계약·검토 저장 API·예정 분모와 누락 |
| [현재 상태](current-state.md) | 구현됨·미구현·기존 제한 |
| [Brain·두 루프 설계 초안](plans/2026-10-14-brain-two-loops.md) | 설계 당시 코드·논문·사용자 요구 대조; 현재 구현은 통합 검증/현재 상태 문서 기준 |
| [구버전 run 기록 호환 계획](plans/2026-10-14-brain-legacy-run-compatibility.md) | #39 구버전 로그를 새 기록과 함께 읽기 위한 원칙·검증 항목; 구현 전 |
| [점검 상태 표시 계획](plans/2026-10-11-check-status.md) | 상태 체크리스트·근거 펼침 유지 |
| [한 화면 배치 계획](plans/2026-10-11-compact-dashboard.md) | 중복 제목 제거·좌우 배치·화면 검사 |
| [API 없는 과업 점검](offline-scenarios.md) | 합성 네 과업·재현 결함·공개 사이트 부분 검증 |
| [후속 개선 이슈](changes/README.md) | 단일 흐름·Claude·기록 개선 PR 작업 |
| [개발 순서](roadmap.md) | 1차 최소 제품과 후속 실험 |
| [개발 환경과 협업](development.md) | 설치·검사·브랜치·이슈·PR |
| [구조](architecture.md) | 모듈별 책임과 변경 영향 |
| [데이터·판정 계약](contracts.md) | 평가·로그·문제 카드 기준 |
| [트러블슈팅](troubleshooting.md) | 함께 확인할 기존 회귀 |
| [검증 기록](verification.md) | 이 저장소에서 실제 실행한 결과 |
| [작업 목록](tasks/README.md) | 이슈와 연결되는 과업·완료 조건 |
| [Fast Loop 단계 분리](tasks/41-fast-loop-stages.md) | #41 인식·계획·행동 결정의 단계별 생성과 기록 |
| [Slow Loop 성찰·계획 검토](tasks/42-slow-reflection-review.md) | #42 비동기 작업, 고정 snapshot, 계획 검토 기록 |
| [Brain 두 루프 조율](tasks/43-brain-coordination.md) | #43 실행별 Fast/Slow 조율, 결과 채택·stale 폐기·종료 취소 |
| [Runner 관찰·실행·독립 평가](tasks/44-runner-evaluation-flow.md) | #44 관찰·Brain·행동·재관찰·평가 순서와 종료 선언 판정 |
| [Persona 기반 1% Wonder](tasks/45-persona-wonder.md) | #45 Slow 작업별 추첨, 별도 생성, 기록·표시 |
| [두 루프 제공자·예산·비교 호환](tasks/46-loop-provider-budget.md) | #46 실제 호출 모델·비용·한도와 Jev/일반 조건 계약 |
| [두 루프 기록 소비](tasks/47-loop-record-consumers.md) | #47 단계·작업·기억 출처의 상세 화면과 출력 |
| [기억 중요도 산정](tasks/40-memory-importance.md) | #40 미산정 기억의 Slow 1~10점 산정과 변경 기록 |
| [기억 검색 정책](tasks/54-memory-search-policy.md) | #54 기준선과 Fast/Slow별 검색 가중치 |
| [기억 제거 경계](tasks/55-memory-retention-boundaries.md) | #55 현재 단계·미산정·Slow snapshot 보호와 출처 |
| [기억 종합 검증](tasks/56-memory-integration-regression.md) | #56 점수·상한·비동기 출처의 runner 회귀 |
| [통합 기획](2026-10-09-persona-product-plan.md) | 제품·화면·기술 실험·출처에 대한 검토용 초안 |
| [과거 명세](reference/legacy-plan/agent.md) | 초기 구현 설계; 현재 완료 상태의 기준이 아님 |
| [과거 검증](reference/validation-2026-10-08.md) | 이전 macOS mock 검증 기록 |

최상위 `AGENTS.md`는 자동 발견을 위해, `README.md`는 저장소 진입점을 위해 유지한다. 그 밖의 기획·기술·검증 Markdown은 docs에 모은다.

- [D-01 사람 판정 입력·저장](tasks/d-review-form.md): #32 구현과 #33~#36 후속 범위.
- [D-04 비교표 측정 범위·누락](tasks/d-comparison-coverage.md): #35의 표시 계약과 가상 데이터 검증.

- [D-05 검토·내보내기 통합 검증](tasks/d-review-export-verification.md): 실제 시연 결과, 수정 사항과 팀원 재현 절차.

- [D 조회 실패·출처·복구 표시](tasks/d-dashboard-hardening.md): #64/#65의 수정과 회귀.
- [메모리 정책 실험 상세](research/2026-10-15-memory-policy-experiment.md): 고정 PR 근거·2차 검색 비교 조건·고정 변수·예산·한계. 팀 대화 반영 상위 계획은 위 Slow 실행·검색 실험 계획을 따른다.

- [D Brain 기록 화면·출력](tasks/d-brain-trace-viewer.md): #47의 읽기 계약·구버전·상태·출처·CSV 행 구분.

- [2026-10-15 아침 인수인계](handoffs/2026-10-15-morning.md): 완료 결과·검증·재현·선행 PR·팀 논의.
