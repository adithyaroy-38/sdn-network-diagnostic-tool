"""
Automatic SDN Topology Discovery
Discovers switches and links using Ryu topology APIs.
"""

import json
import os
import time

from ryu.base import app_manager
from ryu.controller.handler import set_ev_cls
from ryu.topology import event
from ryu.topology.api import get_switch, get_link
from ryu.lib import hub

from config import SWITCH_LINKS


class TopologyDiscovery(app_manager.RyuApp):

    def __init__(self, *args, **kwargs):
        super(TopologyDiscovery, self).__init__(*args, **kwargs)

        self.project_dir = os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))
        )

        self.output_file = os.path.join(
            self.project_dir,
            "data",
            "topology.json"
        )

        self.logger.info("Topology Discovery initialized")

    def switch_name(self, dpid):
        return "s{}".format(int(dpid))

    def refresh_topology(self):

        try:
            # Discover connected switches
            switches = get_switch(self, None)

            # Discover inter-switch links
            links = get_link(self, None)

            switch_data = []
            link_data = []

            for switch in switches:

                ports = []

                for port in switch.ports:
                    ports.append({
                        "port_no": port.port_no,
                        "name": str(port.name)
                    })

                switch_data.append({
                    "name": self.switch_name(switch.dp.id),
                    "dpid": str(switch.dp.id),
                    "ports": ports
                })

            # Remove duplicate reverse-direction links
            seen_links = set()

            delay_map = {
                frozenset((src, dst)): delay
                for src, dst, delay in SWITCH_LINKS
            }

            for link in links:

                src = self.switch_name(link.src.dpid)
                dst = self.switch_name(link.dst.dpid)

                key = frozenset((src, dst))

                if key in seen_links:
                    continue

                seen_links.add(key)

                link_data.append({
                    "source": src,
                    "destination": dst,
                    "source_port": link.src.port_no,
                    "destination_port": link.dst.port_no,
                    "delay_ms": delay_map.get(key)
                })

            topology = {
                "timestamp": time.strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
                "switches": switch_data,
                "links": link_data
            }

            os.makedirs(
                os.path.dirname(self.output_file),
                exist_ok=True
            )

            with open(
                self.output_file,
                "w"
            ) as file:
                json.dump(
                    topology,
                    file,
                    indent=4
                )

            self.logger.info(
                "Topology updated: %d switches, %d links",
                len(switch_data),
                len(link_data)
            )

        except Exception:
            self.logger.exception(
                "Topology discovery failed"
            )

    # Switch connected
    @set_ev_cls(event.EventSwitchEnter)
    def switch_enter_handler(self, ev):

        self.logger.info("Switch entered topology")

        hub.spawn_after(
            1,
            self.refresh_topology
        )

    # Switch disconnected
    @set_ev_cls(event.EventSwitchLeave)
    def switch_leave_handler(self, ev):

        self.logger.warning("Switch left topology")

        hub.spawn_after(
            1,
            self.refresh_topology
        )

    # Link discovered
    @set_ev_cls(event.EventLinkAdd)
    def link_add_handler(self, ev):

        self.logger.info("New link discovered")

        hub.spawn_after(
            1,
            self.refresh_topology
        )

    # Link removed
    @set_ev_cls(event.EventLinkDelete)
    def link_delete_handler(self, ev):

        self.logger.warning("Link removed")

        hub.spawn_after(
            1,
            self.refresh_topology
        )
