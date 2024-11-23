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
#include <atomic>
#include <tuple>
#include <mutex>
#include <condition_variable>

using namespace std;

// lsof -i :8080
// kill -9 50890

/*
Convert char* to string
(char* c) -> { return std::string(c); }

Convert string to char*
const string& s -> { return const_cast<char*>(s.c_str()); }

Sending data
send(data_socket, message, strlen(message), 0)

Recieving data
recv(data_socket, buffer, buffer_size, 0)
*/

vector<vector<int>> pending_requests;
std::mutex pending_requests_mutex;
int curr_turn = 1;
std::mutex curr_turn_mutex;

condition_variable cv;
bool is_turn = false;

int n_cl;
vector<string> memory_data;
int memory_size;

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
    // two cases
    // case 1 - if the offset value is larger than memory size then return message - "$$\n"

    // case 2 - otherwise case - when the offset is smaller than the memory size
    // subcases - everytime the client sends an offset, we might not have total k words left in the memory.
    // so if there are less than k words then we have to send that much amount of words only. ending with a EOF
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
                // cout << "word: " << memory_data[idx + offset_value] << " idx: " << idx << " offset_value: " << offset_value << endl;
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
        }
        // there are remaining k%p packets left to be sent
    }
    else
    {
        // in this case for now we will send packets one by one
        int left_words = memory_size % k;
        num_packets = left_words / p;

        if (left_words > 0 && left_words < p)
        {
            string words_to_send = "";
            for (int idx = memory_size - left_words; idx < memory_size; idx++)
            {
                words_to_send += memory_data[idx] + ",";
            }
            words_to_send += "EOF";
            eof = true;

            words_to_send = words_to_send + '\n';
            char *char_array = new char[words_to_send.length() + 1];
            strcpy(char_array, words_to_send.c_str());
            send(data_socket, char_array, strlen(char_array), 0);
            if (strlen(char_array) > 0)
            {
                server_log << "\t Message sent to client: " << msg_idx << " : \t" << char_array << endl;
                msg_idx++;
            }
        }

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
                // cout << "word: " << memory_data[idx + offset_value] << " idx: " << idx << " offset_value: " << offset_value << endl;
                idx++;
            }
            offset_value += p;
            num_packets--;
            if (num_packets == 0 && left_words % p != 0 && mop_up_packet == true)
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
                // flag = true;
            }
        }
    }

    return eof;
}

void handle_client(int data_socket, int k, int p, int client_number)
{
    ofstream server_log("server_log_" + to_string(client_number) + ".txt");
    int buffer_size = 128;
    char buffer[buffer_size];
    bool eof;
    while (true)
    {
        memset(buffer, 0, buffer_size);

        // Get the message from the client which contains the offset value
        int msg_received = recv(data_socket, buffer, buffer_size, 0);
        string offset = char_to_string(buffer, buffer_size);

        int offset_value = get_offset(offset);

        server_log << "Offset recieved:- " << offset_value << endl;

        {
            std::unique_lock<std::mutex> lock(pending_requests_mutex);
            pending_requests[client_number].push_back(offset_value);

            cv.wait(lock, [client_number]()
                    { return curr_turn == client_number; });
        }

        offset_value = pending_requests[client_number].front();

        if (offset_value > memory_size)
        {
            string msg = "$$\n";
            char *msg_array = new char[msg.length() + 1];
            strcpy(msg_array, msg.c_str());
            send(data_socket, msg_array, strlen(msg_array), 0);
            if (strlen(msg_array) > 0)
            {
                server_log << "\t Message sent to client: \t" << msg_array << endl;
            }
        }

        else
        {
            eof = send_server_to_client_msgs(data_socket, k, p, client_number, offset_value, server_log);
        }

        {
            std::lock_guard<std::mutex> lock(pending_requests_mutex);
            std::lock_guard<std::mutex> lock1(curr_turn_mutex);

            if (pending_requests[client_number].size() > 0)
            {
                pending_requests[client_number].erase(pending_requests[client_number].begin());
            }
            curr_turn++;
            if (curr_turn > n_cl)
            {
                curr_turn = 1;
            }

            cv.notify_all();
        }

        if (eof)
        {
            break;
        }
    }

    close(data_socket);
    cout << "Connection with client number:- " << client_number << " closed successfully\n";
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
    // close(thread_args->data_socket);
    pthread_exit(nullptr);
}

int main(int argc, char *argv[])
{
    // Parsing inputs from the command line
    const char *server_ip = argv[1];
    int server_port = stoi(argv[2]);
    int k = stoi(argv[3]);
    int p = stoi(argv[4]);
    string words_file = argv[5];
    int num_clients = stoi(argv[6]);
    n_cl = num_clients;
    pending_requests.push_back({});

    string line, word;
    ifstream file(words_file);
    while (getline(file, line))
    {
        stringstream ss(line);

        while (std::getline(ss, word, ','))
        {
            memory_data.push_back(word);
        }
    }
    file.close();

    memory_size = memory_data.size();

    // initialization of socket class objects and idenitifers
    struct sockaddr_in server_addr, client_addr;
    int connection_socket;
    int data_socket;
    int temp;
    socklen_t client_len = sizeof(client_addr);
    // Using IP addr and port to establish connection with the client and declaring itself open to receive messages.

    {
        connection_socket = socket(AF_INET, SOCK_STREAM, 0);

        if (connection_socket == -1)
        {
            cout << "Master socket cannot be created\n";
            exit(1);
        }
        cout << "Master socket created successfully\n";

        memset(&server_addr, 0, sizeof(server_addr));
        server_addr.sin_family = AF_INET;
        server_addr.sin_addr.s_addr = inet_addr(server_ip);
        server_addr.sin_port = htons(server_port);

        cout << "Server Socket initialization with values of IP and Port - successful\n";

        int opt = 1;
        if (setsockopt(connection_socket, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt)))
        {
            cout << "Error setting SO_REUSEADDR\n";
            exit(1);
        }

        temp = bind(connection_socket, (struct sockaddr *)&server_addr, sizeof(server_addr));

        if (temp == -1)
        {
            cout << "Binding unsuccessful\n";
            exit(1);
        }
        cout << "Binding successful to IP and port\n";

        temp = listen(connection_socket, 20);
        if (temp == -1)
        {
            cout << "Listening failure\n";
            exit(1);
        }
        cout << "Listening socket created successfully\n";
    }

    vector<pthread_t> threads(num_clients);
    vector<ThreadArgs> thread_args(num_clients);

    int clients_connected = 0;

    while (clients_connected < num_clients)
    {
        cout << "Waiting for the client to send connection request\n";

        int data_socket = accept(connection_socket, (struct sockaddr *)&client_addr, &client_len);
        if (data_socket == -1)
        {
            cerr << "Client connection failed\n";
            continue;
        }

        char client_ip[INET_ADDRSTRLEN];
        inet_ntop(AF_INET, &client_addr.sin_addr, client_ip, INET_ADDRSTRLEN);
        cout << "Connection accepted from client IP: " << client_ip << ", Port: " << ntohs(client_addr.sin_port) << endl;

        pending_requests.push_back({});

        thread_args[clients_connected].data_socket = data_socket;
        thread_args[clients_connected].k = k;
        thread_args[clients_connected].p = p;
        thread_args[clients_connected].client_number = clients_connected + 1;

        if (pthread_create(&threads[clients_connected], nullptr, client_thread, &thread_args[clients_connected]) != 0)
        {
            cout << "Error creating thread\n";
            return EXIT_FAILURE;
        }

        clients_connected++;
    }

    for (pthread_t &thread : threads)
    {
        pthread_join(thread, nullptr);
    }

    close(connection_socket);
    cout << "Connection closed\n";
    cout << "round_robin" << endl;
    
    exit(0);
}