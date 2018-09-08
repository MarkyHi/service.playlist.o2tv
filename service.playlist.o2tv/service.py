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
                      'stream=$(grep -A 1 "${source}$" ' + os.path.join(_profile_, _playlist_src_) + ' | head -n 2 | tail -n 1)\n' + \
                      'streamcount=$(wget -qO - ${stream} | grep -Eo "(http|https)://[\da-z./?A-Z0-9\D=_-]*" | wc -l)\n' + \
                      'streamcount=$((streamcount-1))\n' + \
                      'ffmpeg -re -fflags +genpts -loglevel fatal -i ${stream} -probesize 32 -c copy -map p:${streamcount}?' + \
                      '-f mpegts -mpegts_service_type digital_tv pipe:1'
    def getSetting(setting):
        return _addon_.getSetting(setting).strip().decode('utf-8')


    def getSettingBool(setting):
        return getSetting(setting).lower() == "true"


    def getSettingInt(setting, default):
        try:
            return int(float(getSetting(setting)))
        except ValueError:
            return default


    def setSetting(setting, value):
        _addon_.setSetting(setting, str(value))


    def _toFile(content, name):
        file = open(xbmc.translatePath(os.path.join(_addon_.getAddonInfo('profile'), name)), 'w')
        file.write(content)
        file.close()


    def _testFile(name):
        try:
            file = open(xbmc.translatePath(os.path.join(_addon_.getAddonInfo('profile'), name)), 'r')
        except IOError:
            return False
        else:
            file.close()
            return True


    def _tryExec(name):
        file = xbmc.translatePath(os.path.join(_addon_.getAddonInfo('profile'), name))
        sts = os.stat(file)
        if not (sts.st_mode & stat.S_IEXEC): os.chmod(file, sts.st_mode | stat.S_IEXEC)


    def _timeChange(name):
        file = xbmc.translatePath(os.path.join(_addon_.getAddonInfo('profile'), name))
        return os.stat(file).st_mtime


    def loadSettings(save=False):
        global _username_
        _username_ = getSetting('username')
        global _password_
        _password_ = getSetting('password')
        global _device_id_
        _device_id_ = getSetting('device_id')
        global _acces_token_
        _acces_token_ = getSetting('acces_token')

        global _start_automatic_
        _start_automatic_ = getSettingBool('start_automatic')
        global _start_manual_
        _start_manual_ = getSettingBool('start_manual')
        global _start_hour_
        _start_hour_ = getSettingInt('start_hour', 6)
        if save: setSetting('start_hour', _start_hour_)
        global _start_period_
        _start_period_ = getSettingInt('start_period', 6)
        if save: setSetting('start_period', _start_period_)
        global _start_enable_
        _start_enable_ = getSettingBool('start_enable')
        global _start_delay_
        _start_delay_ = getSettingInt('start_delay', 10)
        if save: setSetting('start_delay', _start_delay_)

        global _playlist_type_
        _playlist_type_ = getSettingInt('playlist_type', 0)
        global _stream_quality_
        _stream_quality_ = getSettingInt('stream_quality', 0)
        global _channel_epgname_
        _channel_epgname_ = getSettingInt('channel_epgname', 0)
        global _channel_epgid_
        _channel_epgid_ = getSettingInt('channel_epgid', 0)
        global _channel_group_
        _channel_group_ = getSettingInt('channel_group', 0)
        global _channel_groupname_
        _channel_groupname_ = getSetting('channel_groupname')
        global _channel_logo_
        _channel_logo_ = getSettingInt('channel_logo', 0)
        global _channel_logopath_
        _channel_logopath_ = getSetting('channel_logopath')
        global _channel_logourl_
        _channel_logourl_ = getSetting('channel_logourl')
        global _channel_logogithub_
        _channel_logogithub_ = getSettingInt('channel_logogithub', 0)
        global _channel_logoname_
        _channel_logoname_ = getSettingInt('channel_logoname', 0)
        global _myscript_
        _myscript_ = getSettingBool('myscript')
        global _myscript_name_
        _myscript_name_ = getSetting('myscript_name')

        global _last_downloaded_
        _last_downloaded_ = getSetting('last_downloaded')
        global _last_skipped_
        _last_skipped_ = getSetting('last_skipped')
        global _last_time_
        _last_time_ = getSetting('last_time')
        global _last_start_
        _last_start_ = getSetting('last_start')
        global _next_time_
        _next_time_ = getSetting('next_time')
        global _last_stest_
        _last_stest_ = getSetting('last_test')
        global _next_test_
        _next_test_ = getSetting('next_test')


    def testSettings():
        _username_ = getSetting('username')
        _password_ = getSetting('password')
        login_error = not _username_ or not _password_
        _start_automatic_ = getSettingBool('start_automatic')
        start_error = not _start_automatic_
        param_error = (_playlist_type_ == 0) or (_playlist_type_ > 3)
        return login_error, start_error, param_error


    def _deviceId():
        mac = get_mac()
        hexed = hex((mac * 7919) % (2 ** 64))
        return ('0000000000000000' + hexed[2:-1])[16:]


    def _randomHex16():
        return ''.join([random.choice('0123456789abcdef') for x in range(16)])


    def idle():
        return execute('Dialog.Close(busydialog)')


    def openSettings():
        execute('Addon.OpenSettings(%s)' % _id_, True)


    def idle():
        return execute('Dialog.Close(busydialog)')


    def yesnoDialog(line1, line2, line3, heading=_name_, nolabel='', yeslabel=''):
        idle()
        return dialog.yesno(heading, line1, line2, line3, nolabel, yeslabel)


    def notification(message, icon=_icon_, time=5000):
        if icon == 'INFO':
            icon = xbmcgui.NOTIFICATION_INFO
        elif icon == 'WARNING':
            icon = xbmcgui.NOTIFICATION_WARNING
        elif icon == 'ERROR':
            icon = xbmcgui.NOTIFICATION_ERROR
        xbmc.executebuiltin("XBMC.Notification(%s,%s,%i,%s)" % (_name_, message.decode('utf-8'), time, icon))


    def infoDialog(message, icon=_icon_, time=5000, sound=False):
        if icon == '':
            icon = icon = _addon_.getAddonInfo('icon')
        elif icon == 'INFO':
            icon = xbmcgui.NOTIFICATION_INFO
        elif icon == 'WARNING':
            icon = xbmcgui.NOTIFICATION_WARNING
        elif icon == 'ERROR':
            icon = xbmcgui.NOTIFICATION_ERROR
        dialog.notification(_name_, message, icon, time, sound=sound)


    def log(msg, level=xbmc.LOGDEBUG):
        if type(msg).__name__ == 'unicode':
            msg = msg.encode('utf-8')
        xbmc.log("[%s] %s" % (_name_, msg.__str__()), level)


    def logNot(msg):
        log(msg, level=xbmc.LOGNOTICE)


    def logWrn(msg):
        log(msg, level=xbmc.LOGWARNING)


    def logDbg(msg):
        log(msg, level=xbmc.LOGDEBUG)


    def logErr(msg):
        log(msg, level=xbmc.LOGERROR)


    def _toString(text):
        if type(text).__name__ == 'unicode':
            output = text.encode('utf-8')
        else:
            output = str(text)
        return output


    urllib3.disable_warnings()

    logNot('Preparation for Service')

    loadSettings(True)
    login_error, start_error, param_error = testSettings()
    while login_error or start_error or param_error:
        line1 = 'Neúplné nastavení parametrů služby'
        line2 = 'Nastavte parametry pro:%s%s%s' % (' Přihlášení' if login_error else '' \
                                                       , ' Spouštění' if start_error else '' \
                                                       , ' Playlist' if param_error else '')
        line3 = 'Spustit nastavení parametrů služby?'
        if yesnoDialog(line1, line2, line3):
            openSettings()
            xbmc.sleep(1000)
            loadSettings(True)
            login_error, start_error, param_error = testSettings()
            continue
        else:
            break
    loadSettings(True)

    if not _device_id_:
        first_device_id = _deviceId()
        second_device_id = _deviceId()
        if first_device_id == second_device_id:
            _device_id_ = first_device_id
        else:
            _device_id_ = _randomHex16()
        setSetting("device_id", _device_id_)

    _toFile(_streamer_code_, _playlist_streamer_)
    _tryExec(_playlist_streamer_)
    _toFile(_streamer_code_, _playlist_streamer_ + '.sample')
    _tryExec(_playlist_streamer_ + '.sample')

try:
    if _stream_quality_ == 0:
        _quality_ = _quality_low_
    else:
        _quality_ = _quality_high_

    _o2tvgo_ = O2TVGO(_device_id_, _username_, _password_, _quality_)


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
            path_file = os.path.join(_channel_logopath_,_logoFile(channel))
            if not os.path.isfile(path_file):
                path_file = ""
        elif _channel_logo_ == 3:
            path_file = _channel_logourl_ + _logoFile(channel)
        elif _channel_logo_ == 4:
            path_file = _marhy_[_channel_logogithub_] + _logoName(channel) + '.png'
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
                logNot("Adding: " + channel.name)
                name = channel.name
                logo = _toString(channel.logo_url)
                url = _toString(channel.url())
                epgname = name
                epgid = name
                # číslo programu v epg
                # viz https://www.o2.cz/file_conver/174210/_025_J411544_Razeni_televiznich_programu_O2_TV_03_2018.pdf
                channel_weight = _toString(channel.weight)
                # logo v mistnim souboru - kdyz soubor neexistuje, tak pouzit url
                if (_channel_logo_ > 1) and (_logoPathFile(name) != ""):
                    logo = _logoPathFile(name)
                playlist_src += '#EXTINF:-1, %s\n%s\n' % (name, url)
                if _playlist_type_ == 1:
                    playlist_dst += '#EXTINF:-1'
                    playlist_dst += _addParam('tvg-name', epgname, _channel_epgname_ != 0)
                    playlist_dst += _addParam('tvg-id', epgid, _channel_epgid_ != 0)
                    playlist_dst += _addParam('tvg-logo', logo, _channel_logo_ != 0)
                    playlist_dst += _addParam('tvg-chno', channel_weight, _channel_epgid_ != 0)
                    playlist_dst += _addParam('group-titles', group, _channel_group_ != 0)
                    playlist_dst += ', %s\n%s\n' % (name, url)
                if (_playlist_type_ == 2) or (_playlist_type_ == 3):
                    playlist_dst += '#EXTINF:-1'
                    playlist_dst += _addParam('tvg-id', epgid, _channel_epgid_ != 0)
                    playlist_dst += _addParam('tvg-logo', logo, _channel_logo_ != 0)
                    playlist_dst += _addParam('tvg-chno', channel_weight, _channel_epgid_ != 0)
                    playlist_dst += _addParam('group-titles', group, _channel_group_ != 0)
                    playlist_dst += ', %s\n' % (name)
                    if _playlist_type_ == 2: playlist_dst += '%s\n' % url
                    if _playlist_type_ == 3: playlist_dst += '%s %s\n' % (streamer, name)
                num += 1
            except ChannelIsNotBroadcastingError:
                logNot("... Not broadcasting. Skipped.")
                err += 1
            except AuthenticationError:
                return _authent_error_, 0, 0
            except TooManyDevicesError:
                return _toomany_error_, 0, 0
        _toFile(playlist_src, _playlist_src_)
        _toFile(playlist_dst, _playlist_dst_)
        setSetting('last_time', time.strftime('%Y-%m-%d %H:%M'))
        setSetting('last_downloaded', _toString(num))
        setSetting('last_skipped', _toString(err))
        return _no_error_, num, err


    def nextTime():
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
        next_time_sec = act_start_sec + offset * 3600
        next_time = time.strftime('%Y-%m-%d %H:%M', time.localtime(next_time_sec))
        logDbg('nextTime result: %s %d %d %s %f %f' % (
        act_start, act_start_sec, next_time_sec, next_time, offset_raw, offset))
        return next_time, next_time_sec


    def toMaster(master):
        return int(time.mktime(time.strptime(time.strftime('%Y-%m-%d %H:%M'), '%Y-%m-%d %H:%M')) + master - time.time())


    logNot('Waiting %s s for Service' % (_start_delay_))
    xbmc.sleep(_start_delay_ * 1000)

    logNot('START Service')
    infoDialog(_lang_(30049))
    setSetting('last_start', time.strftime('%Y-%m-%d %H:%M:%S'))

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
                master_delay = toMaster(_master_delay_)
                continue
            master_delay = _master_delay_ - _cycle_step_
            logDbg('Service running: full cycle - time: %s' % (time.strftime('%Y-%m-%d %H:%M:%S')))

            time_change_sec = _timeChange(_settings_file_)
            if time_change_sec != time_change_saved_sec:
                time_change_saved_sec = time_change_sec
                time_change = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time_change_sec))
                logNot('Change in settings.xml: %s' % (time_change))
                loadSettings()
                logNot('Settings loaded')
                login_error, start_error, param_error = testSettings()
                if not (login_error or start_error or param_error):
                    next_time, next_time_sec = nextTime()
                    if next_time != _next_time_:
                        setSetting('next_time', next_time)
                        _next_time_ = next_time
                        logNot('Change of settings next time - next start: %s' % (_next_time_))
                        change_report = True

            if login_error or start_error or param_error:
                if not error_report:
                    error_report = True
                    infoDialog(_lang_(30048))
                    logWrn('Unfinished settings - login : %s, start : %s, param : %s' % (
                    _toString(login_error), _toString(start_error), _toString(param_error)))
                logDbg('Service running: short cycle (Unfinished settings) - time: %s' % (
                    time.strftime('%Y-%m-%d %H:%M:%S')))
                continue

            if error_report:
                logNot('Finished settings')

            if start:
                start = False
                if not _next_time_ or _start_enable_:
                    next_time_sec = 0
                    logNot('Counter to download clearing - immediate start')
                else:
                    start_report = True
                    next_time_sec = time.mktime(time.strptime(_next_time_, '%Y-%m-%d %H:%M'))
                    logNot('Setting next time - next start: %s' % (_next_time_))

            if error_report or start_report or change_report:
                error_report = False
                start_report = False
                change_report = False
                infoDialog(_lang_(30047) % (_next_time_))

            if (time.time() < next_time_sec) or not _start_automatic_:
                continue

            logNot('Download starts')
            infoDialog(_lang_(30040))
            code, num, err = channelPlaylist()
            if code == _no_error_:
                infoDialog(_lang_(30041) % (num, err))
                logNot('Download finishes %d/%d channel(s) downloaded/skipped' % (num, err))
            else:
                infoDialog(_error_lang_[code])
                logNot('Download aborted: %s' % (_error_str_[code]))

            next_time, next_time_sec = nextTime()
            if next_time != _next_time_:
                setSetting('next_time', _toString(next_time))
            infoDialog(_lang_(30047) % (next_time))

        except Exception as ex:
            infoDialog(_lang_(30042))
            exc_type, exc_value, exc_traceback = sys.exc_info()
            logErr('LOOP error - exc_type:%s, exc_value:%s, exc_traceback:%s' % (
            _toString(exc_type), _toString(exc_value), _toString(exc_traceback)))

    infoDialog(_lang_(30043))
    logNot('DONE Service')
except:
    infoDialog(_lang_(30042))
    exc_type, exc_value, exc_traceback = sys.exc_info()
    logErr('INIT error - exc_type:%s, exc_value:%s, exc_traceback:%s' % (
    _toString(exc_type), _toString(exc_value), _toString(exc_traceback)))
    infoDialog(_lang_(30043))
    logNot('DONE Service')
