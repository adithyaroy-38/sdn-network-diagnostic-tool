"""
SDN Project - Dynamic Shortest Path Calculation

Reads automatically discovered network links from topology.json
and calculates primary and alternative paths using Dijkstra.
"""

import heapq
import json
import os


PROJECT_DIR = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

TOPOLOGY_FILE = os.path.join(
    PROJECT_DIR,
    "data",
    "topology.json"
)


def build_graph(links=None, topology_file=None):
    """Build a weighted graph from discovered topology."""

    graph = {}

    if links is None:

        file_path = topology_file or TOPOLOGY_FILE

        with open(file_path, "r") as file:
            topology = json.load(file)

        # Add discovered switches
        for switch in topology.get("switches", []):
            graph.setdefault(switch["name"], [])

        # Read discovered inter-switch links
        links = []

        for link in topology.get("links", []):

            delay = link.get("delay_ms")

            if delay is None:
                continue

            links.append((
                link["source"],
                link["destination"],
                float(delay)
            ))

    # Build undirected graph
    for source, destination, delay in links:

        graph.setdefault(source, [])
        graph.setdefault(destination, [])

        graph[source].append((destination, float(delay)))
        graph[destination].append((source, float(delay)))

    return graph


def shortest_path(graph, source, destination, excluded_edges=None):
    """Find minimum-delay path using Dijkstra's algorithm."""

    if excluded_edges is None:
        excluded_edges = set()

    if source not in graph or destination not in graph:
        return None

    distances = {
        node: float("inf")
        for node in graph
    }

    previous = {}

    distances[source] = 0

    queue = [(0, source)]

    while queue:

        current_distance, current_node = heapq.heappop(queue)

        if current_distance > distances[current_node]:
            continue

        if current_node == destination:
            break

        for neighbour, delay in graph[current_node]:

            edge = frozenset((current_node, neighbour))

            if edge in excluded_edges:
                continue

            new_distance = current_distance + delay

            if new_distance < distances[neighbour]:

                distances[neighbour] = new_distance
                previous[neighbour] = current_node

                heapq.heappush(
                    queue,
                    (new_distance, neighbour)
                )

    if distances[destination] == float("inf"):
        return None

    # Reconstruct path
    path = []
    current = destination

    while current != source:
        path.append(current)
        current = previous[current]

    path.append(source)
    path.reverse()

    return {
        "path": path,
        "total_delay_ms": distances[destination]
    }


def get_primary_and_alternative_paths(
    source,
    destination,
    topology_file=None
):
    """Calculate primary and alternative routes."""

    graph = build_graph(topology_file=topology_file)

    primary = shortest_path(
        graph,
        source,
        destination
    )

    if primary is None:
        return {
            "primary": None,
            "alternative": None
        }

    candidates = []

    # Exclude each primary-path link individually
    # to find alternative routes.
    for u, v in zip(
        primary["path"],
        primary["path"][1:]
    ):

        excluded = {
            frozenset((u, v))
        }

        alternative = shortest_path(
            graph,
            source,
            destination,
            excluded
        )

        if alternative is not None:
            candidates.append(alternative)

    # Select the lowest-delay alternative
    alternative = min(
        candidates,
        key=lambda item: item["total_delay_ms"],
        default=None
    )

    return {
        "primary": primary,
        "alternative": alternative
    }


if __name__ == "__main__":

    result = get_primary_and_alternative_paths(
        "s1",
        "s4"
    )

    print(json.dumps(result, indent=4))
