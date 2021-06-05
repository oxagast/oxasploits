# oxagast
# use:
#   tcpdump -w ~/capture.pcap 'port 9000'
#   python3 pcap_gen_testcases.py ~/capture.pcap
# this will create a directory of each destination port filled with files each the data section
# of the packets in the pcap file.  One packet is one file.  TCP header info is stripped.

import os
import sys
import scapy_http.http
try:
    import scapy.all as scapy
except ImportError:
    import scapy
def parse_pcap(pcap_path):
    s = 0
    pcap_infos = list()
    packets = scapy.rdpcap(pcap_path)
    for p in packets:
        if p.haslayer("IP"):
            src_ip = p["IP"].src
            dst_ip = p["IP"].dst
            print("sip: %s" % src_ip)
            print("dip: %s" % dst_ip)
        if p.haslayer("TCP"):
            raw_d = p["TCP"].payload.original
            sport = p["TCP"].sport
            dport = p["TCP"].dport
            dport_dir = str(dport)
            if not os.path.exists("testcases/" + dirport):
                os.mkdir("testcases/" + dirport)
            print("sport: %s" % sport)
            print("dport: %s" % dport)
            print("raw_data:\n%s" % raw_d)
            num = str(s)
            out = open(dport_dir + "testcases/pcap.data_packet." + num + ".dat", "wb")
            out.write(raw_d)
            s = s + 1
if not os.path.exists("testcases"):
    os.mkdir("testcases")
parse_pcap(sys.argv[1])
os.system("find testcases/ -empty -type f -delete")
