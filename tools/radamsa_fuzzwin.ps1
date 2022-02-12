mkdir f;
:floop for (;;) {
  for ($i = 0; $i -le 9; $i++) {
    .\radamsa.exe sample.mp4 -o f\"$i.mp4";
  }
  $files = Get-ChildItem "C:\fuzz\f\*.mp4"
  foreach ($f in $files){
    & 'C:\Program Files\VideoLAN\VLC\vlc.exe' $f;
    $ret = $LastExitCode;
    $tf = $?;
    echo "$f Exit was: $ret : $tf";
    if ($tf -ne "True") {
      break floop;
    }
    sleep 3;
    Stop-Process -name "vlc"
  }
}