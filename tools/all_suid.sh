PKG=$(apt-cache search . | cut -f 1 -d ' ');
echo $PKG | xargs apt-get download;
DEB=(`find *.deb`);
for i in ${DEB[@]};
do dpkg -c $i | cut -c 4- | grep ^s | cut -f 2 -d '.' ; done | tee deb_suid_root.txt
