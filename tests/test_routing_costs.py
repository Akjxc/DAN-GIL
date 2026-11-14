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


if __name__ == "__main__":
    unittest.main()
