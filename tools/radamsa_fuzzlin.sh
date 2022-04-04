#!/bin/bash
EXT="pdf"
I=0;
while true; do
  I=$(($I+1));
  sh -c 'sleep 3; pkill -1 evince' &
  radamsa dummy.$EXT > input.$EXT
  evince input.$EXT; C=$?
  echo $C;
  if [ $C -gt 130 ]; then
    cp input.$EXT crash$I.$EXT
    echo "Crash found!"
  fi
done

