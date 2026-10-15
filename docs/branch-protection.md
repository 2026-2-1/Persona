# 브랜치 보호 설정

2026-10-13에 GitHub 원격 main·prototype에 아래 규칙을 적용하고 API 응답으로 확인했다. 적용 전 두 브랜치에는 보호 규칙이 없었다. JSON 파일은 실제 적용에 사용한 요청 본문이며, 저장소 병합만으로 설정이 자동 적용되지는 않는다.

| 설정 | main | prototype |
| --- | --- | --- |
| PR 승인 | 작성자 외 쓰기 권한자 1명 | 동일 |
| 새 코드 변경 후 오래된 승인 | 취소하고 재승인 | 동일 |
| 리뷰 대화 해결 | 필수 | 필수 |
| 관리자 우회 | 적용하지 않음 | 적용하지 않음 |
| force push·삭제 | 금지 | 금지 |
| 필수 CI | 현재 미지정 | Ubuntu 3.11·Windows 3.13 |
| 최신 대상 브랜치 반영 | CI 필수화와 함께 추후 설정 | 필수 |

prototype의 정확한 검사 이름은 `check (ubuntu-latest, 3.11)`과 `check (windows-latest, 3.13)`이다. GitHub Actions 앱 ID 15368로 연결했다. 기존 Prototype checks가 보고한 이름과 앱을 확인했으며 실행 완료된 PR #30에도 같은 이름이 사용된다.

main에는 초기 Next.js/FastAPI 골격의 backend/frontend CI가 있고 prototype에는 Python 실행기의 CI가 있다. 전환 중 존재하지 않는 검사를 필수화해 통합을 막지 않도록 main의 필수 검사 이름은 현재 비워둔다. 최초 prototype→main 통합 시 CI 변경을 함께 검토하고 그 통합 직후 실제 CI 이름을 필수화한다. 그 전에도 팀 규칙상 실패한 검사를 무시해 병합하지 않는다.

리뷰어는 PR 작성자가 Reviewers에서 팀원 1명을 선택한다. 특정 인물을 모든 파일의 필수 소유자로 지정하지 않는다. 자동 지정과 CODEOWNERS는 역할·리뷰 부담을 합의한 뒤 추가할 수 있다. GitHub의 승인 규칙 자체는 리뷰어 요청 여부와 별개로 병합 시 필수 승인 1개를 검사한다.

## 관리자 확인과 재적용

현재 상태를 먼저 조회한다. 아래 PUT 요청은 전체 보호 설정을 바꿀 수 있으므로 향후 재사용할 때 추가된 규칙이 있는지 먼저 비교해야 한다.

```sh
gh api repos/2026-2-1/Persona/branches/prototype/protection
gh api repos/2026-2-1/Persona/branches/main/protection

# 저장소 루트에서, 현재 원격 설정과 비교한 뒤에만 재적용
gh api --method PUT repos/2026-2-1/Persona/branches/prototype/protection --input .github/branch-protection/prototype.json
gh api --method PUT repos/2026-2-1/Persona/branches/main/protection --input .github/branch-protection/main.json
```

설정 원본: [main](../.github/branch-protection/main.json), [prototype](../.github/branch-protection/prototype.json).

PR 작성자 본인 승인과 AI 리뷰는 필수 사람 승인을 대신하지 않는다. GitHub 관리자로도 리뷰를 우회하지 않고, 긴급 상황의 규칙 변경은 별도 기록한다.

참고: [GitHub 브랜치 보호](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches).
