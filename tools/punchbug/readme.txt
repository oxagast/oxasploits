# Persistent reverse shell.

Hides taskserv.exe in C:\Winodws\Tasks, spawns a connect-back shell every 15 seconds
and installs a registry key to start at boot.  Another artibrary program can be bundled
with the shell to to make the backdoor functional, and less detectable by a user.  While
notepad++ is used as an exmaple, any Windows binary should work really.

Don't get caught using this.
