import socket
import time
import argparse
import logging

# python3 p1_server.py 10.17.50.142 8080 0

MSS = 1400
WINDOW_SIZE = 5
DUP_ACK_THRESHOLD = 3 
FILE_PATH = "file.txt"
TIMEOUT = 0.5

log_file = "server_log_file.txt"
logging.basicConfig(filename=log_file, filemode='w', level=logging.INFO, format='%(asctime)s - %(message)s')

def send_file(server_ip, server_port, enable_fast_recovery):

    global TIMEOUT

    rtt_alpha = 0.125
    rtt_beta = 0.25
    estimated_rtt = 0.5
    dev = 0.0

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_socket.bind((server_ip, server_port))
    
    logging.info(f"Server listening on {server_ip}:{server_port}")

    client_address = None
    file_path = FILE_PATH 
    connected=False

    while not connected:
        try:
            server_socket.settimeout(TIMEOUT)
            logging.info("Waiting for client connection...")
            data, client_address = server_socket.recvfrom(1024)

            if data == b"START":
                logging.info("received start from client")

                server_socket.sendto(b"CONNECT",client_address)
                connected=True

        except socket.timeout:
            logging.info("Socket timeout")


    seq_num = 0
    window_base = 0
    unacked_packets = {}
    duplicate_ack_count = 0
    last_ack_received = -1
    complete=False

    with open(file_path, 'rb') as file:
        while not complete:
            chunk = None
            while seq_num < window_base + WINDOW_SIZE: 

                chunk = file.read(MSS)
                logging.info(chunk)
                if not chunk:
                    # send_end_signal(server_socket, client_address)
                    # complete=True
                    break

                packet = create_packet(seq_num, chunk)
                unacked_packets[seq_num] = (packet, time.time(),0) 
                server_socket.sendto(packet, client_address)
                logging.info(f"Sent packet {seq_num}")
                seq_num += 1


            # Wait for ACKs and retransmit if needed
            try:
            	## Handle ACKs, Timeout, Fast retransmit
                server_socket.settimeout(TIMEOUT)
                ack_packet, _ = server_socket.recvfrom(1024)
                rec_time = time.time()

                if ack_packet == b"START":
                    logging.info("received start again from client:- resetting all variables")
                    server_socket.sendto(b"CONNECT",client_address)
                    connected=True
                    continue

                if "ACK" in ack_packet.decode():
                    ack_seq_num = get_seq_no_from_ack_pkt(ack_packet)

                    if ack_seq_num > last_ack_received:
                        logging.info(f"Received cumulative ACK for packet {ack_seq_num}")
                        last_ack_received = ack_seq_num
                        duplicate_ack_count = 0
                        
                        if ack_seq_num in unacked_packets:
                            if unacked_packets[ack_seq_num][2] == 0:
                                rtt_found = rec_time - unacked_packets[ack_seq_num][1]
                                estimated_rtt = (1-rtt_alpha)*estimated_rtt + rtt_alpha*rtt_found
                                dev = (1-rtt_beta)*dev + (rtt_beta*abs(rtt_found - estimated_rtt))
                                TIMEOUT = estimated_rtt + 4*dev
                                logging.info(f"Updated timeout_interval: {TIMEOUT} seconds")

                        # Remove acknowledged packets from the buffer
                        for seq in list(unacked_packets.keys()):
                            if seq < ack_seq_num+1:
                                unacked_packets.pop(seq)
                        window_base = ack_seq_num + 1

                    else:
                        # Duplicate ACK received
                        logging.info(f"Received duplicate ACK for packet {ack_seq_num}, count={duplicate_ack_count}")
                        duplicate_ack_count += 1

                        if enable_fast_recovery and duplicate_ack_count >= DUP_ACK_THRESHOLD:
                            logging.info("Entering fast recovery mode")
                            fast_recovery(server_socket, client_address, unacked_packets)

            except socket.timeout:
                # Timeout handling: retransmit all unacknowledged packets
                logging.info("Timeout occurred, retransmitting unacknowledged packets")
                retransmit_unacked_packets(server_socket, client_address, unacked_packets)

            # Check if we are done sending the file
            if not chunk and len(unacked_packets) == 0:
                logging.info("File transfer complete")
                break

        send_end_signal(server_socket,client_address)

def create_packet(seq_num, data):
    """
    Create a packet with the sequence number and data.
    """
    return f"{seq_num}|".encode() + data

def retransmit_unacked_packets(server_socket, client_address, unacked_packets):
    """
    Retransmit all unacknowledged packets.
    """
    for seq_num, (packet, t, trial) in unacked_packets.items():
        server_socket.sendto(packet, client_address)
        logging.info(f"Retransmitted packet {seq_num}") 
        unacked_packets[seq_num] = (packet, t, trial + 1)

def fast_recovery(server_socket, client_address, unacked_packets):
    """
    Retransmit the earliest unacknowledged packet (fast recovery).
    """
    earliest_packet = min(unacked_packets.keys())
    packet, t, trial = unacked_packets[earliest_packet]
    server_socket.sendto(packet, client_address)
    unacked_packets[earliest_packet] = (packet, t, trial + 1)

    logging.info(f"Fast recovery retransmission: packet {earliest_packet}")

def get_seq_no_from_ack_pkt(ack_packet):
    """
    Extract the sequence number from an ACK packet.
    """
    return int(ack_packet.decode().split('|')[0]) - 1

def send_end_signal(server_socket, client_address):
    """
    Send an END signal to the client to indicate file transfer completion.
    """
    end_ack_rec = False
    server_socket.settimeout(TIMEOUT)
    num_timeout = 0
    while not end_ack_rec and num_timeout <= 3:
        try:
            server_socket.sendto(b"END", client_address)
            data, client_address = server_socket.recvfrom(1024)

            if data == b"END_ACK":
                logging.info("received end ack from client")
                end_ack_rec = True

        except socket.timeout:
            num_timeout += 1
            logging.info("Socket timeout")

# Parse command-line arguments
parser = argparse.ArgumentParser(description='Reliable file transfer server over UDP.')
parser.add_argument('server_ip', help='IP address of the server')
parser.add_argument('server_port', type=int, help='Port number of the server')
parser.add_argument('fast_recovery', type=int, help='Enable fast recovery')

args = parser.parse_args()

# Run the server
send_file(args.server_ip, args.server_port, args.fast_recovery)
