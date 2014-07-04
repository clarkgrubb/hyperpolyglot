#!/usr/bin/env python

import datetime
import os
import re
import sys
import xml.etree.ElementTree

ERROR_PAGE = re.compile(r'^\d{3}.html$')
DATE_FMT = '%Y-%m-%dT%H:%M:%S+00:00'
DOMAIN = 'http://hyperpolyglot.org'

builder = xml.etree.ElementTree.TreeBuilder()
builder.start('urlset',
              {'xmlns': 'http://www.sitemaps.org/schemas/sitemap/0.9'})

html_dir = sys.argv[1]

for filename in os.listdir(html_dir):
    if filename.endswith('.html') and not ERROR_PAGE.match(filename):
        rootname = filename[0:-5]
        if rootname == 'start':
            rootname = ''
        pathname = os.path.join(html_dir, filename)
        t = datetime.datetime.fromtimestamp(os.stat(pathname).st_mtime)

        builder.start('url', {})
        builder.start('loc', {})
        builder.data(DOMAIN + '/' + rootname)
        builder.end('loc')
        builder.start('lastmod', {})
        builder.data(t.strftime(DATE_FMT))
        builder.end('lastmod')
        builder.end('url')

builder.end('urlset')
print(xml.etree.ElementTree.tostring(builder.close()))
