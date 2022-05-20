# File descriptor fuzzer
# this will trash things around the system, do not run unless in a VM
while [ 42 ];
  do rm open_fd fd;
  for i in $(ps aux | awk '//{print $2}');
    do find /proc/$i/fd/ >> open_fd 2>/dev/null;
  done;
  for fd in $(cat open_fd | grep fd/[[:digit:]] | grep -v $$);
    do
    printf "\x00" > $fd;
    printf "%s%s%s%s%s" > $fd;
    dd if=/dev/urandom bs=4 count=256 > $fd;
  done;
done;
