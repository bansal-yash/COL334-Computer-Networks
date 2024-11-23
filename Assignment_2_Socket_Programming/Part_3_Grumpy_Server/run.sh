#!/bin/bash
JSON_FILE="config.json"

arg1=$1

server_ip=$(jq -r '.server_ip' "$JSON_FILE")
server_port=$(jq -r '.server_port' "$JSON_FILE")
k=$(jq -r '.k' "$JSON_FILE")
p=$(jq -r '.p' "$JSON_FILE")
input_file=$(jq -r '.input_file' "$JSON_FILE")
num_clients=$(jq -r '.num_clients' "$JSON_FILE")
slot_time=$(jq -r '.slot_time' "$JSON_FILE")

echo "Server IP: $server_ip"
echo "Server Port: $server_port"
echo "K: $k"
echo "P: $p"
echo "Input File: $input_file"
echo "Number of Clients: $num_clients"
echo "Time for one slot: $slot_time"

if [ "$arg1" == "aloha" ]; then
    ./server "$server_ip" "$server_port" "$k" "$p" "$input_file" "$num_clients" "$slot_time" &
    SERVER_PID=$!

    sleep 1
    echo "ALOHA RUN SH FILE CALLED"

    ./client "$server_ip" "$server_port" "$k" "$p" "$input_file" "$num_clients" "$slot_time" &
    CLIENT_PID=$!

    wait $SERVER_PID
    wait $CLIENT_PID
elif [ "$arg1" == "run-fifo" ]; then
    ./server-fifo "$server_ip" "$server_port" "$k" "$p" "$input_file" "$num_clients" &
    SERVER_PID=$!

    sleep 0.1

    ./client-fifo "$server_ip" "$server_port" "$k" "$p" "$input_file" "$num_clients" &
    CLIENT_PID=$!

    wait $SERVER_PID
    wait $CLIENT_PID
fi
