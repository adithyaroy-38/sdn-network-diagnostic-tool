"""
Dijkstra-based path forwarding utilities.
"""

from config import HOST_SWITCH


# Port numbers from the current diamond topology.
HOST_PORTS = {
    "s1": 1,
    "s2": 1,
    "s3": 1,
    "s4": 1,
}

# Actual OpenFlow port numbers obtained from OVS.
LINK_PORTS = {
    ("s1", "s2"): 2,
    ("s2", "s1"): 2,

    ("s1", "s3"): 3,
    ("s3", "s1"): 2,

    ("s2", "s4"): 3,
    ("s4", "s2"): 2,

    ("s3", "s4"): 3,
    ("s4", "s3"): 3,
}


def get_output_port(current_switch, next_switch):
    """Return the port connecting two neighbouring switches."""
    return LINK_PORTS.get((current_switch, next_switch))


def get_host_switch(host):
    """Return the switch connected to a destination host."""
    return HOST_SWITCH.get(host)


def get_host_output_port(switch):
    """Return the port connected to a host."""
    return HOST_PORTS.get(switch)


def build_forwarding_route(path, destination_host):
    """
    Convert a switch path into output ports for packet forwarding.
    """
    if not path:
        return {}

    route = {}

    for index in range(len(path) - 1):
        current = path[index]
        next_switch = path[index + 1]

        port = get_output_port(current, next_switch)

        if port is None:
            raise ValueError(
                f"No link found between {current} and {next_switch}"
            )

        route[current] = port

    destination_switch = get_host_switch(destination_host)

    if destination_switch != path[-1]:
        raise ValueError("Destination host does not match the path")

    route[path[-1]] = get_host_output_port(path[-1])

    return route
