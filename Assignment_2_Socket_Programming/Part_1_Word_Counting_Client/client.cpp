#include <sys/socket.h>
#include <netinet/in.h>
#include <unistd.h>
#include <arpa/inet.h>
#include <cstring>

#include <iostream>
#include <vector>
#include <map>
#include <fstream>
#include <chrono>

using namespace std;

float total_time = 0;

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

void chat(int data_socket, int k, int p, int client_number)
{
    auto start_time = chrono::high_resolution_clock::now();

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

    ofstream outfile("output.txt");
    for (const auto &pair : freq_dict)
    {
        outfile << pair.first << ", " << pair.second << std::endl;
    }
    outfile.close();
    auto end_time = chrono::high_resolution_clock::now();
    chrono::duration<double> duration = end_time - start_time;
    total_time += duration.count();
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

    int data_socket;
    int temp;

    {
        data_socket = socket(AF_INET, SOCK_STREAM, 0);

        if (data_socket == -1)
        {
            cout << "Client socket cannot be created\n";
            exit(1);
        }
        cout << "Client socket created successfully\n";

        memset(&server_addr, 0, sizeof(server_addr));
        server_addr.sin_family = AF_INET;
        server_addr.sin_port = htons(server_port);

        if (inet_pton(AF_INET, server_ip, &server_addr.sin_addr) <= 0)
        {
            cout << "Invalid address or address not supported\n";
            exit(1);
        }

        temp = connect(data_socket, (struct sockaddr *)&server_addr, sizeof(server_addr));

        if (temp == -1)
        {
            cout << "Connection to server unsuccessful. Server might be down\n";
            exit(1);
        }

        cout << "Connection to server successful\n";
    }

    chat(data_socket, k, p, 1);
    close(data_socket);
    cout << "Client closed successfully" << endl;

    std::ofstream time_file("time.txt", std::ios::app);
    float average_time = static_cast<float>(total_time) / num_clients;
    cout << "Value of p:- " << p << " , Time taken:- " << average_time << endl;
    time_file << p << " " << average_time << endl;
    exit(EXIT_SUCCESS);
}
