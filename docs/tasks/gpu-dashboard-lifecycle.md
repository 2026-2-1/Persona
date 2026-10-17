# 대시보드가 소유하는 GPU 세션

2026-10-17 사용자 후속 요청으로 #85 구현에 추가했다. 기존 수동 SSH·Slurm 사용법을 유지하며, 비공개 GPU 설정을 둔 대시보드만 자동 할당한다. 실제 원격 시작·반환은 SSH 인증 후 검증해야 한다.

## 시작과 종료

```text
대시보드 CLI
 → 비공개 설정 읽기 / HTTP 포트 확보 / 로컬 모델 포트 충돌 확인
 → OpenSSH 로그인 master 인증
 → 고유 세션 이름·복구 상태 저장
 → sbatch --parsable로 단일 노드·작업 할당
 → squeue에서 지정 노드 RUNNING 확인
 → compute SSH master + 채팅/임베딩 loopback 포트 전달
 → 채팅 health / 임베딩 health·GPU·실제 1건 벡터 probe
 → 짧은 Qwen 채팅 요청 / 대시보드 제공
Ctrl+C 또는 SIGTERM
 → 실행 중인 로컬 과업 중지·기록 대기
 → 이 세션의 Slurm 이름·ID 확인 / scancel / squeue에서 반환 확인
 → SSH master 종료 / 로컬 환경 복원 / HTTP 종료
```

브라우저 탭 닫기는 서버 종료가 아니다. SIGKILL·전원 종료·네트워크 단절에서는 즉시 반환을 보장하지 못한다. 유한 Slurm walltime과 로컬 복구 기록을 유지한다. 반환 확인 실패를 성공으로 숨기거나 기록을 삭제하지 않는다.

## 설정

[예시 JSON](../../configs/gpu-session.example.json)을 `runs/private/gpu-session.json`으로 복사해 실제 주소·계정·파티션·노드·자원을 설정한다. 실제 주소와 비밀번호를 공개 설정에 넣지 않는다. 비밀번호 필드는 허용하지 않는다. 예시는 p02/DIS01/A6000 1개·CPU4·48G·4시간이고 실제 클러스터의 허용 옵션을 확인해야 한다. 원격 node와 compute_host가 같은 계산 노드를 가리켜야 한다.

```sh
python3 -m uxagent dashboard
python3 -m uxagent dashboard --gpu-config runs/private/gpu-session.json
python3 -m uxagent dashboard --no-gpu
```

기본 비공개 파일이 없으면 종전 수동 연결 방식이다. 자동 모드는 localhost8001→원격8000 채팅, localhost8002→원격8002 임베딩을 기본으로 사용한다. 따라서 합성 fixture8000과 충돌하지 않는다. 실제 데카트론 설정은 fixture 서버를 사용하지 않는다. 시작/종료 구현은 `gpu_session.py`, 연결은 `cli.py`·`monitor.py`다. SSH ControlMaster/ControlPath를 지원하는 로컬 OpenSSH가 필요하다. Windows의 실제 SSH/Slurm 동작은 미검증이며 CI는 가짜 transport로 수명주기를 검증한다.

## 인증

비밀번호는 OpenSSH의 사용자 터미널 프롬프트에서 입력한다. 앱·환경 변수·JSON·요청·로그에 보관하지 않는다. 실행 중에는 인증한 login master를 ProxyCommand로 재사용하고 agent forwarding을 켜지 않는다. 완전 무인 시작은 운영자가 허용하는 SSH 키 인증을 로그인·계산 노드에 준비해야 한다. 이번 로컬 BatchMode 읽기 전용 점검은 Permission denied였으며 실제 Slurm 명령 지원·할당·서버 실행을 확인하지 못했다. 키/인증파일/known_hosts는 코드가 변경하지 않는다.

## 임베딩 최초 준비

기존 Qwen `.venv-dis01`과 분리해 **원격 `~/persona-llm`에서 최초 한 번** 준비한다. 로그인/계산 노드 HOME 공유와 인터넷 접근을 확인한다. 로컬 대시보드 환경에는 sentence-transformers/torch를 추가하지 않는다.

```sh
cd ~/persona-llm
python3 -m venv .venv-persona-embedding
.venv-persona-embedding/bin/python -m pip install sentence-transformers
HF_HUB_OFFLINE=0 .venv-persona-embedding/bin/python -c 'from sentence_transformers import SentenceTransformer; SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2", device="cpu", trust_remote_code=False)'
.venv-persona-embedding/bin/python -m pip freeze > .persona-embedding-packages.txt
```

이 명령은 이번 작업에서 원격 실행하지 않았다. 설치 버전·모델 캐시·실제 CUDA 메모리 여유를 원격에서 확인해야 한다. 예시 모델은 [공식 모델 카드](https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2)의 다국어384차원 모델이며 최대 길이128 token이다. 긴 기억은 모델 창에서 잘리므로 Qwen 문맥 길이와 혼동하지 않는다. 실제 한국어 검색 품질·U 원본 embedding 모델과의 동등 성능은 검증하지 않았다.

자동 시작은 `embedding_server.py`를 원격 `$HOME/.persona-gpu/`에 고유 이름으로 전달한다. 서버는 CUDA·local_files_only로 모델을 읽고 127.0.0.1에만 bind한다. 모델 다운로드·유료 API·CPU fallback은 시작 경로에 없다. 별도 Python 프로세스로 Qwen과 같은 Slurm 할당 안에서 실행하고 한쪽이 종료되면 다른 쪽도 정리한다. 로그/helper는 원격 `.persona-gpu/`에 남으며 기존 api_server.py를 수정하지 않는다.

`GET /health`는 모델·차원·최대 길이·장치를 반환한다. `POST /v1/embeddings`는 model/input 문자열 배열을 받아 index/embedding과 tokenize attention-mask의 실제 입력 token 수를 반환한다. 정규화·query prefix를 추가하지 않는다. [SentenceTransformer API](https://www.sbert.net/docs/package_reference/sentence_transformer/model.html)를 사용한다. 실패 응답은 입력 본문을 포함하지 않는다.

## 소유권과 복구

- 이름은 실행별 UUID다. 사용자 전체 작업이나 기존 수동 작업을 취소하지 않는다.
- sbatch 응답을 잃으면 해당 사용자+고유 이름으로만 ID를 복구한다.
- 로컬 `runs/private/gpu-session-state.json`은 배타적으로 생성한다. job ID·고유 이름과 임베딩 probe 메타데이터를 저장하고 실제 반환이 확인된 뒤 삭제한다.
- 이전 미반환 기록이 있으면 새 할당을 막는다. 운영자가 같은 사용자/이름의 작업을 확인·반환한 뒤 상태를 정리한다. 단순히 파일만 지워 할당을 숨기지 않는다.
- 자원 할당은 srun --pty 대화형 셸 대신 동일 자원 옵션의 sbatch를 사용한다. 서버 실행/종료를 작업 ID로 관리하기 위해서다. 이 클러스터의 sbatch 정책은 실제 인증 후 확인해야 한다.

근거: [sbatch](https://slurm.schedmd.com/sbatch.html), [squeue](https://slurm.schedmd.com/squeue.html), [scancel](https://slurm.schedmd.com/scancel.html), [OpenSSH](https://man.openbsd.org/ssh).
