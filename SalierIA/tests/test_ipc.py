import json
import threading
import time

import pytest

from src.bridge.ipc import IPCManager, IPCError


def _write_response(ipc: IPCManager, cmd_id: str, delay: float = 0.05):
    time.sleep(delay)
    resp = {'cmd_id': cmd_id, 'status': 'ok', 'message': 'done', 'error_code': None}
    ipc.resp_file.write_text(json.dumps(resp))


def _read_cmd_id(ipc: IPCManager, retries: int = 20) -> str:
    for _ in range(retries):
        time.sleep(0.05)
        if ipc.cmd_file.exists():
            try:
                return json.loads(ipc.cmd_file.read_text())['cmd_id']
            except (json.JSONDecodeError, KeyError):
                pass
    raise RuntimeError('cmd_file never appeared')


def test_send_creates_cmd_file(tmp_path):
    ipc = IPCManager(str(tmp_path))
    result_holder = {}

    def run():
        cmd_id = _read_cmd_id(ipc)
        assert ipc.cmd_file.exists()
        data = json.loads(ipc.cmd_file.read_text())
        assert data['tool'] == 'add_note'
        _write_response(ipc, cmd_id)

    t = threading.Thread(target=run)
    t.start()
    resp = ipc.send_and_wait('add_note', {'pitch': 'C4', 'duration': 'quarter', 'measure': 1})
    t.join()
    assert resp['status'] == 'ok'


def test_response_matched_by_cmd_id(tmp_path):
    ipc = IPCManager(str(tmp_path))

    def run():
        cmd_id = _read_cmd_id(ipc)
        # Write a stale response first
        stale = {'cmd_id': 'stale-id', 'status': 'ok', 'message': 'stale', 'error_code': None}
        ipc.resp_file.write_text(json.dumps(stale))
        time.sleep(0.1)
        # Write the correct response
        _write_response(ipc, cmd_id)

    t = threading.Thread(target=run)
    t.start()
    resp = ipc.send_and_wait('add_rest', {'duration': 'quarter', 'measure': 1})
    t.join()
    assert resp['cmd_id'] != 'stale-id'
    assert resp['message'] == 'done'


def test_timeout_raises(tmp_path):
    ipc = IPCManager(str(tmp_path))
    ipc.RESPONSE_TIMEOUT = 0.3
    with pytest.raises(TimeoutError):
        ipc.send_and_wait('set_tempo', {'bpm': 120})


def test_sibelius_error_raises_ipc_error(tmp_path):
    ipc = IPCManager(str(tmp_path))

    def run():
        cmd_id = _read_cmd_id(ipc)
        err_resp = {
            'cmd_id': cmd_id,
            'status': 'error',
            'message': 'No score is open',
            'error_code': 'no_score',
        }
        time.sleep(0.05)
        ipc.resp_file.write_text(json.dumps(err_resp))

    t = threading.Thread(target=run)
    t.start()
    with pytest.raises(IPCError, match='no_score'):
        ipc.send_and_wait('get_score_info', {})
    t.join()


def test_atomic_write(tmp_path):
    ipc = IPCManager(str(tmp_path))
    tmp_file = ipc.cmd_file.with_suffix('.tmp')

    def run():
        cmd_id = _read_cmd_id(ipc)
        assert not tmp_file.exists(), '.tmp file should not exist after atomic rename'
        _write_response(ipc, cmd_id)

    t = threading.Thread(target=run)
    t.start()
    ipc.send_and_wait('undo', {})
    t.join()


def test_clear_removes_files(tmp_path):
    ipc = IPCManager(str(tmp_path))
    ipc.cmd_file.write_text('{}')
    ipc.resp_file.write_text('{}')
    ipc.clear()
    assert not ipc.cmd_file.exists()
    assert not ipc.resp_file.exists()
