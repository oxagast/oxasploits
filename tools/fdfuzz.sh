#!/usr/bin/bash
# Marshall Whittaker / oxagast
# A small file descriptor fuzzer.
# IMPORTANTL: This will trash things around the system, do not run unless it's contained in a VM.

pn=$1
echo $pn;
rm open_fd fd;
while true;
  do
  for proc in $(ps aux | grep $pn | awk '//{print $2}');
    do find /proc/$proc/fd/ >> open_fd 2>/dev/null;
  done;
  for fd in $(cat open_fd | grep fd/[[:digit:]] | grep -v $$);
    do
    printf "%s%s%s%s%s" > $fd;
    dd if=/dev/urandom bs=4 count=256 > $fd;
    if [[ $(pgrep -x $pn | wc -l) -lt 1 ]]; then rm open_fd fd; exit; fi;
  done;
done;
rm open_fd fd 2>/dev/null;
