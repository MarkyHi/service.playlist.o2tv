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

import codecs
from builtins import open
from future import standard_library
import os
import time
import platform
import urllib3
import common as c
try:
    from configparser import ConfigParser as SafeConfigParser
except ImportError:
    from ConfigParser import SafeConfigParser  # ver. < 3.0
from datetime import datetime
from o2tvgo import AuthenticationError
from o2tvgo import ChannelIsNotBroadcastingError
from o2tvgo import NoPurchasedServiceError
from o2tvgo import NoPlaylistUrlsError
from o2tvgo import O2TVGO
from o2tvgo import TooManyDevicesError
from o2tvgo import NoChannelsError
standard_library.install_aliases()
urllib3.disable_warnings()

config = SafeConfigParser()

def _cut_log(limit, reduction):
    global config
    if config.getint('Common', 'cut_log') == 0:
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
    global config
    path = os.path.dirname(os.path.abspath(__file__))
    if c.is_null_or_whitespace(config.get('Playlist', 'playlist_path')):
        config.set('Playlist', 'playlist_path', path)
    if config.get('Login', 'username') == '' or config.get('Login', 'password') == '':
        return False
    return True


def set_default_config():
    global config
    config.add_section('Login')
    config.set('Login', 'username', '')
    config.set('Login', 'password', '')
    config.set('Login', 'device_id', '')
    config.set('Login', 'access_token', '')
    config.set('Login', 'refresh_token', '')
    config.set('Login', 'token_expire_date','')
    config.add_section('Common')
    config.set('Common', 'playlist_streamer', 'streamer.sh')
    config.set('Common', 'ffmpeg_command', 'ffmpeg')
    config.set('Common', 'my_script', '0')
    config.set('Common', 'my_script_name', 'myscript.sh')
    config.set('Common', 'stream_quality', '1')
    config.set('Common', 'cut_log', '1')
    config.set('Common', 'log_limit', '100')
    config.set('Common', 'log_reduction', '50')
    config.add_section('Playlist')
    config.set('Playlist', 'playlist_path', '')
    config.set('Playlist', 'playlist_src', 'o2tv.generic.m3u8')
    config.set('Playlist', 'playlist_dst', 'o2tv.playlist.m3u8')
    config.set('Playlist', 'cache_playlists', 'False')
    config.set('Playlist', 'playlist_type', '3')
    config.set('Playlist', 'channel_epg_name', '1')
    config.set('Playlist', 'channel_epg_id', '1')
    config.set('Playlist', 'channel_group', '1')
    config.set('Playlist', 'channel_group_name', 'O2TV')
    config.set('Playlist', 'channel_logo', '1')
    config.set('Playlist', 'channel_logo_path', '')
    config.set('Playlist', 'channel_logo_url', '')
    config.set('Playlist', 'channel_logo_name', '0')
    config.set('Playlist', 'channel_logo_github', '0')


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
    global config
    if config.getint('Playlist', 'channel_logo_name') == 0:
        f = c.logo_name(channel) + '.png'
    elif config.getint('Playlist', 'channel_logo_name') == 1:
        f = c.logo_name(channel) + '.jpg'
    elif config.getint('Playlist', 'channel_logo_name') == 2:
        f = channel + '.png'
    elif config.getint('Playlist', 'channel_logo_name') == 3:
        f = channel + '.jpg'
    else:
        return ''
    return f


def _logo_path_file(channel):
    global config
    if config.getint('Playlist', 'channel_logo') == 2:
        path_file = os.path.join(config.get('Playlist', 'channel_logo_path'), _logo_file(channel))
        if not os.path.isfile(path_file):
            path_file = ""
    elif config.getint('Playlist', 'channel_logo') == 3:
        path_file = config['Playlist']['channel_logo_url'] + _logo_file(channel)
    elif config.getint('Playlist', 'channel_logo') == 4:
        path_file = c.marhy[config.getint('Playlist', 'channel_logo_github')] + c.logo_name(channel) + '.png'
    else:
        return ''
    return path_file


def channel_playlist():
    global config
    channels, _code = _fetch_channels()
    if not channels:
        return _code, -1, -1, -1
    channels_sorted = sorted(list(channels.values()), key=lambda _channel: _channel.weight)
    if config.getint('Playlist', 'channel_group') == 1:
        group = c.default_group_name
    else:
        group = config.get('Playlist', 'channel_group_name')
    if config.getboolean('Common', 'my_script'):
        streamer = c.pipe + os.path.join(config.get('Playlist', 'playlist_path'), config.get('Common', 'my_script_name'))
    else:
        streamer = c.pipe + os.path.join(config.get('Playlist', 'playlist_path'), config.get('Common','playlist_streamer'))
    playlist_src = '#EXTM3U\n'
    playlist_dst = '#EXTM3U\n'
    _num = 0
    _err = 0
    _cached = 0
    if len(channels_sorted) == 0:
        _log("Failed to download channels!")
        return c.nochannels_error, 0, 0, 0
    for channel in channels_sorted:
        try:
            _log("Adding: %s..." % channel.name)
            playlist_src += '#EXTINF:-1, %s\n%s\n' % (channel.name, channel.url())
            playlist_dst += c.build_channel_lines(channel, config.getint('Playlist','channel_logo'),
                                                  _logo_path_file(channel.name), streamer, group,
                                                  config.get('Playlist', 'playlist_type'),
                                                  config.getint('Playlist', 'channel_epg_name'),
                                                  config.getint('Playlist', 'channel_epg_id'),
                                                  config.getint('Playlist', 'channel_group'))
            if config.getboolean('Playlist', 'cache_playlists'):
                if c.cache_playlist(channel.url(), config.get('Playlist', 'playlist_path'), _log):
                    _cached += 1
            _num += 1
        except ChannelIsNotBroadcastingError:
            _err += 1
            _log("... Not broadcasting. Skipped.")
        except AuthenticationError:
            return c.authent_error, 0, 0, 0
        except TooManyDevicesError:
            return c.toomany_error, 0, 0, 0
        except NoPlaylistUrlsError:
            _log("... No playlist URL provided. Skipped.")
            _err += 1
    c.write_file(playlist_src, os.path.join(config.get('Playlist', 'playlist_path'),
                                            config.get('Playlist', 'playlist_src')), _log)
    c.write_file(playlist_dst, os.path.join(config.get('Playlist', 'playlist_path'),
                                            config.get('Playlist', 'playlist_dst')), _log)
    return 'OK', _num, _err, _cached


_log("--------------------")
_log('O2TVKodi Playlist')
_log('Version: %s %s' % (c.version, c.date))
_log('Python: %s' % platform.python_version())
_log("--------------------")
_log("Starting...")

set_default_config()
with codecs.open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.ini'), 'r', encoding='utf-8') as f:
    config.read_file(f)

if not check_config():
    _log('Invalid username or password.')
    _log('Please check config.ini')
    exit()
_log('Config OK')
_cut_log(config.getint('Common', 'log_limit'), config.getint('Common', 'log_reduction'))

# device_id = _get_id(c.id_file)
device_id = config.get('Login', 'device_id')
if not (device_id or config.get('Login', 'device_id')):
    first_device_id = c.device_id()
    second_device_id = c.device_id()
    if first_device_id == second_device_id:
        config.set('Login', 'device_id', first_device_id)
    else:
        _device_id_ = c.random_hex16()
    _log('New Device Id: %s' % config.get('Login', 'device_id'))
else:
    if device_id:
        config.set('Login', 'device_id', device_id)

if config.getint('Common', 'stream_quality') == 1:
    _quality_ = 'STB'
else:
    _quality_ = 'TABLET'

_o2tvgo_ = O2TVGO(config.get('Login', 'device_id'), config.get('Login', 'username'),
                  config.get('Login', 'password'), _quality_, _log)
_o2tvgo_.access_token = config.get('Login', 'access_token')
_o2tvgo_.expires_in = config.get('Login','token_expire_date')
_o2tvgo_.app_id = 'O2TVKodi Playlist'

if config.getint('Playlist', 'playlist_type') == 3:
    c.write_streamer(os.path.join(config.get('Playlist', 'playlist_path'), config.get('Common', 'playlist_streamer')),
                     os.path.join(config.get('Playlist', 'playlist_path'), config.get('Playlist', 'playlist_src')),
                     config.get('Common', 'ffmpeg_command'), _log)

code, num, err, cached = channel_playlist()
_log('Download done with result EXIT: %s , DOWNLOADED: %d, SKIPPED: %d, CACHED: %d' % (code, num, err, cached))
_log('Updating config...')
config.set('Login', 'access_token', _o2tvgo_.access_token)
config.set('Login', 'token_expire_date', str(_o2tvgo_.expires_in))
with codecs.open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.ini'), 'wb+', encoding='utf-8')\
        as configfile:
    config.write(configfile)
_log('Finished')
