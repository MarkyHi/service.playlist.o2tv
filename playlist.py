#!/usr/bin/env python
# -*- coding: utf-8 -*-


# Script pro generaci playlistu z OTA služby O2TV
# ***********************************************
# Script je odvozen z Kodi addon service.playlist.o2tv,
# který byl vytvořen z původního addon autora Štěpána Orta.


from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division
from __future__ import absolute_import
from builtins import open
from future import standard_library
import os
import time
import platform
import urllib3
import common as c
import config as cfg
from o2tvgo import AuthenticationError
from o2tvgo import ChannelIsNotBroadcastingError
from o2tvgo import NoPurchasedServiceError
from o2tvgo import NoPlaylistUrlsError
from o2tvgo import O2TVGO
from o2tvgo import TooManyDevicesError
from o2tvgo import NoChannelsError
standard_library.install_aliases()
urllib3.disable_warnings()


def _cut_log(limit, reduction):
    if cfg.cut_log == 0:
        return
    try:
        f = open(c.log_file, 'r', encoding="utf-8")
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
            f = open(c.log_file, 'w', encoding="utf-8")
            f.write(new_lines)
            f.close()
        return


def _log(message):
    f = open(c.log_file, 'a', encoding="utf-8")
    message = format('%s %s' % (time.strftime('%Y-%m-%d %H:%M:%S'), message))
    print(message)
    f.write(message + "\n")
    f.close()


def _get_id(name):
    _id = ''
    try:
        f = open(name, 'r', encoding="utf-8")
        lines = f.readlines()
    except IOError:
        return _id
    else:
        _id = lines[0].rstrip()
        f.close()
        return _id


def check_config():
    path = os.getcwd()
    if "getcwdu" in dir(os):
        path = os.getcwdu()  # pouzit unicode verzi jestli ji mame
    if c.is_null_or_whitespace(cfg.playlist_path):
        cfg.playlist_path = path
    if cfg.username == '' or cfg.password == '':
        return False
    return True


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
        except NoChannelsError:
            return None, c.nochannels_error
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


def channel_playlist():
    channels, _code = _fetch_channels()
    if not channels:
        return _code, -1, -1
    channels_sorted = sorted(list(channels.values()), key=lambda _channel: _channel.weight)
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
    if len(channels_sorted) == 0:
        _log("Failed to download channels!")
        return c.nochannels_error, 0, 0
    for channel in channels_sorted:
        try:
            _log("Adding: %s..." % channel.name)
            playlist_src += '#EXTINF:-1, %s\n%s\n' % (channel.name, channel.url())
            playlist_dst += c.build_channel_lines(channel, cfg.channel_logo, _logo_path_file(channel.name), streamer,
                                                  group, cfg.playlist_type, cfg.channel_epg_name, cfg.channel_epg_id,
                                                  cfg.channel_group)
            _num += 1
        except ChannelIsNotBroadcastingError:
            _err += 1
            _log("... Not broadcasting. Skipped.")
        except AuthenticationError:
            return c.authent_error, 0, 0
        except TooManyDevicesError:
            return c.toomany_error, 0, 0
        except NoPlaylistUrlsError:
            _log("... No playlist URL provided. Skipped.")
            _err += 1
    c.write_file(playlist_src, os.path.join(cfg.playlist_path, cfg.playlist_src), _log)
    c.write_file(playlist_dst, os.path.join(cfg.playlist_path, cfg.playlist_dst), _log)
    return 'OK', _num, _err


_cut_log(cfg.log_limit, cfg.log_reduction)
_log("--------------------")
_log('O2TVKodi Playlist')
_log('Version: %s %s' % (c.version, c.date))
_log('Python: %s' % platform.python_version())
_log("--------------------")
_log("Starting...")

if not check_config():
    _log('Invalid username or password.')
    _log('Please check config.py')
    exit()
_log('Config OK')
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
c.write_file(cfg.device_id, c.id_file, _log)

if cfg.stream_quality == 1:
    _quality_ = 'STB'
else:
    _quality_ = 'TABLET'

_o2tvgo_ = O2TVGO(cfg.device_id, cfg.username, cfg.password, _quality_, _log)

if cfg.playlist_type == 3:
    c.write_streamer(os.path.join(cfg.playlist_path, cfg.playlist_streamer),
                     os.path.join(cfg.playlist_path, cfg.playlist_src),
                     cfg.ffmpeg_command, _log)

code, num, err = channel_playlist()

_log('Download done with result EXIT: %s , DOWNLOADED: %d, SKIPPED: %d' % (code, num, err))
_log('Finished')
