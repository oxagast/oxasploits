import os
import scapy_http.http
try:
    import scapy.all as scapy
except ImportError:
    import scapy
def parse_http_pcap(pcap_path):
    s = 0
    pcap_infos = list()
    packets = scapy.rdpcap(pcap_path)
    for p in packets:
        print("----")
        # To determine whether a layer is included, use haslayer
        if p.haslayer("IP"):
            src_ip = p["IP"].src
            dst_ip = p["IP"].dst
            print("sip: %s" % src_ip)
            print("dip: %s" % dst_ip)
        if p.haslayer("TCP"):
            # Get the original load of a layer. Payload.original
            raw_d = p["TCP"].payload.original
            sport = p["TCP"].sport
            dport = p["TCP"].dport
            dport_dir = str(dport)
            os.system("mkdir " + dport_dir)
            print("sport: %s" % sport)
            print("dport: %s" % dport)
            print("raw_http:\n%s" % raw_d)
            num = str(s)
            out = open(dport_dir + "/out." + num + ".txt", "wb")
            out.write(raw_d)
            s = s + 1

parse_http_pcap("/home/marshall/capture.pcapng")
