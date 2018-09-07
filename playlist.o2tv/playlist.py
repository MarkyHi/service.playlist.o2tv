#!/usr/bin/env python
# -*- coding: utf-8 -*-

'''
Script pro generaci playlistu z OTA služby O2TV
***********************************************
Script je odvozen z Kodi addon service.playlist.o2tv,
který byl vytvořen z původního addon autora Štěpána Orta.
'''

import config as cfg
import os
import random
import stat
import time
import unicodedata
from uuid import getnode as get_mac

import urllib3
from o2tvgo import AuthenticationError
from o2tvgo import ChannelIsNotBroadcastingError
from o2tvgo import NoPurchasedServiceError
from o2tvgo import O2TVGO
from o2tvgo import TooManyDevicesError

_version_ = '0.0.3'
_date_ = '2018-05-29'

_streamer_code_ = '#! /bin/bash\n' + \
                  'source=$*\n' + \
                  'stream=$(grep -A 1 "${source}$" ' + cfg._playlist_path_ + cfg._playlist_src_ + ' | head -n 2 | tail -n 1)\n' + \
                  cfg._command_ffmpeg_ + ' -re -fflags +genpts -loglevel fatal -i ${stream} -probesize 32 -c copy -f mpegts -mpegts_service_type digital_tv pipe:1\n'

_pipe_ = 'pipe://'
_default_groupname_ = "O2TV"
_marhy_ = 'https://marhycz.github.io/picons/640/', 'https://marhycz.github.io/picons/1024/'
_log_file_ = cfg._playlist_path_ + 'playlist.log'
_log_limit_ = 100
_log_reduction_ = 50
_id_file_ = cfg._playlist_path_ + 'device_id'
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
    message = format('%s %s\n' % (time.strftime('%Y-%m-%d %H:%M:%S'), message))
    print(message)
    file.write(message)
    file.close()


def _toFile(content, name):
    _toLog("Saving file: " + name)
    file = open(name, 'w')
    file.write(content)
    file.close()


def _getId(name):
    try:
        id = ''
        file = open(name, 'r')
        lines = file.readlines()
    except IOError as ex:
        return id
    else:
        id = lines[0].rstrip()
        file.close()
        return id


def _deviceId():
    mac = get_mac()
    hexed = hex((mac * 7919) % (2 ** 64))
    return ('0000000000000000' + hexed[2:-1])[16:]


def _randomHex16():
    return ''.join([random.choice('0123456789abcdef') for x in range(16)])


_cutLog(_log_limit_, _log_reduction_)
_toLog("--------------------")
_toLog('O2TVKodi Playlist')
_toLog('Version: %s' % (_version_))
_toLog("--------------------")
_toLog("Starting...")
device_id = _getId(_id_file_)
if not (device_id or cfg._device_id_):
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
    if type(text).__name__ == 'unicode':
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
    if cfg._channel_logoname_ == 0:
        file = _logoName(channel) + '.png'
    elif cfg._channel_logoname_ == 1:
        file = _logoName(channel) + '.jpg'
    elif cfg._channel_logoname_ == 2:
        file = channel + '.png'
    elif cfg._channel_logoname_ == 3:
        file = channel + '.jpg'
    else:
        return ''
    return file


def _logoPathFile(channel):
    if cfg._channel_logo_ == 2:
        path_file = os.path.join(cfg._channel_logopath_ ,_logoFile(channel))
        if not os.path.isfile(path_file):
            path_file = ""
    elif cfg._channel_logo_ == 3:
        path_file = cfg._channel_logourl_ + _logoFile(channel)
    elif cfg._channel_logo_ == 4:
        path_file = _marhy_[cfg._channel_logogithub_] + _logoName(channel) + '.png'
    else:
        return ''
    return path_file


def _addParam(param, value, cond):
    item = ''
    if cond:
        item = ' %s="%s"' % (param, str(value))
    return item


def channelPlaylist():
    channels, code = _fetchChannels()
    if not channels:
        return code, -1, -1
    channels_sorted = sorted(channels.values(), key=lambda channel: channel.weight)
    if cfg._channel_group_ == 1:
        group = _default_groupname_
    else:
        group = cfg._channel_groupname_
    if cfg._myscript_ == 1:
        streamer = _pipe_ + cfg._playlist_path_ + cfg._myscript_name_
    else:
        streamer = _pipe_ + cfg._playlist_path_ + cfg._playlist_streamer_
    playlist_src = '#EXTM3U\n'
    playlist_dst = '#EXTM3U\n'
    num = 0
    err = 0
    for channel in channels_sorted:
        try:
            _toLog("Adding: " + channel.name)
            name = channel.name
            logo = _toString(channel.logo_url)
            url = _toString(channel.url())
            epgname = name
            epgid = name
            # číslo programu v epg
            # viz https://www.o2.cz/file_conver/174210/_025_J411544_Razeni_televiznich_programu_O2_TV_03_2018.pdf
            channel_weight = _toString(channel.weight)
            # logo v mistnim souboru - kdyz soubor neexistuje, tak pouzit url
            if (cfg._channel_logo_ > 1) and (_logoPathFile(name) != ""):
                logo = _logoPathFile(name)
            playlist_src += '#EXTINF:-1, %s\n%s\n' % (name, url)
            if cfg._playlist_type_ == 1:
                playlist_dst += '#EXTINF:-1'
                playlist_dst += _addParam('tvg-name', epgname, cfg._channel_epgname_ != 0)
                playlist_dst += _addParam('tvg-id', epgid, cfg._channel_epgid_ != 0)
                playlist_dst += _addParam('tvg-logo', logo, cfg._channel_logo_ != 0)
                playlist_dst += _addParam('tvg-chno', channel_weight, _channel_epgid_ != 0)
                playlist_dst += _addParam('group-titles', group, cfg._channel_group_ != 0)
                playlist_dst += ', %s\n%s\n' % (name, url)
            if (cfg._playlist_type_ == 2) or (cfg._playlist_type_ == 3):
                playlist_dst += '#EXTINF:-1'
                playlist_dst += _addParam('tvg-id', epgid, cfg._channel_epgid_ != 0)
                playlist_dst += _addParam('tvg-logo', logo, cfg._channel_logo_ != 0)
                playlist_dst += _addParam('tvg-chno', channel_weight, cfg._channel_epgid_ != 0)
                playlist_dst += _addParam('group-titles', group, cfg._channel_group_ != 0)
                playlist_dst += ', %s\n' % (name)
                if cfg._playlist_type_ == 2:
                    playlist_dst += '%s\n' % url
                if cfg._playlist_type_ == 3:
                    playlist_dst += '%s %s\n' % (streamer, name)
            num += 1
        except ChannelIsNotBroadcastingError:
            err += 1
            _toLog("... Not broadcasting. Skipped.")
        except AuthenticationError:
            return _authent_error_, 0, 0
        except TooManyDevicesError:
            return _toomany_error_, 0, 0
    _toFile(playlist_src, cfg._playlist_path_ + cfg._playlist_src_)
    _toFile(playlist_dst, cfg._playlist_path_ + cfg._playlist_dst_)
    return 'OK', num, err


if cfg._stream_quality_ == 1:
    _quality_ = 'STB'
else:
    _quality_ = 'TABLET'

_o2tvgo_ = O2TVGO(_device_id_, cfg._username_, cfg._password_, _quality_)

if cfg._playlist_type_ == 3:
    _toFile(_streamer_code_, cfg._playlist_path_ + cfg._playlist_streamer_ + '.sample')
    _tryExec(cfg._playlist_path_ + cfg._playlist_streamer_ + '.sample')
    _toFile(_streamer_code_, cfg._playlist_path_ + cfg._playlist_streamer_)
    _tryExec(cfg._playlist_path_ + cfg._playlist_streamer_)

code, num, err = channelPlaylist()

_toLog('Download done with result EXIT: %s , DOWNLOADED: %d, SKIPPED: %d' % (code, num, err))
_toLog('Finish')
