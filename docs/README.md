# 문서 안내

AI와 개발자는 아래 순서로 읽는다. 완료 상태의 기준은 현재 코드와 실제 검증 결과이며, 기획 문서의 제안은 구현 완료를 뜻하지 않는다.

| 문서 | 목적 |
|---|---|
| [디자인 기준](design.md) | 사용자 제공 UI 스타일 |
| [모델·설정 도우미](tasks/setup-guide.md) | 발급 안내·모델 선택·추천 적용·호출 한도 |
| [현재 상태](current-state.md) | 구현됨·미구현·기존 제한 |
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
| [통합 기획](2026-10-09-persona-product-plan.md) | 제품·화면·기술 실험·출처에 대한 검토용 초안 |
| [과거 명세](reference/legacy-plan/agent.md) | 초기 구현 설계; 현재 완료 상태의 기준이 아님 |
| [과거 검증](reference/validation-2026-10-08.md) | 이전 macOS mock 검증 기록 |

최상위 `AGENTS.md`는 자동 발견을 위해, `README.md`는 저장소 진입점을 위해 유지한다. 그 밖의 기획·기술·검증 Markdown은 docs에 모은다.
