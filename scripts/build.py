#!/usr/bin/env python3
"""Build a portable HTML reader from the Markdown sources. Requires Pandoc 3.x."""
from __future__ import annotations
import argparse
import html
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
SERIES_FILE = 'series.json'
READER = 'markdown+footnotes+pipe_tables-tex_math_dollars'
SITE_INDEX_END = '<!-- SITE-INDEX-END'
# 本文に直接リンクして表示してよい外部画像のホスト。パブリックドメインの作品をWikimedia Commonsから表示する。
EXTERNAL_IMAGE_HOSTS = {'commons.wikimedia.org'}


def site_index_text(text: str) -> str:
    """README本文のうち、HTML閲覧版のトップページへ載せる範囲(マーカーより前)を返す。"""
    head, marker, _ = text.partition(SITE_INDEX_END)
    return head.rstrip() + '\n' if marker else text


def run_pandoc(text: str, args: list[str]) -> str:
    if not shutil.which('pandoc'):
        raise RuntimeError('Pandoc 3.x が必要である。guides/READING.md を参照。')
    result = subprocess.run(['pandoc', *args], input=text, text=True, encoding='utf-8', capture_output=True, check=False)
    if result.returncode or result.stderr.strip():
        raise RuntimeError(f'Pandoc conversion failed: {result.stderr.strip()}')
    return result.stdout


def parse_markdown(text: str) -> dict:
    # --columns を十分大きくし、パイプテーブルに区切り行由来の相対列幅(colgroup)を付けさせない。列幅はブラウザが内容に応じて決める。
    return json.loads(run_pandoc(text, ['--from', READER, '--to', 'json', '--columns=10000']))


def map_url(url: str) -> str:
    parsed = urlsplit(url)
    if parsed.scheme or url.startswith(('#', '//')):
        return url
    path = parsed.path
    if path.endswith('.md'):
        path = path[:-3] + '.html'
        if Path(path).name == 'README.html':
            path = path[:-len('README.html')] + 'index.html'
    return path + ('?' + parsed.query if parsed.query else '') + ('#' + parsed.fragment if parsed.fragment else '')


def transform_links(node: object) -> None:
    if isinstance(node, dict):
        if node.get('t') in ('Link', 'Image'):
            node['c'][-1][0] = map_url(node['c'][-1][0])
        for child in node.values():
            transform_links(child)
    elif isinstance(node, list):
        for child in node:
            transform_links(child)


NAV_TOP_MD = re.compile(r'<!-- NAV:TOP -->\n(.+?)\n<!-- /NAV -->')
NAV_BOTTOM_MD = re.compile(r'<!-- NAV:BOTTOM -->\n---\n\n(.+?)\n<!-- /NAV -->')


def nav_markdown(text: str, next_note: str = '') -> str:
    """各回の冒頭・末尾の前後リンク（NAV マーカーで囲まれた行）を、Pandoc に渡す前に nav.chapter-nav へ置き換える。
    Pandoc は HTML ブロック内の Markdown を解釈するので、リンクはそのまま書ける。末尾のナビには次回の題名を添える。"""
    def links(line: str) -> str:
        return line.replace(' | ', ' <span class="sep" aria-hidden="true">|</span> ')
    text = NAV_TOP_MD.sub(lambda m: f'<nav class="chapter-nav chapter-nav-top" aria-label="前後の回">\n\n{links(m.group(1))}\n\n</nav>', text)
    tail = f'\n\n<span class="chapter-nav-next">{next_note}</span>' if next_note else ''
    return NAV_BOTTOM_MD.sub(lambda m: f'<nav class="chapter-nav chapter-nav-bottom" aria-label="前後の回">\n\n{links(m.group(1))}{tail}\n\n</nav>', text)


def next_chapter_note(series: dict, source: Path) -> str:
    """章ページの末尾ナビに添える「次回　第N回「題名」」。最終回は空。"""
    chapters = series['chapters']
    for i, c in enumerate(chapters):
        if c['path'] == source.as_posix() and i + 1 < len(chapters):
            n = chapters[i + 1]
            return f'次回　第{n["number"]}回「{html.escape(n["title"])}」'
    return ''


def render(text: str, prefix: str = '', next_note: str = '') -> str:
    ast = parse_markdown(nav_markdown(text, next_note))
    transform_links(ast)
    args = ['--from', 'json', '--to', 'html5', '--wrap=none']
    if prefix:
        args += ['--id-prefix', prefix]
    output = run_pandoc(json.dumps(ast, ensure_ascii=False), args)
    if prefix:
        output = output.replace('id="footnotes"', f'id="{prefix}footnotes"')
    return footnotes_before_nav(wrap_tables(merge_captions(output)))


# Pandoc が alt から作る自動キャプションは aria-hidden 付きで出る。本文由来の figcaption と区別するため、その属性で限定する。
FIGURE_WITH_CAPTION = re.compile(r'<figure>\s*(<img\b[^>]*>)\s*<figcaption aria-hidden="true">.*?</figcaption>\s*</figure>\s*<p><em>(図.*?)</em></p>', re.S)
FIGURE_ALT_ONLY = re.compile(r'<figure>\s*(<img\b[^>]*>)\s*<figcaption aria-hidden="true">.*?</figcaption>\s*</figure>', re.S)
FOOTNOTES = re.compile(r'<section id="[^"]*footnotes"[^>]*>.*?</section>', re.S)
NAV_BOTTOM_HTML = re.compile(r'<nav class="chapter-nav chapter-nav-bottom".*?</nav>', re.S)


IMG_SRC = re.compile(r'\bsrc="([^"]+)"')


def figure_body(img: str) -> str:
    """概念図（SVG）を、横スクロール容器と原寸へのリンクで包む。電話幅では容器が横に流れ、タップで原寸を開ける。
    外部の作品画像は、そのまま本文幅に収める。"""
    m = IMG_SRC.search(img)
    src = m.group(1) if m else ''
    if not src.endswith('.svg'):
        return img
    return f'<div class="figure-scroll"><a class="figure-link" href="{src}" title="図を原寸で開く">{img}</a></div>'


def merge_captions(output: str) -> str:
    """画像直後の「*図N-k：…*」段落を figcaption に取り込み、Pandoc が alt から作る自動キャプションを消す。
    alt は img の属性として残す。本文側のキャプションがない図は figcaption なしにする。"""
    output = FIGURE_WITH_CAPTION.sub(lambda m: f'<figure>{figure_body(m.group(1))}<figcaption>{m.group(2)}</figcaption></figure>', output)
    return FIGURE_ALT_ONLY.sub(lambda m: f'<figure>{figure_body(m.group(1))}</figure>', output)


def footnotes_before_nav(output: str) -> str:
    """Pandoc は脚注を文書の最後に置く。末尾の前後ナビより前（「参考文献・注記」の見出しの直後）へ移す。"""
    notes = FOOTNOTES.search(output)
    nav = NAV_BOTTOM_HTML.search(output)
    if not notes or not nav or notes.start() < nav.start():
        return output
    output = output[:notes.start()] + output[notes.end():]
    nav = NAV_BOTTOM_HTML.search(output)
    return output[:nav.start()] + notes.group(0) + '\n' + output[nav.start():]


def wrap_tables(output: str) -> str:
    """<table> を横スクロール用の <div class="table-wrap"> で包む。table 自体を display:block にすると行が内容幅で止まるため。"""
    output = re.sub(r'<table(\s[^>]*)?>', lambda m: f'<div class="table-wrap"><table{m.group(1) or ""}>', output)
    return output.replace('</table>', '</table></div>')


def load_series() -> dict:
    return json.loads((ROOT / SERIES_FILE).read_text(encoding='utf-8'))


def wrap_page(title: str, body: str, source: Path, series: dict, css: str) -> str:
    depth = len(source.parent.parts)
    root_link = '../' * depth
    links = []
    part_starts = {p['chapters'][0]: p for p in series.get('parts', [])}
    for c in series['chapters']:
        if c['number'] in part_starts:
            p = part_starts[c['number']]
            links.append(f'<div class="toc-part">第{p["number"]}部　{html.escape(p["title"])}</div>')
        current = source.as_posix() == c['path']
        links.append(f'<a class="chapter-link{" current" if current else ""}" href="{root_link}{map_url(c["path"])}"' + (' aria-current="page"' if current else '') + f'><span>{c["number"]:02d}</span>{html.escape(c["title"])}</a>')
    series_title = html.escape(series['title'])
    tagline = html.escape(series['tagline'])
    code = html.escape(series.get('code', 'MEDIUM'))
    index_link = root_link + map_url(series['index'])
    count = len(series['chapters'])
    other = ''.join(f'<a href="{html.escape(r["url"])}">{html.escape(r["title"])}</a>' for r in series.get('related', []))
    other_block = f'<div class="toc-drawer-other"><span>別の連載</span>{other}</div>' if other else ''
    return f'''<!doctype html>
<html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light dark"><title>{series_title if title == series['title'] else html.escape(title) + ' | ' + series_title}</title>
<style>{css}</style></head><body>
<a class="skip" href="#main">本文へ移動</a>
<input type="checkbox" id="toc-state" class="toc-state" aria-label="目次を開く">
<header class="topbar"><a href="{index_link}" class="brand">{series_title}<span>{code}</span></a><div class="topbar-actions"><a href="{root_link}guides/READING.html">読み方</a><label class="toc-toggle" for="toc-state"><svg viewBox="0 0 20 20" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M3 5h14M3 10h14M3 15h14"/></svg>目次</label></div></header>
<label class="toc-backdrop" for="toc-state" aria-hidden="true"></label>
<aside class="toc-drawer" aria-label="連載の目次"><div class="toc-drawer-head"><strong>全{count}回の連載</strong><label class="toc-close" for="toc-state" title="閉じる"><svg viewBox="0 0 20 20" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M5 5l10 10M15 5L5 15"/></svg></label></div><nav aria-label="連載の目次">{''.join(links)}</nav><div class="toc-drawer-foot"><p>{tagline}</p><a href="{root_link}guides/EDITING.html">編集・保守ガイド</a>{other_block}</div></aside>
<div class="layout"><main id="main" tabindex="-1"><article>{body}</article></main></div></body></html>'''


def make_book(series: dict, css: str, dest: Path) -> None:
    code = html.escape(series.get('code', 'MEDIUM'))
    book_dir = (ROOT / Path(series['index']).parent).resolve()
    paths = {str((ROOT / c['path']).resolve()): f'#chapter-{c["number"]:02d}' for c in series['chapters']}
    pieces = []
    for c in series['chapters']:
        source = ROOT / c['path']
        body = render(source.read_text(encoding='utf-8'), prefix=f'c{c["number"]:02d}-', next_note=next_chapter_note(series, Path(c['path'])))

        def rewrite(match: re.Match) -> str:
            attr, url = match.group(1), html.unescape(match.group(2))
            if urlsplit(url).scheme or url.startswith('#'):
                return match.group(0)
            raw = urlsplit(url).path
            if attr == 'href':
                if raw.endswith('index.html'):
                    return 'href="#book-contents"'
                md = (source.parent / (raw[:-5] + '.md' if raw.endswith('.html') else raw)).resolve()
                if str(md) in paths:
                    return f'href="{paths[str(md)]}"'
            target = (source.parent / raw).resolve()
            try:
                target.relative_to(ROOT)
            except ValueError:
                return match.group(0)
            return f'{attr}="{os.path.relpath(target, book_dir)}"'
        body = re.sub(r'(href|src)="([^"]*)"', rewrite, body)
        pieces.append(f'<section class="book-chapter" id="chapter-{c["number"]:02d}">{body}</section>')
    toc = ''.join(f'<li><a href="#chapter-{c["number"]:02d}">第{c["number"]}回　{html.escape(c["title"])}</a></li>' for c in series['chapters'])
    doc = f'''<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(series['title'])} — 全{len(series['chapters'])}回</title><style>{css}\n.book{{max-width:860px;margin:auto;padding:32px 24px}}.book-chapter{{padding-top:55px;margin-top:65px;border-top:2px solid var(--line)}}@media print{{.book-chapter{{break-before:page}}}}</style></head><body><main class="book"><section id="book-contents"><p class="eyebrow">{code} — COMPLETE SERIES</p><h1>{html.escape(series['title'])}</h1><h2>{html.escape(series['subtitle'])}</h2><ol>{toc}</ol></section>{''.join(pieces)}</main></body></html>'''
    dest.write_text(doc, encoding='utf-8')


def build(output: Path) -> dict:
    output = output.resolve()
    if output == ROOT or ROOT.is_relative_to(output):
        raise RuntimeError('出力先にはリポジトリ自身またはその親を指定できない。')
    output.mkdir(parents=True, exist_ok=True)
    series = load_series()
    css = (ROOT / 'site-src/styles.css').read_text(encoding='utf-8')
    documents = [ROOT / 'README.md', *sorted((ROOT / 'guides').glob('*.md')), ROOT / 'CHANGELOG.md', *(ROOT / c['path'] for c in series['chapters'])]
    documents = [p for p in dict.fromkeys(documents) if p.exists()]
    for p in documents:
        source = p.relative_to(ROOT)
        target = output / map_url(source.as_posix())
        target.parent.mkdir(parents=True, exist_ok=True)
        text = p.read_text(encoding='utf-8')
        if p.name == 'README.md':
            text = site_index_text(text)
        title = re.search(r'^# (.+)', text, re.M).group(1)
        target.write_text(wrap_page(title, render(text, next_note=next_chapter_note(series, source)), source, series, css), encoding='utf-8')
    shutil.rmtree(output / 'assets', ignore_errors=True)
    if (ROOT / 'assets').exists():
        shutil.copytree(ROOT / 'assets', output / 'assets')
    shutil.copy2(ROOT / SERIES_FILE, output / SERIES_FILE)
    (output / '.nojekyll').write_text('', encoding='utf-8')
    make_book(series, css, output / 'complete.html')
    result = dict(pages=len(documents), chapters=len(series['chapters']), standalone=['complete.html'])
    (output / 'build-report.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / '_site')
    args = parser.parse_args()
    try:
        print(json.dumps(build(args.output), ensure_ascii=False, indent=2))
        return 0
    except (RuntimeError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
