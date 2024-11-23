#include <sys/socket.h>
#include <netinet/in.h>
#include <unistd.h>
#include <arpa/inet.h>
#include <cstring>

#include <iostream>
#include <vector>
#include <pthread.h>
#include <map>
#include <fstream>

using namespace std;

const char *client_message(int offset_val)
{
    string s = to_string(offset_val);
    s = s + '\n';
    const char *c = s.c_str();
    return c;
}

pair<int, bool> update_freq(string message, map<string, int> &freq_dict)
{
    int num_word = 0;
    bool eof = false;

    for (int i = 0; i < message.size() - 2; i++)
    {
        if ((message[i] == '$' && message[i + 1] == '$' && message[i + 2] == '\n') or (message[i] == 'E' && message[i + 1] == 'O' && message[i + 2] == 'F'))
        {
            message = message.substr(0, i);
            eof = true;
            break;
        }
    }

    string word = "";
    for (char x : message)
    {
        if (x == ',' || x == '\n')
        {
            if (word != "")
            {
                if (freq_dict.find(word) != freq_dict.end())
                {
                    freq_dict[word] += 1;
                }
                else
                {
                    freq_dict[word] = 1;
                }
                num_word++;
            }
            word = "";
        }
        else
        {
            word += x;
        }
    }

    return {num_word, eof};
}

bool check_collision(string msg){
    for(int i=0; i<msg.size()-4; i++){
        if(msg[i] == 'H' && msg[i+1] == 'U' && msg[i+2] == 'H' && msg[i+3] == '!'){
            cout << "check collision function returns true\n";
            return true;
        }
    }
    return false;
}

void chat(int data_socket, int k, int p, int client_number)
{
    map<string, int> freq_dict;

    ofstream client_log("client_log_" + to_string(client_number) + ".txt");

    int buffer_size = 4096;
    char buffer[buffer_size];
    int data_index = 0;
    vector<string> server_outputs;
    bool end_of_file = false;
    int num_words = 0;

    while (true)
    {
        memset(buffer, 0, buffer_size);
        const char *message = client_message(k * data_index);

        if (num_words == 0)
        {
            send(data_socket, message, strlen(message), 0);
            if (strlen(message) > 0)
            {
                client_log << "Message sent to server: " << message << endl;
            }
            data_index++;
        }

        int words_received = recv(data_socket, buffer, buffer_size, 0);
        if (words_received > 0)
        {
            client_log << "Received from server: " << buffer << endl;
        }

        server_outputs.push_back(buffer);
        bool huh_message = check_collision(string(buffer, buffer_size));
        if(huh_message == true){
            client_log << "HUH! message received by client\n";
            data_index--;
            num_words = 0;
            client_log <<"Decreasing data index value, next offset: "<<k*data_index<<"\n";
            // Wait for the frequency here
            
        }
        
        pair<int, bool> mess_det = update_freq(buffer, freq_dict);
        end_of_file = mess_det.second;
        num_words += mess_det.first;

        if (num_words == k)
        {
            num_words = 0;
        }
        if (end_of_file)
        {
            break;
        }
    }

    ofstream outfile("output" + to_string(client_number) + ".txt");
    for (const auto &pair : freq_dict)
    {
        outfile << pair.first << ", " << pair.second << std::endl;
    }
    outfile.close();
}

struct ThreadArgs
{
    sockaddr_in server_addr;
    int k;
    int p;
    int client_number;
};

void *run_client(void *args)
{
    ThreadArgs *thread_args = static_cast<ThreadArgs *>(args);
    int cl_number = thread_args->client_number;
    int data_socket = socket(AF_INET, SOCK_STREAM, 0);
    if (data_socket == -1)
    {
        cerr << "Client socket cannot be created\n";
        pthread_exit(nullptr);
    }
    cout << "Client socket created successfully for client number:- " << cl_number << endl;

    if (connect(data_socket, (struct sockaddr *)&thread_args->server_addr, sizeof(thread_args->server_addr)) == -1)
    {
        cout << "Connection to server unsuccessful. Server might be down\n";
        close(data_socket);
        pthread_exit(nullptr);
    }
    cout << "Connection to server successful for client number:- " << cl_number << endl;

    chat(data_socket, thread_args->k, thread_args->p, cl_number);

    close(data_socket);
    cout << "Client closed successfully for client number:- " << cl_number << endl;
    pthread_exit(nullptr);
}

int main(int argc, char *argv[])
{
    struct sockaddr_in server_addr;

    const char *server_ip = argv[1];
    int server_port = stoi(argv[2]);
    int k = stoi(argv[3]);
    int p = stoi(argv[4]);
    string words_file = argv[5];
    int num_clients = stoi(argv[6]);
    int slot_time = stoi(argv[7]);
    cout<<"****************client ******** slot_time: "<<slot_time<<endl;


    int data_socket;
    int temp;
    memset(&server_addr, 0, sizeof(server_addr));
    server_addr.sin_family = AF_INET;
    server_addr.sin_port = htons(server_port);

    if (inet_pton(AF_INET, server_ip, &server_addr.sin_addr) <= 0)
    {
        cout << "Invalid address or address not supported\n";
        exit(1);
    }

    pthread_t threads[num_clients];
    ThreadArgs thread_args[num_clients];

    for (int i = 0; i < num_clients; i++)
    {
        thread_args[i].server_addr = server_addr;
        thread_args[i].k = k;
        thread_args[i].p = p;
        thread_args[i].client_number = i + 1;

        int result = pthread_create(&threads[i], nullptr, run_client, &thread_args[i]);
        if (result != 0)
        {
            cout << "Error creating thread: " << result << endl;
            return EXIT_FAILURE;
        }
    }

    for (int i = 0; i < num_clients; i++)
    {
        pthread_join(threads[i], nullptr);
    }

    cout << "All Clients closed successfully" << endl;
    exit(EXIT_SUCCESS);
}