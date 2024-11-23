import socket
import argparse
import logging
# python3 p1_client.py 10.17.50.142 8080

# Constants
MSS = 1400  # Maximum Segment Size
CLIENT_TIMEOUT = 0.5

log_file = "client_log_file.txt"
logging.basicConfig(filename=log_file, filemode='w', level=logging.INFO, format='%(asctime)s - %(message)s')

def receive_file(server_ip, server_port):

    client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    client_socket.settimeout(CLIENT_TIMEOUT)  # Set timeout for server response

    server_address = (server_ip, server_port)
    expected_seq_num = 0
    output_file_path = "received_file.txt"  # Default file name
    connected = False
    buffer_dict = {}

    with open(output_file_path, 'wb') as file:
        while True:
            while not connected:
                try:
                    client_socket.settimeout(CLIENT_TIMEOUT)

                    # Send initial connection request to server
                    client_socket.sendto(b"START", server_address)
                    logging.info("sent start \n")

                    # Receive the packet
                    packet, _ = client_socket.recvfrom(max(1024, MSS + 100))  # Allow room for headers

                    if packet == b"CONNECT":
                        connected=True
                        logging.info("Connection to server successful\n")
                        break

                except socket.timeout:
                    logging.info("client Timeout retrying \n")

            try:
                client_socket.settimeout(CLIENT_TIMEOUT)  # Set timeout for server response
                packet, _ = client_socket.recvfrom(max(1024, MSS + 100))  # Allow room for headers
                if packet == b"CONNECT":
                    continue

                if packet == b"END":
                    logging.info("END recieved, file transfer complete")
                    client_socket.sendto(b"END_ACK", server_address)
                    break

                seq_num, data = parse_packet(packet)
                logging.info(seq_num)
                logging.info(expected_seq_num)

                # If the packet is in order, write it to the file
                if seq_num == expected_seq_num:
                    file.write(data)
                    file.flush()
                    logging.info(f"Received packet {seq_num}, writing to file")
                    
                    # Update expected seq number and send cumulative ACK for the received packet
                    send_ack(client_socket, server_address, seq_num)
                    expected_seq_num += 1

                    # Process buffered packets that are now in order
                    rem_from_buffer = False
                    while expected_seq_num in buffer_dict:
                        rem_from_buffer = True
                        file.write(buffer_dict.pop(expected_seq_num))
                        file.flush()
                        logging.info(f"Writing buffered packet {expected_seq_num} to file")
                        # send_ack(client_socket, server_address, expected_seq_num)
                        expected_seq_num += 1

                    if rem_from_buffer:
                        send_ack(client_socket, server_address, expected_seq_num - 1)

                elif seq_num > expected_seq_num:
                    # Packet arrived out of order, buffer it
                    buffer_dict[seq_num] = data
                    logging.info(f"Buffered out-of-order packet {seq_num}")

                elif seq_num < expected_seq_num:
                    # Duplicate or old packet, send ACK again
                    send_ack(client_socket, server_address, expected_seq_num-1)   # ack to be sent for last correct received packet
                # else:
                    # packet arrived out of order
                    # handle_pkt()

            except socket.timeout:
                logging.info("Client Timeout waiting for data")

def parse_packet(packet):
    """
    Parse the packet to extract the sequence number and data.
    """
    seq_num, data = packet.split(b'|', 1)
    return int(seq_num), data

def send_ack(client_socket, server_address, seq_num):
    """
    Send a cumulative acknowledgment for the received packet.
    """
    ack_packet = f"{seq_num + 1}|ACK".encode()
    client_socket.sendto(ack_packet, server_address)
    logging.info(f"Sent cumulative ACK for packet {seq_num}")

# Parse command-line arguments
parser = argparse.ArgumentParser(description='Reliable file receiver over UDP.')
parser.add_argument('server_ip', help='IP address of the server')
parser.add_argument('server_port', type=int, help='Port number of the server')

args = parser.parse_args()

# Run the client
receive_file(args.server_ip, args.server_port)

