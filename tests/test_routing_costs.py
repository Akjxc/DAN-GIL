"""Route choice must respect base costs and prioritize minimal exceptions."""

import unittest

import networkx as nx

from backend.routing import find_route, find_route_with_minimal_exceptions


def add_path(graph, nodes, conditions):
    for u, v, condition in zip(nodes, nodes[1:], conditions):
        graph.add_edge(u, v, kind="indoorPath", condition=condition)


class RoutingCostTests(unittest.TestCase):
    def test_strict_route_prefers_lower_burden_over_fewer_edges(self):
        graph = nx.Graph()
        add_path(graph, ["s", "a", "t"], ["stair", "stair"])
        add_path(graph, ["s", "b", "c", "t"], ["flat"] * 3)

        self.assertEqual(find_route(graph, "s", "t"), ["s", "b", "c", "t"])

    def test_equal_exception_counts_are_resolved_by_base_cost(self):
        graph = nx.Graph()
        add_path(graph, ["s", "p"], ["slope"])
        add_path(graph, ["p", "a", "t"], ["stair", "stair"])
        add_path(graph, ["p", "b", "c", "t"], ["flat"] * 3)

        result = find_route_with_minimal_exceptions(
            graph, "s", "t", excluded_conditions=["slope"]
        )
        self.assertEqual(result, ["s", "p", "b", "c", "t"])

    def test_one_exception_beats_two_even_with_large_base_cost(self):
        graph = nx.Graph()
        expensive_path = ["s", *[f"a{i}" for i in range(7)], "t"]
        add_path(graph, expensive_path, ["slope"] + ["stair"] * 7)
        add_path(graph, ["s", "x", "t"], ["slope", "slope"])

        result = find_route_with_minimal_exceptions(
            graph, "s", "t", excluded_conditions=["slope"]
        )
        self.assertEqual(result, expensive_path)

    def test_kind_and_condition_filters_remain_strict(self):
        graph = nx.Graph()
        add_path(graph, ["s", "a", "t"], ["stair", "flat"])
        add_path(graph, ["s", "b", "t"], ["flat", "flat"])
        graph.edges["s", "b"]["kind"] = "outdoorPath"

        with self.assertRaises(nx.NetworkXNoPath):
            find_route(graph, "s", "t", excluded_kinds=["outdoorPath"],
                       excluded_conditions=["stair"])

    def test_minimal_exception_search_does_not_mutate_edge_attributes(self):
        graph = nx.Graph()
        add_path(graph, ["s", "a", "t"], ["stair", "flat"])
        original = graph.copy()

        find_route_with_minimal_exceptions(
            graph, "s", "t", excluded_conditions=["stair"]
        )
        self.assertTrue(nx.utils.graphs_equal(graph, original))


class DistanceRoutingTests(unittest.TestCase):
    def test_shorter_outdoor_path_wins_even_with_more_edges(self):
        graph = nx.Graph()
        for node_id, latitude, longitude in [
            ("s", 0, 0), ("t", 0, 0.002), ("a", 0.002, 0.001),
            ("b", 0, 0.0006), ("c", 0, 0.0012),
        ]:
            graph.add_node(node_id, latitude=latitude, longitude=longitude)
        for nodes in [["s", "a", "t"], ["s", "b", "c", "t"]]:
            nx.add_path(graph, nodes, kind="outdoorPath", condition="flat")
        original = graph.copy()

        self.assertEqual(find_route(graph, "s", "t"), ["s", "b", "c", "t"])
        self.assertEqual(find_route(graph, "t", "s"), ["t", "c", "b", "s"])
        self.assertTrue(nx.utils.graphs_equal(graph, original))

    def test_indoor_edges_need_no_coordinates_and_use_comparable_scores(self):
        graph = nx.Graph()
        graph.add_node("s", latitude=0, longitude=0)
        graph.add_node("t", latitude=0, longitude=0.002)
        graph.add_edge("s", "t", kind="outdoorPath", condition="flat")
        add_path(graph, ["s", "hall", "t"], ["flat", "flat"])

        self.assertEqual(find_route(graph, "s", "t"), ["s", "hall", "t"])

    def test_indoor_base_cost_override_can_change_route_choice(self):
        graph = nx.Graph()
        add_path(graph, ["s", "a", "t"], ["flat", "flat"])
        graph.edges["s", "a"]["base_cost"] = 8
        add_path(graph, ["s", "b", "c", "t"], ["flat"] * 3)

        self.assertEqual(find_route(graph, "s", "t"), ["s", "b", "c", "t"])

    def test_missing_or_invalid_outdoor_coordinates_are_not_silently_ignored(self):
        for attributes in [
            {}, {"latitude": None, "longitude": 0},
            {"latitude": "37", "longitude": 0},
            {"latitude": float("nan"), "longitude": 0},
            {"latitude": float("inf"), "longitude": 0},
            {"latitude": 91, "longitude": 0},
            {"latitude": 0, "longitude": 181},
        ]:
            with self.subTest(attributes=attributes):
                graph = nx.Graph()
                graph.add_node("s", **attributes)
                graph.add_node("t", latitude=0, longitude=0)
                graph.add_edge("s", "t", kind="outdoorPath", condition="flat")
                with self.assertRaises(ValueError):
                    find_route(graph, "s", "t")

    def test_indoor_override_must_be_a_positive_finite_number(self):
        for value in [0, -1, float("nan"), float("inf"), "3", True]:
            with self.subTest(base_cost=value):
                graph = nx.Graph()
                add_path(graph, ["s", "t"], ["flat"])
                graph.edges["s", "t"]["base_cost"] = value
                with self.assertRaises(ValueError):
                    find_route(graph, "s", "t")

    def test_one_exception_still_wins_over_two_with_long_outdoor_distances(self):
        graph = nx.Graph()
        for node_id, latitude, longitude in [
            ("s", 0, 0), ("t", 0, 0.002), ("a", 0.01, 0), ("b", 0, 0.001),
        ]:
            graph.add_node(node_id, latitude=latitude, longitude=longitude)
        graph.add_edge("s", "a", kind="outdoorPath", condition="slope")
        graph.add_edge("a", "t", kind="outdoorPath", condition="flat")
        graph.add_edge("s", "b", kind="outdoorPath", condition="slope")
        graph.add_edge("b", "t", kind="outdoorPath", condition="slope")
        original = graph.copy()

        self.assertEqual(find_route_with_minimal_exceptions(
            graph, "s", "t", excluded_conditions=["slope"]
        ), ["s", "a", "t"])
        self.assertTrue(nx.utils.graphs_equal(graph, original))

    def test_equal_exception_counts_use_distance_to_break_ties(self):
        graph = nx.Graph()
        for node_id, latitude, longitude in [
            ("s", 0, -0.001), ("p", 0, 0), ("t", 0, 0.002),
            ("a", 0.002, 0.001), ("b", 0, 0.0006), ("c", 0, 0.0012),
        ]:
            graph.add_node(node_id, latitude=latitude, longitude=longitude)
        graph.add_edge("s", "p", kind="outdoorPath", condition="slope")
        for nodes in [["p", "a", "t"], ["p", "b", "c", "t"]]:
            nx.add_path(graph, nodes, kind="outdoorPath", condition="flat")

        self.assertEqual(find_route_with_minimal_exceptions(
            graph, "s", "t", excluded_conditions=["slope"]
        ), ["s", "p", "b", "c", "t"])


if __name__ == "__main__":
    unittest.main()
