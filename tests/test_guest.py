"""Guest access stays isolated and ticket creation still requires review."""
import os
import tempfile
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.api import create_app


class GuestChecks(unittest.TestCase):
    def test_guest_isolation_and_approval(self):
        with patch.dict(os.environ, {'MODEL_MODE': 'demo', 'API_TOKEN': 'admin-secret', 'PUBLIC_GUEST_ACCESS': '1'}), tempfile.TemporaryDirectory() as directory:
            with TestClient(create_app(directory)) as client:
                self.assertFalse(client.get('/health').json()['auth_required'])
                result = client.post('/run', json={'thread_id': 'same-id', 'text': 'Campus wifi outage affecting all students'}).json()
                self.assertEqual(len(result['pending']), 1)
                self.assertEqual(client.get('/tickets').json(), [])
                first_cookie = client.cookies.get('campus-session')
                client.cookies.clear()
                self.assertEqual(client.get('/threads').json(), [])
                self.assertEqual(client.get('/threads/same-id').status_code, 404)
                self.assertEqual(client.post('/approve', json={'thread_id': 'same-id', 'checkpoint_id': result['checkpoint_id']}).status_code, 409)
                client.cookies.clear()
                client.cookies.set('campus-session', first_cookie)
                self.assertEqual(client.post('/approve', json={'thread_id': 'same-id', 'checkpoint_id': result['checkpoint_id']}).status_code, 200)
                self.assertEqual(len(client.get('/tickets').json()), 1)
                self.assertEqual(client.get('/threads', headers={'Authorization': 'Bearer admin-secret'}).json(), [])
                self.assertEqual(client.post('/run', headers={'Origin': 'https://evil.example'}, json={'thread_id': 'bad', 'text': 'Wifi issue'}).status_code, 403)
                client.cookies.clear()
                client.cookies.set('campus-session', first_cookie[:-1] + ('0' if first_cookie[-1] != '0' else '1'))
                self.assertEqual(client.get('/threads').json(), [])


if __name__ == '__main__':
    unittest.main()
