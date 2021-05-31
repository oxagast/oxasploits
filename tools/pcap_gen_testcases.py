# oxagast
# use:
#   capture packets to ~/testcases/, you can save them here with wireshark.
#   mkdir testcases; cd testcases; python3 ../pcap_gen_testcases.py
# this will create a directory of each destination port filled with files each the data section
# of the packets in the pcap file.  One packet is one file.  TCP header info is stripped.

import os
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
            os.system("mkdir " + dport_dir)
            print("sport: %s" % sport)
            print("dport: %s" % dport)
            print("raw_http:\n%s" % raw_d)
            num = str(s)
            out = open(dport_dir + "/pcap.data_packet." + num + ".dat", "wb")
            out.write(raw_d)
            s = s + 1
parse_pcap("capture.pcapng")
os.system("find . -empty -type f -delete")
