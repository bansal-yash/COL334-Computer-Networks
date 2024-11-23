#!/bin/bash
JSON_FILE="config.json"

arg1=$1

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

if [ "$arg1" == "run" ]; then
    ./server "$server_ip" "$server_port" "$k" "$p" "$input_file" "$num_clients" &
    SERVER_PID=$!

    sleep 0.1

    ./client "$server_ip" "$server_port" "$k" "$p" "$input_file" "$num_clients" &
    CLIENT_PID=$!

    wait $SERVER_PID
    wait $CLIENT_PID

elif [ "$arg1" == "server" ]; then
    ./server "$server_ip" "$server_port" "$k" "$p" "$input_file" "$num_clients" &
    SERVER_PID=$!
    sleep 0.1

    wait $SERVER_PID

elif [ "$arg1" == "client" ]; then
    ./client "$server_ip" "$server_port" "$k" "$p" "$input_file" "$num_clients" &
    CLIENT_PID=$!

    wait $CLIENT_PID

elif [ "$arg1" == "plot" ]; then
    num_clients=(4 8 12 16 20 24 28 32)
    num_runs=(1 1 1 1 1 1 1 1 1 1)

    for i in "${num_runs[@]}"; do
        for cl_v in "${num_clients[@]}"; do            
            ./server "$server_ip" "$server_port" "$k" "$p" "$input_file" "$cl_v" &
            SERVER_PID=$!
            
            sleep 0.1
            
            ./client "$server_ip" "$server_port" "$k" "$p" "$input_file" "$cl_v" &
            CLIENT_PID=$!
            
            wait $SERVER_PID
            wait $CLIENT_PID
            
            echo "Completed run with num_clients = $cl_v"
            echo "--------------------------------------"
        done
    done
fi