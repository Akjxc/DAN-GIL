"""Real JSON + team NetworkX routing + AI adapter; no Gemini API requests."""

import unittest
from unittest.mock import patch

import networkx as nx

from backend.graph import load_graph
from backend.routing import find_route, search_places
from backend.tools import ToolExecutor, call_routing


class RoutingIntegrationTests(unittest.TestCase):
    def test_alias_floor_and_basement(self):
        for query, expected in [("정문", "mainGate"),
                                ("소미관 3층", "softwareMediaF3Hall"),
                                ("소미관 지하 1층", "softwareMediaB1Hall"),
                                ("소미관 1층", "softwareMediaF1Hall")]:
            with self.subTest(query=query):
                self.assertEqual([n["id"] for n in search_places(query)["matches"]], [expected])

    def test_ambiguous_engineering_building_keeps_three_candidates(self):
        matches = search_places("공학관 3층")["matches"]
        self.assertEqual({n["building_id"] for n in matches},
                         {"engineering1", "engineering2", "engineering3"})
        self.assertTrue(all(n["floor"] == 3 and n["kind"] == "hall" for n in matches))

    def test_unknown_place_and_unmapped_classroom(self):
        for query in ["없는건물", "제4공학관", "소미관 301호", "소미관 99층"]:
            with self.subTest(query=query):
                self.assertEqual(search_places(query)["matches"], [])

    def test_real_route_excludes_stairs(self):
        executor = ToolExecutor()
        executor.execute("search_places", {"query": "정문"})
        executor.execute("search_places", {"query": "소미관 3층"})
        result = executor.execute("find_route", {
            "start_node_id": "mainGate", "end_node_id": "softwareMediaF3Hall",
            "exclude_conditions": ["stair"],
        })
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["nodes"][0]["id"], "mainGate")
        self.assertEqual(result["nodes"][-1]["id"], "softwareMediaF3Hall")
        self.assertTrue(all(e["condition"] != "stair" for e in result["edges"]))
        self.assertEqual(len(result["edges"]), len(result["nodes"]) - 1)
        self.assertIsNone(result["distance_m"])
        self.assertEqual(result["metric"], "hops")

    def test_missing_node_and_impossible_exclusions(self):
        arguments = {"start_node_id": "mainGate", "end_node_id": "softwareMediaF3Hall",
                     "exclude_kinds": ["outdoorPath", "indoorPath"], "exclude_conditions": []}
        with patch("backend.routing.find_route_with_minimal_exceptions") as fallback:
            self.assertEqual(call_routing("find_route", arguments), {"status": "no_route"})
            fallback.assert_not_called()
        arguments["end_node_id"] = "missing-node"
        self.assertEqual(call_routing("find_route", arguments), {"status": "invalid_request"})

    def test_team_filter_does_not_mutate_original_graph(self):
        graph = load_graph()
        original = graph.copy()
        find_route(graph, "mainGate", "softwareMediaF3Hall", excluded_conditions=["stair"])
        self.assertTrue(nx.utils.graphs_equal(graph, original))

    def test_same_node_returns_one_node_and_no_edges(self):
        result = call_routing("find_route", {
            "start_node_id": "mainGate", "end_node_id": "mainGate",
            "exclude_kinds": [], "exclude_conditions": [],
        })
        self.assertEqual(len(result["nodes"]), 1)
        self.assertEqual(result["edges"], [])


if __name__ == "__main__":
    unittest.main()
