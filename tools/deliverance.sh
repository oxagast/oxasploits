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
if [[ $# -gt 0 ]]; then
  echo "Fuzzing file descriptors of $pn";
  if [[ $(pgrep -x $pn | wc -l) -gt 0 ]]; then
    rm open_fd fd;
    while true;
    do
    for proc in $(ps aux | grep $pn | awk '//{print $2}');
    do
      find /proc/$proc/fd/ >> open_fd 2>/dev/null;
    done;
    for fd in $(cat open_fd | grep fd/[[:digit:]] | grep -v $$);
    do
      dd if=/dev/urandom bs=4 count=256 > junk.dat;
      cat junk.dat > $fd;
      if [[ $(pgrep -x $pn | wc -l) -lt 1 ]]; then rm open_fd fd; exit; fi;
    done;
  done;
  rm open_fd fd 2>/dev/null;
  else
    echo "The program specified needs to be running and have open file descriptors."
    exit 1;
  fi;
else
  echo "You need to supply a program name to fuzz.";
  exit 1
fi;
