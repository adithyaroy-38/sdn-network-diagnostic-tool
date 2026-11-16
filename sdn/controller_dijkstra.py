"""
STP-aware Dijkstra SDN Controller
Network Diagnostic and Path Analysis Tool
"""

import os
import json

from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import (
    MAIN_DISPATCHER,
    DEAD_DISPATCHER,
    CONFIG_DISPATCHER,
    set_ev_cls
)
from ryu.ofproto import ofproto_v1_3
from ryu.lib import stplib
from ryu.lib import dpid as dpid_lib
from ryu.lib.packet import packet, ethernet, ether_types
from ryu.topology import event as topology_event

from config import SWITCHES

from sdn.paths import build_graph, shortest_path

from sdn.forwarding import (
    get_output_port,
    get_host_output_port,
    HOST_PORTS,
    LINK_PORTS
)


# ==========================================
# Configuration
# ==========================================

TOPOLOGY_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "topology.json"
)

DIJKSTRA_COOKIE = 0xD1A60000


# ==========================================
# Controller
# ==========================================

class SDNController(app_manager.RyuApp):

    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    _CONTEXTS = {
        "stplib": stplib.Stp
    }

    def __init__(self, *args, **kwargs):

        super(SDNController, self).__init__(*args, **kwargs)

        self.stp = kwargs["stplib"]

        self.datapaths = {}
        self.mac_locations = {}
        self.port_states = {}
        self.physical_port_states = {}
        self.failed_links = set()

        # Stable physical port-to-link mapping.
        self.port_to_link = {}
        self.link_to_ports = {}

        for (src, dst), src_port in LINK_PORTS.items():
            dst_port = LINK_PORTS.get((dst, src))
            if dst_port is None:
                continue

            edge = frozenset((src, dst))

            self.port_to_link[(int(src[1:]), src_port)] = edge
            self.link_to_ports[edge] = (
                int(src[1:]), src_port,
                int(dst[1:]), dst_port
            )

        self.dpid_to_switch = {
            int(switch[1:]): switch
            for switch in SWITCHES
        }

        # Configure STP priorities.
        stp_config = {}

        for index, switch in enumerate(SWITCHES):

            dpid = dpid_lib.str_to_dpid(
                "%016x" % int(switch[1:])
            )

            stp_config[dpid] = {
                "bridge": {
                    "priority": 0x8000 + index * 0x1000
                }
            }

        self.stp.set_config(stp_config)

        self.logger.info(
            "Dijkstra SDN controller initialized"
        )

    # ======================================
    # Physical port status tracking
    # ======================================

    @set_ev_cls(ofp_event.EventOFPPortStatus, MAIN_DISPATCHER)
    def physical_port_status_handler(self, ev):

        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        port = msg.desc

        key = (datapath.id, port.port_no)

        if msg.reason == ofproto.OFPPR_DELETE:
            is_up = False
        else:
            is_up = not (
                port.config & ofproto.OFPPC_PORT_DOWN
                or port.state & ofproto.OFPPS_LINK_DOWN
            )

        previous = self.physical_port_states.get(key)
        self.physical_port_states[key] = is_up

        self.update_failed_links_for_port(
            datapath.id, port.port_no, is_up
        )

        if previous != is_up:
            self.logger.warning(
                "PHYSICAL PORT STATUS: switch=%s port=%s up=%s",
                self.dpid_to_switch.get(datapath.id, datapath.id),
                port.port_no,
                is_up
            )
            self.clear_dijkstra_flows()

        self.try_recover_links()

    # ======================================
    # Initial physical port information
    # ======================================

    @set_ev_cls(
        ofp_event.EventOFPPortDescStatsReply,
        MAIN_DISPATCHER
    )
    def port_description_reply_handler(self, ev):

        datapath = ev.msg.datapath
        ofproto = datapath.ofproto

        for port in ev.msg.body:

            key = (datapath.id, port.port_no)

            is_up = not (
                port.config & ofproto.OFPPC_PORT_DOWN
                or port.state & ofproto.OFPPS_LINK_DOWN
            )

            self.physical_port_states[key] = is_up

            self.update_failed_links_for_port(
                datapath.id, port.port_no, is_up
            )

            self.logger.info(
                "INITIAL PORT STATUS: switch=%s port=%s up=%s",
                self.dpid_to_switch.get(datapath.id, datapath.id),
                port.port_no,
                is_up
            )

        self.try_recover_links()

    def update_failed_links_for_port(self, dpid, port_no, is_up):
        """Map a physical port to its inter-switch link without topology.json."""

        edge = self.port_to_link.get((dpid, port_no))

        if edge is None:
            return

        if not is_up and edge not in self.failed_links:
            self.failed_links.add(edge)
            src, dst = sorted(edge)
            self.logger.error(
                "PHYSICAL LINK FAILURE: %s <-> %s",
                src, dst
            )

    @set_ev_cls(
        ofp_event.EventOFPStateChange,
        [MAIN_DISPATCHER, DEAD_DISPATCHER]
    )
    def switch_state_handler(self, ev):

        datapath = ev.datapath

        if ev.state == MAIN_DISPATCHER:

            self.datapaths[datapath.id] = datapath

            # Request the switch's current physical port states.
            parser = datapath.ofproto_parser
            request = parser.OFPPortDescStatsRequest(
                datapath,
                0
            )
            datapath.send_msg(request)

            self.logger.info(
                "Requested initial port descriptions: switch=%s",
                self.dpid_to_switch.get(datapath.id, datapath.id)
            )

            self.logger.info(
                "Switch connected: %s",
                self.dpid_to_switch.get(
                    datapath.id,
                    datapath.id
                )
            )

        elif ev.state == DEAD_DISPATCHER:

            self.datapaths.pop(datapath.id, None)

            self.logger.warning(
                "Switch disconnected: %s",
                self.dpid_to_switch.get(
                    datapath.id,
                    datapath.id
                )
            )

    # ======================================
    # Dijkstra flow cleanup
    # ======================================

    def clear_dijkstra_flows(self):
        """
        Remove only flows installed by this Dijkstra controller.

        Table-miss and unrelated flows are preserved.
        """

        for datapath in list(self.datapaths.values()):

            parser = datapath.ofproto_parser
            ofproto = datapath.ofproto

            flow_mod = parser.OFPFlowMod(
                datapath=datapath,
                cookie=DIJKSTRA_COOKIE,
                cookie_mask=0xFFFFFFFFFFFFFFFF,
                table_id=ofproto.OFPTT_ALL,
                command=ofproto.OFPFC_DELETE,
                out_port=ofproto.OFPP_ANY,
                out_group=ofproto.OFPG_ANY,
                match=parser.OFPMatch()
            )

            datapath.send_msg(flow_mod)

            self.logger.info(
                "Cleared Dijkstra flows on switch %s",
                self.dpid_to_switch.get(
                    datapath.id,
                    datapath.id
                )
            )

    # ======================================
    # STP port-state management
    # ======================================

    @set_ev_cls(
        stplib.EventPortStateChange,
        MAIN_DISPATCHER
    )
    def port_state_change_handler(self, ev):

        key = (
            ev.dp.id,
            ev.port_no
        )

        previous_state = self.port_states.get(key)

        self.port_states[key] = ev.port_state

        self.logger.info(
            "STP port state: switch=%s port=%s state=%s",
            ev.dp.id,
            ev.port_no,
            ev.port_state
        )

        # Clear old routes whenever an STP state changes.
        if previous_state != ev.port_state:

            self.logger.warning(
                "STP topology changed. Clearing Dijkstra routes."
            )

            self.clear_dijkstra_flows()

        self.try_recover_links()

    # ======================================
    # Physical link failure and recovery
    # ======================================

    @set_ev_cls(topology_event.EventLinkDelete)
    def link_delete_handler(self, ev):

        link = ev.link

        src = self.dpid_to_switch.get(link.src.dpid)
        dst = self.dpid_to_switch.get(link.dst.dpid)

        if src is None or dst is None:
            self.logger.warning(
                "Topology link deleted, but switch mapping is unavailable"
            )
            return

        self.logger.warning(
            "LLDP TOPOLOGY LINK DELETED: %s <-> %s. "
            "Checking physical port status separately.",
            src,
            dst
        )

        # LLDP deletion alone does not establish physical failure.
        # Physical failures are tracked by OpenFlow port status.
        self.clear_dijkstra_flows()

    @set_ev_cls(topology_event.EventLinkAdd)
    def link_add_handler(self, ev):

        link = ev.link

        src = self.dpid_to_switch.get(link.src.dpid)
        dst = self.dpid_to_switch.get(link.dst.dpid)

        if src is None or dst is None:
            return

        edge = frozenset((src, dst))

        if edge in self.failed_links:
            self.logger.warning(
                "LINK REDISCOVERED BUT STILL MARKED FAILED: %s <-> %s",
                src,
                dst
            )

            # LLDP rediscovery alone does not prove link recovery.
            # Keep the edge blocked until recovery is verified.

    # ======================================
    # Verify physical link recovery
    # ======================================

    def try_recover_links(self):
        """Recover links using stable port mappings and physical port status."""

        if not self.failed_links:
            return

        for edge in list(self.failed_links):
            ports = self.link_to_ports.get(edge)

            if ports is None:
                continue

            src_dpid, src_port, dst_dpid, dst_port = ports

            src_physical = self.physical_port_states.get(
                (src_dpid, src_port)
            )
            dst_physical = self.physical_port_states.get(
                (dst_dpid, dst_port)
            )

            src_stp = self.port_states.get((src_dpid, src_port))
            dst_stp = self.port_states.get((dst_dpid, dst_port))

            # BLOCK is a valid STP state for a healthy redundant link.
            if (
                src_physical is True
                and dst_physical is True
                and src_stp is not None
                and dst_stp is not None
                and src_stp != stplib.PORT_STATE_DISABLE
                and dst_stp != stplib.PORT_STATE_DISABLE
            ):
                self.failed_links.discard(edge)

                src, dst = sorted(edge)
                self.logger.warning(
                    "VERIFIED PHYSICAL LINK RECOVERY: %s <-> %s",
                    src, dst
                )
                self.clear_dijkstra_flows()

    def get_blocked_edges(self):
        """
        Exclude inter-switch links if either endpoint
        is not currently in the STP forwarding state.
        """

        blocked = []

        # Exclude links reported as physically deleted,
        # even if topology.json has not refreshed yet.
        for edge in self.failed_links:
            switches = list(edge)
            blocked.append((switches[0], switches[1]))
            blocked.append((switches[1], switches[0]))

        if not os.path.exists(TOPOLOGY_FILE):
            return blocked

        try:

            with open(TOPOLOGY_FILE, "r") as file:
                topology = json.load(file)

        except (OSError, json.JSONDecodeError) as error:

            self.logger.error(
                "Cannot read topology: %s",
                error
            )

            return blocked

        for link in topology.get("links", []):

            src = link["source"]
            dst = link["destination"]

            src_dpid = int(src[1:])
            dst_dpid = int(dst[1:])

            src_port = link["source_port"]
            dst_port = link["destination_port"]

            state1 = self.port_states.get(
                (src_dpid, src_port)
            )

            state2 = self.port_states.get(
                (dst_dpid, dst_port)
            )

            physical1 = self.physical_port_states.get(
                (src_dpid, src_port)
            )

            physical2 = self.physical_port_states.get(
                (dst_dpid, dst_port)
            )

            # Exclude an edge if either endpoint is physically
            # down or is not in the STP forwarding state.
            # Unknown physical/STP states are not treated as down.
            if (
                physical1 is False
                or physical2 is False
                or state1 != stplib.PORT_STATE_FORWARD
                or state2 != stplib.PORT_STATE_FORWARD
            ):

                blocked.append((src, dst))
                blocked.append((dst, src))

        return blocked

    # ======================================
    # Install OpenFlow route
    # ======================================

    def install_route(
        self,
        datapath,
        in_port,
        src_mac,
        dst_mac,
        out_port
    ):

        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto

        match = parser.OFPMatch(
            in_port=in_port,
            eth_src=src_mac,
            eth_dst=dst_mac
        )

        actions = [
            parser.OFPActionOutput(out_port)
        ]

        instructions = [
            parser.OFPInstructionActions(
                ofproto.OFPIT_APPLY_ACTIONS,
                actions
            )
        ]

        flow = parser.OFPFlowMod(
            datapath=datapath,
            cookie=DIJKSTRA_COOKIE,
            priority=20,
            match=match,
            instructions=instructions,
            idle_timeout=120
        )

        datapath.send_msg(flow)

        self.logger.info(
            "DIJKSTRA FLOW INSTALLED: switch=%s in=%s out=%s",
            self.dpid_to_switch.get(
                datapath.id,
                datapath.id
            ),
            in_port,
            out_port
        )

    # ======================================
    # Dijkstra forwarding
    # ======================================

    def forward_using_dijkstra(
        self,
        msg,
        current_switch,
        src_mac,
        dst_mac,
        destination_switch
    ):

        try:

            graph = build_graph(
                topology_file=TOPOLOGY_FILE
            )

        except (
            OSError,
            json.JSONDecodeError,
            KeyError
        ) as error:

            self.logger.error(
                "Graph construction failed: %s",
                error
            )

            self.flood_packet(msg)
            return False

        blocked_edges = self.get_blocked_edges()

        result = shortest_path(
            graph,
            current_switch,
            destination_switch,
            excluded_edges={
                frozenset(edge)
                for edge in blocked_edges
            }
        )

        if result is None:

            self.logger.warning(
                "No Dijkstra path from %s to %s",
                current_switch,
                destination_switch
            )

            self.flood_packet(msg)
            return False

        path = result["path"]

        self.logger.info(
            "DIJKSTRA ROUTE SELECTED: %s | Delay: %s ms",
            " -> ".join(path),
            result["total_delay_ms"]
        )

        route_entries = []

        # Validate the complete route before installing flows.
        for index, switch in enumerate(path):

            datapath = self.datapaths.get(
                int(switch[1:])
            )

            if datapath is None:

                self.logger.error(
                    "Datapath unavailable for %s",
                    switch
                )

                return False

            # Determine incoming port.
            if index == 0:

                in_port = msg.match["in_port"]

            else:

                in_port = get_output_port(
                    switch,
                    path[index - 1]
                )

            # Determine outgoing port.
            if index == len(path) - 1:

                out_port = get_host_output_port(
                    switch
                )

            else:

                out_port = get_output_port(
                    switch,
                    path[index + 1]
                )

            if in_port is None or out_port is None:

                self.logger.error(
                    "Invalid port mapping at %s: in=%s out=%s",
                    switch,
                    in_port,
                    out_port
                )

                return False

            route_entries.append(
                (datapath, in_port, out_port)
            )

        # Install flows on every switch.
        for datapath, in_port, out_port in route_entries:

            self.install_route(
                datapath,
                in_port,
                src_mac,
                dst_mac,
                out_port
            )

        # Forward the packet that triggered route calculation.
        datapath = msg.datapath

        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        first_out_port = route_entries[0][2]

        data = (
            msg.data
            if msg.buffer_id == ofproto.OFP_NO_BUFFER
            else None
        )

        packet_out = parser.OFPPacketOut(
            datapath=datapath,
            buffer_id=msg.buffer_id,
            in_port=msg.match["in_port"],
            actions=[
                parser.OFPActionOutput(first_out_port)
            ],
            data=data
        )

        datapath.send_msg(packet_out)

        return True

    # ======================================
    # Flood packets
    # ======================================

    def flood_packet(self, msg):

        datapath = msg.datapath

        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        data = (
            msg.data
            if msg.buffer_id == ofproto.OFP_NO_BUFFER
            else None
        )

        packet_out = parser.OFPPacketOut(
            datapath=datapath,
            buffer_id=msg.buffer_id,
            in_port=msg.match["in_port"],
            actions=[
                parser.OFPActionOutput(
                    ofproto.OFPP_FLOOD
                )
            ],
            data=data
        )

        datapath.send_msg(packet_out)

    # ======================================
    # OpenFlow table-miss rule
    # ======================================

    @set_ev_cls(
        ofp_event.EventOFPSwitchFeatures,
        CONFIG_DISPATCHER
    )
    def switch_features_handler(self, ev):

        datapath = ev.msg.datapath

        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto

        match = parser.OFPMatch()

        actions = [
            parser.OFPActionOutput(
                ofproto.OFPP_CONTROLLER,
                ofproto.OFPCML_NO_BUFFER
            )
        ]

        instructions = [
            parser.OFPInstructionActions(
                ofproto.OFPIT_APPLY_ACTIONS,
                actions
            )
        ]

        flow = parser.OFPFlowMod(
            datapath=datapath,
            priority=0,
            match=match,
            instructions=instructions
        )

        datapath.send_msg(flow)

        self.logger.info(
            "TABLE-MISS FLOW INSTALLED on switch %s",
            self.dpid_to_switch.get(
                datapath.id,
                datapath.id
            )
        )

    # ======================================
    # Packet-in handler
    # ======================================

    @set_ev_cls(
        ofp_event.EventOFPPacketIn,
        MAIN_DISPATCHER
    )
    def packet_in_handler(self, ev):

        msg = ev.msg
        datapath = msg.datapath

        self.datapaths[datapath.id] = datapath

        in_port = msg.match["in_port"]

        pkt = packet.Packet(msg.data)

        eth = pkt.get_protocol(
            ethernet.ethernet
        )

        if eth is None:
            return

        # Ignore LLDP packets.
        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            return

        # Ignore STP bridge-control packets.
        if eth.dst.lower() == "01:80:c2:00:00:00":
            return

        switch = self.dpid_to_switch.get(
            datapath.id
        )

        if switch is None:
            return

        src = eth.src
        dst = eth.dst

        # Learn source MAC addresses only from host ports.
        if in_port == HOST_PORTS.get(switch):

            self.mac_locations[src] = switch

        # Flood broadcast packets.
        if dst.lower() == "ff:ff:ff:ff:ff:ff":

            self.flood_packet(msg)
            return

        # Flood multicast packets.
        first_octet = int(
            dst.split(":")[0],
            16
        )

        if first_octet & 1:

            self.flood_packet(msg)
            return

        self.logger.info(
            "UNICAST PACKET: switch=%s in=%s src=%s dst=%s",
            switch,
            in_port,
            src,
            dst
        )

        destination_switch = self.mac_locations.get(dst)

        if destination_switch is None:

            self.logger.info(
                "Destination MAC %s not learned; flooding",
                dst
            )

            self.flood_packet(msg)
            return

        self.logger.info(
            "Destination MAC %s learned at %s",
            dst,
            destination_switch
        )

        self.forward_using_dijkstra(
            msg,
            switch,
            src,
            dst,
            destination_switch
        )
