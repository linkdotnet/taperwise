#!/usr/bin/env python3
"""Usage: python3 tools/build_i18n.py   (run from anywhere; writes <lang>/index.html for each language)"""
import json, pathlib, re
from html import unescape
from html.parser import HTMLParser
from urllib.parse import urljoin

ROOT = pathlib.Path(__file__).resolve().parent.parent
SITE = 'https://taperwise.run'
LANGS = ['de', 'fr', 'it', 'es', 'pt-BR', 'nl', 'ja']
ALL = ['en'] + LANGS
OG_LOCALE = {'en': 'en_US', 'de': 'de_DE', 'fr': 'fr_FR', 'it': 'it_IT', 'es': 'es_ES', 'pt-BR': 'pt_BR', 'nl': 'nl_NL', 'ja': 'ja_JP'}
NAMES = {'en': 'English', 'de': 'Deutsch', 'fr': 'Français', 'it': 'Italiano', 'es': 'Español', 'pt-BR': 'Português (Brasil)', 'nl': 'Nederlands', 'ja': '日本語'}
SKIP = {'nav', 'script', 'style', 'svg', 'select', 'video', 'figure', 'head'}
BLOCK = {'p', 'li', 'h1', 'h2', 'h3', 'h4', 'div', 'article', 'section', 'header', 'footer', 'main', 'ul', 'ol', 'dl', 'table', 'tr'}
VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}


def folder(code):
    return '' if code == 'en' else code.lower() + '/'


def url(code):
    return f'{SITE}/{folder(code)}'


def head_links(code):
    lines = [f'<link rel="canonical" href="{url(code)}">']
    lines += [f'<link rel="alternate" hreflang="{c}" href="{url(c)}">' for c in ALL]
    lines.append(f'<link rel="alternate" hreflang="x-default" href="{url("en")}">')
    lines.append(f'<link rel="alternate" type="text/markdown" href="{url(code)}index.md">')
    return '\n'.join(lines) + '\n'


class Scan(HTMLParser):
    def __init__(self, src, strings):
        super().__init__(convert_charrefs=False)
        self.src = src
        self.strings = strings
        self.line_starts = [0] + [m.end() for m in re.finditer('\n', src)]
        self.stack = []
        self.edits = []

    def absolute(self):
        line, col = self.getpos()
        return self.line_starts[line - 1] + col

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        start = self.absolute()
        tag_text = self.get_starttag_text()
        for pair in a.get('data-i18n-attr', '').split(';') if 'data-i18n-attr' in a else []:
            attr, key = pair.split(':')
            if key not in self.strings:
                continue
            m = re.search(r'\s' + re.escape(attr) + r'="([^"]*)"', tag_text)
            value = self.strings[key].replace('"', '&quot;')
            self.edits.append((start + m.start(1), start + m.end(1), value))
        if tag in VOID:
            return
        entry = a.get('data-i18n')
        self.stack.append((tag, entry, start + len(tag_text)))

    def handle_endtag(self, tag):
        end = self.absolute()
        while self.stack:
            name, key, content_start = self.stack.pop()
            if key in self.strings:
                self.edits.append((content_start, end, self.strings[key]))
            if name == tag:
                break


class Markdown(HTMLParser):
    """Readable Markdown for agents; skips chrome (nav, media, demo HUD) and keeps headings, copy and links."""

    def __init__(self, page_url):
        super().__init__()
        self.page_url = page_url
        self.blocks, self.buf, self.skip, self.href = [], '', 0, None
        self.prefix = ''

    def flush(self):
        text = re.sub(r'\s+', ' ', self.buf).strip()
        if text:
            self.blocks.append(self.prefix + text)
        self.buf, self.prefix = '', ''

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if self.skip or tag in SKIP or 'hud' in (a.get('class') or '').split() or a.get('hidden') is not None or a.get('href', '').startswith('#'):
            if tag not in VOID:
                self.skip += 1
            return
        if tag in BLOCK:
            self.flush()
        if tag in ('h1', 'h2', 'h3', 'h4'):
            self.prefix = '#' * (int(tag[1]) + 1) + ' '
        elif tag == 'li':
            self.prefix = '- '
        elif tag == 'tr':
            self.prefix = '| '
        elif tag == 'br':
            self.buf += ' '
        elif tag == 'strong':
            self.buf += '**'
        elif tag == 'a':
            href = a.get('href', '')
            self.href = None if href.startswith('#') else urljoin(self.page_url, href)
            if self.href:
                self.buf += '['

    def handle_endtag(self, tag):
        if self.skip:
            if tag not in VOID:
                self.skip -= 1
            return
        if tag == 'strong':
            self.buf = self.buf.rstrip() + '**'
        elif tag == 'a' and self.href:
            self.buf = self.buf.rstrip() + f']({self.href})'
            self.href = None
        elif tag in ('span', 'dd', 'dt'):
            self.buf += ' '
        elif tag in ('td', 'th'):
            self.buf += ' | '
        elif tag == 'thead':
            self.blocks[-1] += '\n' + '|---' * (self.blocks[-1].count(' | ') + 1) + '|'
        elif tag in BLOCK:
            self.flush()

    def handle_data(self, data):
        if not self.skip:
            self.buf += data


def markdown(html, page_url, code=None):
    title = re.search(r'<title[^>]*>(.*?)</title>', html, re.S).group(1)
    desc = re.search(r'<meta name="description"[^>]*content="([^"]*)"', html).group(1)
    md = Markdown(page_url)
    md.feed(html)
    md.close()
    md.flush()
    head = [f'# {unescape(title)}', f'> {unescape(desc)}', f'Source: {page_url}']
    if code:
        head.append(' · '.join(f'[{NAMES[c]}]({url(c)}index.md)' for c in ALL))
    return '\n\n'.join(head + md.blocks).replace('|\n\n|', '|\n|') + '\n'


def llms_txt(en_html):
    desc = re.search(r'<meta name="description"[^>]*content="([^"]*)"', en_html).group(1)
    pages = [f'- [{NAMES[c]}]({url(c)}index.md): Taperwise overview in {NAMES[c]}' for c in ALL]
    return '\n'.join([
        '# Taperwise', '', f'> {unescape(desc)}', '',
        'Taperwise is a running app for iPhone and Apple Watch by BitSpire GmbH (Cham, Switzerland). '
        'It is available on the App Store: https://apps.apple.com/app/id6823595769. Contact: apps@bitspire.ch', '',
        '## Overview', *pages, '',
        '## Policies',
        f'- [Privacy policy]({SITE}/privacy/index.md): what the app reads, where it is stored and what leaves the device',
        f'- [Legal notice]({SITE}/legal/index.md): publisher and contact details', '',
    ])


def build(code, base_src, strings):
    scan = Scan(base_src, strings)
    scan.feed(base_src)
    scan.close()
    out = base_src
    for start, end, text in sorted(scan.edits, reverse=True):
        out = out[:start] + text + out[end:]
    out = out.replace('<html lang="en">', f'<html lang="{code}">', 1)
    out = re.sub(r'="(assets|privacy|legal)/', r'="../\1/', out)
    out = out.replace('content="../assets/img/icon.png"', f'content="{SITE}/assets/img/icon.png"')
    out = out.replace(f'<meta property="og:url" content="{url("en")}">', f'<meta property="og:url" content="{url(code)}">', 1)
    out = out.replace('<link rel="icon"', head_links(code) + '<link rel="icon"', 1)
    out = out.replace('<meta property="og:locale" content="en_US">', f'<meta property="og:locale" content="{OG_LOCALE[code]}">', 1)
    return re.sub(r'(<script type="application/ld\+json">)(.*?)(</script>)', lambda m: m[1] + ld_json(m[2], code, strings) + m[3], out, count=1, flags=re.S)


def ld_json(src, code, strings):
    data = json.loads(src)
    data.update(url=url(code), inLanguage=code, description=strings.get('meta.description', data['description']))
    return json.dumps(data, ensure_ascii=False)


def sitemap():
    alternates = ''.join(f'\n    <xhtml:link rel="alternate" hreflang="{c}" href="{url(c)}"/>' for c in ALL)
    alternates += f'\n    <xhtml:link rel="alternate" hreflang="x-default" href="{url("en")}"/>'
    pages = ''.join(f'\n  <url>\n    <loc>{url(c)}</loc>{alternates}\n  </url>' for c in ALL)
    pages += ''.join(f'\n  <url>\n    <loc>{SITE}/{p}/</loc>\n  </url>' for p in ('privacy', 'legal'))
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">{pages}\n</urlset>\n'



def main():
    base = (ROOT / 'index.html').read_text(encoding='utf-8')
    base = re.sub(r'<link rel="(?:canonical|alternate)"[^>]*>\n', '', base)
    for code in LANGS:
        path = ROOT / 'assets' / 'i18n' / f'{code}.json'
        strings = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
        page = build(code, base, strings)
        target = ROOT / folder(code) / 'index.html'
        target.parent.mkdir(exist_ok=True)
        target.write_text(page, encoding='utf-8')
        print(f'{target.relative_to(ROOT)}: {len(strings)} translated keys')
    (ROOT / 'sitemap.xml').write_text(sitemap(), encoding='utf-8')
    for code in ALL:
        html = (ROOT / folder(code) / 'index.html').read_text(encoding='utf-8')
        (ROOT / folder(code) / 'index.md').write_text(markdown(html, url(code), code), encoding='utf-8')
    for page in ('privacy', 'legal'):
        html = (ROOT / page / 'index.html').read_text(encoding='utf-8')
        (ROOT / page / 'index.md').write_text(markdown(html, f'{SITE}/{page}/'), encoding='utf-8')
    (ROOT / 'llms.txt').write_text(llms_txt((ROOT / 'index.html').read_text(encoding='utf-8')), encoding='utf-8')


if __name__ == '__main__':
    main()
