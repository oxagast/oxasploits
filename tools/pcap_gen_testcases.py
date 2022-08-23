# oxagast
# use:
#   tcpdump -w ~/capture.pcap 'port 9000'
#   python3 pcap_gen_testcases.py ~/capture.pcap
# this will create a testcase directory of each destination port filled with files each
# the data section of the packets in the pcap file.  One packet is one file.  TCP header
# info is stripped.

import os
import sys
try:
    import scapy.all as scapy
except ImportError:
    import scapy
def prune_e(path):
    for (dirpath, dirnames, filenames) in os.walk(path):
        for filename in filenames:
            filef = dirpath + "/" + filename
            if os.path.getsize(filef) == 0:
                os.remove(filef)
def parse_pcap(pcap_path):
    print("Generating testcases based on " + sys.argv[1] + ".  This will take a while...")
    s = 0
    pcap_infos = list()
    packets = scapy.rdpcap(pcap_path)
    for p in packets:
        if p.haslayer("IP"):
            src_ip = p["IP"].src
            dst_ip = p["IP"].dst
        if p.haslayer("TCP"):
            raw_d = p["TCP"].payload.original
            sport = p["TCP"].sport
            dport = p["TCP"].dport
            dport_dir = str(dport)
            if not os.path.exists("testcases/" + dport_dir):
                os.mkdir("testcases/" + dport_dir)
            num = str(s)
            out = open("testcases/" + dport_dir + "/pcap.data_packet." + num + ".dat", "wb")
            out.write(raw_d) # yeah, i do hit it raw.
            s = s + 1
if len(sys.argv) != 2:
    print("You need to provide a .pcap file.")
    sys.exit(1)
if not os.path.exists(sys.argv[1]):
    print("The .pcap file does not exist.")
    sys.exit(1)
if not os.path.exists("testcases"):
    os.mkdir("testcases")
parse_pcap(sys.argv[1])
prune_e("testcases")
print("Done.")
sys.exit(0)
