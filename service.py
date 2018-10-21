# -*- coding: utf-8 -*-

'''
*********************************************************
Script pro generaci playlistu z OTA služby O2TV
*********************************************************
Script je odvozen z Kodi addon service.playlist.o2tv,
který byl vytvořen z původního addon autora Štěpána Orta.
*********************************************************
'''

import sys
import os
import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon
import urllib
import httplib
from urlparse import urlparse
import json
import traceback
import random
from uuid import getnode as get_mac
from o2tvgo import O2TVGO
from o2tvgo import AuthenticationError
from o2tvgo import TooManyDevicesError
from o2tvgo import ChannelIsNotBroadcastingError
from o2tvgo import NoPurchasedServiceError
import xbmcvfs
import time
import _strptime
import string
import unicodedata
import stat
import urllib3

params = False

if __name__ == '__main__':
    monitor = xbmc.Monitor()

    _addon_ = xbmcaddon.Addon('service.playlist.o2tv')
    _profile_ = xbmc.translatePath(_addon_.getAddonInfo('profile'))
    _lang_ = _addon_.getLocalizedString
    _name_ = _addon_.getAddonInfo('name')
    _version_ = _addon_.getAddonInfo('version')
    _id_ = _addon_.getAddonInfo('id')
    _icon_ = xbmc.translatePath(os.path.join(_addon_.getAddonInfo('path'), 'icon.png'))

    addon = xbmcaddon.Addon
    dialog = xbmcgui.Dialog()
    progressDialog = xbmcgui.DialogProgress()
    keyboard = xbmc.Keyboard
    infoLabel = xbmc.getInfoLabel
    addonInfo = addon().getAddonInfo
    execute = xbmc.executebuiltin

    INFO = 'INFO'
    WARNING = 'WARNING'
    ERROR = 'ERROR'

    _start_period_hours_ = 1, 2, 3, 4, 6, 8, 12, 24
    _marhy_ = _lang_(30274), _lang_(30276)
    _no_error_ = 0
    _authent_error_ = 1
    _toomany_error_ = 2
    _nopurch_error_ = 3
    _error_code_ = 0, 1, 2, 3
    _error_str_ = 'OK', 'AuthenticationError', 'TooManyDevicesError', 'NoPurchasedServiceError'
    _error_lang_ = 'OK', _lang_(30003), _lang_(30006), _lang_(30008)
    _default_groupname_ = _lang_(30242)
    _quality_high_ = 'STB'
    _quality_low_ = 'TABLET'
    _cycle_step_ = 5
    _master_delay_ = 60
    _playlist_path_ = _profile_
    _playlist_src_ = 'o2tv.generic.m3u8'
    _playlist_dst_ = 'o2tv.playlist.m3u8'
    _playlist_streamer_ = 'streamer.sh'
    _pipe_ = 'pipe://'
    _settings_file_ = 'settings.xml'

    _streamer_code_ = '#! /bin/bash\n' + \
                      'source=$*\n' + \
                      'tempplaylist=$(mktemp -u)".m3u8"\n' + \
                      'stream=$(grep -A 1 "${source}$" ' + _playlist_src_ + ' | head -n 2 | tail -n 1)\n' + \
                      'wget -qO ${tempplaylist} ${stream}\n' + \
                      'streamcount=$(cat ${tempplaylist} | grep -Eo "(http|https)://[\da-z./?A-Z0-9\D=_-]*" | wc -l)\n' + \
                      'streamcount=$((streamcount-1))\n' + \
                      'if  [ "$streamcount" = "-1" ]; then streamcount=0; fi\n' + \
                      'ffmpeg -protocol_whitelist file,http,https,tcp,tls -fflags +genpts -loglevel fatal' + \
                      '-i ${tempplaylist} -probesize 32 -reconnect_at_eof 1 -reconnect_streamed 1 -c copy ' + \
                      '-map p:${streamcount}? -f mpegts -tune zerolatency -bsf:v h264_mp4toannexb,dump_extra ' + \
                      '-mpegts_service_type digital_tv pipe:1\n'

    def get_setting(setting):
        return _addon_.getSetting(setting).strip().decode('utf-8')


    def get_setting_bool(setting):
        return get_setting(setting).lower() == "true"


    def get_setting_int(setting, default):
        try:
            return int(float(get_setting(setting)))
        except ValueError:
            return default


    def set_setting(setting, value):
        _addon_.setSetting(setting, str(value))


    def _to_file(content, name):
        f = open(xbmc.translatePath(os.path.join(_addon_.getAddonInfo('profile'), name)), 'w')
        f.write(content)
        f.close()


    def _test_file(name):
        try:
            f = open(xbmc.translatePath(os.path.join(_addon_.getAddonInfo('profile'), name)), 'r')
        except IOError:
            return False
        else:
            f.close()
            return True


    def _try_exec(name):
        f = xbmc.translatePath(os.path.join(_addon_.getAddonInfo('profile'), name))
        sts = os.stat(f)
        if not (sts.st_mode & stat.S_IEXEC):
            os.chmod(f, sts.st_mode | stat.S_IEXEC)


    def _time_change(name):
        f = xbmc.translatePath(os.path.join(_addon_.getAddonInfo('profile'), name))
        return os.stat(f).st_mtime


    def load_settings(save=False):
        global _username_
        _username_ = get_setting('username')
        global _password_
        _password_ = get_setting('password')
        global _device_id_
        _device_id_ = get_setting('device_id')
        global _access_token_
        _access_token_ = get_setting('acces_token')

        global _start_automatic_
        _start_automatic_ = get_setting_bool('start_automatic')
        global _start_manual_
        _start_manual_ = get_setting_bool('start_manual')
        global _start_hour_
        _start_hour_ = get_setting_int('start_hour', 6)
        if save:
            set_setting('start_hour', _start_hour_)
        global _start_period_
        _start_period_ = get_setting_int('start_period', 6)
        if save:
            set_setting('start_period', _start_period_)
        global _start_enable_
        _start_enable_ = get_setting_bool('start_enable')
        global _start_delay_
        _start_delay_ = get_setting_int('start_delay', 10)
        if save:
            set_setting('start_delay', _start_delay_)

        global _playlist_type_
        _playlist_type_ = get_setting_int('playlist_type', 0)
        global _stream_quality_
        _stream_quality_ = get_setting_int('stream_quality', 0)
        global _channel_epgname_
        _channel_epgname_ = get_setting_int('channel_epgname', 0)
        global _channel_epgid_
        _channel_epgid_ = get_setting_int('channel_epgid', 0)
        global _channel_group_
        _channel_group_ = get_setting_int('channel_group', 0)
        global _channel_groupname_
        _channel_groupname_ = get_setting('channel_groupname')
        global _channel_logo_
        _channel_logo_ = get_setting_int('channel_logo', 0)
        global _channel_logopath_
        _channel_logopath_ = get_setting('channel_logopath')
        global _channel_logourl_
        _channel_logourl_ = get_setting('channel_logourl')
        global _channel_logogithub_
        _channel_logogithub_ = get_setting_int('channel_logogithub', 0)
        global _channel_logoname_
        _channel_logoname_ = get_setting_int('channel_logoname', 0)
        global _myscript_
        _myscript_ = get_setting_bool('myscript')
        global _myscript_name_
        _myscript_name_ = get_setting('myscript_name')

        global _last_downloaded_
        _last_downloaded_ = get_setting('last_downloaded')
        global _last_skipped_
        _last_skipped_ = get_setting('last_skipped')
        global _last_time_
        _last_time_ = get_setting('last_time')
        global _last_start_
        _last_start_ = get_setting('last_start')
        global _next_time_
        _next_time_ = get_setting('next_time')
        global _last_stest_
        _last_stest_ = get_setting('last_test')
        global _next_test_
        _next_test_ = get_setting('next_test')


    def test_settings():
        _username = get_setting('username')
        _password = get_setting('password')
        _login_error = not _username or not _password
        _start_automatic = get_setting_bool('start_automatic')
        _start_error = not _start_automatic
        _param_error = (_playlist_type_ == 0) or (_playlist_type_ > 3)
        return _login_error, _start_error, _param_error


    def _device_id():
        mac = get_mac()
        hexed = hex((mac * 7919) % (2 ** 64))
        return ('0000000000000000' + hexed[2:-1])[16:]


    def _random_hex16():
        return ''.join([random.choice('0123456789abcdef') for x in range(16)])


    def idle():
        return execute('Dialog.Close(busydialog)')


    def open_settings():
        execute('Addon.OpenSettings(%s)' % _id_, True)


    def idle():
        return execute('Dialog.Close(busydialog)')


    def yes_no_dialog(_line1_, _line2_, _line3_, _heading_=_name_, _nolabel_='', _yeslabel_=''):
        idle()
        return dialog.yesno(_heading_, _line1_, _line2_, _line3_, _nolabel_, _yeslabel_)


    def notification(message, icon=_icon_, _time=5000):
        if icon == 'INFO':
            icon = xbmcgui.NOTIFICATION_INFO
        elif icon == 'WARNING':
            icon = xbmcgui.NOTIFICATION_WARNING
        elif icon == 'ERROR':
            icon = xbmcgui.NOTIFICATION_ERROR
        xbmc.executebuiltin("XBMC.Notification(%s,%s,%i,%s)" % (_name_, message.decode('utf-8'), _time, icon))


    def info_dialog(message, icon=_icon_, _time=5000, sound=False):
        if icon == '':
            icon = icon = _addon_.getAddonInfo('icon')
        elif icon == 'INFO':
            icon = xbmcgui.NOTIFICATION_INFO
        elif icon == 'WARNING':
            icon = xbmcgui.NOTIFICATION_WARNING
        elif icon == 'ERROR':
            icon = xbmcgui.NOTIFICATION_ERROR
        dialog.notification(_name_, message, icon, _time, sound=sound)


    def log(msg, level=xbmc.LOGDEBUG):
        if type(msg).__name__ == 'unicode':
            msg = msg.encode('utf-8')
        xbmc.log("[%s] %s" % (_name_, msg.__str__()), level)


    def log_not(msg):
        log(msg, level=xbmc.LOGNOTICE)


    def _log_wrn(msg):
        log(msg, level=xbmc.LOGWARNING)


    def _log_dbg(msg):
        log(msg, level=xbmc.LOGDEBUG)


    def log_err(msg):
        log(msg, level=xbmc.LOGERROR)


    def _to_string(text):
        if type(text).__name__ == 'unicode':
            output = text.encode('utf-8')
        else:
            output = str(text)
        return output


    urllib3.disable_warnings()

    log_not('Preparation for Service')

    load_settings(True)
    login_error, start_error, param_error = test_settings()
    while login_error or start_error or param_error:
        line1 = _lang_(30800)
        line2 = _lang_(30801) % (_lang_(30802) if login_error else '',
                                 _lang_(30803) if start_error else '',
                                 _lang_(30804) if param_error else '')
        line3 = _lang_(30805)
        if yes_no_dialog(line1, line2, line3):
            open_settings()
            xbmc.sleep(1000)
            load_settings(True)
            login_error, start_error, param_error = test_settings()
            continue
        else:
            break
    load_settings(True)

    if not _device_id_:
        first_device_id = _device_id()
        second_device_id = _device_id()
        if first_device_id == second_device_id:
            _device_id_ = first_device_id
        else:
            _device_id_ = _random_hex16()
        set_setting("device_id", _device_id_)

    _to_file(_streamer_code_, _playlist_streamer_)
    _try_exec(_playlist_streamer_)
    _to_file(_streamer_code_, _playlist_streamer_ + '.sample')
    _try_exec(_playlist_streamer_ + '.sample')

try:
    if _stream_quality_ == 0:
        _quality_ = _quality_low_
    else:
        _quality_ = _quality_high_

    _o2tvgo_ = O2TVGO(_device_id_, _username_, _password_, _quality_)
    _o2tvgo_.log_function = _log_dbg


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
        return channels, _no_error_


    def _reload_settings():
        _addon_.openSettings()
        global _username_
        _username_ = _addon_.getSetting("username")
        global _password_
        _password_ = _addon_.getSetting("password")
        global _quality_
        _stream_quality_ = int(_addon_.getSetting('stream_quality'))
        if _stream_quality_ == 0:
            _quality_ = _quality_low_
        else:
            _quality_ = _quality_high_
        global _o2tvgo_
        _o2tvgo_ = O2TVGO(_device_id_, _username_, _password_, _quality_)


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
        if _channel_logoname_ == 0:
            f = _logo_name(channel) + '.png'
        elif _channel_logoname_ == 1:
            f = _logo_name(channel) + '.jpg'
        elif _channel_logoname_ == 2:
            f = channel + '.png'
        elif _channel_logoname_ == 3:
            f = channel + '.jpg'
        else:
            return ''
        return f


    def _logo_path_file(channel):
        if _channel_logo_ == 2:
            path_file = os.path.join(_channel_logopath_, _logo_file(channel))
            if not os.path.isfile(path_file):
                path_file = ""
        elif _channel_logo_ == 3:
            path_file = _channel_logourl_ + _logo_file(channel)
        elif _channel_logo_ == 4:
            path_file = _marhy_[_channel_logogithub_] + _logo_name(channel) + '.png'
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
        if _channel_group_ == 1:
            group = _default_groupname_
        else:
            group = _channel_groupname_
        if _myscript_ == 1:
            streamer = _pipe_ + os.path.join(_playlist_path_, _myscript_name_)
        else:
            streamer = _pipe_ + os.path.join(_playlist_path_, _playlist_streamer_)
        playlist_src = '#EXTM3U\n'
        playlist_dst = '#EXTM3U\n'
        _num = 0
        _err = 0
        for channel in channels_sorted:
            try:
                log_not("Adding: " + channel.name)
                name = channel.name
                logo = _to_string(channel.logo_url)
                url = _to_string(channel.url())
                epgname = name
                epgid = name
                # číslo programu v epg
                # viz https://www.o2.cz/file_conver/174210/_025_J411544_Razeni_televiznich_programu_O2_TV_03_2018.pdf
                channel_weight = _to_string(channel.weight)
                # logo v mistnim souboru - kdyz soubor neexistuje, tak pouzit url
                if (_channel_logo_ > 1) and (_logo_path_file(name) != ""):
                    logo = _logo_path_file(name)
                playlist_src += '#EXTINF:-1, %s\n%s\n' % (name, url)
                if _playlist_type_ == 1:
                    playlist_dst += '#EXTINF:-1'
                    playlist_dst += _add_param('tvg-name', epgname, _channel_epgname_ != 0)
                    playlist_dst += _add_param('tvg-id', epgid, _channel_epgid_ != 0)
                    playlist_dst += _add_param('tvg-logo', logo, _channel_logo_ != 0)
                    playlist_dst += _add_param('tvg-chno', channel_weight, _channel_epgid_ != 0)
                    playlist_dst += _add_param('group-titles', group, _channel_group_ != 0)
                    playlist_dst += ', %s\n%s\n' % (name, url)
                if (_playlist_type_ == 2) or (_playlist_type_ == 3):
                    playlist_dst += '#EXTINF:-1'
                    playlist_dst += _add_param('tvg-id', epgid, _channel_epgid_ != 0)
                    playlist_dst += _add_param('tvg-logo', logo, _channel_logo_ != 0)
                    playlist_dst += _add_param('tvg-chno', channel_weight, _channel_epgid_ != 0)
                    playlist_dst += _add_param('group-titles', group, _channel_group_ != 0)
                    playlist_dst += ', %s\n' % name
                    if _playlist_type_ == 2:
                        playlist_dst += '%s\n' % url
                    if _playlist_type_ == 3:
                        playlist_dst += '%s %s\n' % (streamer, name)
                _num += 1
            except ChannelIsNotBroadcastingError:
                log_not("... Not broadcasting. Skipped.")
                _err += 1
            except AuthenticationError:
                return _authent_error_, 0, 0
            except TooManyDevicesError:
                return _toomany_error_, 0, 0
        _to_file(playlist_src, _playlist_src_)
        _to_file(playlist_dst, _playlist_dst_)
        set_setting('last_time', time.strftime('%Y-%m-%d %H:%M'))
        set_setting('last_downloaded', _to_string(_num))
        set_setting('last_skipped', _to_string(_err))
        return _no_error_, _num, _err


    def next_time_():
        start_period = int(_start_period_hours_[int(_start_period_)])
        act_time_sec = time.time()
        act_date = time.strftime('%Y-%m-%d')
        act_start = ('%s %s:00' % (act_date, _start_hour_))
        act_start_sec = time.mktime(time.strptime(act_start, '%Y-%m-%d %H:%M'))
        offset_raw = (act_time_sec - act_start_sec) / (start_period * 3600)
        offset = int(offset_raw)
        if offset_raw >= 0:
            offset += 1
        offset *= start_period
        _next_time_sec = act_start_sec + offset * 3600
        _next_time = time.strftime('%Y-%m-%d %H:%M', time.localtime(_next_time_sec))
        _log_dbg('next_time_ result: %s %d %d %s %f %f' % (act_start, act_start_sec, _next_time_sec,
                                                           _next_time, offset_raw, offset))
        return _next_time, _next_time_sec


    def to_master(master):
        return int(time.mktime(time.strptime(time.strftime('%Y-%m-%d %H:%M'), '%Y-%m-%d %H:%M')) + master - time.time())


    log_not('Waiting %s s for Service' % _start_delay_)
    xbmc.sleep(_start_delay_ * 1000)

    log_not('START Service')
    info_dialog(_lang_(30049))
    set_setting('last_start', time.strftime('%Y-%m-%d %H:%M:%S'))

    start = True
    init_error = True
    last_minute = False
    error_report = False
    start_report = False
    change_report = False
    time_change_saved_sec = 0
    cycle_step = _cycle_step_
    master_delay = 0
    next_time = ''

    while not monitor.abortRequested():
        try:
            if monitor.waitForAbort(_cycle_step_):
                break
            if master_delay > _cycle_step_:
                master_delay = to_master(_master_delay_)
                continue
            master_delay = _master_delay_ - _cycle_step_
            _log_dbg('Service running: full cycle - time: %s' % (time.strftime('%Y-%m-%d %H:%M:%S')))

            time_change_sec = _time_change(_settings_file_)
            if time_change_sec != time_change_saved_sec:
                time_change_saved_sec = time_change_sec
                time_change = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time_change_sec))
                log_not('Change in settings.xml: %s' % time_change)
                load_settings()
                log_not('Settings loaded')
                login_error, start_error, param_error = test_settings()
                if not (login_error or start_error or param_error):
                    next_time, next_time_sec = next_time_()
                    if next_time != _next_time_:
                        set_setting('next_time', next_time)
                        _next_time_ = next_time
                        log_not('Change of settings next time - next start: %s' % (_next_time_))
                        change_report = True

            if login_error or start_error or param_error:
                if not error_report:
                    error_report = True
                    info_dialog(_lang_(30048))
                    _log_wrn('Unfinished settings - login : %s, start : %s, param : %s' % (
                        _to_string(login_error), _to_string(start_error), _to_string(param_error)))
                _log_dbg('Service running: short cycle (Unfinished settings) - time: %s' % (
                    time.strftime('%Y-%m-%d %H:%M:%S')))
                continue

            if error_report:
                log_not('Finished settings')

            if start:
                start = False
                if not _next_time_ or _start_enable_:
                    next_time_sec = 0
                    log_not('Counter to download clearing - immediate start')
                else:
                    start_report = True
                    next_time_sec = time.mktime(time.strptime(_next_time_, '%Y-%m-%d %H:%M'))
                    log_not('Setting next time - next start: %s' % _next_time_)

            if error_report or start_report or change_report:
                error_report = False
                start_report = False
                change_report = False
                info_dialog(_lang_(30047) % (_next_time_))

            if (time.time() < next_time_sec) or not _start_automatic_:
                continue

            log_not('Download starts')
            info_dialog(_lang_(30040))
            code, num, err = channel_playlist()
            if code == _no_error_:
                info_dialog(_lang_(30041) % (num, err))
                log_not('Download finishes %d/%d channel(s) downloaded/skipped' % (num, err))
            else:
                info_dialog(_error_lang_[code])
                log_not('Download aborted: %s' % (_error_str_[code]))

            next_time, next_time_sec = next_time_()
            if next_time != _next_time_:
                set_setting('next_time', _to_string(next_time))
            info_dialog(_lang_(30047) % (next_time))

        except Exception as ex:
            info_dialog(_lang_(30042))
            exc_type, exc_value, exc_traceback = sys.exc_info()
            log_err('LOOP error - exc_type:%s, exc_value:%s, exc_traceback:%s' % (
                _to_string(exc_type), _to_string(exc_value), _to_string(exc_traceback)))

    info_dialog(_lang_(30043))
    log_not('DONE Service')
except:
    info_dialog(_lang_(30042))
    exc_type, exc_value, exc_traceback = sys.exc_info()
    log_err('INIT error - exc_type:%s, exc_value:%s, exc_traceback:%s' % (
        _to_string(exc_type), _to_string(exc_value), _to_string(exc_traceback)))
    info_dialog(_lang_(30043))
    log_not('DONE Service')
