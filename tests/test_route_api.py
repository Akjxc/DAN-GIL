import unittest
from unittest.mock import patch

import networkx as nx
from fastapi.testclient import TestClient

from backend.main import create_app


class RouteApiTests(unittest.TestCase):
    def setUp(self):
        with patch.dict('os.environ', {'CORS_ALLOWED_ORIGINS': '["https://dangil.vercel.app"]'}):
            self.client = TestClient(create_app())

    def test_existing_cost_request_without_metric_still_works(self):
        response = self.client.post('/api/routes', json={
            'start_node_id': 'mainGate', 'end_node_id': 'mainGate',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['metric'], 'cost')
        self.assertEqual(response.json()['cost'], 0)

    def test_distance_route_remains_available_with_cors(self):
        graph = nx.Graph()
        for node in ['a', 'b', 'c']:
            graph.add_node(node, id=node, name=node)
        for u, v, meters in [('a', 'c', 100), ('a', 'b', 2), ('b', 'c', 3)]:
            graph.add_edge(u, v, distance_m=meters)
        with patch('backend.main.load_graph', return_value=graph):
            response = self.client.post('/api/routes', json={
                'start_node_id': 'a', 'end_node_id': 'c', 'metric': 'distance',
            }, headers={'Origin': 'https://dangil.vercel.app'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual([n['id'] for n in response.json()['nodes']], ['a', 'b', 'c'])
        self.assertEqual(response.json()['distance_m'], 5)
        self.assertIsNone(response.json()['total_cost'])
        self.assertEqual(response.headers['access-control-allow-origin'], 'https://dangil.vercel.app')

    def test_distance_request_rejects_avoidance_options(self):
        response = self.client.post('/api/routes', json={
            'start_node_id': 'mainGate', 'end_node_id': 'mainGate',
            'metric': 'distance', 'exclude_conditions': ['stair'],
        })
        self.assertEqual(response.status_code, 422)

    def test_unknown_metric_is_rejected(self):
        response = self.client.post('/api/routes', json={
            'start_node_id': 'mainGate', 'end_node_id': 'mainGate', 'metric': 'unknown',
        })
        self.assertEqual(response.status_code, 422)
