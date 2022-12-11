pyinstaller.exe --windowed --noconsole --onefile --uac-admin .\taskserv.py
copy dist\taskserv.exe .\taskserv.exe
pyinstaller.exe --add-binary="taskserv.exe;." --add-binary="nppi.exe;." --icon=npp_103.ico --windowed --noconsole --onefile --uac-admin .\loader.py
