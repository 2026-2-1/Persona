import json
import subprocess
from pathlib import Path

import pytest

from uxagent import gpu_passwords
from uxagent.gpu_session import GpuSession
from test_gpu_session import config


def test_setup_saves_only_keychain_and_nonsecret_mode(tmp_path, monkeypatch):
    path=tmp_path/'gpu.json'; path.write_text(config().model_dump_json())
    values=iter(['login-secret','login-secret','node-secret','node-secret'])
    monkeypatch.setattr(gpu_passwords.sys,'platform','darwin')
    monkeypatch.setattr(gpu_passwords.sys.stdin,'isatty',lambda:True)
    monkeypatch.setattr(gpu_passwords.getpass,'getpass',lambda prompt:next(values))
    saved=[]
    monkeypatch.setattr(gpu_passwords,'store_password',lambda service,account,password:saved.append((service,account,password)))
    gpu_passwords.setup_passwords(path,repo_root=tmp_path/'repo')
    data=json.loads(path.read_text())
    assert data['ssh_password_store']=='macos-keychain'
    assert data['ssh_batch_mode'] is False
    assert [v[2] for v in saved]==['login-secret','node-secret']
    assert 'secret' not in path.read_text()


def test_master_uses_askpass_without_password_in_env_or_args(tmp_path, monkeypatch):
    manager=GpuSession(config().model_copy(update={'ssh_password_store':'macos-keychain','ssh_batch_mode':True}))
    manager.temp=__import__('tempfile').TemporaryDirectory(dir=tmp_path)
    calls=[]
    monkeypatch.setattr(gpu_passwords.sys,'platform','darwin')
    monkeypatch.setattr('uxagent.gpu_session.subprocess.run',lambda args,**kw:(calls.append((args,kw)) or subprocess.CompletedProcess(args,0)))
    try:
        manager._master('node.test',tmp_path/'socket')
        args,kw=calls[-1]
        assert 'BatchMode=no' in args and 'NumberOfPasswordPrompts=1' in args
        assert 'StrictHostKeyChecking=yes' in args
        assert kw['env']['SSH_ASKPASS_REQUIRE']=='force'
        script=Path(kw['env']['SSH_ASKPASS']).read_text()
        assert 'node.test' not in script
        assert kw['env']['UXAGENT_SSH_ACCOUNT']=='user@node.test:10000'
        assert kw['stdin'] is subprocess.DEVNULL
    finally:
        manager.temp.cleanup()


def test_askpass_refuses_host_confirmations_and_missing_credentials(monkeypatch,capsys):
    monkeypatch.setenv('UXAGENT_SSH_ACCOUNT','user@node.test:10000')
    calls=[]
    monkeypatch.setattr(gpu_passwords,'read_password',lambda *args:calls.append(args) or 'stored-secret')
    assert gpu_passwords.askpass('Are you sure you want to continue connecting (yes/no)?')==1
    assert not calls
    assert gpu_passwords.askpass("user@node.test's password: ")==0
    assert capsys.readouterr().out=='stored-secret\n'


@pytest.mark.parametrize('inputs',[['',''],['first','different']])
def test_empty_or_mismatching_password_never_saves(monkeypatch,tmp_path,inputs):
    path=tmp_path/'gpu.json'; original=config().model_dump_json(); path.write_text(original)
    monkeypatch.setattr(gpu_passwords.sys,'platform','darwin')
    monkeypatch.setattr(gpu_passwords.sys.stdin,'isatty',lambda:True)
    values=iter(inputs)
    monkeypatch.setattr(gpu_passwords.getpass,'getpass',lambda prompt:next(values))
    monkeypatch.setattr(gpu_passwords,'store_password',lambda *args:pytest.fail('must not store'))
    with pytest.raises(ValueError): gpu_passwords.setup_passwords(path,repo_root=tmp_path/'repo')
    assert path.read_text()==original
