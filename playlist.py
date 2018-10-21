#!/usr/bin/env python
# -*- coding: utf-8 -*-


# Script pro generaci playlistu z OTA služby O2TV
# ***********************************************
# Script je odvozen z Kodi addon service.playlist.o2tv,
# který byl vytvořen z původního addon autora Štěpána Orta.


import os
import stat
import time


import config as cfg
import urllib3
import common as c
from o2tvgo import AuthenticationError
from o2tvgo import ChannelIsNotBroadcastingError
from o2tvgo import NoPurchasedServiceError
from o2tvgo import O2TVGO
from o2tvgo import TooManyDevicesError

urllib3.disable_warnings()


def _cut_log(limit, reduction):
    if cfg.cut_log == 0: return
    try:
        f = open(c.log_file, 'r')
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
            f = open(c.log_file, 'w')
            f.write(new_lines)
            f.close()
        return


def _log(message):
    f = open(c.log_file, 'a')
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


_cut_log(cfg.log_limit, cfg.log_reduction)
_log("--------------------")
_log('O2TVKodi Playlist')
_log('Version: %s %s' % (c.version, c.date))
_log("--------------------")
_log("Starting...")
device_id = _get_id(c.id_file)
if not (device_id or cfg.device_id):
    first_device_id = c.device_id()
    second_device_id = c.device_id()
    if first_device_id == second_device_id:
        cfg.device_id = first_device_id
    else:
        _device_id_ = c.random_hex16()
    _log('New Device Id: %s' % cfg.device_id)
else:
    if device_id:
        cfg.device_id = device_id
_to_file(cfg.device_id, c.id_file)


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
            return None, c.authent_error
        except TooManyDevicesError:
            return None, c.toomany_error
        except NoPurchasedServiceError:
            return None, c.nopurch_error
    return channels, 'OK'

def _logo_file(channel):
    if cfg.channel_logo_name == 0:
        f = c.logo_name(channel) + '.png'
    elif cfg.channel_logo_name == 1:
        f = c.logo_name(channel) + '.jpg'
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
        path_file = c.marhy[cfg.channel_logo_github] + c.logo_name(channel) + '.png'
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
        group = c.default_group_name
    else:
        group = cfg.channel_group_name
    if cfg.my_script == 1:
        streamer = c.pipe + os.path.join(cfg.playlist_path, cfg.my_script_name)
    else:
        streamer = c.pipe + os.path.join(cfg.playlist_path, cfg.playlist_streamer)
    playlist_src = '#EXTM3U\n'
    playlist_dst = '#EXTM3U\n'
    _num = 0
    _err = 0
    for channel in channels_sorted:
        try:
            _log("Adding: " + channel.name)
            name = channel.name
            logo = c.to_string(channel.logo_url)
            url = c.to_string(channel.url())
            epgname = name
            epgid = name
            # číslo programu v epg
            # viz https://www.o2.cz/file_conver/174210/_025_J411544_Razeni_televiznich_programu_O2_TV_03_2018.pdf
            channel_weight = c.to_string(channel.weight)
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
            return c.authent_error, 0, 0
        except TooManyDevicesError:
            return c.toomany_error, 0, 0
    _to_file(playlist_src, os.path.join(cfg.playlist_path, cfg.playlist_src))
    _to_file(playlist_dst, os.path.join(cfg.playlist_path, cfg.playlist_dst))
    return 'OK', _num, _err


if cfg.stream_quality == 1:
    _quality_ = 'STB'
else:
    _quality_ = 'TABLET'

_o2tvgo_ = O2TVGO(cfg.device_id, cfg.username, cfg.password, _quality_)
_o2tvgo_.log_function = _log;

if cfg.playlist_type == 3:
    _to_file(c.streamer_code, os.path.join(cfg.playlist_path, cfg.playlist_streamer + '.sample'))
    _try_exec(os.path.join(cfg.playlist_path, cfg.playlist_streamer + '.sample'))
    _to_file(c.streamer_code, os.path.join(cfg.playlist_path, cfg.playlist_streamer))
    _try_exec(os.path.join(cfg.playlist_path, cfg.playlist_streamer))

code, num, err = channel_playlist()

_log('Download done with result EXIT: %s , DOWNLOADED: %d, SKIPPED: %d' % (code, num, err))
_log('Finish')
