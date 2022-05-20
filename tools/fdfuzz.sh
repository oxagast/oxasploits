while 1
do
rm open_fd fd
for i in $(ps aux | awk '//{print $2}')
do
find /proc/$i/fd/ >> open_fd 2>/dev/null
done;
for fd in $(cat open_fd | grep fd/[[:digit:]])
do
printf "hellofuzzed" > $fd
printf "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA" > $fd
printf "%s%s%s%s%s" > $fd
done;
done;
