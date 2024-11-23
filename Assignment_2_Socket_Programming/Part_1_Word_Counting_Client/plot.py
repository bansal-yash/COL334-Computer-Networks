import numpy as np
import matplotlib.pyplot as plt

data = {}
with open('time.txt', 'r') as file:
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

plt.plot(p_values, average_times, marker='o')
plt.title('Average Time for Each Value of p')
plt.xlabel('p')
plt.ylabel('Average Time')
plt.xticks(p_values)
plt.grid()
plt.savefig("plot.png")
