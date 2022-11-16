#!/bin/bash
# Leaves a list of an entire repository's SUID binaries in deb_suid_root.txt.
PKG=$(apt-cache search . | cut -f 1 -d ' ');
for i in ${PKG[@]}; do
 apt-get download $i;
dpkg -c *.deb | cut -c 4- | grep ^s | cut -f 2 -d '.' | tee -a deb_suid_root.txt
rm *.deb
done
