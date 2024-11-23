from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER, set_ev_cls
from ryu.ofproto import ofproto_v1_0

# These libraries now are for parsing the data packet to extract useful information
from ryu.lib.packet import packet, ipv4, icmp

# ryu-manager p1_hub.py

class HubController(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_0.OFP_VERSION]

    # Initializing the ryu controller for hub topology
    def __init__(self, *args, **kwargs):
        # Initialising the controller
        super(HubController, self).__init__(*args, **kwargs)

    # set_ev_cls ensures that the method is called whenever this event is triggered
    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        # Packet came to a switch, now controller need to handle this packet

        # Parsing the packet and extracting useful details
        msg = ev.msg
        dp = msg.datapath
        ofp = dp.ofproto
        ofp_parser = dp.ofproto_parser
        in_port = msg.in_port  # Input port where the packet if received
        dpid = dp.id  # Switch name where the packet is recived

        # Defining the actions to flood the packet to all ports except the input port
        actions = []
        switch_ports = dp.ports.keys()  # Get all ports of the switch

        for port in switch_ports:
            if port != in_port:
                actions.append(ofp_parser.OFPActionOutput(port))

        # Parse the incoming packet and extract protocols
        pkt = packet.Packet(msg.data)

        # Extracting which protocols exist in the packet
        ipv4_pkt = pkt.get_protocol(ipv4.ipv4)
        icmp_pkt = pkt.get_protocol(icmp.icmp)

        # Extracting source and destination IP
        if ipv4_pkt:
            src_ip = ipv4_pkt.src
            dst_ip = ipv4_pkt.dst

        # Printing the details for ping packets
        if ipv4_pkt and icmp_pkt:
            print(f"\nPing packet received at switch: {dpid}, input port: {in_port}")
            print(f"Source IP (ICMP): {src_ip}, Destination IP (ICMP): {dst_ip}")
            print(
                f"Flooding packet from switch {dpid} to all ports except port {in_port}\n"
            )

        # Sending the datapacket and data back to the switch with required packet out action information:- flooding in this case
        data = None
        if msg.buffer_id == ofp.OFP_NO_BUFFER:
            data = msg.data

        out = ofp_parser.OFPPacketOut(
            datapath=dp,
            buffer_id=msg.buffer_id,
            in_port=in_port,
            actions=actions,
            data=data,
        )
        dp.send_msg(out)
