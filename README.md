# oxasploits
## A number of exploits written by oxagast
Most of these CVEs are accreddited to oxagast as well<br>
Contact: <a href="malito:marshall@oxasploits.com">Marshall Whittaker</a>
<p align="center">
<img src="https://raw.githubusercontent.com/oxagast/oxasploits/JoshuaJohnWard/oxasploits.logo.nobg.png" alt="Logo">
</p>
# CVEs and PoC code

## CVE-2006-3392
### Webmin <=1.29 remote root exploit
This exploit, lifts a Webmin cookie with a directory transversal and
aritrary read exploit, then reuses the cookie to use an authenticated
user exploit to get root remotely.


## CVE-2010-2626
### Perl pipe upload and shell for Miyabi CGI Tools <=1.02 and iOffice 0.1
This exploit uploads a perl program via buggy perl open reads (|).  After
pushing the program it chmods and spawns a shell.  Should work
regaurdless if the server is firewalled or not.


## CVE-2016-10401
### PK5001Z router remote root exploit
Uses known telnet user and root pass to log in as root.


## CVE-2018-17336
### UDisks <=2.8.0 DoS
This is example code that crashes udisks2 via malformed filesystem label
that when mounted then logged a string format vulnerability exists allowing
arbitrary read/write of memory as root.


## CVE-2019-12881
### Linux Kernel 4.15.x i915 driver NULL pointer dereference
This code demonstrates crafted ioctl calls to the i915 garphics
driver that allow overwrite of CR2 register in kernel space triggering
a NULL pointer dereference.


## CVE-2019-15947
### Bitcoin Core bitcoin-qt wallet.dat recoverable from .core dump
This exploit recovers wallet.dat's that were loaded at the time of a crash 
from bitcoin-qt .core crash dump files by grepping for a magic string at 
the beginning of the wallet, calculating the offset, then reconstructing 
the wallet.dat(s) with xxd.

## CVE-2017-5816
### HP iMC dbman.exe PLAT 7.3 command injection exploit
Incorrect santization of input leads to a remote code execution vulnerabilty 
within dbman.exe of the HP iMC PLAT 7.3 suite.  Code execs with SYSTEM privileges.

## CVE-2021-3560
### Polkit and dbus race conditon LPE exploit
A race condition exists in polkit where if you send dbus messages, then
kill the process midway through, incorrect permissions are set on users that were
never intended to be able to be created, with system priviledges.  This leads to
local root compromise.

## RougeTooth
### Abusing Bluetooth HCI_EVT and HID control codes on a Samsung Galaxy S8
If you can get an unsuspecting user to connect to an attacking machine, by
maquorading it as a speaker (or whatever), you can inject HID codes and take
control over the device, to the extent where you can blindly pop a shell if
termux is installed, al-la rubber-ducky style.  Working PoC and video included.

## WoahIsRead
### OpenSSH 9.2 SSHd banner symbolic link LPE
OpenSSHd 9.2 and below do not properly check permissions and ownership on files
used as banners.  If the banner is set to a user writeable file, this allows an
attacker to remove the file, create a symbolic link to any root-only readable file
on the system (like /etc/shadow for example), and it will be dumped on next
connection to the sshd daemon.  Successful login to sshd is not required for this
to work.

______________________________________________________________________________

<code>
-----BEGIN PGP PUBLIC KEY BLOCK-----

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
=PxXt
-----END PGP PUBLIC KEY BLOCK-----
</code>

