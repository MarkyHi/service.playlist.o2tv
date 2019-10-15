@echo off
set zip="c:\program files\7-zip\7z.exe"
if exist service.playlist.o2tv.zip del service.playlist.o2tv.zip
%zip% a service.playlist.o2tv.zip ..\service.playlist.o2tv -r -x!repository.pavucina.info.bin -x!_sonar.cmd -x!__pycache__ -x!*.pyc -x!.idea -x!.git -x!device_id -x!playlist.log -x!o2tv.generic.m3u8 -x!o2tv.playlist.m3u8 -x!streamer.sh*
%zip% d service.playlist.o2tv.zip service.playlist.o2tv\config.ini
%zip% rn service.playlist.o2tv.zip service.playlist.o2tv\config.ini.sample service.playlist.o2tv\config.ini
