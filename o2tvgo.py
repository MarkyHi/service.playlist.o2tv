#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Wrapper pro O2TV Go
"""
from __future__ import unicode_literals
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
from future import standard_library
from builtins import str
from builtins import object
import requests
import time

standard_library.install_aliases()

__author__ = "Štěpán Ort"
__license__ = "MIT"
__version__ = "1.1.8"
__email__ = "stepanort@gmail.com"

_COMMON_HEADERS = {"X-NanguTv-App-Version": "Android#6.4.1",
                   "X-NanguTv-Device-Name": "O2TVKodi",
                   "User-Agent": "Dalvik/2.1.0",
                   "Accept-Encoding": "gzip",
                   "Connection": "Keep-Alive"}


def _to_string(text):
    if (type(text).__name__ == 'unicode') or (type(text).__name__ == 'newstr'):
        output = text.encode('utf-8')
    elif type(text).__name__ == 'str':
        output = text
    else:
        output = str(text)
    return output


# Kanál


class LiveChannel(object):

    # JiRo - doplněn parametr kvality
    def __init__(self, o2tv, channel_key, name, logo_url, weight, quality, log_function=None):
        self._o2tv = o2tv
        self.channel_key = channel_key
        self.name = name
        self.weight = weight
        self.logo_url = logo_url
        self._last_url = None
        self.log_function = log_function
        self.quality = quality  # doplněn parametr kvality

    def _log(self, message):
        if self.log_function:
            self.log_function(message)

    def url(self, attempts=5, delay=1000):
        if self._last_url:
            return self._last_url
        done = False
        start_attempts = attempts
        while not done:
            self._url()
            if self._last_url:
                done = True
            else:
                #
                time.sleep(delay / 1000)
            attempts -= 1
            if attempts <= 0:
                done = True
        if not self._last_url:
            raise NoPlaylistUrlsError()
        if attempts < (start_attempts - 1):
            self._log("Attempts: %d" % (start_attempts - attempts))
        return self._last_url

    def _url(self):
        if not self._o2tv.access_token:
            self._o2tv.refresh_access_token()
        access_token = self._o2tv.access_token
        if not self._o2tv.subscription_code:
            self._o2tv.refresh_configuration()
        subscription_code = self._o2tv.subscription_code
        playlist = None
        while access_token:
            params = {"serviceType": "LIVE_TV",
                      "subscriptionCode": subscription_code,
                      "channelKey": self.channel_key,
                      "deviceType": self.quality,
                      "streamingProtocol": "HLS",
                      # "videoCodec": "H264",
                      "encryptionType": "NONE",
                      # "streamType":"LIVE"
                      # "contentId": "-1",
                      # "fromTimeStamp": int((datetime.now(tz=None) - datetime(1970,1,1)).total_seconds()),
                      # "toTimeStamp": int((datetime(2100,1,1) - datetime(1970,1,1)).total_seconds()),
                      # "id": "-1"
                      # "contentId":"LIVE"
                      }  # JiRo - doplněn parametr kvality
            headers = _COMMON_HEADERS
            cookies = {"access_token": access_token,
                       "deviceId": self._o2tv.device_id}
            req = requests.get('http://app.o2tv.cz/sws/server/streaming/uris.json',
                               params=params, headers=headers, cookies=cookies)
            req.encoding = req.apparent_encoding
            json_data = req.json()
            access_token = None
            if 'statusMessage' in json_data:
                status = json_data['statusMessage']
                if status == 'bad-credentials':
                    access_token = self._o2tv.refresh_access_token()
                elif status == 'channel.not-found':
                    raise ChannelIsNotBroadcastingError()
                else:
                    raise Exception(status)
            elif len(json_data["uris"]) < 1:
                # raise NoPlaylistUrlsError()
                return None
            else:
                # Pavuucek: Pokus o vynucení HD kvality
                playlist = ""
                # pro kvalitu STB nebo PC se pokusíme vybrat HD adresu.
                # když není k dispozici, tak první v seznamu
                for uris in json_data["uris"]:
                    if self.quality == "STB" or self.quality == "PC":
                        if uris["resolution"] == "HD" and playlist == "":
                            playlist = uris["uri"]
                    else:
                        # pro ostatní vracíme SD adresu
                        if uris["resolution"] == "SD" and playlist == "":
                            playlist = uris["uri"]
                # playlist nebyl přiřazený, takže první adresa v seznamu
                if playlist == "":
                    playlist = json_data["uris"][0]["uri"]
        self._last_url = playlist
        return playlist


class ChannelIsNotBroadcastingError(BaseException):
    pass


class AuthenticationError(BaseException):
    pass


class TooManyDevicesError(BaseException):
    pass


# JiRo - doplněna kontrola zaplacené služby
class NoPurchasedServiceError(BaseException):
    pass


# Nebyl vrácen playlist
class NoPlaylistUrlsError(BaseException):
    pass


# Nebyl vrácen seznam kanálů
class NoChannelsError(BaseException):
    pass


class O2TVGO(object):

    def __init__(self, device_id, username, password, quality, log_function=None):  # JiRo - doplněn parametr kvality
        self.username = username
        self.password = password
        self._live_channels = {}
        self.access_token = None
        self.refresh_token = None
        self.subscription_code = None
        self.locality = None
        self.offer = None
        self.tariff = None
        self.expires_in = None
        self.device_id = device_id
        self.quality = quality  # JiRo - doplněn parametr kvality
        self.log_function = log_function

    def _log(self, message):
        if self.log_function:
            self.log_function(message)

    def get_access_token_password(self):
        self._log('Getting Token via password...')
        if not self.username or not self.password:
            raise AuthenticationError()
        headers = _COMMON_HEADERS
        headers["Content-Type"] = "application/x-www-form-urlencoded;charset=UTF-8"
        data = {'grant_type': 'password',
                'client_id': 'tef-web-portal-etnetera',
                'client_secret': '2b16ac9984cd60dd0154f779ef200679',
                'username': self.username,
                'password': self.password,
                'platform_id': '231a7d6678d00c65f6f3b2aaa699a0d0',
                'language': 'cs'}
        req = requests.post('https://oauth.o2tv.cz/oauth/token',
                            data=data, headers=headers, verify=False)
        req.encoding = req.apparent_encoding
        j = req.json()
        if 'error' in j:
            error = j['error']
            if error == 'authentication-failed':
                self._log('Authentication Error')
                return None
            else:
                raise Exception(error)
        self.access_token = j["access_token"]
        self.expires_in = j["expires_in"]
        self._log('Token OK')
        return self.access_token

    def get_access_token_mediator(self):
        self._log('Getting token from mediator...')
        _HEADERS = {
            'X-Nangu-Device-Name': self.device_id,
            'X-Nangu-App-Version': 'Android',
            'User-Agent': 'okhttp/3.10.0',
            'Accept-Encoding': 'gzip',
            'Connection': 'Keep-Alive',
            'Content-Type': 'application/x-www-form-urlencoded'
        }

        headers = _HEADERS
        data = {
            'username': self.username,
            'password': self.password
        }
        req = requests.post('https://ottmediator.o2tv.cz:4443/ottmediator-war/login',
                            data=data, headers=headers, verify=False)
        req.encoding = req.apparent_encoding
        j = req.json()
        service_id = str(j['services'][0]['service_id'])
        remote_access_token = str(j['remote_access_token'])

        datax = {
            'service_id': service_id,
            'remote_access_token': remote_access_token
        }
        requests.post('https://ottmediator.o2tv.cz:4443/ottmediator-war/loginChoiceService',
                      data=datax, headers=headers, verify=False)

        _HEADERS1 = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Connection': 'Keep-Alive'
        }
        headers1 = _HEADERS1
        data1 = {
            'client_id': 'tef-web-portal-etnetera',
            'client_secret': '2b16ac9984cd60dd0154f779ef200679',
            'platform_id': '231a7d6678d00c65f6f3b2aaa699a0d0',
            'language': 'cs',
            'grant_type': 'remote_access_token',
            'remote_access_token': remote_access_token,
            'authority': 'tef-sso',
            'isp_id': '1'
        }
        req1 = requests.post('https://oauth.o2tv.cz/oauth/token',
                             data=data1, headers=headers1, verify=False)
        req1.encoding = req1.apparent_encoding
        j = req1.json()
        if 'error' in j:
            error = j['error']
            if error == 'authentication-failed':
                self._log('Authentication Error')
                return None
            else:
                raise Exception(error)
        self.access_token = j['access_token']
        self.refresh_token = j['refresh_token']
        self.expires_in = j['expires_in']
        self._log('Token OK')
        return self.access_token

    def refresh_access_token(self):
        if not self.access_token:
            self.get_access_token_password()
        if not self.access_token:
            self.get_access_token_mediator()
        if not self.access_token:
            self._log('Authentication Error (failed to get token)')
            raise AuthenticationError()
        return self.access_token

    def refresh_configuration(self):
        if not self.access_token:
            self.refresh_access_token()
        access_token = self.access_token
        headers = _COMMON_HEADERS
        cookies = {"access_token": access_token, "deviceId": self.device_id}
        req = requests.get(
            'http://app.o2tv.cz/sws/subscription/settings/subscription-configuration.json', headers=headers,
            cookies=cookies)
        req.encoding = req.apparent_encoding
        j = req.json()
        if 'errorMessage' in j:
            error_message = j['errorMessage']
            status_message = j['statusMessage']
            # JiRo - změna z 'unauthorized-device' na 'devices-limit-exceeded'
            if status_message == 'devices-limit-exceeded':
                raise TooManyDevicesError()
            else:
                raise Exception(error_message)
        self.subscription_code = j["subscription"]
        self.offer = j["billingParams"]["offers"]
        self.tariff = j["billingParams"]["tariff"]
        self.locality = j["locality"]

    def live_channels(self):
        if not self.access_token:
            self.refresh_access_token()
        access_token = self.access_token
        if not self.offer:
            self.refresh_configuration()
        offer = self.offer
        if not self.tariff:
            self.refresh_configuration()
        tariff = self.tariff
        if not self.locality:
            self.refresh_configuration()
        locality = self.locality
        quality = self.quality  # JiRo - doplněn parametr kvality
        if len(self._live_channels) == 0:
            headers = _COMMON_HEADERS
            cookies = {"access_token": access_token,
                       "deviceId": self.device_id}
            params = {"locality": locality,
                      "tariff": tariff,
                      "isp": "1",
                      "language": "ces",
                      "deviceType": quality,
                      "imageSize": "LARGE",
                      "liveTvStreamingProtocol": "HLS",
                      "offer": offer}  # doplněn parametr kvality
            req = requests.get('http://app.o2tv.cz/sws/server/tv/channels.json',
                               params=params, headers=headers, cookies=cookies)
            req.encoding = req.apparent_encoding
            j = req.json()
            purchased_channels = j['purchasedChannels']
            if len(purchased_channels) == 0:  # JiRo - doplněna kontrola zaplacené služby
                raise NoPurchasedServiceError()  # JiRo - doplněna kontrola zaplacené služby
            items = j['channels']
            for channel_id, item in list(items.items()):
                if channel_id in purchased_channels:
                    # tohle bývá někdy false
                    live = item['liveTvPlayable']
                    if live:
                        channel_key = item['channelKey']
                        logo = item['logo']
                        if not logo.startswith('http://'):
                            logo = 'http://app.o2tv.cz' + logo
                        name = item['channelName']
                        weight = item['weight']
                        self._live_channels[channel_key] = LiveChannel(
                            # doplněn parametr kvality
                            self, channel_key, name, logo, weight, quality, self.log_function)
            done = False
            offset = 0
            while not done:
                headers = _COMMON_HEADERS
                params = {"language": "ces",
                          "audience": "over_18",
                          "channelKey": list(self._live_channels.keys()),
                          "limit": 30,
                          "offset": offset}
                req = requests.get(
                    'http://www.o2tv.cz/mobile/tv/channels.json', params=params, headers=headers)
                req.encoding = req.apparent_encoding
                j = req.json()
                items = j['channels']['items']
                for item in items:
                    item = item['channel']
                    channel_key = item['channelKey']
                    if 'logoUrl' in list(item.keys()):
                        logo_url = "http://www.o2tv.cz" + item['logoUrl']
                        if channel_key in self._live_channels.keys():
                            self._live_channels[channel_key].logo_url = logo_url
                        else:
                            done = True  # derp
                offset += 30
                total_count = j['channels']['totalCount']
                if offset >= total_count:
                    done = True
        if len(self._live_channels) == 0:
            raise NoChannelsError()
        return self._live_channels
