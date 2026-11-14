import json
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.main import create_app


class CorsTests(unittest.TestCase):
    def client(self, origins=None):
        values = {} if origins is None else {"CORS_ALLOWED_ORIGINS": json.dumps(origins)}
        with patch.dict("os.environ", values, clear=True):
            return TestClient(create_app())

    def test_allowed_origin_can_post_json(self):
        client = self.client(["https://frontend.example.com"])
        response = client.options('/api/routes', headers={
            'Origin': 'https://frontend.example.com',
            'Access-Control-Request-Method': 'POST',
            'Access-Control-Request-Headers': 'content-type',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['access-control-allow-origin'], 'https://frontend.example.com')
        response = client.post('/api/routes', headers={'Origin': 'https://frontend.example.com'}, json={
            'start_node_id': 'mainGate', 'end_node_id': 'mainGate',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['cost'], 0)
        self.assertEqual(response.headers['access-control-allow-origin'], 'https://frontend.example.com')

    def test_other_origins_are_not_allowed(self):
        client = self.client(["https://frontend.example.com"])
        for origin in ['https://other.example.com', 'https://frontend.example.com.attacker.com']:
            response = client.options('/api/routes', headers={
                'Origin': origin, 'Access-Control-Request-Method': 'POST',
            })
            self.assertEqual(response.status_code, 400)
            self.assertNotIn('access-control-allow-origin', response.headers)

    def test_missing_configuration_keeps_health_and_blocks_cross_origin(self):
        response = self.client().get('/api/health', headers={'Origin': 'https://frontend.example.com'})
        self.assertEqual(response.json(), {'status': 'ok'})
        self.assertNotIn('access-control-allow-origin', response.headers)

    def test_api_errors_keep_cors_headers(self):
        client = self.client(["https://frontend.example.com"])
        headers = {'Origin': 'https://frontend.example.com'}
        responses = [
            client.post('/api/routes', json={}, headers=headers),
            client.post('/api/routes', json={'start_node_id': 'missing', 'end_node_id': 'mainGate'}, headers=headers),
        ]
        with patch.dict('os.environ', {}, clear=True):
            responses.append(client.post('/api/chat', json={'message': '안녕'}, headers=headers))
        self.assertEqual([r.status_code for r in responses], [422, 400, 503])
        for response in responses:
            self.assertEqual(response.headers['access-control-allow-origin'], 'https://frontend.example.com')

    def test_invalid_origin_configuration_fails_clearly(self):
        for value in ['not-json', '"https://frontend.example.com"', '["*"]', '[12]', '["https://example.com/path"]']:
            with self.subTest(value=value), patch.dict('os.environ', {'CORS_ALLOWED_ORIGINS': value}):
                with self.assertRaisesRegex(ValueError, 'CORS_ALLOWED_ORIGINS'):
                    create_app()
