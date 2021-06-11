mkdir f;
:floop for (;;) {
  for ($i = 0; $i -le 9; $i++) {
    .\radamsa.exe test.jpeg -o f\"$i.jpeg";
  }
  $files = Get-ChildItem "C:\fuzz\f\*.jpeg"
  foreach ($f in $files){
    mspaint $f;
    $ret = $LastExitCode;
    echo "$f Exit was: $ret : $?";
    if ($ret -ne 0) {
      break floop;
    }
    sleep 1;
    Stop-Process -name "mspaint"
  }
}