from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER, set_ev_cls
from ryu.ofproto import ofproto_v1_0

# These libraries now are for parsing the data packet to extract useful information
from ryu.lib.packet import packet, ethernet, ether_types, ipv4, icmp

# ryu-manager p1_learning.py

class learning_controller(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_0.OFP_VERSION]

    # Initializing the ryu controller for hub topology
    def __init__(self, *args, **kwargs):
        # Initialising the controller
        super(learning_controller, self).__init__(*args, **kwargs)

        # A dictionary of dictionary which for a given switch, for each mac address learned, stored the port for that mac address
        self.mac_to_port = {}

    def add_flow(self, datapath, dst, actions):
        # Function to add the flow method for the given switch(datapath)
        ofproto = datapath.ofproto

        # Match the packet with input port, source and destination
        # haddr_to_bin converts the mac address to required binary form expected by the internal function
        match = datapath.ofproto_parser.OFPMatch(dl_dst=dst)

        # Do the required action if the packet matches the match specifications
        mod = datapath.ofproto_parser.OFPFlowMod(
            datapath=datapath,
            match=match,
            cookie=0,
            command=ofproto.OFPFC_ADD,  # Add the flow entry
            idle_timeout=0,  # 0 means entry never expires
            hard_timeout=0,
            priority=ofproto.OFP_DEFAULT_PRIORITY,
            flags=ofproto.OFPFF_SEND_FLOW_REM,
            actions=actions,
        )

        # Send the information to the switch to update its flow table accordingly
        print(f"Flow table updated for switch {datapath.id}\n")
        datapath.send_msg(mod)

    # set_ev_cls ensures that the method is called whenever this event is triggered
    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        # Packet came to a switch, now controller need to handle this packet

        # Parsing the packet and extracting useful details
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        in_port = msg.in_port  # Input port where the packet if received
        dpid = datapath.id  # Switch name where the packet is recived

        # Parse the incoming packet
        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)

        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            # ignore lldp packet
            return

        # Extracting source and destination MAC address from the ethernet packet
        dst = eth.dst
        src = eth.src

        # Add the switch id to the mac_to_port dictionary with empty mac table if not already exists
        if not (dpid in self.mac_to_port):
            print(f"Adding switch {dpid} to the mac_to_port table\n")
        self.mac_to_port.setdefault(dpid, {})

        # learn a mac address from the incoming packet and add its source ip address to the mac table of the switch
        self.mac_to_port[dpid][src] = in_port

        # If port for the destination already learned, then send the packet to that port, else flood the packet
        if dst in self.mac_to_port[dpid]:
            out_port = self.mac_to_port[dpid][dst]
            actions = [datapath.ofproto_parser.OFPActionOutput(out_port)]
            self.add_flow(datapath, dst, actions)

        else:
            actions = []
            switch_ports = datapath.ports.keys()  # Get all ports of the switch

            for port in switch_ports:
                if port != in_port:
                    actions.append(datapath.ofproto_parser.OFPActionOutput(port))

        # Extracting which protocols exist in the packet
        ipv4_pkt = pkt.get_protocol(ipv4.ipv4)
        icmp_pkt = pkt.get_protocol(icmp.icmp)

        # Only prints when the ping protocol packet goes through the condition when the flow table of the switch does not contain that entry
        # Otherwise, the packet never reach the controller and passes straight through the switch through installed flow table
        if ipv4_pkt and icmp_pkt:
            src_ip = ipv4_pkt.src
            dst_ip = ipv4_pkt.dst
            print("MAC to PORT dictionary: ", self.mac_to_port)
            print(f"\nPing packet received at switch: {dpid}, input port: {in_port}")
            print(f"Source IP (ICMP): {src_ip}, Destination IP (ICMP): {dst_ip}")
            print(
                f"Flooding packet from switch {dpid} to all ports except port {in_port}\n"
            )

        # Sending the datapacket and data back to the switch with required packet out action information:- flooding or sending to the necessary port only depending on the condition
        data = None
        if msg.buffer_id == ofproto.OFP_NO_BUFFER:
            data = msg.data

        out = datapath.ofproto_parser.OFPPacketOut(
            datapath=datapath,
            buffer_id=msg.buffer_id,
            in_port=msg.in_port,
            actions=actions,
            data=data,
        )
        datapath.send_msg(out)
