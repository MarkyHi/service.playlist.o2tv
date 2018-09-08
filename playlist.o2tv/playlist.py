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

_version_ = '0.0.4'
_date_ = '2018-09-09'

_streamer_code_ = '#! /bin/bash\n' + \
                  'source=$*\n' + \
                  'tempplaylist=$(mktemp -u)".m3u8"\n' + \
                  'stream=$(grep -A 1 "${source}$" ' + os.path.join(cfg.playlist_path, cfg.playlist_src) + \
                  ' | head -n 2 | tail -n 1)\n' + \
                  'wget -qO ${tempplaylist} ${stream}\n' + \
                  'streamcount=$(cat ${tempplaylist} | grep -Eo "(http|https)://[\da-z./?A-Z0-9\D=_-]*" | wc -l)\n' + \
                  'streamcount=$((streamcount-1))\n' + \
                  'if  [ "$streamcount" = "-1" ]; then streamcount=0; fi\n' + \
                  cfg.ffmpeg_command + ' -protocol_whitelist file,http,https,tcp,tls -fflags +genpts ' + \
                  '-loglevel fatal -i ${tempplaylist} -probesize 32 -reconnect_at_eof 1 -reconnect_streamed 1 ' + \
                  '-c copy -map p:${streamcount}? -f mpegts -tune zerolatency -bsf:v h264_mp4toannexb,dump_extra ' + \
                  '-mpegts_service_type digital_tv pipe:1\n'

_pipe_ = 'pipe://'
_default_groupname_ = "O2TV"
_marhy_ = 'https://marhycz.github.io/picons/640/', 'https://marhycz.github.io/picons/1024/'
_log_file_ = cfg.playlist_path + 'playlist.log'
_log_limit_ = 100
_log_reduction_ = 50
_id_file_ = cfg.playlist_path + 'device_id'
_authent_error_ = 'AuthenticationError'
_toomany_error_ = 'TooManyDevicesError'
_nopurch_error_ = 'NoPurchasedServiceError'

urllib3.disable_warnings()


def _cut_log(limit, reduction):
    try:
        f = open(_log_file_, 'r')
        lines = f.readlines()
        f.close()
    except IOError:
        return
    else:
        length = len(lines)
        count = 0
        if length > limit:
            limit = length - limit + reduction + 1
            new_lines = ''
            for line in lines:
                count += 1
                if count < limit:
                    continue
                new_lines += line
            f = open(_log_file_, 'w')
            f.write(new_lines)
            f.close()
        return


def _log(message):
    f = open(_log_file_, 'a')
    message = format('%s %s' % (time.strftime('%Y-%m-%d %H:%M:%S'), message))
    print(message)
    f.write(message + "\n")
    f.close()


def _to_file(content, name):
    _log("Saving file: " + name)
    f = open(name, 'w')
    f.write(content)
    f.close()


def _get_id(name):
    _id = ''
    try:
        f = open(name, 'r')
        lines = f.readlines()
    except IOError:
        return _id
    else:
        _id = lines[0].rstrip()
        f.close()
        return _id


def _device_id():
    mac = get_mac()
    hexed = hex((mac * 7919) % (2 ** 64))
    return ('0000000000000000' + hexed[2:-1])[16:]


def _random_hex16():
    return ''.join([random.choice('0123456789abcdef') for x in range(16)])


_cut_log(_log_limit_, _log_reduction_)
_log("--------------------")
_log('O2TVKodi Playlist')
_log('Version: %s' % _version_)
_log("--------------------")
_log("Starting...")
device_id = _get_id(_id_file_)
if not (device_id or cfg.device_id):
    first_device_id = _device_id()
    second_device_id = _device_id()
    if first_device_id == second_device_id:
        cfg.device_id = first_device_id
    else:
        _device_id_ = _random_hex16()
    _log('New Device Id: %s' % cfg.device_id)
else:
    if device_id:
        cfg.device_id = device_id
_to_file(cfg.device_id, _id_file_)


def _try_exec(name):
    f = name
    sts = os.stat(f)
    if not (sts.st_mode & stat.S_IEXEC):
        os.chmod(f, sts.st_mode | stat.S_IEXEC)


def _fetch_channels():
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


def _to_string(text):
    if type(text).__name__ == 'unicode':
        output = text.encode('utf-8')
    else:
        output = str(text)
    return output


def _logo_name(channel):
    channel = unicode(channel, 'utf-8')
    channel = unicodedata.normalize('NFKD', channel)
    channel = channel.lower()
    name = ''
    for char in channel:
        if not unicodedata.combining(char) and (char.isalpha() or char.isdigit()):
            name += char
    return name


def _logo_file(channel):
    if cfg.channel_logo_name == 0:
        f = _logo_name(channel) + '.png'
    elif cfg.channel_logo_name == 1:
        f = _logo_name(channel) + '.jpg'
    elif cfg.channel_logo_name == 2:
        f = channel + '.png'
    elif cfg.channel_logo_name == 3:
        f = channel + '.jpg'
    else:
        return ''
    return f


def _logo_path_file(channel):
    if cfg.channel_logo == 2:
        path_file = os.path.join(cfg.channel_logo_path, _logo_file(channel))
        if not os.path.isfile(path_file):
            path_file = ""
    elif cfg.channel_logo == 3:
        path_file = cfg.channel_logo_url + _logo_file(channel)
    elif cfg.channel_logo == 4:
        path_file = _marhy_[cfg.channel_logo_github] + _logo_name(channel) + '.png'
    else:
        return ''
    return path_file


def _add_param(param, value, cond):
    item = ''
    if cond:
        item = ' %s="%s"' % (param, str(value))
    return item


def channel_playlist():
    channels, _code = _fetch_channels()
    if not channels:
        return _code, -1, -1
    channels_sorted = sorted(channels.values(), key=lambda _channel: _channel.weight)
    if cfg.channel_group == 1:
        group = _default_groupname_
    else:
        group = cfg.channel_group_name
    if cfg.my_script == 1:
        streamer = _pipe_ + cfg.playlist_path + cfg.my_script_name
    else:
        streamer = _pipe_ + cfg.playlist_path + cfg.playlist_streamer
    playlist_src = '#EXTM3U\n'
    playlist_dst = '#EXTM3U\n'
    _num = 0
    _err = 0
    for channel in channels_sorted:
        try:
            _log("Adding: " + channel.name)
            name = channel.name
            logo = _to_string(channel.logo_url)
            url = _to_string(channel.url())
            epgname = name
            epgid = name
            # číslo programu v epg
            # viz https://www.o2.cz/file_conver/174210/_025_J411544_Razeni_televiznich_programu_O2_TV_03_2018.pdf
            channel_weight = _to_string(channel.weight)
            # logo v mistnim souboru - kdyz soubor neexistuje, tak pouzit url
            if (cfg.channel_logo > 1) and (_logo_path_file(name) != ""):
                logo = _logo_path_file(name)
            playlist_src += '#EXTINF:-1, %s\n%s\n' % (name, url)
            if cfg.playlist_type == 1:
                playlist_dst += '#EXTINF:-1'
                playlist_dst += _add_param('tvg-name', epgname, cfg.channel_epg_name != 0)
                playlist_dst += _add_param('tvg-id', epgid, cfg.channel_epg_id != 0)
                playlist_dst += _add_param('tvg-logo', logo, cfg.channel_logo != 0)
                playlist_dst += _add_param('tvg-chno', channel_weight, cfg.channel_epg_id != 0)
                playlist_dst += _add_param('group-titles', group, cfg.channel_group != 0)
                playlist_dst += ', %s\n%s\n' % (name, url)
            if (cfg.playlist_type == 2) or (cfg.playlist_type == 3):
                playlist_dst += '#EXTINF:-1'
                playlist_dst += _add_param('tvg-id', epgid, cfg.channel_epg_id != 0)
                playlist_dst += _add_param('tvg-logo', logo, cfg.channel_logo != 0)
                playlist_dst += _add_param('tvg-chno', channel_weight, cfg.channel_epg_id != 0)
                playlist_dst += _add_param('group-titles', group, cfg.channel_group != 0)
                playlist_dst += ', %s\n' % name
                if cfg.playlist_type == 2:
                    playlist_dst += '%s\n' % url
                if cfg.playlist_type == 3:
                    playlist_dst += '%s %s\n' % (streamer, name)
            _num += 1
        except ChannelIsNotBroadcastingError:
            _err += 1
            _log("... Not broadcasting. Skipped.")
        except AuthenticationError:
            return _authent_error_, 0, 0
        except TooManyDevicesError:
            return _toomany_error_, 0, 0
    _to_file(playlist_src, cfg.playlist_path + cfg.playlist_src)
    _to_file(playlist_dst, cfg.playlist_path + cfg.playlist_dst)
    return 'OK', _num, _err


if cfg.stream_quality == 1:
    _quality_ = 'STB'
else:
    _quality_ = 'TABLET'

_o2tvgo_ = O2TVGO(cfg.device_id, cfg.username, cfg.password, _quality_)

if cfg.playlist_type == 3:
    _to_file(_streamer_code_, cfg.playlist_path + cfg.playlist_streamer + '.sample')
    _try_exec(cfg.playlist_path + cfg.playlist_streamer + '.sample')
    _to_file(_streamer_code_, cfg.playlist_path + cfg.playlist_streamer)
    _try_exec(cfg.playlist_path + cfg.playlist_streamer)

code, num, err = channel_playlist()

_log('Download done with result EXIT: %s , DOWNLOADED: %d, SKIPPED: %d' % (code, num, err))
_log('Finish')
