#!/usr/bin/env python3
"""Usage: python3 tools/build_i18n.py   (run from anywhere; writes <lang>/index.html for each language)"""
import json, pathlib, re
from html.parser import HTMLParser

ROOT = pathlib.Path(__file__).resolve().parent.parent
SITE = 'https://taperwise.run'
LANGS = ['de', 'fr', 'it', 'es', 'pt-BR', 'nl', 'ja']
ALL = ['en'] + LANGS
VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}


def folder(code):
    return '' if code == 'en' else code.lower() + '/'


def url(code):
    return f'{SITE}/{folder(code)}'


def head_links(code):
    lines = [f'<link rel="canonical" href="{url(code)}">']
    lines += [f'<link rel="alternate" hreflang="{c}" href="{url(c)}">' for c in ALL]
    lines.append(f'<link rel="alternate" hreflang="x-default" href="{url("en")}">')
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
    return out


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


if __name__ == '__main__':
    main()
