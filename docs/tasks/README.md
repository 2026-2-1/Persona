# 작업과 GitHub 이슈

- [#85 U 기억 검색](85-u-memory.md)
- [#86 U DOM parser 화면 관찰](86-u-observation.md)
- [#87 U 행동 집합과 접근 정책](87-u-actions.md)
- [대시보드 GPU 수명주기](gpu-dashboard-lifecycle.md)

완료한 최소 구현과 남은 전체 목표는 각 문서의 현재 상태에서 구분한다. 열린 이슈는 후속 보완·검증 작업이다.

2026-10-17 U 전환: [#83 Fast 구현 범위](83-u-fast.md). #84~#90의 나머지 전환은 해당 GitHub 이슈를 따른다. #83의 작업 브랜치 검증을 전체 U 전환 완료로 간주하지 않는다.

#84 작업 브랜치는 [U Slow·Wonder 반복](84-u-slow.md)을 연결한다. #85 기억 검색과 #86 DOM 관찰까지 현재 작업 브랜치에 이어졌고, #87~#90은 후속이다.

| 순서 | 작업 문서 | GitHub | 단계 |
|---|---|---|---|
| 01 | [[phase:1] 검색 입력과 세부 행동 지원](01-search-actions.md) | [#2](https://github.com/2026-2-1/Persona/issues/2) | phase:1 |
| 02 | [[phase:1] 검색·필터·상세의 독립 평가기](02-task-evaluators.md) | [#3](https://github.com/2026-2-1/Persona/issues/3) | phase:1 |
| 03 | [[phase:1] 사전 등록 세션과 성공률·복구·기록 지표](03-metrics.md) | [#4](https://github.com/2026-2-1/Persona/issues/4) | phase:1 |
| 04 | [[phase:1] 일반 AI·페르소나 AI 대응 비교 실행](04-ai-comparison.md) | [#5](https://github.com/2026-2-1/Persona/issues/5) | phase:1 |
| 05 | [[phase:1] 쉬운 API 연결과 ChatGPT 구독 연동 PoC](05-ai-connection.md) | [#6](https://github.com/2026-2-1/Persona/issues/6) | phase:1 |
| 06 | [[phase:1] 초보자용 설정·테스트·비교 대시보드](06-dashboard.md) | [#7](https://github.com/2026-2-1/Persona/issues/7) | phase:1 |
| 07 | [[phase:1] 개발자 개선 카드와 HTML·Markdown·CSV/JSON 출력](07-developer-output.md) | [#8](https://github.com/2026-2-1/Persona/issues/8) | phase:1 |
| 08 | [[phase:1] 1차 최소 제품 통합 검증과 발표 시연](08-demo-validation.md) | [#9](https://github.com/2026-2-1/Persona/issues/9) | phase:1 |
| 09 | [[phase:2] 4개 과업·환경 편차·2인 검토·개선 전후 실험](09-human-ab.md) | [#10](https://github.com/2026-2-1/Persona/issues/10) | phase:2 |
| 10 | [[phase:2] Jev·Slow Loop·MiroFish·프롬프트 기술 비교](10-technology-experiments.md) | [#11](https://github.com/2026-2-1/Persona/issues/11) | phase:2 |
| 11 | [[phase:3] 논문·기술백서·재현 자료와 선택 MCP 연동](11-research-mcp.md) | [#12](https://github.com/2026-2-1/Persona/issues/12) | phase:3 |
| 40 | [[phase:1] 기억 중요도 비동기 산정](40-memory-importance.md) | [#40](https://github.com/2026-2-1/Persona/issues/40) | phase:1 |
| 41 | [[phase:1] Fast Loop의 인식·계획·행동 결정 분리](41-fast-loop-stages.md) | [#41](https://github.com/2026-2-1/Persona/issues/41) | phase:1 |
| 42 | [[phase:1] Slow Loop 성찰·계획 검토](42-slow-reflection-review.md) | [#42](https://github.com/2026-2-1/Persona/issues/42) | phase:1 |
| 43 | [[phase:1] Brain 모듈 신설과 두 루프 비동기 조율](43-brain-coordination.md) | [#43](https://github.com/2026-2-1/Persona/issues/43) | phase:1 |
| 44 | [[phase:1] Runner 관찰·Brain·실행·독립 평가 흐름 연결](44-runner-evaluation-flow.md) | [#44](https://github.com/2026-2-1/Persona/issues/44) | phase:1 |
| 45 | [[phase:1] Persona 기반 1% Wonder](45-persona-wonder.md) | [#45](https://github.com/2026-2-1/Persona/issues/45) | phase:1 |
| 46 | [[phase:1] 두 루프 LLM 제공자·예산·비교 조건 호환](46-loop-provider-budget.md) | [#46](https://github.com/2026-2-1/Persona/issues/46) | phase:1 |
| 47 | [[phase:1] 두 루프 기록의 대시보드·보고서 연결](47-loop-record-consumers.md) | [#47](https://github.com/2026-2-1/Persona/issues/47) | phase:1 |
| 54 | [[phase:1] 메모리 검색 점수·가중치 수정 보완](54-memory-search-policy.md) | [#54](https://github.com/2026-2-1/Persona/issues/54) | phase:1 |
| 55 | [[phase:1] 활성 메모리 제거 경계와 비동기 출처 보호](55-memory-retention-boundaries.md) | [#55](https://github.com/2026-2-1/Persona/issues/55) | phase:1 |
| 56 | [[phase:1] 메모리 점수·상한·비동기 출처 종합 검증](56-memory-integration-regression.md) | [#56](https://github.com/2026-2-1/Persona/issues/56) | phase:1 |

- [#25 모델·발급 안내와 설정 도우미](setup-guide.md): 무료 예시와 요청형 AI 추천, 모델별 연결 확인.

- [C 담당 P05/P06/P08](c-review-data.md): 이슈 #27/#28/#29, 계약·검토 이력·집계 후속.
