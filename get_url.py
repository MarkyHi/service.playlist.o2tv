#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division
from __future__ import absolute_import

import os

from o2tvgo import AuthenticationError
from o2tvgo import ChannelIsNotBroadcastingError
from o2tvgo import NoPurchasedServiceError
from o2tvgo import NoPlaylistUrlsError
from o2tvgo import O2TVGO
from o2tvgo import TooManyDevicesError
from o2tvgo import NoChannelsError

from future import standard_library
import sys
import codecs
import common as c
try:
    from configparser import ConfigParser as SafeConfigParser
except ImportError:
    from ConfigParser import SafeConfigParser  # ver. < 3.0

if __name__ == '__main__':
    pos = 1
    cmdLine = ""
    while len(sys.argv)-1 >= pos:
        cmdLine += sys.argv[pos].decode(sys.getfilesystemencoding()) + ' '
        pos += 1
    cmdLine = cmdLine.rstrip()
    print('Get Url: ' + cmdLine)
    config = SafeConfigParser()
    c.set_default_config(config)

    with codecs.open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.ini'), 'r',
                     encoding='utf-8') as f:
        config.read_file(f)

    if config.getint('Common', 'stream_quality') == 1:
        _quality_ = 'STB'
    else:
        _quality_ = 'TABLET'

    _o2tvgo_ = O2TVGO(config.get('Login', 'device_id'), config.get('Login', 'username'),
                      config.get('Login', 'password'), _quality_, None)
    _o2tvgo_.access_token = config.get('Login', 'access_token')
    _o2tvgo_.expires_in = config.get('Login', 'token_expire_date')
    _o2tvgo_.app_id = 'O2TVKodi Playlist'
    channels = _o2tvgo_.live_channels()
    if cmdLine in channels:
        print('Channel found!')
    else:
        print('Channel not found!')
        exit()
    print(channels[cmdLine].url())
