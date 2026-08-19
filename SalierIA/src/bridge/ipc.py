import json
import time
import uuid
from pathlib import Path


class IPCError(Exception):
    pass


class IPCManager:
    RESPONSE_TIMEOUT = 8.0
    POLL_INTERVAL = 0.1

    def __init__(self, bridge_dir: str):
        self.bridge = Path(bridge_dir)
        self.bridge.mkdir(parents=True, exist_ok=True)
        self.cmd_file = self.bridge / 'agent_cmd.json'
        self.resp_file = self.bridge / 'agent_resp.json'

    def send_and_wait(self, tool_name: str, params: dict) -> dict:
        cmd_id = str(uuid.uuid4())
        command = {
            'cmd_id': cmd_id,
            'timestamp': time.time(),
            'tool': tool_name,
            'params': params,
        }

        self.resp_file.unlink(missing_ok=True)

        tmp = self.cmd_file.with_suffix('.tmp')
        tmp.write_text(json.dumps(command, ensure_ascii=False))
        tmp.rename(self.cmd_file)

        deadline = time.time() + self.RESPONSE_TIMEOUT
        while time.time() < deadline:
            if self.resp_file.exists():
                try:
                    resp = json.loads(self.resp_file.read_text())
                    if resp.get('cmd_id') == cmd_id:
                        if resp.get('status') == 'error':
                            raise IPCError(
                                f"Sibelius error [{resp.get('error_code')}]: {resp.get('message')}"
                            )
                        return resp
                except json.JSONDecodeError:
                    pass
            time.sleep(self.POLL_INTERVAL)

        raise TimeoutError(f'Sibelius did not respond to {tool_name} within {self.RESPONSE_TIMEOUT}s')

    def clear(self):
        self.cmd_file.unlink(missing_ok=True)
        self.resp_file.unlink(missing_ok=True)
