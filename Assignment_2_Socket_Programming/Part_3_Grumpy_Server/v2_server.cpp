#include <sys/socket.h>
#include <netinet/in.h>
#include <unistd.h>
#include <arpa/inet.h>
#include <cstring>
#include <iostream>
#include <pthread.h>
#include <fstream>
#include <sstream>
#include <vector>
#include <string>
using namespace std;

// Global mutex to protect request handling
pthread_mutex_t request_mutex = PTHREAD_MUTEX_INITIALIZER;
bool is_busy = false;           // Track if the server is busy
int current_client_socket = -1; // Socket of the currently active client
int current_client = 0;

vector<string> memory_data;
int memory_size;

// Helper Functions
char *string_to_char(string s) { return &s[0]; }

string char_to_string(char *c, int char_arr_size) { return string(c, char_arr_size); }

int get_offset(string offset_str)
{
    return stoi(offset_str);
}

bool send_server_to_client_msgs(int data_socket, int k, int p, int client_number, int offset_value, ofstream &server_log)
{
    bool eof = false;
    // Send packets of size p words each, from the memory. Send a maximum of k words.
    int msg_idx = 1;
    int offset_initial = offset_value;
    int num_packets = 0;
    bool mop_up_packet = true;
    if (memory_size - offset_value >= k)
    {
        num_packets = k / p;
        while (num_packets > 0)
        {
            string words_to_send = "";
            int idx = 0;
            while (idx < p && idx + offset_value < k + offset_initial)
            {
                if (idx + offset_value == memory_size - 1)
                {
                    words_to_send += memory_data[idx + offset_value] + ",EOF";
                    eof = true;
                }
                else
                {
                    if (k % p == 0)
                    {
                        if (idx + offset_value == k + offset_initial - 1)
                        {
                            words_to_send += memory_data[idx + offset_value];
                        }
                        else
                        {
                            words_to_send += memory_data[idx + offset_value] + ',';
                        }
                    }
                    else
                    {
                        if (mop_up_packet == false)
                        {
                            if (idx + offset_value == k + offset_initial - 1)
                            {
                                words_to_send = words_to_send + memory_data[idx + offset_value];
                            }
                            else
                            {
                                words_to_send = words_to_send + memory_data[idx + offset_value] + ',';
                            }
                        }
                        else
                        {
                            words_to_send = words_to_send + memory_data[idx + offset_value] + ',';
                        }
                    }
                }
                idx++;
            }
            offset_value += p;
            num_packets--;
            if (num_packets == 0 && k % p != 0 && mop_up_packet == true)
            {
                num_packets = 1;
                mop_up_packet = false;
            }
            words_to_send = words_to_send + '\n';
            char *char_array = new char[words_to_send.length() + 1];
            strcpy(char_array, words_to_send.c_str());
            send(data_socket, char_array, strlen(char_array), 0);
            if (strlen(char_array) > 0)
            {
                server_log << "\t Message sent to client: " << msg_idx << " : \t" << char_array << endl;
                msg_idx++;
            }
            delete[] char_array; // Free allocated memory
        }
    }
    else
    {
        // If offset_value + k exceeds memory_size, adjust k accordingly
        int adjusted_k = memory_size - offset_value;
        if (adjusted_k <= 0)
        {
            // No data to send
            string msg = "$$\n";
            char *msg_array = new char[msg.length() + 1];
            strcpy(msg_array, msg.c_str());
            send(data_socket, msg_array, strlen(msg_array), 0);
            server_log << "\t Message sent to client: \t" << msg_array << endl;
            delete[] msg_array;
            return true;
        }

        num_packets = adjusted_k / p;
        while (num_packets > 0)
        {
            string words_to_send = "";
            int idx = 0;
            while (idx < p && idx + offset_value < memory_size)
            {
                if (idx + offset_value == memory_size - 1)
                {
                    words_to_send += memory_data[idx + offset_value] + ",EOF";
                    eof = true;
                }
                else
                {
                    words_to_send += memory_data[idx + offset_value] + ",";
                }
                idx++;
            }
            offset_value += p;
            num_packets--;
            if (num_packets == 0 && adjusted_k % p != 0 && mop_up_packet == true)
            {
                num_packets = 1;
                mop_up_packet = false;
            }
            words_to_send = words_to_send + '\n';
            char *char_array = new char[words_to_send.length() + 1];
            strcpy(char_array, words_to_send.c_str());
            send(data_socket, char_array, strlen(char_array), 0);
            if (strlen(char_array) > 0)
            {
                server_log << "\t Message sent to client: " << msg_idx << " : \t" << char_array << endl;
                msg_idx++;
            }
            delete[] char_array; // Free allocated memory
        }
    }

    return eof;
}

void handle_client(int data_socket, int k, int p, int client_number)
{
    ofstream server_log("server_log_" + to_string(client_number) + ".txt");
    int buffer_size = 128;
    char buffer[buffer_size];

    while (true)
    {
        memset(buffer, 0, buffer_size);

        // Get the message from the client which contains the offset value
        int msg_received = recv(data_socket, buffer, buffer_size, 0);
        if (msg_received <= 0)
        {
            // Client disconnected or error
            server_log << "Client disconnected or error occurred.\n";
            break;
        }
        string offset = char_to_string(buffer, msg_received);

        int offset_value = get_offset(offset);

        server_log << "Offset received: " << offset_value << endl;

        // Lock the mutex to check and update server state
        pthread_mutex_lock(&request_mutex);

        if (is_busy == false)
        {
            // Server is free, take this request
            is_busy = true;
            current_client_socket = data_socket;
            current_client = client_number;
            pthread_mutex_unlock(&request_mutex);

            // Process the request
            if (offset_value >= memory_size)
            {
                string msg = "$$\n";
                send(data_socket, msg.c_str(), msg.length(), 0);
                server_log << "\t Message sent to client: \t" << msg;
            }
            else
            {
                bool eof = send_server_to_client_msgs(data_socket, k, p, client_number, offset_value, server_log);
                if (eof)
                {
                    server_log << "EOF reached. Closing connection.\n";
                    break;
                }
            }

            // After processing, reset the server state
            pthread_mutex_lock(&request_mutex);
            is_busy = false;
            pthread_mutex_unlock(&request_mutex);
        }
        else
        {
            // Server is busy, send "HUH!" to both current and new client
            string msg = "HUH!\n";
            cout<<"Entered this case ------------------ \n";
            send(data_socket, msg.c_str(), msg.length(), 0);
            server_log << "\t Server busy, sending HUH! to new client.\n" << data_socket;

            // Send "HUH!" to the currently active client
            send(current_client_socket, msg.c_str(), msg.length(), 0);
            server_log << "\t Server busy, sending HUH! to current active client.\n" << current_client_socket;

            // Reset server state
            pthread_mutex_lock(&request_mutex);
            is_busy = false;
            pthread_mutex_unlock(&request_mutex);

            // break;
        }
    }

    close(data_socket);
    cout << "Connection with client number: " << client_number << " closed successfully\n";
}

struct ThreadArgs
{
    int data_socket;
    int k;
    int p;
    int client_number;
};

void *client_thread(void *args)
{
    ThreadArgs *thread_args = static_cast<ThreadArgs *>(args);
    handle_client(thread_args->data_socket, thread_args->k, thread_args->p, thread_args->client_number);
    pthread_exit(nullptr);
}

int main(int argc, char *argv[])
{
    if (argc != 7)
    {
        cerr << "Usage: " << argv[0] << " <server_ip> <server_port> <k> <p> <words_file> <num_clients>\n";
        return EXIT_FAILURE;
    }

    // Parsing inputs from the command line
    const char *server_ip = argv[1];
    int server_port = stoi(argv[2]);
    int k = stoi(argv[3]);
    int p = stoi(argv[4]);
    string words_file = argv[5];
    int num_clients = stoi(argv[6]);

    // Load words from the file into memory_data
    string line, word;
    ifstream file(words_file);
    if (!file.is_open())
    {
        cerr << "Failed to open words file: " << words_file << endl;
        return EXIT_FAILURE;
    }

    while (getline(file, line))
    {
        stringstream ss(line);

        while (getline(ss, word, ','))
        {
            memory_data.push_back(word);
        }
    }
    file.close();

    memory_size = memory_data.size();

    // Initialization of socket structures
    struct sockaddr_in server_addr, client_addr;
    int connection_socket;
    int temp;
    socklen_t client_len = sizeof(client_addr);

    // Create master socket
    connection_socket = socket(AF_INET, SOCK_STREAM, 0);
    if (connection_socket == -1)
    {
        cerr << "Master socket cannot be created\n";
        exit(1);
    }
    cout << "Master socket created successfully\n";

    // Zero out the server_addr structure
    memset(&server_addr, 0, sizeof(server_addr));
    server_addr.sin_family = AF_INET;
    server_addr.sin_addr.s_addr = inet_addr(server_ip);
    server_addr.sin_port = htons(server_port);

    cout << "Server Socket initialization with IP " << server_ip << " and Port " << server_port << " successful\n";

    // Set socket options to reuse address and port
    int opt = 1;
    if (setsockopt(connection_socket, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt)) < 0)
    {
        cerr << "Error setting SO_REUSEADDR\n";
        close(connection_socket);
        exit(1);
    }

    // Bind the socket to the specified IP and port
    temp = bind(connection_socket, (struct sockaddr *)&server_addr, sizeof(server_addr));
    if (temp == -1)
    {
        cerr << "Binding unsuccessful\n";
        close(connection_socket);
        exit(1);
    }
    cout << "Binding successful to IP and port\n";

    // Listen for incoming connections
    temp = listen(connection_socket, 20);
    if (temp == -1)
    {
        cerr << "Listening failure\n";
        close(connection_socket);
        exit(1);
    }
    cout << "Listening socket created successfully\n";

    // Prepare to accept client connections
    vector<pthread_t> threads(num_clients);
    vector<ThreadArgs> thread_args(num_clients);

    int clients_connected = 0;

    while (clients_connected < num_clients)
    {
        cout << "Waiting for client " << clients_connected + 1 << " to send connection request...\n";

        int data_socket = accept(connection_socket, (struct sockaddr *)&client_addr, &client_len);
        if (data_socket == -1)
        {
            cerr << "Client connection failed\n";
            continue;
        }

        char client_ip[INET_ADDRSTRLEN];
        inet_ntop(AF_INET, &client_addr.sin_addr, client_ip, INET_ADDRSTRLEN);
        cout << "Connection accepted from client " << clients_connected + 1
             << " IP: " << client_ip
             << ", Port: " << ntohs(client_addr.sin_port) << endl;

        // Prepare thread arguments
        thread_args[clients_connected].data_socket = data_socket;
        thread_args[clients_connected].k = k;
        thread_args[clients_connected].p = p;
        thread_args[clients_connected].client_number = clients_connected + 1;

        // Create a new thread for the connected client
        if (pthread_create(&threads[clients_connected], nullptr, client_thread, &thread_args[clients_connected]) != 0)
        {
            cerr << "Error creating thread for client " << clients_connected + 1 << "\n";
            close(data_socket);
            continue;
        }

        clients_connected++;
    }

    // Wait for all threads to finish
    for (int i = 0; i < num_clients; ++i)
    {
        pthread_join(threads[i], nullptr);
        cout << "Thread for client " << i + 1 << " has finished.\n";
    }

    // Destroy the mutex
    pthread_mutex_destroy(&request_mutex);

    // Close the master connection socket
    close(connection_socket);
    cout << "Master connection socket closed. Server shutting down.\n";

    return 0;
}
