# edit app path and testcase files to reflect what you're fuzzing
$apppath = "C:\Program Files\KMPlayer 64X\KMPlayer64.exe";
$testcase = "sample.mp4";


$ext = [System.IO.Path]::GetExtension($testcase)
$appname = Split-Path $apppath -leaf
if (!(Test-Path "f"))
{
  mkdir f;
}
:floop for (;;) {
  for ($i = 0; $i -le 9; $i++) {
    .\radamsa.exe sample$ext -o f\"$i$ext";
  }
  $files = Get-ChildItem ".\f\*$ext"
  foreach ($f in $files){
    & $apppath $f;
    $ret = $LastExitCode;
    $tf = $?;
    echo "$apppath $f - Exit was: $ret : $tf";
    if ($tf -ne "True") {
      echo "Crash detected ret $ret with file $f";
      $rand = Get-Random -Minimum 10000 -Maximum 99999;
      move $f $rand.crash.$f;
      break floop;
    }
    sleep 6;
    taskkill /im "$appname";
  }
}
