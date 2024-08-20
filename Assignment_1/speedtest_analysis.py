import dpkt
import sys
import matplotlib.pyplot as plt
import math

pcap_file = sys.argv[1]
to_plot = False
to_give_throughput = False

if "--plot" in sys.argv:
    to_plot = True
if "--throughput" in sys.argv:
    to_give_throughput = True


with open(pcap_file, "rb") as f:
    pcap = list(dpkt.pcapng.Reader(f))


speed_pkt = []
upload_pkt = []
download_pkt = []

total_packets = 0
speedtest_packets = 0
total_bytes = 0
speedtest_bytes = 0

for ts, pkt in pcap:
    total_packets += 1
    total_bytes += len(pkt)

    eth = dpkt.ethernet.Ethernet(pkt)
    ip = eth.data

    if isinstance(ip, dpkt.ip.IP) or isinstance(ip, dpkt.ip6.IP6):
        tcp = ip.data
        if isinstance(tcp, dpkt.tcp.TCP) and (tcp.sport == 443 or tcp.dport == 443):
            speedtest_packets += 1
            speedtest_bytes += len(pkt)
            speed_pkt.append((ts, len(pkt)))

            if tcp.dport == 443:
                upload_pkt.append((ts, len(pkt)))
            else:
                download_pkt.append((ts, len(pkt)))


first_ts = speed_pkt[0][0]
for i in range(len(speed_pkt)):
    speed_pkt[i] = (speed_pkt[i][0] - first_ts + 0.3, speed_pkt[i][1])

for i in range(len(upload_pkt)):
    upload_pkt[i] = (upload_pkt[i][0] - first_ts + 0.3, upload_pkt[i][1])

for i in range(len(download_pkt)):
    download_pkt[i] = (download_pkt[i][0] - first_ts + 0.3, download_pkt[i][1])

avg_factor = 1
t_max = math.ceil(speed_pkt[-1][0])

up_with_ts = {}
down_with_ts = {}

for pkt in upload_pkt:
    t = math.floor(pkt[0] / avg_factor)
    if t in up_with_ts:
        up_with_ts[math.floor(pkt[0] / avg_factor)] += (pkt[1] * 8) / 1e6
    else:
        up_with_ts[math.floor(pkt[0] / avg_factor)] = (pkt[1] * 8) / 1e6

for pkt in download_pkt:
    t = math.floor(pkt[0] / avg_factor)
    if t in down_with_ts:
        down_with_ts[math.floor(pkt[0] / avg_factor)] += (pkt[1] * 8) / 1e6
    else:
        down_with_ts[math.floor(pkt[0] / avg_factor)] = (pkt[1] * 8) / 1e6

up_max = max(up_with_ts.values())
down_max = max(down_with_ts.values())
up_time = 0
up_size = 0
down_time = 0
down_size = 0
factor = 4

for pkt_key in up_with_ts:
    if up_with_ts[pkt_key] >= up_max / factor:
        up_time += avg_factor
        up_size += up_with_ts[pkt_key]

for pkt_key in down_with_ts:
    if down_with_ts[pkt_key] >= down_max / factor:
        down_time += avg_factor
        down_size += down_with_ts[pkt_key]

up_speed = up_size / up_time
down_speed = down_size / down_time

percent_speedtest_bytes = ((speedtest_bytes) / total_bytes) * 100
percent_speedtest_packets = ((speedtest_packets) / total_packets) * 100

print("Percent packets for speedtest :- ", f"{percent_speedtest_packets:.3f}")
print(
    "Percent bytes for speedtest :- ",
    f"{percent_speedtest_bytes:.3f}",
)

if to_give_throughput:
    print("Download and upload speeds in Megabits per second are:- ")
    print(f"{down_speed:.3f}" + " , " + f"{up_speed:.3f}")

if to_plot:
    up_keys, up_vals = up_with_ts.keys(), up_with_ts.values()
    down_keys, down_vals = down_with_ts.keys(), down_with_ts.values()
    plt.figure(figsize=(12, 6))
    plt.plot(up_keys, up_vals, label="Upload Throughput")
    plt.plot(down_keys, down_vals, label="Download Throughput")
    plt.xlabel("Time (Seconds)")
    plt.ylabel("Throughput (Mega bits per Second (Mbps))")
    plt.title("Time-Series of Throughput")
    plt.legend()
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig("avg_throughput.png")
    plt.show()
