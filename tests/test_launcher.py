"""Startup must stop on an incompatible interpreter or dependency failure."""
from pathlib import Path
import shutil
import subprocess

def prepare(tmp_path, body):
    shutil.copyfile(Path(__file__).resolve().parents[1] / 'start.command', tmp_path / 'start.command')
    interpreter = tmp_path / '.venv' / 'bin' / 'python'
    interpreter.parent.mkdir(parents=True)
    interpreter.write_text('#!/bin/bash\n' + body)
    interpreter.chmod(0o700)
    return subprocess.run(['bash', str(tmp_path / 'start.command')], cwd=tmp_path, text=True, capture_output=True)

def test_old_python_stops_before_install(tmp_path):
    result = prepare(tmp_path, 'exit 1\n')
    assert result.returncode == 1
    assert 'needs Python 3.9 or newer' in result.stdout
    assert not (tmp_path / 'data').exists()

def test_failed_install_never_starts_app(tmp_path):
    result = prepare(tmp_path, '''
case "$*" in
    *"import sys"*) exit 0 ;;
    --version) echo 'Python 3.9.25'; exit 0 ;;
    '-m pip install -r requirements.lock') echo 'Simulated install failure' >&2; exit 17 ;;
    *) touch unexpected-app-start; exit 99 ;;
esac
''')
    assert result.returncode == 17
    assert 'Simulated install failure' in result.stderr
    assert not (tmp_path / 'unexpected-app-start').exists()
    assert not (tmp_path / 'data').exists()

def test_password_setup_without_scrypt(tmp_path, monkeypatch):
    # Some Mac system Python builds do not expose hashlib.scrypt.
    import getpass
    import hashlib
    import runpy
    import sys
    import store
    from werkzeug.security import check_password_hash
    monkeypatch.setattr(store, 'DB', str(tmp_path / 'tracker.sqlite3'))
    monkeypatch.delattr(hashlib, 'scrypt', raising=False)
    monkeypatch.setattr(getpass, 'getpass', lambda prompt: 'portable-test-password')
    monkeypatch.setattr(sys, 'argv', ['app.py', '--set-password'])
    runpy.run_path(str(Path(__file__).resolve().parents[1] / 'app.py'), run_name='__main__')
    value = (tmp_path / 'password.hash').read_text()
    assert value.startswith('pbkdf2:sha256:1000000$')
    assert check_password_hash(value, 'portable-test-password')
