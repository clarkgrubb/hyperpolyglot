#!/usr/bin/env python

# http://www.wikidot.com/doc:api-methods

import argparse
import codecs
import ConfigParser
import os
import sys
import xmlrpclib

APP = 'page_content.py'

URI_FMT = 'https://{app}:{access_key}@www.wikidot.com/xml-rpc-api.php'

CONFIG_FILE = os.path.join(os.getenv('HOME'), '.wikidot')
SECTION_API = 'API'
SITE_KEY = 'site'
KEY_READONLY_ACCESS_KEY = 'readonly_access_key'
KEY_READWRITE_ACCESS_KEY = 'readwrite_access_key'
ENCODING = 'utf-8'

sys.stdin = codecs.getreader(ENCODING)(sys.stdin)
sys.stdout = codecs.getwriter(ENCODING)(sys.stdout)
sys.stderr = codecs.getwriter(ENCODING)(sys.stderr)


def load_config():

    if os.path.exists(CONFIG_FILE):
        config = ConfigParser.SafeConfigParser()
        config.read(CONFIG_FILE)

    else:
        raise Exception('Config file not found: {}'.format(CONFIG_FILE))

    return config


def download(page, output_stream):

    config = load_config()
    access_key = config.get(SECTION_API, KEY_READONLY_ACCESS_KEY)
    site = config.get(SECTION_API, SITE_KEY)
    uri = URI_FMT.format(app=APP, access_key=access_key)

    sp = xmlrpclib.ServerProxy(uri)
    p = sp.pages.get_one({'site': site,
                          'page': page})
    output_stream.write(p['content'])


def upload(page, input_stream):

    config = load_config()
    access_key = config.get(SECTION_API, KEY_READWRITE_ACCESS_KEY)
    site = config.get(SECTION_API, SITE_KEY)
    uri = URI_FMT.format(app=APP, access_key=access_key)

    content = input_stream.read()

    sp = xmlrpclib.ServerProxy(uri)
    sp.pages.save_one({'site': site,
                       'page': page,
                       'content': content})


if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument('--page', '-p',
                        required=True,
                        dest='page')
    parser.add_argument('--upload', '-u',
                        dest='upload',
                        action='store_true')
    parser.add_argument('--download', '-d',
                        dest='download',
                        action='store_true')
    args = parser.parse_args()

    if args.download and args.upload:
        raise Exception('--download and --upload flags are exclusive')
    elif args.download:
        download(args.page, sys.stdout)
    elif args.upload:
        upload(args.page, sys.stdin)
    else:
        raise Exception('use --download or --upload flag')
