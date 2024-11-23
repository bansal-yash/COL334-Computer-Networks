import numpy as np
import matplotlib.pyplot as plt

def read_times(filename):
    data = {}
    with open(filename, 'r') as file:
        for line in file:
            p, time = line.split()
            p = int(p)
            time = float(time)

            if p not in data:
                data[p] = []
            data[p].append(time)

    p_values = []
    average_times = []
    for p, times in sorted(data.items()):
        p_values.append(p)
        average_times.append(np.mean(times))
        
    return p_values, average_times

p_fifo, avg_time_fifo = read_times('time-fifo.txt')
p_rr, avg_time_rr = read_times('time-rr.txt')

plt.plot(p_fifo, avg_time_fifo, marker='o', label='FIFO')
plt.plot(p_rr, avg_time_rr, marker='x', label='Round Robin')

plt.title('Average Time per Client vs Number of Clients')
plt.xlabel('Number of Clients')
plt.ylabel('Average Time per Client')
plt.xticks(sorted(set(p_fifo).union(p_rr))) 
plt.grid()
plt.legend()
plt.savefig("plot.png")
