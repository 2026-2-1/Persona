import base64
import json
import os
from pathlib import Path
import subprocess

import pytest

from uxagent.gpu_ssh_keys import install_public_key, prepare_identity, setup_gpu_key
from uxagent.gpu_session import GpuSession, GpuSessionConfig

PUBLIC = 'ssh-ed25519 ' + base64.b64encode(b'public-test-fixture').decode() + ' persona-gpu'


@pytest.mark.skipif(os.name=='nt',reason='remote POSIX authorized_keys installer uses flock')
def test_install_preserves_other_keys_and_is_idempotent(tmp_path):
    directory=tmp_path/'ssh';directory.mkdir()
    target=directory/'authorized_keys';target.write_text('existing-key-without-newline')
    assert install_public_key(directory,PUBLIC)['added'] is True
    saved=target.read_text()
    assert saved.startswith('existing-key-without-newline\n')
    assert install_public_key(directory,PUBLIC)['added'] is False
    assert target.read_text()==saved


@pytest.mark.skipif(os.name=='nt',reason='remote POSIX authorized_keys installer uses flock')
def test_existing_restricted_key_does_not_get_unrestricted_duplicate(tmp_path):
    directory=tmp_path/'ssh';directory.mkdir()
    target=directory/'authorized_keys';target.write_text('from="10.0.0.0/8" '+PUBLIC+'\n')
    before=target.read_bytes()
    assert install_public_key(directory,PUBLIC)['added'] is False
    assert target.read_bytes()==before


@pytest.mark.skipif(os.name=='nt',reason='remote POSIX authorized_keys installer uses flock')
def test_install_refuses_authorized_keys_symlink(tmp_path):
    directory=tmp_path/'ssh';directory.mkdir()
    other=tmp_path/'other';other.write_text('untouched')
    (directory/'authorized_keys').symlink_to(other)
    with pytest.raises(ValueError,match='symlink'): install_public_key(directory,PUBLIC)
    assert other.read_text()=='untouched'


def test_existing_identity_is_reused_without_reading_private_key(tmp_path,monkeypatch):
    key=tmp_path/'identity';key.write_text('private-fixture-not-for-reading');key.chmod(0o600)
    key.with_name(key.name+'.pub').write_text(PUBLIC)
    calls=[]
    def run(args,**kwargs):
        calls.append(args);return subprocess.CompletedProcess(args,0,'','')
    monkeypatch.setattr('uxagent.gpu_ssh_keys.subprocess.run',run)
    assert prepare_identity(key,repo_root=tmp_path/'repo')==PUBLIC
    assert not any(args[:2]==['ssh-keygen','-t'] for args in calls)
    assert all(str(key) not in args for args in calls)


def test_identity_must_live_outside_repository(tmp_path):
    with pytest.raises(ValueError,match='저장소 밖'):
        prepare_identity(tmp_path/'key',repo_root=tmp_path)


def test_partial_identity_is_not_overwritten(tmp_path):
    key=tmp_path/'identity';key.write_text('keep')
    with pytest.raises(ValueError,match='쌍'):
        prepare_identity(key,repo_root=tmp_path/'repo')
    assert key.read_text()=='keep'


def write_config(tmp_path):
    c=GpuSessionConfig(login_host='login.test',compute_host='node.test',user='user',
       partition='p02',node='DIS01',gres='gpu:A6000:1',cpus=4,memory='48G',walltime='04:00:00')
    p=tmp_path/'repo/runs/private/gpu-session.json';p.parent.mkdir(parents=True);p.write_text(c.model_dump_json())
    return p


def fake_setup(tmp_path,monkeypatch,*,failure=False):
    events=[]
    monkeypatch.setattr('uxagent.gpu_ssh_keys.prepare_identity',lambda *a,**kw:PUBLIC)
    monkeypatch.setattr('uxagent.gpu_ssh_keys.load_identity',lambda *a,**kw:None)
    class Session:
        def __init__(self,config,state_path): self.config=config
        def open_login(self): events.append('login')
        def _remote(self,*args,**kwargs):
            assert json.loads(kwargs['input'])['public_key']==PUBLIC
            events.append('install_login');return '{"added":true}'
        def start(self,**kwargs): assert kwargs=={'authentication_only':True};events.append('allocate')
        def install_compute_key(self,command,payload): events.append('install_compute')
        def close(self): events.append('release')
    def verify(config,host):
        events.append('verify_'+host)
        if failure and host=='node.test': raise RuntimeError('key rejected')
    monkeypatch.setattr('uxagent.gpu_ssh_keys.GpuSession',Session)
    monkeypatch.setattr('uxagent.gpu_ssh_keys.verify_key_auth',verify)
    return events


@pytest.mark.parametrize('previous_store',[None,'macos-keychain'])
def test_configuration_is_enabled_only_after_both_fresh_auth_checks_and_release(tmp_path,monkeypatch,previous_store):
    path=write_config(tmp_path);events=fake_setup(tmp_path,monkeypatch)
    initial=json.loads(path.read_text());initial['ssh_password_store']=previous_store;path.write_text(json.dumps(initial))
    setup_gpu_key(path,key_path=tmp_path/'identity',repo_root=tmp_path/'repo')
    saved=json.loads(path.read_text())
    assert saved['ssh_batch_mode'] is True and saved['identity_file']==str(tmp_path/'identity')
    assert saved['ssh_password_store'] is None
    assert events==['login','install_login','verify_login.test','allocate','install_compute','verify_node.test','release']


def test_rejected_compute_key_preserves_configuration_and_releases_job(tmp_path,monkeypatch):
    path=write_config(tmp_path);before=path.read_bytes();events=fake_setup(tmp_path,monkeypatch,failure=True)
    with pytest.raises(RuntimeError,match='key rejected'):
        setup_gpu_key(path,key_path=tmp_path/'identity',repo_root=tmp_path/'repo')
    assert path.read_bytes()==before and events[-1]=='release'


def test_batch_identity_options_apply_to_jump_and_target(tmp_path):
    path=write_config(tmp_path)
    config=GpuSessionConfig.model_validate_json(path.read_text()).model_copy(update={
        'identity_file':str(tmp_path/'identity'),'ssh_batch_mode':True})
    manager=GpuSession(config)
    args=manager._ssh('node.test',tmp_path/'control')
    assert '-i' in args and str(tmp_path/'identity') in args and 'IdentitiesOnly=yes' in args


def test_agent_registration_uses_os_keychain_and_checks_the_specific_public_key(tmp_path,monkeypatch):
    from uxagent.gpu_ssh_keys import load_identity
    calls=[]
    monkeypatch.setattr('uxagent.gpu_ssh_keys.sys.platform','darwin')
    monkeypatch.setattr('uxagent.gpu_ssh_keys.sys.stdin.isatty',lambda:True)
    def run(args,**kwargs):
        calls.append((args,kwargs))
        return subprocess.CompletedProcess(args,0,'','')
    monkeypatch.setattr('uxagent.gpu_ssh_keys.subprocess.run',run)
    key=tmp_path/'identity'
    load_identity(key,state_dir=tmp_path)
    assert any(args==['/usr/bin/ssh-add','--apple-use-keychain',str(key)] for args,_ in calls)
    assert any(args==['/usr/bin/ssh-add','-T',str(key)+'.pub'] for args,_ in calls)
    add_options=next(kwargs for args,kwargs in calls if '--apple-use-keychain' in args)
    assert 'input' not in add_options and 'capture_output' not in add_options


def test_key_probe_disables_existing_connections_and_password_methods(tmp_path,monkeypatch):
    from uxagent.gpu_ssh_keys import verify_key_auth
    path=write_config(tmp_path)
    config=GpuSessionConfig.model_validate_json(path.read_text()).model_copy(update={'identity_file':str(tmp_path/'identity')})
    calls=[]
    def run(args,**kwargs):
        calls.append(args);return subprocess.CompletedProcess(args,0,'','')
    monkeypatch.setattr('uxagent.gpu_ssh_keys.subprocess.run',run)
    verify_key_auth(config,config.compute_host)
    args=calls[0];proxy=next(arg for arg in args if arg.startswith('ProxyCommand='))
    for option in ['ControlPath=none','PreferredAuthentications=publickey','BatchMode=yes','IdentitiesOnly=yes']:
        assert option in args and option in proxy


def test_cli_exposes_setup_and_unlock_commands():
    from uxagent.cli import _parser
    assert _parser().parse_args(['gpu-key-setup']).identity_file=='~/.ssh/uxagent_gpu_ed25519'
    assert _parser().parse_args(['gpu-key-unlock']).gpu_config=='runs/private/gpu-session.json'


def test_noninteractive_key_generation_does_not_create_files(tmp_path,monkeypatch):
    monkeypatch.setattr('uxagent.gpu_ssh_keys.sys.stdin.isatty',lambda:False)
    key=tmp_path/'not-created'
    with pytest.raises(ValueError,match='사용자 터미널'):
        prepare_identity(key,repo_root=tmp_path/'repo')
    assert not key.exists() and not key.with_name(key.name+'.pub').exists()


@pytest.mark.skipif(os.name=='nt',reason='isolated POSIX ssh-agent integration')
def test_real_isolated_agent_can_sign_with_ephemeral_fixture_key(tmp_path,monkeypatch):
    import shutil
    from uxagent.gpu_ssh_keys import load_identity
    if not all(shutil.which(tool) for tool in ('ssh-agent','ssh-add','ssh-keygen')):
        pytest.skip('OpenSSH tools unavailable')
    key=tmp_path/'fixture-key'
    subprocess.run(['ssh-keygen','-q','-t','ed25519','-N','','-f',str(key)],check=True,capture_output=True)
    monkeypatch.setattr('uxagent.gpu_ssh_keys.sys.platform','linux')
    monkeypatch.setattr('uxagent.gpu_ssh_keys.sys.stdin.isatty',lambda:True)
    monkeypatch.setenv('SSH_AUTH_SOCK',str(tmp_path/'no-existing-agent'))
    try:
        socket_path=load_identity(key,state_dir=tmp_path)
        saved=json.loads((tmp_path/'gpu-ssh-agent.json').read_text())
        assert socket_path==saved['socket'] and Path(socket_path).is_socket()
        environment={**os.environ,'SSH_AUTH_SOCK':socket_path}
        assert subprocess.run(['ssh-add','-T',str(key)+'.pub'],env=environment,capture_output=True).returncode==0
    finally:
        state=tmp_path/'gpu-ssh-agent.json'
        if state.exists():
            saved=json.loads(state.read_text())
            subprocess.run(['ssh-agent','-k'],env={**os.environ,'SSH_AGENT_PID':str(saved['pid']),'SSH_AUTH_SOCK':saved['socket']},capture_output=True,check=False)


@pytest.mark.skipif(os.name=='nt',reason='remote POSIX authorized_keys installer')
def test_noncooperating_concurrent_append_is_preserved(tmp_path,monkeypatch):
    directory=tmp_path/'ssh';directory.mkdir()
    target=directory/'authorized_keys';target.write_text('existing-key\n')
    original_fdopen=os.fdopen
    class Handle:
        def __init__(self,handle): self.handle=handle;self.injected=False
        def __getattr__(self,name): return getattr(self.handle,name)
        def __enter__(self): self.handle.__enter__();return self
        def __exit__(self,*args): return self.handle.__exit__(*args)
        def write(self,data):
            if not self.injected:
                with target.open('ab') as external: external.write(b'concurrent-key\n')
                self.injected=True
            return self.handle.write(data)
    with monkeypatch.context() as local:
        local.setattr(os,'fdopen',lambda *a,**kw:Handle(original_fdopen(*a,**kw)))
        install_public_key(directory,PUBLIC)
    assert target.read_text().splitlines()==['existing-key','concurrent-key',PUBLIC]
