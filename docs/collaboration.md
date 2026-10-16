# 브랜치와 커밋 운영

## 브랜치의 역할

| 브랜치 | 용도 | 반영 방법 |
| --- | --- | --- |
| main | 발표·공유할 안정 버전 | 검증한 prototype을 별도 PR로 통합 |
| prototype | 네 역할의 개발 통합 기준 | 작업 브랜치에서 PR과 리뷰를 거쳐 반영 |
| feat/<issue>-<topic> | 기능 추가 | prototype에서 시작해 prototype으로 PR |
| fix/<issue>-<topic> | 결함 수정 | prototype에서 시작해 prototype으로 PR |
| docs/<issue>-<topic> | 문서 변경 | prototype 대상으로 PR |
| chore/<issue>-<topic> | CI·협업 설정·유지보수 | prototype 대상으로 PR |
| experiment/<issue>-<topic> | MiroFish·프롬프트·파인튜닝 등의 비교 실험 | 기준 커밋·조건·결과를 기록하고 채택할 변경만 PR |

AI 도구의 `codex/<topic>` 브랜치도 같은 PR·검증 규칙을 적용한다. 장기 역할별 브랜치를 따로 유지하지 않고, 역할 A~D는 이슈의 담당 영역으로 표시한다. 한 작업이 끝나면 다음 작업은 최신 prototype에서 시작한다.

main과 prototype에는 직접 push·force push하지 않는다. prototype→main 통합은 일반 기능 PR과 분리하고 시연 결과·알려진 제한·기준 커밋을 확인한다. main 통합 PR의 원본 브랜치인 prototype은 삭제하지 않는다.

## 작업 시작과 최신 변경 반영

작업 중인 변경을 먼저 확인하고 보존한 다음 아래 명령을 실행한다. 예시의 123은 실제 이슈 번호로 바꾼다.

```sh
git fetch origin
git switch prototype
git pull --ff-only origin prototype
git switch -c feat/123-task-evaluator
```

기능 브랜치에 통합 변경을 가져올 때는 다음과 같이 merge한다. 다른 사람과 공유한 브랜치 이력을 강제로 다시 쓰지 않는다.

```sh
git fetch origin
git merge origin/prototype
```

## 커밋 규칙

형식은 `type: 변경 내용` 또는 `type(scope): 변경 내용`이다. 제목은 한국어·영어 모두 가능하다.

| type | 용도 | 예시 |
| --- | --- | --- |
| feat | 새 기능 | feat(review): 후보 판정 저장 추가 |
| fix | 결함 수정 | fix(metrics): 미실행 세션 분모 유지 |
| test | 재현·검증 | test: 잘못된 완료 선언 재현 |
| refactor | 동작 유지 구조 개선 | refactor: 기록 조회 함수 분리 |
| docs | 설명·실험 결과 | docs: 대표 과업의 검증 범위 기록 |
| chore / ci | 설정·자동화 | ci: 리뷰와 알림 설정 추가 |
| style | 동작 없는 스타일 | style: 판정 행 간격 조정 |
| perf | 성능 개선 | perf: 반복 기록 읽기 축소 |

한 커밋에는 한 가지 목적을 담는다. 협업 규칙·PR 양식·리뷰 보호·알림 준비를 서로 다른 커밋으로 나누는 식이다. 커밋 수를 늘리기 위한 줄 단위 분할은 하지 않는다. 기능 수정은 재현 검사와 구현을 함께 추적하고, 최종 PR에서는 검사가 통과해야 한다.

각자 본인 계정에 연결된 Git 이메일로 작성하고, 공동 작성한 변경에만 실제 공동 작성자를 남긴다. 기여는 이슈·코드·검증·리뷰 링크로 기록한다. prototype의 커밋이 GitHub 프로필 기여 그래프에 바로 나타난다고 가정하지 않는다. main 통합과 계정 이메일 등 집계 조건이 별도로 적용된다.

## 병합과 실험

- 작업별 커밋을 보존하려면 PR에서 **Create a merge commit**을 기본으로 사용한다. 특히 prototype→main에는 merge commit을 사용해 두 장기 브랜치의 이력을 연결한다.
- squash가 필요하면 작성자와 합의한다. 이 설정 작업에서는 저장소의 다른 병합 옵션을 임의로 끄지 않는다.
- 실험은 원래 버전과 개선 버전을 같은 과업·모델·환경·예산으로 비교한다. 미채택 결과도 기록하되 실제 API 키와 runs 원자료는 커밋하지 않는다.
- 기능·실험·문서가 서로 독립적이면 PR도 나눈다. 함께 있어야 동작하는 변경은 한 PR에서 목적별 커밋으로 구성한다.

PR 작성은 [PR과 리뷰 규칙](pull-requests.md), 설치·검사는 [개발 안내](development.md)를 따른다.
