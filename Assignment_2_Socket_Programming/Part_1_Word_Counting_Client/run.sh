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
    p_values=(1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20)
    num_runs=(1 1 1 1 1)

    for i in "${num_runs[@]}"; do
        for p_v in "${p_values[@]}"; do
            echo "Running server and client with p = $p"
            
            ./server "$server_ip" "$server_port" "$k" "$p_v" "$input_file" "$num_clients" &
            SERVER_PID=$!
            
            sleep 0.1
            
            ./client "$server_ip" "$server_port" "$k" "$p_v" "$input_file" "$num_clients" &
            CLIENT_PID=$!
            
            wait $SERVER_PID
            wait $CLIENT_PID
            
            echo "Completed run with p = $p_v"
            echo "--------------------------------------"
        done
    done
fi