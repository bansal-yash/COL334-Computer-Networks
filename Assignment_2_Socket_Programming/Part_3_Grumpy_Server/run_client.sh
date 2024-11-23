#!/bin/bash
JSON_FILE="config.json"


server_ip=$(jq -r '.server_ip' "$JSON_FILE")
server_port=$(jq -r '.server_port' "$JSON_FILE")
k=$(jq -r '.k' "$JSON_FILE")
p=$(jq -r '.p' "$JSON_FILE")
input_file=$(jq -r '.input_file' "$JSON_FILE")
num_clients=$(jq -r '.num_clients' "$JSON_FILE")

echo "Server IP: $server_ip"
echo "Server Port: $server_port"
echo "K: $k"
echo "P: $p"
echo "Input File: $input_file"
echo "Number of Clients: $num_clients"

./client "$server_ip" "$server_port" "$k" "$p" "$input_file" "$num_clients" &
CLIENT_PID=$!

wait $CLIENT_PID
