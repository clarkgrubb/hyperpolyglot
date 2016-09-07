#!/usr/bin/env python
import re
import sys


def die(lineno, line, highlight, escape):
    raise Exception(
        'ERROR: lineno: {} highlight: {} escape: {} line: {}'.format(
            lineno, highlight, escape, line))

# Match '>@@', '<@@', '@@', '@<', '@>', '##gray|', or '##' in that order
RX_NEXT = re.compile(r'>@@|<@@|@@|@<|>@|##[a-zA-F0-9]+\||##')
RX_NEXT_INSIDE_HIGHLIGHT = re.compile(r'>@@|<@@|@@|@<|>@|##')

highlight = None
escape = None
for lineno, line in enumerate(sys.stdin, start=1):
    s = line
    while s:
        if highlight:
            md = RX_NEXT_INSIDE_HIGHLIGHT.search(s)
        else:
            md = RX_NEXT.search(s)
        if md:
            prematch = s[0:md.start(0)]
            match = md.group()
            postmatch = s[md.end(0):len(s)]

            sys.stdout.write(prematch)

            if md.group() == '>@@':
                if escape == '@<':
                    match = '>@'
                    postmatch = '@' + postmatch
                else:
                    sys.stdout.write('>')
                    match = '@@'
            elif md.group() == '<@@':
                if escape == '@@':
                    sys.stdout.write('<')
                    match = '@@'
                elif escape == '<@':
                    raise NotImplementedError('handle this situation')
                else:
                    match = '<@'
                    postmatch = '@' + postmatch

            if escape == '@@':
                sys.stdout.write(match)
                if match == '@@':
                    escape = None
            elif escape == '@<':
                sys.stdout.write(match)
                if match == '>@':
                    escape = None
            elif match == '@@':
                sys.stdout.write(match)
                escape = '@@'
            elif match == '@<':
                sys.stdout.write(match)
                escape = '@<'
            elif md.group() == '##':
                if highlight:
                    if highlight == 'gray':
                        sys.stdout.write(match)
                    highlight = None
                else:
                    sys.stdout.write(match)
            elif match.startswith('##'):
                if highlight:
                    die(lineno=lineno, line=line, escape=escape,
                        highlight=highlight)
                elif match == '##gray|':
                    highlight = 'gray'
                    sys.stdout.write(match)
                else:
                    highlight = 'not gray'
            else:
                die(lineno=lineno, line=line, escape=escape,
                    highlight=highlight)
            s = postmatch
        else:
            sys.stdout.write(s)
            s = None
