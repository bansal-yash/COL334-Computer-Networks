from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER, set_ev_cls, CONFIG_DISPATCHER
from ryu.ofproto import ofproto_v1_3
from ryu.topology import event
from ryu.topology.api import get_all_switch, get_all_link
import time
import heapq
from collections import defaultdict
from ryu.lib.packet import packet, ethernet, ether_types, ipv4, icmp, lldp
from ryu.lib import hub


class spr__ca_controller(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(spr__ca_controller, self).__init__(*args, **kwargs)

        self.mac_to_port = {}
        self.switch_graph = {}
        self.link_delays_dict = {}
        self.rtt_dict = {}
        self.rtt_send_time = {}
        self.spt_tree = {}
        self.flow_rule_tree = {}

        self.switches_list = []
        self.links_list = []
        self.to_update = False
        self.stable_time = time.time()
        self.connect_start = False
        self.update_called = False
        self.is_spt_calc = False

    def add_flow(self, datapath, priority, match, actions, buffer_id=None):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
        if buffer_id:
            mod = parser.OFPFlowMod(
                datapath=datapath,
                buffer_id=buffer_id,
                priority=priority,
                match=match,
                instructions=inst,
            )
        else:
            mod = parser.OFPFlowMod(
                datapath=datapath, priority=priority, match=match, instructions=inst
            )
        print("Flow table updated for switch: ", datapath.id)
        datapath.send_msg(mod)

    def delete_flows(self, datapath):
        ofproto = datapath.ofproto
        match = datapath.ofproto_parser.OFPMatch()
        mod = datapath.ofproto_parser.OFPFlowMod(
            datapath=datapath,
            command=ofproto.OFPFC_DELETE,
            match=match,
        )
        datapath.send_msg(mod)

    def graph_to_adj_list(self):
        adj_list = {}
        for edge in self.link_delays_dict.keys():
            a, b = edge
            if a not in adj_list:
                adj_list[a] = {}
            if b not in adj_list:
                adj_list[b] = {}
            adj_list[a][b] = self.link_delays_dict[edge]
            if a not in adj_list[b]:
                adj_list[b][a] = self.link_delays_dict[edge]
        return adj_list

    def dijkstra(self, graph, source):
        dist = {vertex: float("inf") for vertex in graph}
        dist[source] = 0
        pq = [(0, source)]
        parent = {source: None}
        while pq:
            current_dist, u = heapq.heappop(pq)
            if current_dist > dist[u]:
                continue
            for v, weight in graph[u].items():
                distance = current_dist + weight
                if distance < dist[v]:
                    dist[v] = distance
                    parent[v] = u
                    heapq.heappush(pq, (distance, v))
        return dist, parent

    def shortest_path_tree(self, graph, source):
        dist, parent = self.dijkstra(graph, source)
        spt_adj_list = defaultdict(dict)
        for node, par in parent.items():
            if par is not None:
                spt_adj_list[par][node] = graph[par][node]
                spt_adj_list[node][par] = graph[node][par]
        return spt_adj_list

    def compute_spt(self, source_node_id):
        graph = self.graph_to_adj_list()
        personal_spt = self.shortest_path_tree(graph, source_node_id)
        self.spt_tree[source_node_id] = personal_spt

        for src_id in personal_spt.keys():
            for dst_id in personal_spt[src_id].keys():
                personal_spt[src_id][dst_id] = self.switch_graph[src_id][dst_id]

        self.flow_rule_tree[source_node_id] = personal_spt

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        current_time = time.time()
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match["in_port"]
        dpid = datapath.id
        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)
        dst = eth.dst
        src = eth.src

        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            if self.is_spt_calc == True:
                return
            lldp_pkt = pkt.get_protocol(lldp.lldp)
            for tlv in lldp_pkt.tlvs:
                if isinstance(tlv, lldp.OrganizationallySpecific):
                    received_timestamp = int(tlv.info.decode("ascii"))
                    current_time = current_time * 1000
                    link_delay = current_time - received_timestamp
                    src_id = dpid
                    dst_id = None
                    for a, b in self.switch_graph[src_id].items():
                        if b == in_port:
                            dst_id = a
                            break

                    if (src_id, dst_id) not in self.link_delays_dict:
                        self.link_delays_dict[(src_id, dst_id)] = (
                            link_delay
                            - (self.rtt_dict.get(src_id, 0) / 2)
                            - (self.rtt_dict.get(dst_id, 0) / 2)
                        )

                    num_links = len(self.links_list)

                    if num_links == len(self.link_delays_dict):
                        self.is_spt_calc = True
                        for switch in self.switches_list:
                            self.compute_spt(switch.dp.id)

                        print(f"\nLink Delays dict: \n {self.link_delays_dict}\n")
                        print("\n\nAll shortest path trees : \n", self.spt_tree, "\n\n")
                        print("\n\nFlow rule tree: \n", self.flow_rule_tree, "\n")

                        for switch in self.switches_list:
                            self.delete_flows(switch.dp)

        if not (dpid in self.mac_to_port):
            print(f"Adding switch {dpid} to the mac_to_port table\n")
        self.mac_to_port.setdefault(dpid, {})

        self.mac_to_port[dpid][src] = in_port

        if dst in self.mac_to_port[dpid]:
            out_port = self.mac_to_port[dpid][dst]
            actions = [datapath.ofproto_parser.OFPActionOutput(out_port)]
            match = parser.OFPMatch(eth_dst=dst)
            # verify if we have a valid buffer_id, if yes avoid to send both
            # flow_mod & packet_out
            if msg.buffer_id != ofproto.OFP_NO_BUFFER:
                self.add_flow(datapath, 1, match, actions, msg.buffer_id)
                return
            else:
                self.add_flow(datapath, 1, match, actions)
        else:
            switch_ports = datapath.ports.keys()
            actions = []

            for port in switch_ports:
                if port != in_port:
                    if port not in list(self.switch_graph[dpid].values()):
                        actions.append(datapath.ofproto_parser.OFPActionOutput(port))
                    else:
                        if dpid in self.spt_tree:
                            if port in list(self.flow_rule_tree[dpid][dpid].values()):
                                actions.append(
                                    datapath.ofproto_parser.OFPActionOutput(port)
                                )
                    # actions.append(datapath.ofproto_parser.OFPActionOutput(port))

        ipv4_pkt = pkt.get_protocol(ipv4.ipv4)
        icmp_pkt = pkt.get_protocol(icmp.icmp)

        if ipv4_pkt and icmp_pkt:
            src_ip = ipv4_pkt.src
            dst_ip = ipv4_pkt.dst
            print(f"\nPing packet received at switch: {dpid}, input port: {in_port}")
            print(f"Source IP (ICMP): {src_ip}, Destination IP (ICMP): {dst_ip}")
            print(
                f"Flooding packet from switch {dpid} to all ports except port {in_port}\n"
            )

        data = None
        if msg.buffer_id == ofproto.OFP_NO_BUFFER:
            data = msg.data

        out = datapath.ofproto_parser.OFPPacketOut(
            datapath=datapath,
            buffer_id=msg.buffer_id,
            in_port=msg.match["in_port"],
            actions=actions,
            data=data,
        )
        datapath.send_msg(out)

    @set_ev_cls(event.EventSwitchEnter)
    def switch_enter_handler(self, ev):
        self.to_update = True
        self.stable_time = time.time()
        self.connect_start = True
        if not self.update_called:
            self.update_called = True
            self.update_topology()

    @set_ev_cls(event.EventSwitchLeave)
    def switch_leave_handler(self, ev):
        self.to_update = True
        self.stable_time = time.time()
        self.connect_start = True
        if not self.update_called:
            self.update_called = True
            self.update_topology()

    @set_ev_cls(event.EventLinkAdd)
    def link_add_handler(self, ev):
        self.to_update = True
        self.stable_time = time.time()
        self.connect_start = True
        if not self.update_called:
            self.update_called = True
            self.update_topology()

    @set_ev_cls(event.EventLinkDelete)
    def link_delete_handler(self, ev):
        self.to_update = True
        self.stable_time = time.time()
        self.connect_start = True
        if not self.update_called:
            self.update_called = True
            self.update_topology()

    def update_topology(self):
        while not (self.connect_start and (time.time() - self.stable_time) > 10):
            x = 1

        print("all networks connected")
        time.sleep(10)

        first = True
        if self.to_update == True:
            self.to_update = False
        else:
            return

        self.switches_list = get_all_switch(self)
        self.links_list = get_all_link(self)
        self.switch_graph = {}

        for switch in self.switches_list:
            dpid = switch.dp.id
            self.switch_graph[dpid] = {}

        for link in self.links_list:
            src_dpid = link.src.dpid
            src_port = link.src.port_no
            dst_dpid = link.dst.dpid
            dst_port = link.dst.port_no
            self.switch_graph[src_dpid][dst_dpid] = src_port
            self.switch_graph[dst_dpid][src_dpid] = dst_port

        print(f"\nCurrent switch graph: \n{self.switch_graph}\n")

        hub.spawn(self.send_periodic)

    def send_periodic(self):
        first = True
        while True:
            if not first:
                hub.sleep(10)
            first = False
            self.link_delays_dict = {}
            self.rtt_dict = {}
            self.rtt_send_time = {}
            self.spt_tree = {}
            self.flow_rule_tree = {}

            self.is_spt_calc = False
            for switch in self.switches_list:
                self.delete_flows(switch.dp)

            self.send_rtt_packets()
            self.send_LLDP_messages()

    
    def send_LLDP_messages(self):
        for switch in self.switches_list:
            dpid = switch.dp.id
            if dpid in self.switch_graph.keys():
                for port in self.switch_graph[dpid].values():
                    self.send_lldp_packet(switch.dp, port)

    def build_lldp_packet(self, datapath, port_no):
        eth = ethernet.ethernet(
            dst=lldp.LLDP_MAC_NEAREST_BRIDGE,
            src=datapath.ports[port_no].hw_addr,
            ethertype=ethernet.ether.ETH_TYPE_LLDP,
        )
        chassis_id = lldp.ChassisID(
            subtype=lldp.ChassisID.SUB_LOCALLY_ASSIGNED,
            chassis_id=datapath.id.to_bytes(8, byteorder="big"),
        )
        port_id = lldp.PortID(
            subtype=lldp.PortID.SUB_PORT_COMPONENT, port_id=str(port_no).encode("ascii")
        )
        ttl = lldp.TTL(ttl=120)

        oui = b"\x00\x01\x02"
        subtype = 0x01
        timestamp = time.time()
        timestamp = timestamp * 1000
        custom_data = str(int(timestamp)).encode("ascii")
        organizational_tlv = lldp.OrganizationallySpecific(
            oui=oui,
            subtype=subtype,
            info=custom_data,
        )

        lldp_pkt = packet.Packet()
        lldp_pkt.add_protocol(eth)
        lldp_pkt.add_protocol(
            lldp.lldp(tlvs=[chassis_id, port_id, ttl, organizational_tlv])
        )
        lldp_pkt.serialize()
        return lldp_pkt

    def send_lldp_packet(self, datapath, port_no):
        lldp_pkt = self.build_lldp_packet(datapath, port_no)
        ofproto = datapath.ofproto
        actions = [datapath.ofproto_parser.OFPActionOutput(port_no)]
        out = datapath.ofproto_parser.OFPPacketOut(
            datapath=datapath,
            buffer_id=ofproto.OFP_NO_BUFFER,
            in_port=ofproto.OFPP_CONTROLLER,
            actions=actions,
            data=lldp_pkt.data,
        )
        datapath.send_msg(out)

    def send_rtt_packets(self):
        for switch in self.switches_list:
            datapath = switch.dp
            dpid = datapath.id
            parser = datapath.ofproto_parser
            echo_req = parser.OFPEchoRequest(datapath)
            self.rtt_send_time[dpid] = time.time()
            datapath.send_msg(echo_req)

    @set_ev_cls(ofp_event.EventOFPEchoReply, MAIN_DISPATCHER)
    def _echo_reply_handler(self, ev):
        recv_time = time.time()
        datapath = ev.msg.datapath
        send_time = self.rtt_send_time.get(datapath.id, float("inf"))
        rtt = max(recv_time - send_time, 0)
        self.rtt_dict[datapath.id] = rtt * 1000

        print("Current RTT dict: \n", self.rtt_dict, "\n")

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        match = parser.OFPMatch()
        actions = [
            parser.OFPActionOutput(ofproto.OFPP_CONTROLLER, ofproto.OFPCML_NO_BUFFER)
        ]
        self.add_flow(datapath, 0, match, actions)
