"""
Custom SDN Controller
Project: Network Diagnostic and Path Analysis Tool
"""

from ryu.app import simple_switch_13
from ryu.controller.handler import MAIN_DISPATCHER, set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib import stplib
from ryu.lib import dpid as dpid_lib
from ryu.lib.packet import packet, ethernet, ether_types

from ryu import cfg

from config import SWITCHES


class SDNController(simple_switch_13.SimpleSwitch13):

    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    # Enable Spanning Tree Protocol
    _CONTEXTS = {
        'stplib': stplib.Stp
    }

    def __init__(self, *args, **kwargs):
        super(SDNController, self).__init__(*args, **kwargs)

        self.mac_to_port = {}

        self.stp = kwargs['stplib']

        # Configure STP priorities for all four switches
        stp_config = {}

        for index, switch in enumerate(SWITCHES):
            dpid = dpid_lib.str_to_dpid(
                '%016x' % int(switch[1:])
            )

            stp_config[dpid] = {
                'bridge': {
                    'priority': 0x8000 + (index * 0x1000)
                }
            }

        self.stp.set_config(stp_config)

        self.logger.info("Custom SDN Controller initialized")
        self.logger.info("OpenFlow 1.3 enabled")
        self.logger.info("STP configured for four switches")

    # Handle incoming Ethernet packets
    @set_ev_cls(stplib.EventPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):

        msg = ev.msg
        datapath = msg.datapath

        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        in_port = msg.match['in_port']

        pkt = packet.Packet(msg.data)

        eth = pkt.get_protocol(ethernet.ethernet)

        if eth is None:
            return

        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            return

        dst = eth.dst
        src = eth.src

        dpid = datapath.id

        self.mac_to_port.setdefault(dpid, {})

        # Learn source MAC address
        self.mac_to_port[dpid][src] = in_port

        # Find destination MAC address
        if dst in self.mac_to_port[dpid]:
            out_port = self.mac_to_port[dpid][dst]
        else:
            out_port = ofproto.OFPP_FLOOD

        actions = [
            parser.OFPActionOutput(out_port)
        ]

        # Install forwarding flow
        if out_port != ofproto.OFPP_FLOOD:

            match = parser.OFPMatch(
                in_port=in_port,
                eth_dst=dst
            )

            self.add_flow(
                datapath,
                1,
                match,
                actions
            )

        data = None

        if msg.buffer_id == ofproto.OFP_NO_BUFFER:
            data = msg.data

        out = parser.OFPPacketOut(
            datapath=datapath,
            buffer_id=msg.buffer_id,
            in_port=in_port,
            actions=actions,
            data=data
        )

        datapath.send_msg(out)

    # Handle topology changes
    @set_ev_cls(stplib.EventTopologyChange, MAIN_DISPATCHER)
    def topology_change_handler(self, ev):

        datapath = ev.dp
        dpid = datapath.id

        self.logger.warning(
            "Topology changed on switch %s",
            dpid
        )

        if dpid not in self.mac_to_port:
            return

        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # Remove previously installed forwarding flows
        for dst in list(self.mac_to_port[dpid].keys()):

            match = parser.OFPMatch(
                eth_dst=dst
            )

            mod = parser.OFPFlowMod(
                datapath,
                command=ofproto.OFPFC_DELETE,
                out_port=ofproto.OFPP_ANY,
                out_group=ofproto.OFPG_ANY,
                priority=1,
                match=match
            )

            datapath.send_msg(mod)

        self.mac_to_port[dpid].clear()

    # Monitor STP port states
    @set_ev_cls(stplib.EventPortStateChange, MAIN_DISPATCHER)
    def port_state_change_handler(self, ev):

        states = {
            stplib.PORT_STATE_DISABLE: "DISABLE",
            stplib.PORT_STATE_BLOCK: "BLOCK",
            stplib.PORT_STATE_LISTEN: "LISTEN",
            stplib.PORT_STATE_LEARN: "LEARN",
            stplib.PORT_STATE_FORWARD: "FORWARD"
        }

        state = states.get(
            ev.port_state,
            "UNKNOWN"
        )

        self.logger.info(
            "Switch %s Port %s State: %s",
            ev.dp.id,
            ev.port_no,
            state
        )
