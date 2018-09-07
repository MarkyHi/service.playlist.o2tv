#!/usr/bin/env python
# -*- coding: utf-8 -*-

'''
Script pro generaci playlistu z OTA služby O2TV
***********************************************
Script je odvozen z Kodi addon service.playlist.o2tv,
který byl vytvořen z původního addon autora Štěpána Orta.
'''

import sys
import os
import urllib
import httplib
import json
import traceback
import random
import stat
import unicodedata
import time
import urllib3
from urlparse import urlparse
from uuid import getnode as get_mac
from o2tvgo import O2TVGO
from o2tvgo import AuthenticationError
from o2tvgo import TooManyDevicesError
from o2tvgo import ChannelIsNotBroadcastingError
from o2tvgo import NoPurchasedServiceError

_version_ = '0.0.3'
_date_ = '2018-05-29'

###########################################################################################################
# Základní parametry
###########################################################################################################
# Přihlašovací jméno a heslo:
_username_ = ''
_password_ = ''
# ID zařízení:
_device_id_ = ''
# Adresář pro vytvářené soubory a případného vlastního skriptu:
# Pozor! Je třeba zadat absolutní cestu!
_playlist_path_ = ''
# Jméno souboru stahovaného playlistu
_playlist_src_ = 'o2tv.generic.m3u8'
# Jméno souboru vytvářeného playlistu
_playlist_dst_ = 'o2tv.playlist.m3u8'
# Jméno souboru skriptu streameru
_playlist_streamer_ = 'streamer.sh'
# Povel pro spuštění ffmpeg
_command_ffmpeg_ = 'ffmpeg'
# Použití streameru
# 0 - bude použit vygenerovaný skript se jménem uloženým v _playlist_streamer_
# 1 - bude použit vlastní script se zadaným jménem. Skript musí být umístěn v cestě uložené v _playlist_path_!
_myscript_ = 0
# Jméno souboru vlastního skriptu streameru - jméno nesmí být shodné se jménem uloženým v _playlist_streamer_!
_myscript_name_ = 'myscript.sh'
# Kvalita streamu
# 0 - pro nižsí kvalitu, zpravidla (maximálně) 1280x720
# 1 - pro vyšší kvalitu, zpravidla 1920x1080
_stream_quality_ = 1
###########################################################################################################

###########################################################################################################
# Parametry vytvářeného playlistu
###########################################################################################################
# Typ playlistu
# 1 - pro IPTV Simple Client
# 2 - pro Tvheadend
# 3 - pro Tvheadend@
_playlist_type_ = 3
# Parametry v řádku EXTINF
# Parametr tvg_name - používá se pro Typ playlistu = 1
# 0 - nepoužije se
# 1 - přebírá se ze jména kanálu
_channel_epgname_ = 0
# Parametr tvg_id - používá se pro Typ playlistu = 1, 2, 3
# 0 - nepoužije se
# 1 - přebírá se ze jména kanálu
_channel_epgid_ = 0
# Parametr group-titles - používá se pro Typ playlistu = 1, 2, 3
# 0 - nepoužije se
# 1 - Použije se text: O2TV
# 2 - použije se text z proměnné _channel_groupname_
_channel_group_ = 0
_channel_groupname_ = ''
# Parametr tvg_logo - používá se pro Typ playlistu = 1, 2, 3
# Typ loga, případně cesta pro umístění souborů slogem
# 0 - nepoužije se
# 1 - přebírá se ze zdroje
# 2 - místní umístění, pro cestu se použije obsah proměnné _channel_logopath_
# 3 - internetové umístění, pro url se použije obsah proměnné _channel_logourl_
# 4 - logo od @marhycz na Github
_channel_logo_ = 0
_channel_logopath_ = ''
_channel_logourl_ = ''
# Konvence jména souboru - používá se pro Typ loga = 2 a 3
# 0 - nazevsouboru.png
# 1 - nazevsouboru.jpg
# 2 - Název souboru.png
# 3 - Název souboru.jpg
_channel_logoname_ = 0
# Kvalita @marhycz loga - používá se pro Typ loga = 4
# 0 - 640x640
# 1 - 1024x1024
_channel_logogithub_ = 0
###########################################################################################################

###########################################################################################################
# Samples of messages in playlist.log
###########################################################################################################
# RRRR-MM-DD HH:MM:SS Download done with result EXIT:AuthenticationError , DOWNLOADED:-1, SKIPPED:-1
# - přihlášení k účtu neproběhlo korektně, zkontrolujte _username_ a _password_
# - hodnoty -1 u stažených/přeskočených kanálů znamenají, že se stahování vůbec nespustilo
# RRRR-MM-DD HH:MM:SS Download done with result EXIT:NoPurchasedServiceError , DOWNLOADED:-1, SKIPPED:-1
# - seznam služeb vašeho účtu je prázdný
# - pravděpodobně nemáte zaplacenou vámi objednanou sližbu
# RRRR-MM-DD HH:MM:SS Download done with result EXIT:TooManyDevicesError , DOWNLOADED:-1, SKIPPED:-1
# - překročili jste limit 4 identifikovaných a registrovaných zařízení
# - upravte počet registrovaných zařízení na https://www.o2tv.cz/sprava-zarizeni/
# RRRR-MM-DD HH:MM:SS Download done with result EXIT:OK , DOWNLOADED:11, SKIPPED:0
# - generace playlist proběhla v pořádku
# - SKIPPED je počet kanálů, pro které v době stažení playlist nebyl k dispozici žádný stream
###########################################################################################################

_streamer_code_ = '#! /bin/bash\n' + \
    'source=$*\n' + \
    'stream=$(grep -A 1 "${source}$" ' + _playlist_path_ + _playlist_src_ + ' | head -n 2 | tail -n 1)\n' + \
    _command_ffmpeg_ + ' -re -fflags +genpts -loglevel fatal -i ${stream} -probesize 32 -c copy -f mpegts -mpegts_service_type digital_tv pipe:1\n'

_pipe_ = 'pipe://'
_default_groupname_ = "O2TV"
_marhy_ = 'https://marhycz.github.io/picons/640/', 'https://marhycz.github.io/picons/1024/'
_log_file_ = _playlist_path_ + 'playlist.log'
_log_limit_ = 100
_log_reduction_ = 50
_id_file_ = _playlist_path_ + 'device_id'
_authent_error_ = 'AuthenticationError'
_toomany_error_ = 'TooManyDevicesError'
_nopurch_error_ = 'NoPurchasedServiceError'

urllib3.disable_warnings()

def _cutLog(limit, reduction):
    try:
        file = open(_log_file_, 'r')
        lines = file.readlines()
        file.close()
    except IOError as ex:
        return
    else:
        lenght = len(lines)
        count = 0
        if lenght > limit:
            limit = lenght - limit + reduction + 1
            new_lines = ''
            for line in lines:
                count += 1
                if count < limit:
                    continue
                new_lines += line
            file = open(_log_file_, 'w')
            file.write(new_lines)
            file.close()
        return
        
def _toLog(message):
    file = open(_log_file_, 'a')
    file.write('%s %s\n' % (time.strftime('%Y-%m-%d %H:%M:%S'), message))
    file.close()

def _toFile(content, name):
    file = open(name, 'w')
    file.write(content)
    file.close()

def _getId(name):
    try:
        id = ''
        file = open(name,'r')
        lines = file.readlines()
    except IOError as ex:
        return id
    else:
        id = lines[0].rstrip()
        file.close()
        return id

def _deviceId():
    mac = get_mac()
    hexed = hex((mac*7919)%(2**64))
    return ('0000000000000000'+hexed[2:-1])[16:]

def _randomHex16():
    return ''.join([random.choice('0123456789abcdef') for x in range(16)])
    
_cutLog(_log_limit_, _log_reduction_)
_toLog('Start')
_toLog('Version: %s' % (_version_))

device_id = _getId(_id_file_)
if not (device_id or _device_id_):
    first_device_id = _deviceId()
    second_device_id = _deviceId()
    if first_device_id == second_device_id:
        _device_id_ = first_device_id
    else:
        _device_id_ = _randomHex16()
    _toLog('New Device Id: %s' % (_device_id_))
else:
    if device_id:
        _device_id_ = device_id  
_toFile(_device_id_, _id_file_)

def _tryFile(name):
    try:
        file = open(name, 'r')
    except IOError:
        return False
    else:
        file.close()
        return True

def _tryExec(name):
    file = name
    sts = os.stat(file)
    if not (sts.st_mode & stat.S_IEXEC):
        os.chmod(file, sts.st_mode | stat.S_IEXEC)

def _fetchChannels():
    global _o2tvgo_
    channels = None
    while not channels:
        try:
            channels = _o2tvgo_.live_channels()
        except AuthenticationError:
            return None, _authent_error_
        except TooManyDevicesError:
            return None, _toomany_error_
        except NoPurchasedServiceError:
            return None, _nopurch_error_
    return channels, 'OK'

def _toString(text):
    if type(text).__name__=='unicode':
        output = text.encode('utf-8')
    else:
        output = str(text)
    return output

def _logoName(channel):
    channel = unicode(channel, 'utf-8')
    channel = unicodedata.normalize('NFKD', channel)
    channel = channel.lower()
    name = ''
    for char in channel:
        if not unicodedata.combining(char) and (char.isalpha() or char.isdigit()):
            name += char
    return name

def _logoFile(channel):
    if _channel_logoname_ == 0:
        file = _logoName(channel) + '.png'
    elif _channel_logoname_ == 1:
        file = _logoName(channel) + '.jpg'
    elif _channel_logoname_ == 2:
        file = channel + '.png'
    elif _channel_logoname_ == 3:
        file = channel + '.jpg'
    else:
        return ''
    return file

def _logoPathFile(channel):
    if _channel_logo_ == 2:
        path_file = _channel_logopath_ + _logoFile(channel)
    elif _channel_logo_ == 3:
        path_file = _channel_logourl_ + _logoFile(channel)
    elif _channel_logo_ == 4:
        path_file = _marhy_[_channel_logogithub_] + _logoName(channel) + '.png'
    else:
        return ''
    return path_file

def _addParam (param, value, cond):
    item =''
    if cond:
        item = ' %s="%s"' % (param, str(value))
    return item

def channelPlaylist():
    channels, code = _fetchChannels()
    if not channels:
        return code, -1, -1
    channels_sorted = sorted(channels.values(), key=lambda channel: channel.weight)
    if _channel_group_ == 1:
        group = _default_groupname_
    else:
        group = _channel_groupname_
    if _myscript_ == 1:
        streamer = _pipe_ + _playlist_path_ + _myscript_name_
    else:
        streamer = _pipe_ + _playlist_path_ + _playlist_streamer_
    playlist_src = '#EXTM3U\n'
    playlist_dst = '#EXTM3U\n'
    num = 0
    err = 0
    for channel in channels_sorted:
        try:
            name = channel.name
            logo = _toString(channel.logo_url)
            url = _toString(channel.url())
            epgname = name
            epgid = name
            if _channel_logo_ > 1:
                logo = _logoPathFile(name)
            playlist_src += '#EXTINF:-1, %s\n%s\n' % (name, url)
            if _playlist_type_ == 1:
                playlist_dst += '#EXTINF:-1'
                playlist_dst += _addParam('tvg-name', epgname, _channel_epgname_ != 0)
                playlist_dst += _addParam('tvg-id', epgid, _channel_epgid_ != 0)
                playlist_dst += _addParam('tvg-logo', logo, _channel_logo_ != 0)
                playlist_dst += _addParam('group-titles', group, _channel_group_ != 0)
                playlist_dst += ', %s\n%s\n' % (name, url)
            if (_playlist_type_ == 2) or (_playlist_type_ == 3):
                playlist_dst += '#EXTINF:-1'
                playlist_dst += _addParam('tvg-id', epgid, _channel_epgid_ != 0)
                playlist_dst += _addParam('tvg-logo', logo, _channel_logo_ != 0)
                playlist_dst += _addParam('group-titles', group, _channel_group_ != 0)
                playlist_dst += ', %s\n' % (name)
                if _playlist_type_ == 2: playlist_dst += '%s\n' % (url)
                if _playlist_type_ == 3: playlist_dst += '%s %s\n' % (streamer, name)
            num += 1
        except ChannelIsNotBroadcastingError:
            err += 1
        except AuthenticationError:
            return _authent_error_, 0, 0
        except TooManyDevicesError:
            return _toomany_error_, 0, 0
    _toFile(playlist_src, _playlist_path_ + _playlist_src_)
    _toFile(playlist_dst, _playlist_path_ + _playlist_dst_)
    return 'OK', num, err

if _stream_quality_ == 1:
    _quality_ = 'STB'
else:
    _quality_ = 'TABLET'

_o2tvgo_ = O2TVGO(_device_id_, _username_, _password_, _quality_)

if _playlist_type_ == 3:
    _toFile(_streamer_code_, _playlist_path_ + _playlist_streamer_ + '.sample')
    _tryExec(_playlist_path_ + _playlist_streamer_ + '.sample')
    _toFile(_streamer_code_, _playlist_path_ + _playlist_streamer_)
    _tryExec(_playlist_path_ + _playlist_streamer_)

code, num, err = channelPlaylist()

_toLog('Download done with result EXIT:%s , DOWNLOADED:%d, SKIPPED:%d' % (code, num, err))
_toLog('Finish')
