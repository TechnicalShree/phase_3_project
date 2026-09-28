"""Real HTTP/process checks: SQLite survives server termination, not just object recreation."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from urllib.request import Request, urlopen


class ServerChecks(unittest.TestCase):
    def test_http_restart_and_stream(self):
        with tempfile.TemporaryDirectory() as directory:
            with socket.socket() as listener:
                listener.bind(('127.0.0.1', 0))
                port = listener.getsockname()[1]
            base = f'http://127.0.0.1:{port}'
            env = {**os.environ, 'DATA_DIR': directory, 'MODEL_MODE': 'demo', 'API_TOKEN': ''}
            def request(path, body=None):
                data = json.dumps(body).encode() if body is not None else None
                with urlopen(Request(base + path, data=data, headers={'Content-Type': 'application/json'}), timeout=15) as response:
                    return response.read().decode()
            def start():
                process = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'app.api:app', '--host', '127.0.0.1', '--port', str(port)],
                                           env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                for _ in range(150):
                    try:
                        request('/health')
                        return process
                    except OSError:
                        if process.poll() is not None:
                            self.fail('Server exited during startup')
                        time.sleep(.05)
                process.kill()
                process.wait()
                self.fail('Server did not become healthy')
            process = start()
            try:
                streamed = request('/stream', {'thread_id': 'restart', 'text': 'Campus wifi outage affecting all students'})
                events = [json.loads(chunk[6:]) for chunk in streamed.split('\n\n') if chunk.startswith('data: ')]
                self.assertTrue(any('tools' in event.get('nodes', []) for event in events))
                pending = events[-1]
                self.assertEqual(pending['event'], 'result')
                self.assertEqual(len(pending['pending']), 1)
                self.assertEqual(json.loads(request('/tickets')), [])
                process.kill()
                process.wait(timeout=10)
                process = start()
                saved = json.loads(request('/threads/restart'))
                self.assertEqual(saved['checkpoint_id'], pending['checkpoint_id'])
                approved = json.loads(request('/approve', {'thread_id': 'restart', 'checkpoint_id': saved['checkpoint_id']}))
                self.assertEqual(approved['values']['write_result']['status'], 'created')
                followup = json.loads(request('/run', {'thread_id': 'restart', 'text': 'Campus wifi is working now'}))
                self.assertEqual(len(followup['values']['history']), 2)
                self.assertEqual(len(json.loads(request('/tickets'))), 1)
            finally:
                process.terminate()
                process.wait(timeout=10)


if __name__ == '__main__':
    unittest.main()
