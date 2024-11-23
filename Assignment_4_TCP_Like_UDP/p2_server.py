import socket
import time
import argparse
import logging
import csv

# python3 p1_server.py 10.17.50.142 8080 0

MSS = 1400
WINDOW_SIZE = 5
DUP_ACK_THRESHOLD = 3 
FILE_PATH = "file.txt"
TIMEOUT = 1


csv_file = open('seq_num_vs_cnwd.csv', mode='w', newline='')
writer_csv = csv.writer(csv_file)
writer_csv.writerow(['Timestamp', 'Seq_num', 'CNWD Size', 'SS_threshold'])

def convert_file_to_dict():
    file_path = FILE_PATH
    words_dict = {}
    seq_num = 0 
    chunk = None

    with open(file_path, 'rb') as file:
        while True:
            chunk = file.read(MSS)
            # # logging.info(chunk)
            if not chunk:
                break
            words_dict[seq_num] = chunk
            seq_num += 1
            # # logging.info("ldhiejhfjerhjr")

    # logging.info("dictionary of file made")
    # logging.info(words_dict)
    return words_dict

def send_file(server_ip, server_port):

    global TIMEOUT
    cnwd = 1
    ss_threshold = 100
    mode = 0
    # 0 - slow start, 1 - congestion avoidance, 2 - fast recovery

    
    rtt_alpha = 0.125
    rtt_beta = 0.25
    estimated_rtt = 0.0
    dev = 0.0

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_socket.bind((server_ip, server_port))
    # server_socket.settimeout(TIMEOUT)
    
    logging.info(f"Server listening on {server_ip}:{server_port}")

    client_address = None
    file_path = FILE_PATH
    # connected=False

    while True:
        try:
            # logging.info("Waiting for client connection...")
            data, client_address = server_socket.recvfrom(1024)

            if data == b"START":
                # logging.info("received start from client")

                server_socket.sendto(b"CONNECT",client_address)
                # logging.info("sent connect to client")
                # connected=True
                break
        except socket.timeout as e:
            logging.info("Socket timeout")


    seq_num = 0
    window_base = 0
    logging.info("Starting to convert file to dict")
    file_dict = convert_file_to_dict()
    logging.info("Ended the function to convert file to dict")
    # unacked_packets is a dictionary which stores only those packets which are not yet unacked at any specific time.
    # it stores in the format-> { seq_num : [actual_packet, time when packet was made, number of times that packet was tried to send] }
    # The third parameter in the key - is initialized with 0
    unacked_packets = {}
    duplicate_ack_count = 0
    last_ack_received = -1
    complete=False

    with open(file_path, 'rb') as file:
        while not complete:
            writer_csv.writerow([time.time(), seq_num, cnwd, ss_threshold])
            # send data packets
            # The while loop that sends all packets in the current window at the sender side
            # chunk = None
            logging.info(f"Starting : {seq_num},{window_base},{cnwd},{last_ack_received}")
            while seq_num < window_base + cnwd:
                if(seq_num not in file_dict):
                    chunk=None
                    break
                chunk = file_dict[seq_num]
                packet = create_packet(seq_num, chunk)
                if(seq_num in list(unacked_packets.keys())):
                    trial_rn = unacked_packets[seq_num][2] + 1
                    time_old = unacked_packets[seq_num][1]
                    unacked_packets[seq_num] = (packet, time_old, trial_rn)
                else:
                    unacked_packets[seq_num] = (packet, time.time(), 0) 
                server_socket.sendto(packet, client_address)
                logging.info(f"Sent packet {seq_num}")
                seq_num += 1

            # Wait for ACKs and retransmit if needed
            try:
            	## Handle ACKs, Timeout, Fast retransmit
                server_socket.settimeout(TIMEOUT)
                ack_packet, _ = server_socket.recvfrom(1024)
                rec_time = time.time() # log the receive time

                if ack_packet == b"START":
                    # logging.info("received start again from client:- resetting all variables")
                    server_socket.sendto(b"CONNECT",client_address)
                    # connected=True
                    continue

                if "ACK" in ack_packet.decode():
                    # ACK packet received for some packet that was sent earlier
                    ack_seq_num = get_seq_no_from_ack_pkt(ack_packet)

                    if ack_seq_num > last_ack_received:
                        # If seq no in ack packet(n) > last ack received, then this would indicate a cumulative ack for all packets until n.
                        # This is like a new ACK is received, meaning the circuit is all-is-well and can assume no congestion is happening
                        # So the next packet to be transfered is window_base + WINDOW_SIZE + 1, which is already there in "seq_num"
                        """ ---- Congestion Control ---- """
                        # In the case a new ACK arrived, you know that the network is not congested in general. you should look at increasing the cnwd size, but how much you increase it by depends on how close you are to the ss_threshold, which is told by the mode you are in.
                        if(mode == 0): # slow start mode
                            if(cnwd < ss_threshold):
                                cnwd = cnwd + 1
                            else:
                                mode = 1
                        if(mode == 1): # congestion avoidance mode
                            cnwd = cnwd + (1/(int(cnwd)))
                        if(mode == 2): # fast recovery mode
                            mode = 1
                            cnwd = ss_threshold
                            cnwd = cnwd + (1/(int(cnwd)))
                        """ ---- Congestion Control ---- """
                        
                        # logging.info(f"Received cumulative ACK for packet {ack_seq_num}")
                        last_ack_received = ack_seq_num
                        duplicate_ack_count = 0
                        seq_num = max(seq_num,ack_seq_num)
                        if ack_seq_num in unacked_packets:
                            if unacked_packets[ack_seq_num][2] == 0:
                                rtt_found = rec_time - unacked_packets[ack_seq_num][1]
                                estimated_rtt = (1-rtt_alpha)*estimated_rtt + rtt_alpha*rtt_found
                                dev = (1-rtt_beta)*dev + (rtt_beta*abs(rtt_found - estimated_rtt))
                                TIMEOUT = estimated_rtt + 4*dev
                                # logging.info(f"Updated timeout_interval: {TIMEOUT} seconds")

                        # Remove acknowledged packets from the buffer
                        # There is a chance that packets until n can be unacked, as some of their's ACK message might have been lost by
                        # the time it reaches the server. So, since ACK(n) is a cumulative ack, that would mean that all packets before n are acked
                        for seq in list(unacked_packets.keys()):
                            if seq < ack_seq_num+1:
                                unacked_packets.pop(seq)
                        window_base = ack_seq_num + 1
                        # logging.info(f"Ending : {seq_num},{window_base},{cnwd},{last_ack_received}")
                    else:
                        # Duplicate ACK received
                        # logging.info(f"Received duplicate ACK for packet {ack_seq_num}, count={duplicate_ack_count}")
                        duplicate_ack_count += 1
                        

                        if duplicate_ack_count >= DUP_ACK_THRESHOLD:
                            if(mode == 0 or mode == 1):
                                mode = 2 # enter fast recovery mode
                                ss_threshold = cnwd // 2
                                cnwd = ss_threshold + 3
                            # logging.info("Entering fast recovery mode")
                            fast_recovery(server_socket, client_address, unacked_packets)

            except socket.timeout:
                if(mode == 0):
                    ss_threshold = cnwd // 2
                    cnwd = 1
                if(mode == 1  or mode == 2):
                    ss_threshold = cnwd // 2
                    cnwd = 1
                    mode = 0
                duplicate_ack_count = 0
                # Here - send only the most old unacked packet and for all the other packets enter the loop normally
                # Timeout handling: retransmit all unacknowledged packets
                # logging.info("Timeout occurred, retransmitting unacknowledged packets")
                # retransmit_unacked_packets(server_socket, client_address, unacked_packets)
                """ --------------------------------------------------------------------------------------------------------------------"""
                """ --------------------------------------------------------------------------------------------------------------------"""
                # Here instead of retransmitting all the packets that are present in the unacked_packets dictionary
                # take the system back to the state where the seq_num to send is the least unacked_packet and continue
                seq_num = min(unacked_packets.keys())
                window_base = seq_num
                """ --------------------------------------------------------------------------------------------------------------------"""
                """ --------------------------------------------------------------------------------------------------------------------"""

            # Check if we are done sending the file
            if not chunk and len(unacked_packets) == 0:
                logging.info("File transfer complete")
                break

        send_end_signal(server_socket,client_address)
        logging.info("Sending End signal complete")


def create_packet(seq_num, data):
    """
    Create a packet with the sequence number and data.
    """
    return f"{seq_num}|".encode() + data

# def retransmit_unacked_packets(server_socket, client_address, unacked_packets):
#     """
#     Retransmit all unacknowledged packets.
#     """
#     for seq_num, (packet, t, trial) in unacked_packets.items():
#         server_socket.sendto(packet, client_address)
#         # logging.info(f"Retransmitted packet {seq_num}") 
#         unacked_packets[seq_num] = (packet, t, trial + 1)

def fast_recovery(server_socket, client_address, unacked_packets):
    """
    Retransmit the earliest unacknowledged packet (fast recovery).
    """
    earliest_packet = min(unacked_packets.keys())
    packet, t, trial = unacked_packets[earliest_packet]
    server_socket.sendto(packet, client_address)
    unacked_packets[earliest_packet] = (packet, t, trial + 1)

    # logging.info(f"Fast recovery retransmission: packet {earliest_packet}")

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
    while not end_ack_rec and num_timeout <= 10:
        try:
            server_socket.sendto(b"END", client_address)
            data, client_address = server_socket.recvfrom(1024)

            if data == b"END_ACK":
                # logging.info("received end ack from client")
                end_ack_rec = True

        except socket.timeout:
            num_timeout += 1
            logging.info("Socket timeout")

# Parse command-line arguments
parser = argparse.ArgumentParser(description='Reliable file transfer server over UDP.')
parser.add_argument('server_ip', help='IP address of the server')
parser.add_argument('server_port', type=int, help='Port number of the server')
# parser.add_argument('fast_recovery', type=int, help='Enable fast recovery')
# parser.add_argument('log_file')
args = parser.parse_args()
# log_file = args.log_file
logging.basicConfig(filename=f"{args.server_ip}_ser_log.txt", filemode='w', level=logging.INFO, format='%(asctime)s - %(message)s')


# Run the server
send_file(args.server_ip, args.server_port)
csv_file.close()

