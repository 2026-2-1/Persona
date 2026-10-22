"""Dashboard-owned SSH/Slurm lifecycle with OpenSSH/OS credential storage."""
from __future__ import annotations

import json
import os
import re
import shlex
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
import uuid
from typing import Literal
from importlib.resources import files
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .model_json import loads_json


class GpuSessionConfig(BaseModel):
    model_config = ConfigDict(extra='forbid', hide_input_in_errors=True)
    login_host: str
    compute_host: str
    user: str
    ssh_port: int = Field(default=10000, ge=1, le=65535)
    partition: str
    node: str
    gres: str
    cpus: int = Field(gt=0)
    memory: str
    walltime: str
    remote_dir: str = 'persona-llm'
    venv_dir: str = '.venv-dis01'
    server_script: str = 'api_server.py'
    local_port: int = Field(default=8001, ge=1024, le=65535)
    remote_port: int = Field(default=8000, ge=1024, le=65535)
    tokenizer_enabled: bool = True
    tokenizer_local_port: int = Field(default=8003, ge=1024, le=65535)
    tokenizer_remote_port: int = Field(default=8003, ge=1024, le=65535)
    startup_timeout: int = Field(default=600, gt=0, le=3600)
    ssh_timeout: int = Field(default=60, gt=0, le=300)
    embedding_model: str | None = None
    embedding_venv: str = '.venv-persona-embedding'
    embedding_local_port: int = Field(default=8002, ge=1024, le=65535)
    embedding_remote_port: int = Field(default=8002, ge=1024, le=65535)
    identity_file: str | None = None
    identity_agent: str | None = None
    ssh_batch_mode: bool = False
    ssh_password_store: Literal['macos-keychain'] | None = None

    @field_validator('login_host', 'compute_host', 'user', 'partition', 'node', 'gres', 'memory')
    @classmethod
    def safe_token(cls, value):
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:@-]*', value):
            raise ValueError('invalid SSH/Slurm identifier')
        return value

    @field_validator('walltime')
    @classmethod
    def bounded_time(cls, value):
        if not re.fullmatch(r'(?:[0-9]+-)?[0-9]{1,3}:[0-5][0-9]:[0-5][0-9]', value) or not any(c in '123456789' for c in value):
            raise ValueError('a finite Slurm walltime is required')
        return value

    @field_validator('remote_dir', 'venv_dir', 'server_script', 'embedding_venv')
    @classmethod
    def relative_path(cls, value):
        if not re.fullmatch(r'[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*', value) or '..' in value.split('/'):
            raise ValueError('a safe path relative to the remote home/project is required')
        return value


class GpuSession:
    def __init__(self, config, state_path='runs/private/gpu-session-state.json'):
        self.config = config
        self.state_path = Path(state_path)
        self.job_id = None
        self.token = uuid.uuid4().hex
        self.job_name = 'persona-' + self.token
        self.temp = None
        self.login_socket = self.compute_socket = None
        self.previous_url = None
        self.previous_embedding_url = None
        self.previous_tokenizer_url = None
        self.environment_set = False
        self.closed = False
        self.submission_started = False
        self.state_created = False
        self.embedding_validation = None
        self.authentication_only = False

    def identity_options(self):
        if not self.config.identity_file:
            return []
        args = ['-i', str(Path(self.config.identity_file).expanduser()),
                '-o', 'IdentitiesOnly=yes', '-o', 'AddKeysToAgent=yes']
        if self.config.identity_agent and Path(self.config.identity_agent).is_socket():
            args += ['-o', 'IdentityAgent=' + self.config.identity_agent]
        if sys.platform == 'darwin':
            args += ['-o', 'IgnoreUnknown=UseKeychain', '-o', 'UseKeychain=yes']
        return args

    def open_login(self):
        if self.closed:
            raise RuntimeError('GPU session is closed')
        if self.temp is not None and self._control_alive(self.config.login_host, self.login_socket):
            return
        if self.temp is None:
            self.temp = tempfile.TemporaryDirectory(prefix='px-', dir='/tmp' if os.name != 'nt' else None)
            self.login_socket = Path(self.temp.name) / 'login'
            self.compute_socket = Path(self.temp.name) / 'compute'
        elif self.login_socket.exists():
            self._stop_master(self.config.login_host, self.login_socket)
        self._master(self.config.login_host, self.login_socket)

    def _control_alive(self, host, control):
        result = subprocess.run(['ssh', '-S', str(control), '-O', 'check',
            '-p', str(self.config.ssh_port), f'{self.config.user}@{host}'],
            capture_output=True, timeout=10, check=False)
        return result.returncode == 0

    def _stop_master(self, host, control):
        if not control:
            return
        subprocess.run(['ssh', '-S', str(control), '-O', 'exit',
            '-p', str(self.config.ssh_port), f'{self.config.user}@{host}'],
            capture_output=True, timeout=10, check=False)
        # The path belongs to this session's private temporary directory.
        control.unlink(missing_ok=True)

    def _open_compute(self):
        proxy = shlex.join(self._ssh(self.config.login_host, self.login_socket)[:-1]
                           + ['-W', '%h:%p', f'{self.config.user}@{self.config.login_host}'])
        options = ['-o', 'ProxyCommand=' + proxy]
        if not self.authentication_only:
            options += ['-L', f'127.0.0.1:{self.config.local_port}:127.0.0.1:{self.config.remote_port}']
        if self.config.embedding_model and not self.authentication_only:
            options += ['-L', f'127.0.0.1:{self.config.embedding_local_port}:127.0.0.1:{self.config.embedding_remote_port}']
        if self.config.tokenizer_enabled and not self.authentication_only:
            options += ['-L', f'127.0.0.1:{self.config.tokenizer_local_port}:127.0.0.1:{self.config.tokenizer_remote_port}']
        self._master(self.config.compute_host, self.compute_socket, options)

    def check_health(self):
        from .llm import LocalQwenProvider
        LocalQwenProvider().health(url=f'http://127.0.0.1:{self.config.local_port}/v1/chat/completions')
        if self.config.tokenizer_enabled:
            with urllib.request.urlopen(f'http://127.0.0.1:{self.config.tokenizer_local_port}/health', timeout=2) as response:
                data = loads_json(response.read())
            if data.get('status') != 'ok' or data.get('model') != 'persona-qwen' or data.get('input_token_limit') != 8192:
                raise ValueError('Qwen 토큰 계산 서비스의 상태·모델·한도가 다릅니다')
        if self.config.embedding_model:
            with urllib.request.urlopen(f'http://127.0.0.1:{self.config.embedding_local_port}/health', timeout=2) as response:
                data = loads_json(response.read())
            if (data.get('status') != 'ok' or data.get('model') != self.config.embedding_model
                    or not str(data.get('device', '')).startswith('cuda')):
                raise ValueError('GPU 임베딩 health의 상태·모델·장치가 설정과 다릅니다')

    def ensure_ready(self):
        """Repair this allocation's lost SSH masters, without submitting a job."""
        if self.closed or not self.job_id or self.authentication_only:
            raise RuntimeError('GPU 할당이 없습니다. 대시보드를 다시 시작하세요.')
        try:
            self.check_health()
            return
        except (OSError, ValueError):
            pass
        self.open_login()
        identity = self._remote(shlex.join(['squeue', '--noheader', '--user', self.config.user,
            '--name', self.job_name, '--format=%i|%j|%T|%N']))
        if not identity:
            raise RuntimeError('GPU 할당이 종료됐습니다. 대시보드를 다시 시작해 재할당하세요.')
        if identity != f'{self.job_id}|{self.job_name}|RUNNING|{self.config.node}':
            raise RuntimeError('GPU 작업의 소유권 또는 할당 상태가 다릅니다. 복구를 중단했습니다.')
        if not self._control_alive(self.config.compute_host, self.compute_socket):
            self._stop_master(self.config.compute_host, self.compute_socket)
            # A plain probe bind sees this tunnel's TIME_WAIT sockets as busy.
            # OpenSSH binds with its own socket options; ExitOnForwardFailure
            # still prevents taking over a live listener from another process.
            self._open_compute()
        self.check_health()

    def _ssh(self, host, control):
        return ['ssh', '-S', str(control), '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10',
                *self.identity_options(),
                '-p', str(self.config.ssh_port), f'{self.config.user}@{host}']

    def install_compute_key(self, command, payload):
        result = subprocess.run(self._ssh(self.config.compute_host, self.compute_socket) + [command],
            input=payload, text=True, capture_output=True, timeout=self.config.ssh_timeout, check=False)
        if result.returncode:
            raise RuntimeError('계산 노드 공개 키 등록을 완료하지 못했습니다')

    def _remote(self, command, *, input=None):
        result = subprocess.run(self._ssh(self.config.login_host, self.login_socket) + [command],
            input=input, text=True, capture_output=True, timeout=self.config.ssh_timeout, check=False)
        if result.returncode:
            # Remote output can contain environment values; do not copy it to UI/errors.
            raise RuntimeError(f'GPU SSH command failed (exit {result.returncode})')
        return result.stdout.strip()

    def _master(self, host, control, extra=()):
        # Password mode uses a dedicated askpass pipe; terminal mode remains available.
        password_mode = self.config.ssh_password_store == 'macos-keychain'
        options = {}
        if password_mode:
            from .gpu_passwords import askpass_environment
            options = {'env':askpass_environment(self.config, host, self.temp.name),
                       'stdin':subprocess.DEVNULL}
            extra = [*extra, '-o', 'StrictHostKeyChecking=yes',
                     '-o', 'NumberOfPasswordPrompts=1', '-o', 'PubkeyAuthentication=no',
                     '-o', 'PreferredAuthentications=password,keyboard-interactive']
        args = ['ssh', '-M', '-S', str(control), '-fN', '-o', 'ControlPersist=no',
                '-o', 'ExitOnForwardFailure=yes', '-o', 'ServerAliveInterval=15',
                '-o', 'ServerAliveCountMax=3', '-o', 'ConnectTimeout=10', *extra,
                *self.identity_options(),
                '-o', 'BatchMode=' + ('yes' if self.config.ssh_batch_mode and not password_mode else 'no'),
                '-p', str(self.config.ssh_port), f'{self.config.user}@{host}']
        result = subprocess.run(args, timeout=self.config.ssh_timeout, check=False, **options)
        if result.returncode:
            raise RuntimeError('SSH 인증/터널 연결에 실패했습니다. 저장한 자격증명·호스트 신뢰·SSH 설정을 확인하세요.')

    def _check_ports(self):
        ports = [self.config.local_port]
        if self.config.embedding_model:
            if self.config.embedding_local_port == self.config.local_port or self.config.embedding_remote_port == self.config.remote_port:
                raise ValueError('채팅과 임베딩 포트는 달라야 합니다')
            ports.append(self.config.embedding_local_port)
        if self.config.tokenizer_enabled:
            if (self.config.tokenizer_local_port in ports or self.config.tokenizer_remote_port == self.config.remote_port
                    or (self.config.embedding_model and self.config.tokenizer_remote_port == self.config.embedding_remote_port)):
                raise ValueError('토큰 계산·채팅·임베딩 포트는 달라야 합니다')
            ports.append(self.config.tokenizer_local_port)
        for port in ports:
            with socket.socket() as probe:
                if os.name == 'nt':
                    exclusive = getattr(socket, 'SO_EXCLUSIVEADDRUSE', None)
                    if exclusive is not None:
                        probe.setsockopt(socket.SOL_SOCKET, exclusive, 1)
                else:
                    probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                try:
                    probe.bind(('127.0.0.1', port))
                except OSError:
                    raise RuntimeError('GPU 로컬 포트가 이미 사용 중입니다. 기존 터널을 확인하세요.') from None

    def _script(self):
        if self.authentication_only:
            return '#!/bin/bash\nexec sleep 600\n'
        c = self.config
        script = ('#!/bin/bash\nset -euo pipefail\numask 077\n'
                f'cd "$HOME"/{shlex.quote(c.remote_dir)}\n'
                f'source {shlex.quote(c.venv_dir + "/bin/activate")}\n'
                'export HF_HUB_OFFLINE=1\n')
        if not c.embedding_model and not c.tokenizer_enabled:
            return script + f'exec python -u {shlex.quote(c.server_script)}\n'
        # All services share one owned allocation. Any child exit ends it.
        script += (
            'chat_pid=""; embedding_pid=""; tokenizer_pid=""\n'
            'cleanup() { trap - EXIT TERM INT; '
            '[ -z "$chat_pid" ] || kill "$chat_pid" 2>/dev/null || true; '
            '[ -z "$embedding_pid" ] || kill "$embedding_pid" 2>/dev/null || true; '
            '[ -z "$tokenizer_pid" ] || kill "$tokenizer_pid" 2>/dev/null || true; wait || true; }\n'
            'trap cleanup EXIT\ntrap "exit 143" TERM\ntrap "exit 130" INT\n')
        children = ['"$chat_pid"']
        if c.tokenizer_enabled:
            script += (f'python -u "$HOME/.persona-gpu/{self.token}-tokenizer.py" '
                       f'--server-script {shlex.quote(c.server_script)} --port {c.tokenizer_remote_port} '
                       '&\ntokenizer_pid=$!\n')
            children.append('"$tokenizer_pid"')
        if c.embedding_model:
            script += (f'{shlex.quote(c.embedding_venv + "/bin/python")} '
                       f'"$HOME/.persona-gpu/{self.token}-embedding.py" --model {shlex.quote(c.embedding_model)} '
                       f'--port {c.embedding_remote_port} &\nembedding_pid=$!\n')
            children.append('"$embedding_pid"')
        return script + f'python -u {shlex.quote(c.server_script)} &\nchat_pid=$!\nwait -n ' + ' '.join(children) + '\n'

    def _wait_tokenizer_health(self):
        from .token_counter import QwenTokenCounter
        counter = QwenTokenCounter(f'http://127.0.0.1:{self.config.tokenizer_local_port}/tokenize')
        deadline = time.monotonic() + self.config.startup_timeout
        while time.monotonic() < deadline:
            if not self._remote(shlex.join(['squeue', '--noheader', '--user', self.config.user,
                                          '--name', self.job_name, '--format=%T'])):
                raise RuntimeError('토큰 계산 서비스 준비 전에 Slurm 작업이 종료됐습니다')
            try:
                result = counter.count([{'role': 'user', 'content': '토큰 계산 연결 확인'}])
                if result['prompt_tokens'] <= 0:
                    raise ValueError('empty token probe')
                self._save_job_id(tokenizer_validation={key: result[key] for key in
                    ('model', 'tokenizer_fingerprint', 'input_token_limit', 'max_output_tokens')})
                print('Qwen 토큰 계산 서비스 연결 완료', flush=True)
                return
            except (RuntimeError, ValueError):
                time.sleep(1)
        raise RuntimeError('Qwen 토큰 계산 서비스 시작 대기 시간이 초과됐습니다')

    def _submit_command(self):
        c = self.config
        return shlex.join(['sbatch', '--parsable', '--nodes=1', '--ntasks=1',
            f'--job-name={self.job_name}', f'--partition={c.partition}', f'--nodelist={c.node}',
            f'--gres={c.gres}', f'--cpus-per-task={c.cpus}', f'--mem={c.memory}',
            f'--time={c.walltime}', f'--output=.persona-gpu/{self.token}-%j.log'])

    def _save(self):
        # Create exclusively: a second dashboard must not replace an owned job record.
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(self.state_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            json.dump({'job_id': self.job_id, 'job_name': self.job_name,
                       'login_host': self.config.login_host, 'user': self.config.user,
                       'ssh_port': self.config.ssh_port}, handle)
        self.state_created = True

    def _save_job_id(self, **metadata):
        saved = json.loads(self.state_path.read_text())
        if saved.get('job_name') != self.job_name:
            raise RuntimeError('GPU ownership record changed')
        saved['job_id'] = self.job_id
        saved.update(metadata)
        temporary = self.state_path.with_name(self.state_path.name + '.' + self.token)
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            json.dump(saved, handle)
        temporary.replace(self.state_path)

    def _wait_running(self):
        deadline = time.monotonic() + self.config.startup_timeout
        while time.monotonic() < deadline:
            state = self._remote(shlex.join(['squeue', '--noheader', '--user', self.config.user, '--name', self.job_name, '--format=%T|%N']))
            if state == 'RUNNING|' + self.config.node:
                return
            if not state or state.split('|')[0] not in {'PENDING', 'CONFIGURING', 'RUNNING'}:
                raise RuntimeError('GPU Slurm 작업이 종료됐거나 예상 노드와 다릅니다.')
            time.sleep(1)
        raise RuntimeError('GPU Slurm 할당 대기 시간이 초과됐습니다.')

    def _wait_health(self):
        deadline = time.monotonic() + self.config.startup_timeout
        url = f'http://127.0.0.1:{self.config.local_port}/health'
        while time.monotonic() < deadline:
            if not self._remote(shlex.join(['squeue', '--noheader', '--user', self.config.user, '--name', self.job_name, '--format=%T'])):
                raise RuntimeError('GPU 모델 서버가 준비되기 전에 Slurm 작업이 종료됐습니다.')
            try:
                with urllib.request.urlopen(url, timeout=2) as response:
                    data = loads_json(response.read())
                if data.get('status') == 'ok' and data.get('model') == 'persona-qwen':
                    return
            except (OSError, ValueError):
                pass
            time.sleep(1)
        raise RuntimeError('GPU 모델 서버 health 대기 시간이 초과됐습니다.')

    def _wait_embedding_health(self):
        from .memory import MemoryStore
        deadline = time.monotonic() + self.config.startup_timeout
        base = f'http://127.0.0.1:{self.config.embedding_local_port}'
        while time.monotonic() < deadline:
            if not self._remote(shlex.join(['squeue', '--noheader', '--user', self.config.user,
                                          '--name', self.job_name, '--format=%T'])):
                raise RuntimeError('임베딩 준비 전에 Slurm 작업이 종료됐습니다. 원격 .persona-gpu 로그를 확인하세요.')
            try:
                with urllib.request.urlopen(base + '/health', timeout=2) as response:
                    health = loads_json(response.read())
                if health.get('model') != self.config.embedding_model or not str(health.get('device', '')).startswith('cuda'):
                    raise RuntimeError('임베딩 서버의 실제 모델/GPU가 설정과 다릅니다.')
                request = urllib.request.Request(base + '/v1/embeddings',
                    data=json.dumps({'model':self.config.embedding_model, 'input':['연결 확인']}).encode(),
                    headers={'Content-Type':'application/json'})
                with urllib.request.urlopen(request, timeout=120) as response:
                    result = loads_json(response.read())
                if result.get('model') != self.config.embedding_model or len(result['data']) != 1:
                    raise ValueError('embedding probe model/count mismatch')
                dimension = health.get('dimension')
                if type(dimension) is not int or dimension <= 0:
                    raise ValueError('embedding dimension invalid')
                MemoryStore.validate_embedding(result['data'][0]['embedding'], dimension)
                self.embedding_validation = {'model':self.config.embedding_model,
                    'dimension':dimension, 'device':health['device'], 'max_seq_length':health.get('max_seq_length'),
                    'input_tokens':result.get('usage', {}).get('prompt_tokens')}
                self._save_job_id(embedding_validation=self.embedding_validation)
                print(f'GPU 임베딩 검증 완료: {self.config.embedding_model}, {dimension}차원', flush=True)
                return
            except OSError:
                pass
            time.sleep(1)
        raise RuntimeError('GPU 임베딩 서버 준비 시간이 초과됐습니다.')

    def start(self, *, authentication_only=False):
        if self.job_id or self.closed:
            raise RuntimeError('GPU session cannot be restarted')
        if self.state_path.exists():
            raise RuntimeError('이전 GPU 작업의 미반환 기록이 있습니다. 반환을 확인한 뒤 다시 시작하세요.')
        self.authentication_only = authentication_only
        if not authentication_only:
            self._check_ports()
        if self.config.ssh_password_store:
            print('키체인에 저장한 비밀번호로 GPU SSH 인증과 Slurm 할당을 시작합니다.', flush=True)
        else:
            print('GPU SSH 인증과 Slurm 할당을 시작합니다. 암호는 터미널에서만 입력하세요.', flush=True)
        try:
            self.open_login()
            self._save()
            self._remote('umask 077; mkdir -p "$HOME/.persona-gpu" && chmod 700 "$HOME/.persona-gpu"')
            if self.config.embedding_model and not authentication_only:
                self._remote(f'cat > "$HOME/.persona-gpu/{self.token}-embedding.py"',
                             input=files('uxagent').joinpath('embedding_server.py').read_text())
            if self.config.tokenizer_enabled and not authentication_only:
                self._remote(f'cat > "$HOME/.persona-gpu/{self.token}-tokenizer.py"',
                             input=files('uxagent').joinpath('tokenizer_server.py').read_text())
            self.submission_started = True
            submitted = self._remote('cd "$HOME" && umask 077 && ' + self._submit_command(), input=self._script())
            if not re.fullmatch(r'[0-9]+', submitted):
                raise RuntimeError('Slurm job ID 응답을 확인할 수 없습니다.')
            self.job_id = submitted
            self._save_job_id()
            print(f'GPU Slurm 작업 {self.job_id}의 할당을 기다립니다.', flush=True)
            self._wait_running()
            # Reuse authenticated login master for the jump; no agent forwarding.
            self._open_compute()
            if authentication_only:
                return self
            self._wait_health()
            if self.config.tokenizer_enabled:
                self._wait_tokenizer_health()
            if self.config.embedding_model:
                self._wait_embedding_health()
            self.previous_url = os.environ.get('PERSONA_QWEN_API_URL')
            os.environ['PERSONA_QWEN_API_URL'] = f'http://127.0.0.1:{self.config.local_port}/v1/chat/completions'
            self.environment_set = True
            if self.config.tokenizer_enabled:
                self.previous_tokenizer_url = os.environ.get('PERSONA_QWEN_TOKENIZER_URL')
                os.environ['PERSONA_QWEN_TOKENIZER_URL'] = f'http://127.0.0.1:{self.config.tokenizer_local_port}/tokenize'
            if self.config.embedding_model:
                self.previous_embedding_url = os.environ.get('PERSONA_EMBEDDING_API_URL')
                os.environ['PERSONA_EMBEDDING_API_URL'] = f'http://127.0.0.1:{self.config.embedding_local_port}/v1/embeddings'
        except BaseException as original:
            try:
                self.close()
            except Exception as cleanup:
                raise RuntimeError(f'GPU 시작 실패 후 반환도 확인하지 못했습니다. {self.state_path}를 확인하세요.') from cleanup
            raise original
        return self

    def close(self):
        if self.closed:
            return
        error = None
        try:
            if self.submission_started or self.job_id:
                self.open_login()
            if self.submission_started and not self.job_id:
                # A lost SSH reply does not prove sbatch failed. Find only this
                # session's unique name for this user, never cancel all user jobs.
                recovered = self._remote(shlex.join(['squeue', '--noheader', '--user', self.config.user,
                    '--name', self.job_name, '--format=%i']))
                if recovered:
                    if not re.fullmatch(r'[0-9]+', recovered):
                        raise RuntimeError('GPU submission identity could not be recovered')
                    self.job_id = recovered
                    self._save_job_id()
            if self.job_id:
                identity = self._remote(shlex.join(['squeue', '--noheader', '--user', self.config.user, '--name', self.job_name, '--format=%i|%j']))
                if identity and identity != self.job_id + '|' + self.job_name:
                    raise RuntimeError('GPU Slurm job ownership does not match')
                if identity:
                    try:
                        self._remote(shlex.join(['scancel', self.job_id]))
                    except Exception:
                        if self._remote(shlex.join(['squeue', '--noheader', '--user', self.config.user, '--name', self.job_name, '--format=%i'])):
                            raise
                deadline = time.monotonic() + 30
                while self._remote(shlex.join(['squeue', '--noheader', '--user', self.config.user, '--name', self.job_name, '--format=%i'])):
                    if time.monotonic() >= deadline:
                        raise RuntimeError('GPU 작업 반환 확인 시간 초과')
                    time.sleep(.5)
                if self.state_path.exists():
                    saved = json.loads(self.state_path.read_text())
                    if saved.get('job_id') == self.job_id and saved.get('job_name') == self.job_name:
                        self.state_path.unlink()
                print(f'GPU Slurm 작업 {self.job_id} 반환을 확인했습니다.', flush=True)
                self.job_id = None
            elif self.state_created and self.state_path.exists():
                saved = json.loads(self.state_path.read_text())
                if saved.get('job_name') == self.job_name:
                    self.state_path.unlink()
        except Exception as exc:
            error = exc
        finally:
            for host, control in ((self.config.compute_host, self.compute_socket),
                                  (self.config.login_host, self.login_socket)):
                if control:
                    try:
                        subprocess.run(['ssh', '-S', str(control), '-O', 'exit', '-p', str(self.config.ssh_port),
                                        f'{self.config.user}@{host}'], capture_output=True, timeout=10, check=False)
                    except (OSError, subprocess.TimeoutExpired):
                        pass
            if self.environment_set:
                if self.config.tokenizer_enabled:
                    if self.previous_tokenizer_url is None:
                        os.environ.pop('PERSONA_QWEN_TOKENIZER_URL', None)
                    else:
                        os.environ['PERSONA_QWEN_TOKENIZER_URL'] = self.previous_tokenizer_url
                if self.previous_url is None:
                    os.environ.pop('PERSONA_QWEN_API_URL', None)
                else:
                    os.environ['PERSONA_QWEN_API_URL'] = self.previous_url
                if self.config.embedding_model:
                    if self.previous_embedding_url is None:
                        os.environ.pop('PERSONA_EMBEDDING_API_URL', None)
                    else:
                        os.environ['PERSONA_EMBEDDING_API_URL'] = self.previous_embedding_url
            if self.temp:
                self.temp.cleanup()
            self.closed = True
        if error:
            raise RuntimeError(f'GPU 작업 반환을 확인하지 못했습니다. {self.state_path}의 작업 ID를 확인하세요.') from error
