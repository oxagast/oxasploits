#!/usr/bin/bash
# Marshall Whittaker / oxagast
# A small file descriptor fuzzer.
# IMPORTANT: This will trash things around the system, do not run unless it's contained in a VM.
#
# Deliverance
# noun
#  1. the action of being rescued or set free.
#
# Useage: ./deliverance.sh firefox
# Note: Some processes will spin off other processes, for example with skype, you need to use
# skypeforlinux as the program name to fuzz, as that is how it shows up in ps/pgrep.

pn=$1;

fuzz () {
  rm open_fd fd;
  while true;
  do
    for proc in $(ps aux | grep $pn | awk '//{print $2}');
    do
      find /proc/$proc/fd/ >> open_fd 2>/dev/null;
    done;
    pid=$(pgrep $pn);
    for fd in $(cat open_fd | grep fd/[[:digit:]] | grep -v $$);
    do
      dd if=/dev/urandom bs=$blksize count=1 > junk.dat 2>/dev/null;
      cp junk.dat junk.`date +%s`.dat
      cat junk.dat > $fd;
      find -type f  -type f -name "*.dat" -mmin +2 -exec rm {} +
      if [[ $(pgrep -x $pn | wc -l) -lt 1 ]]; then
        rm open_fd fd;
        echo "Code: $pn";
        echo "PID List:"
        echo "$pid";
        echo "Last used payload size: $blksize bytes";
        echo "Fuzz data:";
        hexdump -C junk.dat;
        exit;
      fi;
    done;
  done;
  rm open_fd fd 2>/dev/null;
}


if [[ $# -gt 0 ]]; then
if [[ $# -eq 2 ]]; then 
blksize=$2;
else blksize=256;
fi;
  if [[ $(pgrep -x $pn | wc -l) -gt 0 ]]; then
    echo "Fuzzing file descriptors of $pn";
    fuzz
  else
    echo "The program specified needs to be running and have open file descriptors."
    exit 1;
  fi;
else
  echo "You need to supply a program name to fuzz.";
  exit 1
fi;
