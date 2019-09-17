#!/usr/bin/env python3
"""
Reads lines of input containing Wikidot-style markup
from an input stream and writes the corresponding HTML to an
output stream.

## Markup

  BLOCK ELEMENTS:
    <blockquote>: >
    <div>: [[div id="..." class="..." style="..." data-...="..."]]
    <pre><code>: [[code type="..."]]
    <div class="math-equation" id="equation-...">: [[math]]
    <ul>: *
    <ol>: #
    <hn>: +
    <p>:
    <hr>: ----
    <table>: ||

  INLINE ELEMENTS:
    <em>: //
    <strong>: **
    <tt>: {{ }}
    <span style="text-decoration: line-through">: --
    <span style="text-decoration: underline">: __
    <sub>: ,,
    <sup>: ^^
    <span>: [[span]]
    <font color="...">:
    <font size="...">: [[size]]
    <a href="...">: [#
    <a name="...">: [[# ...]]
    <br>: _
    literal: @@
    html entity literal: @< >@

## Architecture

The *BlockParser* iterates through input by line and assigns each line
to an object of type *Block*.  If a *Block* object has inline content,
*lex* is used to tokenize the content and *InlineParser* is used to
convert the token stream to a tree of *Node* and *Text* objects.
*Block*s are rendered by calling the *close* method.  *Node*s and
*Text* are rendered by calling the *__str__* method.

## Debugging

    The following are sufficient for debugging:

        import pprint
        import traceback

        PP = pprint.PrettyPrinter(stream=sys.stderr)

        PP.pprint([1, [2, 3]])
        sys.stderr.write("DEBUG foo: {}\n".format(foo))
        traceback.print_stack()

    To diagnose a problem, first find a minimal input which causes the
    problem.

    To find out how the lexer is splitting the input into tokens, use
    PP.print(tokens) before str_lex() or token_lex() returns.

    In InlineParser.parse(), use debug statements to figure out which
    clause is getting triggered for each token.

    If a Node object is rendered incorrectly, inspect the attributes
    of the object when it renders in __str__().

    Put debug statements in Block subclass constructors or
    BlockParser.add_line() to diagnose problems with how Block objects
    are created.  Use traceback.print_stack() to figure out who the
    caller is.

    Put debug statements in Block.close() or the close() method of
    derived classes to inspect self.lines or self.matches if the Block
    object is not rendered correctly.

## Design Defects

 * BLOCK_TYPE_* constants unnecessary?  Just use object types
 * token_lex sometimes returns token objects, sometimes strings
 * row_to_cells contains logic also in the lexers

"""

import argparse
import html
import pprint
import re
import sys
# import traceback

PP = pprint.PrettyPrinter(stream=sys.stderr)

BLOCK_TYPE_CODE = 'code'
BLOCK_TYPE_MATH = 'math'
BLOCK_TYPE_P = 'p'
BLOCK_TYPE_UL = 'ul'
BLOCK_TYPE_OL = 'ol'
BLOCK_TYPE_BLOCKQUOTE = 'blockquote'
BLOCK_TYPE_TABLE = 'table'
BLOCK_TYPE_H1 = 'h1'
BLOCK_TYPE_H2 = 'h2'
BLOCK_TYPE_H3 = 'h3'
BLOCK_TYPE_H4 = 'h4'
BLOCK_TYPE_H5 = 'h5'
BLOCK_TYPE_H6 = 'h6'
BLOCK_TYPE_HR = 'hr'
BLOCK_TYPE_HN = '_hn'
BLOCK_TYPE_EMPTY = '_empty'

MULTILINE_BLOCK_TYPES = [BLOCK_TYPE_CODE,
                         BLOCK_TYPE_MATH,
                         BLOCK_TYPE_OL,
                         BLOCK_TYPE_P,
                         BLOCK_TYPE_TABLE,
                         BLOCK_TYPE_UL]

TOC_LITERAL = '[[toc]]'

RX_FULL_URL = re.compile(r'^(?P<scheme>[a-z]+):(?P<rest>.*)$')
RX_BLOCKQUOTE = re.compile(
    r'^(?P<greater_than_signs>>+)\s*(?P<content>.*?)(?P<br> _)?$')
RX_CODE_START = re.compile(
    r'^(?P<indent>\s*)(?P<raw_tag>\[\[code(\s+type="(?P<type>.*?)"\s*)?\]\])'
    r'(?P<content>.*)$')
RX_CODE_END = re.compile(r'^\[\[/code\]\]$')
RX_CODE_CONTENT = re.compile(r'^(?P<content>.*?)$')
RX_MATH_START = re.compile(
    r'^(?P<indent>\s*)(?P<raw_tag>\[\[math\]\])'
    r'(?P<content>.*)$')
RX_MATH_END = re.compile(r'^\[\[/math\]\]$')
RX_MATH_CONTENT = re.compile(r'^(?P<content>.*?)$')
RX_DIV_START = re.compile(
    r'^(?P<indent>\s*)(?P<raw_tag>\[\[div(?P<attributes>.*)\]\])$')
RX_DIV_ATTR = re.compile(r'^\s*(?P<name>[a-z0-9-]+)="(?P<value>.*?)"'
                         r'(?P<rest>.*)$')
RX_DIV_END = re.compile(r'^\[\[/div\]\]$')
RX_UL = re.compile(
    r'^(?P<indent>\s*)(?P<raw_tag>\*)\s+(?P<content>\S.*?)(?P<br> _)?$')
RX_OL = re.compile(
    r'^(?P<indent>\s*)(?P<raw_tag>\#)\s+(?P<content>\S.*?)(?P<br> _)?$')
RX_TABLE = re.compile(
    r'^(?P<indent>\s*)(?P<content>\|\|.*?)(?P<br> _)?$')
RX_HN = re.compile(
    r'^(?P<indent>\s*)'
    r'(?P<plus_signs>\+{1,6})'
    r'\s+'
    r'(?P<content>\S.*?)'
    r'(?P<br> _)?$')
RX_HR = re.compile(r'^(?P<indent>\s*)----(?P<content>)(?P<br> _)?$')
RX_EMPTY = re.compile(r'^\s*(?P<content>)(?P<br> _)?$')
RX_P = re.compile(r'^\s*(?P<content>.*?)(?P<br> _)?$')
RX_MARKERS = re.compile(r'(//|\*\*|\{\{|\}\}|@@|\[!--|--\]|--|__|,,|\^\^|'
                        r'\[\[span [^\]]+\]\]|\[\[/span\]\]|\[\[/size\]\]|'
                        r'\]\]|##)')
RX_WHITESPACE = re.compile(r'(\s+)')
RX_SPAN = re.compile(r'^\[\[span ([^\]]+)\]\]$')
RX_SIZE = re.compile(r'^\[\[size ([^\]]+)\]\]$')
RX_RGB = re.compile(r'^[a-fA-F0-9]{6}$')
RX_PARSE_TRIPLE_BRACKET = re.compile(
    r'^\[\[\[(?P<href>[^|]*)(\|(?P<name>.+))?\]\]\]$')
RX_PARSE_DOUBLE_BRACKET = re.compile(r'^\[\[#\s+(?P<anchor>.+)\]\]$')
RX_PARSE_SINGLE_BRACKET = re.compile(r'^\[(?P<href>\S+)\s+(?P<name>.+)\]$')
RX_TRIPLE_BRACKET = re.compile(
    r'(?P<token>^\[\[\[[^\]|]+(\|[^\]|]+)?\]\]\])(?P<text>.*)$')
RX_DOUBLE_BRACKET = re.compile(
    r'^(?P<token>\[\[[^\]]+\]\])(?P<text>.*)$')
RX_SINGLE_BRACKET = re.compile(
    r'^(?P<token>\[(?P<head>[^\]\s]+)[^\]]*\])(?P<text>.*)$')
RX_ESCAPE_CHAR = re.compile(r'@|<|>')
RX_DOUBLED_CHAR = re.compile(
    r'^(//|\*\*|\{\{|\}\}|--|__|,,|\^\^|\|\|)')
RX_COLOR_HEAD = re.compile(r'^(?P<token>##[a-zA-Z][a-zA-Z0-9 ]*\|)'
                           '(?P<text>.*)$')
RX_LEAD_WHITESPACE = re.compile(r'^(?P<token>\s+)(?P<text>.*)$')
RX_URL_FRAGMENT = re.compile(r'^#[a-zA-Z0-9][a-zA-Z0-9-_]*$')
RX_URL = re.compile(
    r'^(?P<token>https?://[a-zA-Z0-9-._~:/#&?=+,;]*[a-zA-Z0-9-_~/#&?=+])'
    r'(?P<text>.*)$')
RX_IMAGE = re.compile(r'^\[\[(?P<alignment>=?)image\s+(?P<src>\S+)\s*(?P<attrs>.*)\]\]$')
RX_IMAGE_ATTR = re.compile(
    r'^\s*(?P<attr>[^ =]+)'
    r'\s*=\s*'
    r'"(?P<value>[^"]*)"'
    r'\s*(?P<rest>.*)$')
RX_SPACE = re.compile(r' ')
RX_FULL_ROW = re.compile(r'^\|\|(?P<row>.*)\|\|$')
RX_START_ROW = re.compile(r'^\|\|(?P<row>.*)$')
RX_END_ROW = re.compile(r'^(?P<row>.*)\|\|$')
RX_TAGGED_CELL = re.compile(r'^(?P<tag>~|<|=|>)\s+(?P<content>.*)$')
RX_EMPTY_PARAGRAPH = re.compile(r'^(<br />|\s)*$', re.M)
RX_BLANK_LINE = re.compile(r'^\s*$')
RX_TABLE_CELL_LEXER = re.compile(r'(\|\||@|<|>)')


class NullOutputStream:
    def write(self, s):
        pass


class ClosureNode:
    def __init__(self, is_closed):
        self.is_closed = is_closed

    def closed(self):
        return self.is_closed


OPEN_NODE = ClosureNode(False)
CLOSED_NODE = ClosureNode(True)


class Node:
    def __init__(self, wikidot, raw_tag='', open_tag='', close_tag=None):
        self.wikidot = wikidot
        self.children = []
        self.raw_tag = raw_tag
        self.open_tag = open_tag
        self.close_tag = open_tag if close_tag is None else close_tag
        self.closure = OPEN_NODE

    def set_closure(self, nd=True):
        self.closure = nd

    def closed(self):
        return self.closure.closed()

    def __str__(self):
        if not self.children:
            first = ''
            rest = ''
        elif len(self.children) == 1:
            if self.children[0] == ' ':
                first = ' '
                rest = ''
            else:
                first = ''
                rest = str(self.children[0])
        else:
            if self.children[0] == ' ':
                first = ' '
                rest = ''.join([str(child) for child in self.children[1:]])
            else:
                first = ''
                rest = ''.join([str(child) for child in self.children])

        if self.closed():
            if rest:
                return '{}<{}>{}</{}>'.format(first,
                                              self.open_tag,
                                              rest,
                                              self.close_tag)
            return first
        return '{}{}{}{}'.format(first, self.raw_tag, rest, '')


class Italic(Node):
    def __init__(self, wikidot, raw_tag='//'):
        Node.__init__(self, wikidot, raw_tag, 'em')


class Bold(Node):
    def __init__(self, wikidot, raw_tag='**'):
        Node.__init__(self, wikidot, raw_tag, 'strong')


class FixedWidth(Node):
    def __init__(self, wikidot, raw_tag='{{'):
        Node.__init__(self, wikidot, raw_tag, 'tt')


class StrikeThru(Node):
    def __init__(self, wikidot, raw_tag='--'):
        Node.__init__(self,
                      wikidot,
                      raw_tag,
                      'span style="text-decoration: line-through;"',
                      'span')


class Underline(Node):
    def __init__(self, wikidot, raw_tag='__'):
        Node.__init__(self,
                      wikidot,
                      raw_tag,
                      'span style="text-decoration: underline;"',
                      'span')


class Subscript(Node):
    def __init__(self, wikidot, raw_tag=',,'):
        Node.__init__(self, wikidot, raw_tag, 'sub')


class Superscript(Node):
    def __init__(self, wikidot, raw_tag='^^'):
        Node.__init__(self, wikidot, raw_tag, 'sup')


class Span(Node):
    def __init__(self, wikidot, raw_tag, tag):
        Node.__init__(self, wikidot, raw_tag, tag, 'span')

    def __str__(self):
        return '{}{}{}'.format(
            '<{}>'.format(self.open_tag),
            ''.join([str(child) for child in self.children]).rstrip(),
            '</span>')


class Color(Node):
    def __init__(self, wikidot, raw_tag, tag):
        Node.__init__(self, wikidot, raw_tag, tag, 'span')


class Size(Node):
    def __init__(self, wikidot, raw_tag, tag):
        Node.__init__(self, wikidot, raw_tag, tag, 'span')


class Literal(Node):
    def __init__(self, wikidot, raw_tag, tag):
        Node.__init__(self, wikidot, raw_tag, tag, 'span')

    def __str__(self):
        s = ''.join([str(child) for child in self.children])
        s = RX_SPACE.sub('&#32;', s)
        return '<{}>{}</{}>'.format(self.open_tag,
                                    s,
                                    self.close_tag)


class HTMLEntityLiteral(Node):
    def __init__(self, wikidot, raw_tag, tag):
        Node.__init__(self, wikidot, raw_tag, tag, 'span')

    def __str__(self):
        s = ''.join([str(child) for child in self.children])
        s = RX_SPACE.sub('&#32;', s)
        return '<{}>{}</{}>'.format(self.open_tag,
                                    s,
                                    self.close_tag)


class Text:
    def __init__(self, wikidot, raw_tag='', open_tag='', close_tag=None):
        self.wikidot = wikidot
        self.raw_tag = raw_tag
        self.open_tag = open_tag
        self.close_tag = open_tag if close_tag is None else close_tag

    def __str__(self):
        return self.raw_tag


class Link(Text):
    def __init__(self, wikidot, raw_tag, href, content):
        self.wikidot = wikidot
        full_href = href
        match = RX_FULL_URL.search(href)
        if not match and not href.startswith('#'):
            full_href = '{}/{}{}'.format(self.wikidot.link_prefix.rstrip('/'),
                                         href.lstrip('/'),
                                         self.wikidot.link_suffix)
        Text.__init__(self, wikidot, raw_tag, 'a href="{}"'.format(full_href), 'a')
        self.content = content

    def __str__(self):
        return '<{}>{}</{}>'.format(self.open_tag,
                                    self.content,
                                    self.close_tag)


class Anchor(Text):
    def __init__(self, wikidot, raw_tag, name):
        Text.__init__(self, wikidot, raw_tag, 'a name="{}"'.format(name), 'a')

    def __str__(self):
        return '<{}></{}>'.format(self.open_tag, self.close_tag)


class Image(Text):
    ATTRS = ['title', 'width', 'height', 'style', 'class', 'size']

    def __init__(self, wikidot, raw_tag, src, attrs, alignment):
        self.wikidot = wikidot
        Text.__init__(self,
                      wikidot,
                      raw_tag,
                      'img')
        self.src = src
        self.attrs = attrs
        self.alignemnt = alignment

    def __str__(self):
        s = '<img src="{}{}"'.format(self.wikidot.image_prefix, self.src)
        for attr in Image.ATTRS:
            value = self.attrs.get(attr, None)
            if value:
                s += ' {}="{}"'.format(attr, value)
        value = self.attrs.get('alt', self.src)
        s += ' alt="{}"'.format(value)
        value = self.attrs.get('class', 'image')
        s += ' class="{}"'.format(value)
        s += ' />'
        link = self.attrs.get('link', None)
        if link:
            s = '<a href="{}">{}</a>'.format(link, s)
        if self.alignemnt == '=':
            s = '<div class="image-container aligncenter">{}</div>'.format(s)

        return s


class LineBreak(Node):
    def __init__(self, wikidot):
        Node.__init__(self, wikidot)

    def __str__(self):
        return '<br />\n'


def str_lex(text):
    tokens = []
    prefix_and_text = text
    prefix = ''
    text_i = 0
    while text:
        if text.startswith('['):
            if text.startswith('[!--'):
                tokens.append('[!--')
                prefix_and_text = text[4:]
                text = prefix_and_text
                text_i = 0
                continue
            md = RX_TRIPLE_BRACKET.search(text)
            if md:
                if prefix:
                    tokens.append(prefix)
                    prefix = ''
                tokens.append(md.group('token'))
                prefix_and_text = md.group('text')
                text = prefix_and_text
                text_i = 0
                continue
            md = RX_DOUBLE_BRACKET.search(text)
            if md:
                if prefix:
                    tokens.append(prefix)
                    prefix = ''
                tokens.append(md.group('token'))
                prefix_and_text = md.group('text')
                text = prefix_and_text
                text_i = 0
                continue
            md = RX_SINGLE_BRACKET.search(text)
            if md:
                head = md.group('head')
                if RX_URL.search(head) or RX_URL_FRAGMENT.search(head):
                    if prefix:
                        tokens.append(prefix)
                        prefix = ''
                    tokens.append(md.group('token'))
                    prefix_and_text = md.group('text')
                    text = prefix_and_text
                    text_i = 0
                    continue
        if text.startswith('##'):
            if prefix:
                tokens.append(prefix)
                prefix = ''
            md = RX_COLOR_HEAD.search(text)
            if md:
                tokens.append(md.group('token'))
                prefix_and_text = md.group('text')
                text = prefix_and_text
                text_i = 0
                continue
            tokens.append(text[0:2])
            prefix_and_text = text[2:]
            text = prefix_and_text
            text_i = 0
            continue
        md = RX_LEAD_WHITESPACE.search(text)
        if md:
            if prefix:
                tokens.append(prefix)
                prefix = ''
            tokens.append(md.group('token'))
            prefix_and_text = md.group('text')
            text = prefix_and_text
            text_i = 0
            continue
        if text.startswith('--]'):
            tokens.append('--]')
            prefix_and_text = text[3:]
            text = prefix_and_text
            text_i = 0
            continue
        md = RX_ESCAPE_CHAR.search(text)
        if md:
            tokens.append(text[0:1])
            prefix_and_text = text[1:]
            text = prefix_and_text
            text_i = 0
            continue
        md = RX_DOUBLED_CHAR.search(text)
        if md:
            if prefix:
                tokens.append(prefix)
                prefix = ''
            tokens.append(text[0:2])
            prefix_and_text = text[2:]
            text = prefix_and_text
            text_i = 0
            continue
        if text.startswith('http'):
            md = RX_URL.search(text)
            if md:
                tokens.append(md.group('token'))
                prefix_and_text = md.group('text')
                text = prefix_and_text
                text_i = 0
                continue
        text_i += 1
        prefix = prefix_and_text[0:text_i]
        text = prefix_and_text[text_i:]

    if prefix:
        tokens.append(prefix)

    return tokens


class Token:
    pass


class LiteralStartToken(Token):
    pass


class LiteralEndToken(Token):
    pass


class HTMLEntityLiteralStartToken(Token):
    pass


class HTMLEntityLiteralEndToken(Token):
    pass


LITERAL_START_TOKEN = LiteralStartToken()
LITERAL_END_TOKEN = LiteralEndToken()
HTML_ENTITY_LITERAL_START_TOKEN = HTMLEntityLiteralStartToken()
HTML_ENTITY_LITERAL_END_TOKEN = HTMLEntityLiteralEndToken()


def count_literal_escapes(str_tokens):
    prev_s = ''
    literal_cnt = 0
    for s in str_tokens:
        if prev_s + s == '@@':
            literal_cnt += 1
            prev_s = ''
        else:
            prev_s = s

    return literal_cnt


def token_lex(text):
    last_idx = -1
    last_html_entity_idx = -1
    prev_s = ''
    str_tokens = str_lex(text)
    tokens = []
    remaining_literal_cnt = count_literal_escapes(str_tokens)

    for s in str_tokens:
        if prev_s + s == '@@' and last_idx > -1:
            remaining_literal_cnt -= 1
            tokens.append(LITERAL_END_TOKEN)
            tokens[last_idx] = LITERAL_START_TOKEN
            last_idx = -1
            prev_s = ''
        elif prev_s + s == '@@' and remaining_literal_cnt > 1:
            remaining_literal_cnt -= 1
            tokens.append('@@')
            last_idx = len(tokens) - 1
            prev_s = ''
        elif prev_s + s == '@<':
            tokens.append('@<')
            if last_html_entity_idx == -1:
                last_html_entity_idx = len(tokens) - 1
            prev_s = ''
        elif prev_s + s == '>@':
            if last_html_entity_idx > -1:
                tokens[last_html_entity_idx] = HTML_ENTITY_LITERAL_START_TOKEN
                last_html_entity_idx = -1
                tokens.append(HTML_ENTITY_LITERAL_END_TOKEN)
                prev_s = ''
            else:
                tokens.append('>')
                prev_s = '@'
        elif s in {'@', '>'}:
            if prev_s:
                tokens.append(prev_s)
            prev_s = s
        else:
            if prev_s:
                tokens.append(prev_s)
                prev_s = ''
            tokens.append(s)

    return tokens


class InlineParser:
    def __init__(self, wikidot):
        self.wikidot = wikidot
        self.italic = False
        self.bold = False
        self.escape_literal = False
        self.no_escape_literal = False
        self.fixed_width = False
        self.strike_thru = False
        self.underline = False
        self.subscript = False
        self.superscript = False
        self.comment = False
        self.span_depth = 0
        self.color = False
        self.size = False
        self.top_node = Node(self.wikidot)
        self.nodes = [self.top_node]
        self.tokens = None

    def __str__(self):
        return str(self.top_node)

    def set_flag(self, cls, value):
        if cls == Italic:
            self.italic = value
        elif cls == Bold:
            self.bold = value
        elif cls == FixedWidth:
            self.fixed_width = value
        elif cls == StrikeThru:
            self.strike_thru = value
        elif cls == Underline:
            self.underline = value
        elif cls == Subscript:
            self.subscript = value
        elif cls == Superscript:
            self.superscript = value
        elif cls == Literal:
            self.escape_literal = value
        elif cls == HTMLEntityLiteral:
            self.no_escape_literal = value
        elif cls == Span:
            if value:
                self.span_depth += 1
            else:
                self.span_depth -= 1
            if self.span_depth < 0:
                raise Exception('negative span depth')
        elif cls == Color:
            self.color = value
        elif cls == Size:
            self.size = value
        elif cls == Node:
            pass
        else:
            raise Exception('unknown class: {}'.format(cls))

    def remove_flag(self, cls):
        self.set_flag(cls, False)

    def add_flag(self, cls):
        self.set_flag(cls, True)

    def remove_all_nodes(self):
        removed_nodes = []
        while self.nodes:
            nd = self.nodes.pop()
            removed_nodes.append(nd)
            self.remove_flag(type(nd))

        return removed_nodes

    def restore_all_nodes(self, removed_nodes):
        self.top_node = type(removed_nodes.pop())(self.wikidot)
        self.nodes = [self.top_node]
        self.restore_nodes(removed_nodes)

    def restore_nodes(self, removed_nodes):
        while removed_nodes:
            old_nd = removed_nodes.pop()
            new_nd = type(old_nd)('')
            old_nd.set_closure(new_nd)
            self.add_node(new_nd)

    def remove_nodes_to_class(self, cls_to_remove):
        removed_nodes = []
        while True:
            if not self.nodes:
                raise Exception('not on stack: {}'.format(cls_to_remove))
            nd = self.nodes.pop()
            removed_nodes.append(nd)
            self.remove_flag(type(nd))
            if isinstance(nd, cls_to_remove):
                break

        return removed_nodes

    def remove_node(self, cls_to_remove):
        removed_nodes = self.remove_nodes_to_class(cls_to_remove)
        nd = removed_nodes.pop()
        self.restore_nodes(removed_nodes)

        return nd

    def add_node(self, nd):
        self.nodes[-1].children.append(nd)
        self.nodes.append(nd)
        self.add_flag(type(nd))

    def add_text(self, s):
        self.nodes[-1].children.append(s)

    def handle_token(self, i, raw_tag, inside_tag, cls):
        tokens = self.tokens
        if inside_tag:
            if i > 0 and not RX_WHITESPACE.match(tokens[i - 1]):
                nd = self.remove_node(cls)
                nd.set_closure(CLOSED_NODE)
            else:
                self.add_text(raw_tag)
        else:
            if i < len(tokens) - 1 and not RX_WHITESPACE.match(tokens[i + 1]):
                self.add_node(cls(self.wikidot))
            else:
                self.add_text(raw_tag)

    def parse_image_attrs(self, attrs):
        d = {}
        while True:
            md = RX_IMAGE_ATTR.search(attrs)
            if md:
                d[md.group('attr')] = md.group('value')
                attrs = md.group('rest')
            else:
                break

        return d

    def parse_image(self, token):
        md = RX_IMAGE.search(token)
        if md:
            src = md.group('src')
            alignment = md.group('alignment')
            attrs = self.parse_image_attrs(md.group('attrs'))
            self.add_text(Image(self.wikidot, token, src, attrs, alignment))
        else:
            self.add_text(token)

    def parse(self, tokens):
        self.tokens = tokens
        for i, token in enumerate(tokens):
            if self.comment:
                if token != '--]':
                    pass
                elif token == '--]':
                    self.comment = False
            elif token == '[!--':
                self.comment = True
            elif isinstance(token, LiteralEndToken) and self.escape_literal:
                self.escape_literal = False
                self.remove_node(Literal)
            elif isinstance(token, LiteralStartToken):
                self.escape_literal = True
                self.add_node(Literal(
                    self.wikidot,
                    '@@',
                    'span style="white-space: pre-wrap;"'))
            elif isinstance(token, HTMLEntityLiteralEndToken) \
                    and self.no_escape_literal:
                self.no_escape_literal = False
                self.remove_node(HTMLEntityLiteral)
            elif isinstance(token, HTMLEntityLiteralEndToken):
                self.add_text(html.escape('>@'))
            elif self.escape_literal:
                self.add_text(html.escape(token))
            elif self.no_escape_literal:
                self.add_text(token)
            elif isinstance(token, HTMLEntityLiteralStartToken):
                self.no_escape_literal = True
                self.add_node(HTMLEntityLiteral(
                    self.wikidot,
                    '@@',
                    'span style="white-space: pre-wrap;"'))
            elif not isinstance(token, str):
                raise Exception('expected token to be a string: ' +
                                str(type(token)) + ': ' +
                                str(token))
            elif RX_WHITESPACE.match(token):
                self.add_text(' ')
            elif token.startswith('[[span'):
                md = RX_SPAN.search(token)
                if md:
                    attributes = md.groups()[0]
                    self.add_node(Span(self.wikidot, token, 'span {}'.format(attributes)))
                else:
                    self.add_text(token)
            elif token == '[[/span]]':
                if self.span_depth > 0:
                    nd = self.remove_node(Span)
                    nd.set_closure(CLOSED_NODE)
                else:
                    self.add_text(token)
            elif token.startswith('[[size'):
                md = RX_SIZE.search(token)
                if md:
                    attributes = md.groups()[0]
                    self.add_node(
                        Size(self.wikidot,
                             token,
                             'span style="font-size:{};"'.format(attributes)))
                else:
                    self.add_text(token)
            elif token == '[[/size]]':
                if self.size:
                    nd = self.remove_node(Size)
                    nd.set_closure(CLOSED_NODE)
                else:
                    self.add_text(token)
            elif token.startswith('[[image'):
                self.parse_image(token)
            elif token.startswith('[[=image'):
                self.parse_image(token)
            elif token.startswith('[[['):
                md = RX_PARSE_TRIPLE_BRACKET.search(token)
                if md:
                    name = md.group('name') or md.group('href')
                    self.add_text(Link(self.wikidot,
                                       token,
                                       md.group('href'),
                                       name))
                else:
                    self.add_text(token)
            elif token.startswith('[['):
                md = RX_PARSE_DOUBLE_BRACKET.search(token)
                if md:
                    self.add_text(Anchor(self.wikidot, token, md.group('anchor')))
                else:
                    self.add_text(token)
            elif token.startswith('['):
                md = RX_PARSE_SINGLE_BRACKET.search(token)
                if md:
                    self.add_text(
                        Link(self.wikidot, token, md.group('href'), md.group('name')))
                else:
                    self.add_text(token)
            elif token == '##':
                if self.color:
                    nd = self.remove_node(Color)
                    nd.set_closure(CLOSED_NODE)
                else:
                    self.add_text(token)
            elif token.startswith('##'):
                if self.color:
                    raise Exception('FIXME: nested color')
                if token.endswith('|'):
                    color = token[2:-1]
                    if RX_RGB.search(color):
                        tag = 'span style="color: #{}"'.format(color.lower())
                    else:
                        tag = 'span style="color: {}"'.format(color)
                    self.add_node(Color(self.wikidot, token, tag))
                else:
                    self.add_text(token)
            elif token == '--':
                self.handle_token(i, '--', self.strike_thru, StrikeThru)
            elif token == '__':
                self.handle_token(i, '__', self.underline, Underline)
            elif token == '//':
                self.handle_token(i, '//', self.italic, Italic)
            elif token == '**':
                self.handle_token(i, '**', self.bold, Bold)
            elif token == ',,':
                self.handle_token(i, ',,', self.subscript, Subscript)
            elif token == '^^':
                self.handle_token(i, '^^', self.superscript, Superscript)
            elif token == '{{':
                if not self.fixed_width:
                    if i < len(tokens) - 1 and \
                       not RX_WHITESPACE.match(tokens[i + 1]):
                        self.add_node(FixedWidth(self.wikidot))
                    else:
                        self.add_text('{{')
            elif token == '}}':
                if self.fixed_width:
                    if i > 0 and not RX_WHITESPACE.match(tokens[i - 1]):
                        nd = self.remove_node(FixedWidth)
                        nd.set_closure(CLOSED_NODE)
                    else:
                        self.add_text('}}')
            elif token.startswith('http'):
                md = RX_URL.search(token)
                if md:
                    self.add_text(Link(self.wikidot, token, token, token))
                else:
                    self.add_text(html.escape(token))
            else:
                self.add_text(html.escape(token))

        return self.top_node


def analyze_line(line, current_block):
    if not current_block or current_block.block_type != BLOCK_TYPE_TABLE:
        md = RX_UL.search(line)
        if md:
            return BLOCK_TYPE_UL, md
        md = RX_OL.search(line)
        if md:
            return BLOCK_TYPE_OL, md
        md = RX_HN.search(line)
        if md:
            return BLOCK_TYPE_HN, md
        md = RX_HR.search(line)
        if md:
            return BLOCK_TYPE_HR, md
    md = RX_TABLE.search(line)
    if md:
        return BLOCK_TYPE_TABLE, md
    md = RX_EMPTY.search(line)
    if md:
        return BLOCK_TYPE_EMPTY, md
    md = RX_P.search(line)
    if md:
        return BLOCK_TYPE_P, md

    raise Exception('unparseable line: {}'.format(line))


class Block:
    def __init__(self, wikidot, line, lineno, block_type=None, match=None):
        self.wikidot = wikidot
        self.lines = [line]
        self.linenos = [lineno]
        if block_type:
            self.block_type = block_type
            self.matches = [match]
        else:
            self.block_type, match = analyze_line(line, None)
            self.matches.append(match)
        self.tag = self._tag()

    def add_line(self, line, lineno,
                 block_type=None, match=None, continued=False):
        self.lines.append(line)
        self.linenos.append(lineno)
        if block_type is None:
            block_type, match = analyze_line(line, None)
        if not continued and \
           block_type != BLOCK_TYPE_P and \
           block_type != BLOCK_TYPE_EMPTY and \
           block_type != self.block_type:
            raise Exception('block type mismatch: {}: {}'.format(
                self.block_type, block_type))
        self.matches.append(match)

    def _tag(self):
        return self.block_type

    def multiline_type(self):
        return self.block_type in MULTILINE_BLOCK_TYPES

    def write_open_tag(self, output_stream):
        output_stream.write('<{}>'.format(self.tag))

    def content(self):
        parser = InlineParser(self.wikidot)
        for match in self.matches:
            parser.parse(token_lex(match.group('content')))

        return str(parser.top_node)

    def write_content(self, parser, output_stream):
        for match in self.matches:
            parser.parse(token_lex(match.group('content')))
            output_stream.write(str(parser.top_node))

    def write_close_tag(self, output_stream):
        output_stream.write('</{}>\n'.format(self.tag))

    def close(self, output_stream):
        parser = InlineParser(self.wikidot)
        self.write_open_tag(output_stream)
        self.write_content(parser, output_stream)
        self.write_close_tag(output_stream)


class TOC:
    def __init__(self, wikidot):
        self.wikidot = wikidot
        self.headers = []

    def add_header(self, header):
        self.headers.append({
            'n': header.n(),
            'toc_number': header.toc_number,
            'text': header.content()
        })

    def close(self, output_stream):
        output_stream.write('<div id="toc">\n')
        output_stream.write('<div class="title">Table of Contents</div>\n')
        output_stream.write('<div id="toc-list">\n')
        for header in self.headers:
            output_stream.write('<div style="margin-left: {}em;">\n'.format(header['n'] + 1))
            output_stream.write('<a href="#toc{}">{}</a>\n'.format(header['toc_number'],
                                                                   header['text']))
            output_stream.write('</div>\n')
        output_stream.write('</div>\n')
        output_stream.write('</div>\n')


class Header(Block):
    def __init__(self, wikidot, line, lineno, match):
        Block.__init__(self, wikidot, line, lineno, BLOCK_TYPE_HN, match)
        self.wikidot = wikidot
        self.toc_number = self.wikidot.next_toc_number
        self.wikidot.next_toc_number += 1
        self.wikidot.toc.add_header(self)

    def write_open_tag(self, output_stream):
        output_stream.write('<{} id="toc{}"><span>'.format(self.tag,
                                                           self.toc_number))

    def write_close_tag(self, output_stream):
        output_stream.write('</span></{}>\n'.format(self.tag))

    def n(self):
        return len(self.matches[0].group('plus_signs'))

    def _tag(self):
        return 'h{}'.format(self.n())


class HorizontalRule(Block):
    def __init__(self, wikidot, line, lineno, match):
        Block.__init__(self, wikidot, line, lineno, BLOCK_TYPE_HR, match)

    def close(self, output_stream):
        output_stream.write('<hr />\n')


class Table(Block):
    def __init__(self, wikidot, line, lineno, match):
        Block.__init__(self, wikidot, line, lineno, BLOCK_TYPE_TABLE, match)
        self.wikidot = wikidot
        self.cell_type = 'td'
        self.colspan = 1
        self.text_align = None
        self.cell_content = ''
        self.parser = None

    def start_cell(self):
        self.parser = InlineParser(self.wikidot)

    def add_cell_content(self, content):
        self.parser.parse(token_lex(content))

    def add_line_break(self):
        self.parser.add_text(self.wikidot.LINE_BREAK)

    def end_cell(self, output_stream):
        output_stream.write('<{}>{}</{}>\n'.format(self.open_cell_tag(),
                                                   str(self.parser.top_node),
                                                   self.cell_type))

    def analyze_cell(self, cell):
        md = RX_TAGGED_CELL.search(cell)
        if md:
            tag = md.group('tag')
            self.cell_content = md.group('content')
        else:
            tag = ''
            self.cell_content = cell

        if tag == '~':
            self.cell_type = 'th'
        else:
            self.cell_type = 'td'

        if tag == '<':
            self.text_align = 'left'
        elif tag == '=':
            self.text_align = 'center'
        elif tag == '>':
            self.text_align = 'right'
        else:
            self.text_align = ''

    def open_cell_tag(self):
        components = [self.cell_type]
        if self.colspan > 1:
            components.append('colspan="{}"'.format(self.colspan))
        if self.text_align:
            components.append(
                'style="text-align: {};"'.format(self.text_align))

        return ' '.join(components)

    def print_middle_of_cell(self, cell):
        self.add_cell_content(cell)
        self.add_line_break()

    def print_start_of_cell(self, cell):
        self.analyze_cell(cell)
        self.start_cell()
        self.add_cell_content(self.cell_content)
        self.add_line_break()
        self.colspan = 1

    def print_end_of_cell(self, output_stream, cell):
        self.add_cell_content(cell)
        self.end_cell(output_stream)

    def print_full_cell(self, output_stream, cell):
        self.analyze_cell(cell)
        self.start_cell()
        self.add_cell_content(self.cell_content)
        self.end_cell(output_stream)
        self.colspan = 1

    def print_cells(self, output_stream, first_cell, cells, last_cell,
                    lone_cell=None):
        self.colspan = 1
        if lone_cell is not None:
            self.print_middle_of_cell(lone_cell)
        if first_cell is not None:
            self.print_end_of_cell(output_stream, first_cell)
        for cell in cells:
            if not cell:
                self.colspan += 1
            else:
                self.print_full_cell(output_stream, cell)
        if last_cell is not None:
            self.print_start_of_cell(last_cell)

    def row_to_cells(self, row):
        return row.split('||')

    def row_to_cells_(self, row):
        tokens = row.split(RX_TABLE_CELL_LEXER)
        cells = []
        current_cell = ''
        prev_s = ''
        literal_contents = None
        html_entity_literal_contents = None

        for s in tokens:
            if prev_s + s == '@@':
                if literal_contents is not None:
                    current_cell += literal_contents
                    literal_contents = None
                elif html_entity_literal_contents is not None:
                    html_entity_literal_contents += '@@'
                else:
                    pass
            elif prev_s + s == '@<':
                pass
            elif prev_s + s == '>@':
                pass
            elif s in {'@', '>'}:
                pass
            elif s == '||':
                if literal_contents or html_entity_literal_contents:
                    current_cell += '||'
                else:
                    cells.append(current_cell)
                    current_cell = ''
            else:
                if prev_s:
                    current_cell += prev_s
                    prev_s = ''
                current_cell += s

        if current_cell:
            cells.append(current_cell)

        return cells

    def close(self, output_stream):
        output_stream.write('<table class="wiki-content-table">\n')
        inside_cell = False
        for i, match in enumerate(self.matches):
            try:
                content = match.group('content')
            except IndexError:
                content = ''
            try:
                md = RX_FULL_ROW.search(content)
                if md:
                    if inside_cell:
                        raise Exception('unterminated cell')
                    row = md.group('row')
                    cells = self.row_to_cells(row)
                    output_stream.write('<tr>\n')
                    self.print_cells(output_stream, None, cells, None)
                    output_stream.write('</tr>\n')
                    inside_cell = False
                    continue
                md = RX_START_ROW.search(content)
                if md:
                    if inside_cell:
                        raise Exception('unterminated cell')
                    row = md.group('row')
                    cells = self.row_to_cells(row)
                    last_cell = cells.pop()
                    output_stream.write('<tr>\n')
                    self.print_cells(output_stream, None, cells, last_cell)
                    inside_cell = True
                    continue
                md = RX_END_ROW.search(content)
                if md:
                    if not inside_cell:
                        raise Exception('not inside cell')
                    row = md.group('row')
                    cells = self.row_to_cells(row)
                    first_cell = cells.pop(0)
                    self.print_cells(output_stream, first_cell, cells, None)
                    output_stream.write('</tr>\n')
                    inside_cell = False
                    continue
                row = content
                cells = self.row_to_cells(row)
                if len(cells) == 1:
                    lone_cell = cells.pop()
                    self.print_cells(output_stream, None, [], None, lone_cell)
                else:
                    first_cell = cells.pop(0)
                    last_cell = cells.pop()
                    self.print_cells(output_stream,
                                     first_cell,
                                     cells,
                                     last_cell)
                inside_cell = True
            except Exception:
                if i < len(self.linenos):
                    sys.stderr.write(
                        "ERROR line number at source: {}\n".format(
                            self.linenos[i]))
                raise
        output_stream.write('</table>\n')


class List(Block):
    def __init__(self, wikidot, line, lineno, match):
        self.raw_tag = match.group('raw_tag')
        Block.__init__(self,
                       wikidot,
                       line,
                       lineno,
                       self.raw_tag_to_tag(self.raw_tag),
                       match)
        self.opened_lists = None
        self.inside_line = None

    def raw_tag_to_tag(self, raw_tag):
        if raw_tag == '*':
            return BLOCK_TYPE_UL
        if raw_tag == '#':
            return BLOCK_TYPE_OL
        raise Exception('unrecognized raw tag {}'.format(raw_tag))

    def open_list(self, output_stream, tag, indent):
        if self.inside_line.get(indent - 1, False):
            output_stream.write('\n')
        elif indent > 0:
            self.open_line(output_stream, indent - 1)
            output_stream.write('\n')
        output_stream.write('<{}>\n'.format(tag))
        self.opened_lists.append(tag)

    def close_list(self, output_stream, indent):
        if self.inside_line.get(indent, False):
            self.close_line(output_stream, indent)
        tag = self.opened_lists.pop()
        output_stream.write('</{}>\n'.format(tag))

    def open_line(self, output_stream, indent):
        if self.inside_line.get(indent, False):
            self.close_line(output_stream, indent)
        output_stream.write('<li>')
        self.inside_line[indent] = True

    def close_line(self, output_stream, indent):
        output_stream.write('</li>\n')
        self.inside_line[indent] = False

    def write_list_content(self, output_stream, node):
        output_stream.write(str(node))

    def close(self, output_stream):
        parser = InlineParser(self.wikidot)
        node_tag_indent = []
        triple = None
        for match in self.matches:
            if not triple:
                triple = [None,
                          self.raw_tag_to_tag(match.group('raw_tag')),
                          len(match.group('indent'))]
            content = match.group('content')
            parser.parse(token_lex(content))
            if match.group('br'):
                parser.add_text(self.wikidot.LINE_BREAK)
            else:
                triple[0] = parser.top_node
                node_tag_indent.append(triple)
                triple = None
                removed_nodes = parser.remove_all_nodes()

                parser.restore_all_nodes(removed_nodes)

        last_indent = -1
        self.opened_lists = []
        self.inside_line = {}
        for node, tag, indent in node_tag_indent:
            for i in range(indent, last_indent):
                self.close_list(output_stream, i + 1)
            for i in range(last_indent, indent):
                self.open_list(output_stream, tag, i + 1)
            self.open_line(output_stream, indent)
            self.write_list_content(output_stream, node)
            last_indent = indent
        for i in range(-1, last_indent):
            self.close_list(output_stream, i + 1)


class Empty(Block):
    def __init__(self, wikidot, line, lineno, match):
        Block.__init__(self, wikidot, line, lineno, BLOCK_TYPE_EMPTY, match)

    def close(self, output_stream):
        pass


class Code(Block):
    def __init__(self, wikidot, line, lineno, match):
        self.input_nesting_level = 0
        self.output_nesting_level = 0
        Block.__init__(self, wikidot, line, lineno, BLOCK_TYPE_CODE, match)

    def write_open_tag(self, output_stream):
        output_stream.write('<div class="code">\n')
        output_stream.write('<pre>\n')
        output_stream.write('<code>')

    def write_code_content(self, output_stream):
        n = self.output_nesting_level
        while n > 0:
            output_stream.write('[[code]]\n')
            n -= 1

        for i, match in enumerate(self.matches):
            if i == 0 and RX_BLANK_LINE.search(match.group('content')):
                continue
            output_stream.write(html.escape(match.group('content'), quote=True))
            if i < len(self.matches) - 1:
                output_stream.write('\n')

        while self.output_nesting_level > 0:
            output_stream.write('\n[[/code]]')
            self.output_nesting_level -= 1

    def write_close_tag(self, output_stream):
        output_stream.write('</code>\n')
        output_stream.write('</pre></div>\n')

    def close(self, output_stream):
        self.write_open_tag(output_stream)
        self.write_code_content(output_stream)
        self.write_close_tag(output_stream)


class Math(Block):
    def __init__(self, wikidot, line, lineno, match):
        self.input_nesting_level = 0
        self.output_nesting_level = 0
        Block.__init__(self, wikidot, line, lineno, BLOCK_TYPE_MATH, match)
        self.eqn_number = self.wikidot.next_eqn_number
        self.wikidot.next_eqn_number += 1

    def write_open_tag(self, output_stream):
        output_stream.write(
            '<span class="equation-number">({})</span>\n'.format(
                self.eqn_number))
        output_stream.write(
            '<div class="math-equation" id="equation-{}">'.format(
                self.eqn_number))
        output_stream.write(r'$$ \begin{align} ')

    def write_math_content(self, output_stream):
        n = self.output_nesting_level
        while n > 0:
            output_stream.write('[[math]]\n')
            n -= 1

        for i, match in enumerate(self.matches):
            if i == 0 and RX_BLANK_LINE.search(match.group('content')):
                continue
            output_stream.write(html.escape(match.group('content'), quote=True))
            if i < len(self.matches) - 1:
                output_stream.write('\n')

        while self.output_nesting_level > 0:
            output_stream.write('\n[[/math]]')
            self.output_nesting_level -= 1

    def write_close_tag(self, output_stream):
        output_stream.write(r' \end{align} $$')
        output_stream.write('</div>\n')

    def close(self, output_stream):
        self.write_open_tag(output_stream)
        self.write_math_content(output_stream)
        self.write_close_tag(output_stream)


class Paragraph(Block):
    def __init__(self, wikidot, line, lineno, match):
        self.wikidot = wikidot
        Block.__init__(self, wikidot, line, lineno, BLOCK_TYPE_P, match)

    def get_content(self, parser):
        for i, match in enumerate(self.matches):
            parser.parse(token_lex(match.group('content')))
            if i < len(self.matches) - 1:
                parser.add_text(self.wikidot.LINE_BREAK)

        return parser.top_node

    def close(self, output_stream):
        parser = InlineParser(self.wikidot)
        top_node = self.get_content(parser)
        content = str(top_node)
        suppress_tags = False
        if len(top_node.children) == 1:
            child_node = top_node.children[0]
            if isinstance(child_node, Image):
                suppress_tags = True
        if not RX_EMPTY_PARAGRAPH.search(content):
            if not suppress_tags:
                self.write_open_tag(output_stream)
            output_stream.write(content)
            if not suppress_tags:
                self.write_close_tag(output_stream)
            else:
                output_stream.write('\n')


class Div:
    def __init__(self, wikidot, output_stream, match):
        self.wikidot = wikidot
        self.attributes = {}
        self.parse_attributes(match)
        attrs = self.attributes_to_str()
        if attrs:
            output_stream.write('<div {}>\n'.format(attrs))
        else:
            output_stream.write('<div>\n')

    def parse_attributes(self, match):
        rest = match.group('attributes') or ''
        while rest:
            md = RX_DIV_ATTR.search(rest)
            if md:
                name = md.group('name')
                value = md.group('value')
                if name == 'id':
                    self.attributes[name] = 'u-' + value
                else:
                    self.attributes[name] = value
                rest = md.group('rest')
            else:
                rest = ''

    def attributes_to_str(self):
        attrs = []
        for k in ['id', 'class', 'style']:
            if k in self.attributes:
                attrs.append('{}="{}"'.format(k, self.attributes[k]))
        for k in sorted(self.attributes.keys()):
            if k.startswith('data-'):
                attrs.append('{}="{}"'.format(k, self.attributes[k]))

        return ' '.join(attrs)

    def close(self, output_stream):
        output_stream.write('</div>\n')


class BlockParser:
    def __init__(self, wikidot, input_stream):
        self.wikidot = wikidot
        self.input_stream = input_stream
        self.input_lines = self.input_stream.readlines()
        self.current_block = None
        self.bq_level = 0
        self.continued_line = False
        self.divs = []
        self.toc = None

    def close_current_block(self, output_stream):
        if self.current_block:
            self.current_block.close(output_stream)
        self.current_block = None

    def block_factory(self, line, lineno, block_type=None, match=None):
        if block_type == BLOCK_TYPE_UL:
            return List(wikidot=self.wikidot, line=line, lineno=lineno, match=match)
        if block_type == BLOCK_TYPE_OL:
            return List(wikidot=self.wikidot, line=line, lineno=lineno, match=match)
        if block_type == BLOCK_TYPE_EMPTY:
            return Empty(wikidot=self.wikidot, line=line, lineno=lineno, match=match)
        if block_type == BLOCK_TYPE_HR:
            return HorizontalRule(wikidot=self.wikidot, line=line, lineno=lineno, match=match)
        if block_type == BLOCK_TYPE_CODE:
            return Code(wikidot=self.wikidot, line=line, lineno=lineno, match=match)
        if block_type == BLOCK_TYPE_MATH:
            return Math(wikidot=self.wikidot, line=line, lineno=lineno, match=match)
        if block_type == BLOCK_TYPE_P:
            return Paragraph(wikidot=self.wikidot, line=line, lineno=lineno, match=match)
        if block_type == BLOCK_TYPE_HN:
            return Header(wikidot=self.wikidot, line=line, lineno=lineno, match=match)
        if block_type == BLOCK_TYPE_TABLE:
            return Table(wikidot=self.wikidot, line=line, lineno=lineno, match=match)
        return Block(wikidot=self.wikidot,
                     line=line,
                     lineno=lineno,
                     block_type=block_type,
                     match=match)

    def adjust_blockquote_level(self, output_stream, line):
        if isinstance(self.current_block, Code):
            return line

        md = RX_BLOCKQUOTE.search(line)
        if md:
            new_bq_level = len(md.group('greater_than_signs'))
            line = md.group('content')
        else:
            new_bq_level = 0

        if new_bq_level != self.bq_level:
            self.close_current_block(output_stream)

        if new_bq_level > self.bq_level:
            for _ in range(0, new_bq_level - self.bq_level):
                output_stream.write('<blockquote>\n')
        elif new_bq_level < self.bq_level:
            for _ in range(0, self.bq_level - new_bq_level):
                output_stream.write('</blockquote>\n')

        self.bq_level = new_bq_level

        return line

    def check_for_div(self, output_stream, line):
        md = RX_DIV_START.search(line)
        if md:
            self.close_current_block(output_stream)
            self.divs.append(Div(self.wikidot, output_stream, md))
            return True

        md = RX_DIV_END.search(line)
        if md:
            self.close_current_block(output_stream)
            if self.divs:
                div = self.divs.pop()
                div.close(output_stream)
            return True

        return False

    def close_divs(self, output_stream):
        while self.divs:
            div = self.divs.pop()
            div.close(output_stream)

    def block_type_and_match(self, output_stream, line):
        if isinstance(self.current_block, Code):
            md = RX_CODE_START.search(line)
            if md:
                self.current_block.input_nesting_level += 1
                self.current_block.output_nesting_level += 1
                return None, None
            md = RX_CODE_END.search(line)
            if md:
                if self.current_block.input_nesting_level == 0:
                    self.close_current_block(output_stream)
                    return None, None
                self.current_block.input_nesting_level -= 1
                return None, None
            md = RX_CODE_CONTENT.search(line)
            if md:
                return BLOCK_TYPE_CODE, md
            raise Exception('unparseable line: {}'.format(line))

        if isinstance(self.current_block, Math):
            md = RX_MATH_START.search(line)
            if md:
                self.current_block.input_nesting_level += 1
                self.current_block.output_nesting_level += 1
                return None, None
            md = RX_MATH_END.search(line)
            if md:
                if self.current_block.input_nesting_level == 0:
                    self.close_current_block(output_stream)
                    return None, None
                self.current_block.input_nesting_level -= 1
                return None, None
            md = RX_MATH_CONTENT.search(line)
            if md:
                return BLOCK_TYPE_MATH, md
            raise Exception('unparseable line: {}'.format(line))

        if self.bq_level == 0:
            md = RX_CODE_START.search(line)
            if md:
                self.close_current_block(output_stream)
                return BLOCK_TYPE_CODE, md
            md = RX_MATH_START.search(line)
            if md:
                self.close_current_block(output_stream)
                return BLOCK_TYPE_MATH, md

        return analyze_line(line, self.current_block)

    def _process_lines(self, output_stream):
        try:
            for lineno, line in enumerate(self.input_lines, start=1):
                line = line.rstrip()
                line = self.adjust_blockquote_level(output_stream, line)

                if line == TOC_LITERAL and self.toc:
                    self.toc.close(output_stream)
                    continue

                if self.check_for_div(output_stream, line):
                    continue

                block_type, match = self.block_type_and_match(output_stream, line)
                if not block_type:
                    continue

                if block_type == BLOCK_TYPE_EMPTY and self.bq_level > 0:
                    continue

                if not self.current_block:
                    self.current_block = self.block_factory(line,
                                                            lineno,
                                                            block_type,
                                                            match)
                elif self.continued_line:
                    self.current_block.add_line(line,
                                                lineno,
                                                block_type,
                                                match,
                                                continued=True)
                elif (block_type == self.current_block.block_type and
                      self.current_block.multiline_type()):
                    self.current_block.add_line(line,
                                                lineno,
                                                block_type,
                                                match)
                else:
                    self.close_current_block(output_stream)
                    self.current_block = self.block_factory(line,
                                                            lineno,
                                                            block_type,
                                                            match)

                try:
                    self.continued_line = line.endswith(' _')
                except IndexError:
                    self.continued_line = False

            self.close_current_block(output_stream)
            self.adjust_blockquote_level(output_stream, '')
        except Exception:
            sys.stderr.write("ERROR at line {}: {}\n".format(lineno, line))
            raise

    def process_lines(self, output_stream):
        self._process_lines(NullOutputStream())

        self.wikidot.next_toc_number = 0
        self.wikidot.next_eqn_number = 1
        self.toc = self.wikidot.toc
        self.wikidot.toc = TOC(self.wikidot)

        self._process_lines(output_stream)


class Wikidot:
    def __init__(self, args):
        self.image_prefix = args.image_prefix
        self.link_prefix = args.link_prefix
        self.link_suffix = args.link_suffix
        self.LINE_BREAK = LineBreak(self)
        self.toc = TOC(self)
        self.next_toc_number = 0
        self.next_eqn_number = 1

    def to_html(self, input_stream, output_stream):
        BlockParser(self, input_stream).process_lines(output_stream)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--image-prefix',
                        dest='image_prefix',
                        default='')
    parser.add_argument('--link-prefix',
                        dest='link_prefix',
                        default='')
    parser.add_argument('--link-suffix',
                        dest='link_suffix',
                        default='')
    args = parser.parse_args()
    Wikidot(args).to_html(sys.stdin, sys.stdout)
