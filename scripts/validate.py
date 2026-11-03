#!/usr/bin/env python3
"""Validate manuscripts and local references against series.json."""
from __future__ import annotations
import argparse
from dataclasses import dataclass, asdict
import json
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build import EXTERNAL_IMAGE_HOSTS, ROOT, SERIES_FILE, parse_markdown  # noqa: E402

MIN_BODY_CHARS = 1500
REFERENCES_HEADING = '## 参考文献・注記'
COMMONS_FILE_PAGE = 'https://commons.wikimedia.org/wiki/File:'


@dataclass
class Result:
    chapters: int = 0
    local_links: int = 0
    external_links: int = 0
    manuscript_characters: int = 0
    footnotes: int = 0
    figures: int = 0
    svg_files: int = 0


def svg_errors(path: Path) -> list[str]:
    errors = []
    try:
        root = ET.fromstring(path.read_text(encoding='utf-8'))
    except (OSError, ET.ParseError, UnicodeError) as exc:
        return [f'{path.name}: SVG parse error: {exc}']
    tag = lambda n: n.tag.rsplit('}', 1)[-1]
    if tag(root) != 'svg':
        errors.append(f'{path.name}: root must be svg')
    if not root.get('viewBox'):
        errors.append(f'{path.name}: missing viewBox')
    if root.get('role') != 'img':
        errors.append(f'{path.name}: missing role=img')
    names = {tag(n) for n in root.iter()}
    if not {'title', 'desc'} <= names:
        errors.append(f'{path.name}: missing title/desc')
    ids = [n.attrib['id'] for n in root.iter() if 'id' in n.attrib]
    if len(ids) != len(set(ids)):
        errors.append(f'{path.name}: duplicate id')
    for label_id in root.get('aria-labelledby', '').split():
        if label_id not in ids:
            errors.append(f'{path.name}: unresolved aria-labelledby')
    for n in root.iter():
        if tag(n).lower() in {'script', 'foreignobject', 'iframe', 'image', 'use', 'style', 'animate', 'set'}:
            errors.append(f'{path.name}: forbidden SVG element {tag(n)}')
        for key, value in n.attrib.items():
            k = key.rsplit('}', 1)[-1].lower()
            if k.startswith('on'):
                errors.append(f'{path.name}: forbidden event handler {k}')
            if k == 'href' and not value.startswith('#'):
                errors.append(f'{path.name}: external href')
            if re.search(r'url\(\s*["\']?(?!#)[^)]', value):
                errors.append(f'{path.name}: external url()')
    return errors


def walk(node: object):
    if isinstance(node, dict):
        yield node
        for v in node.values():
            yield from walk(v)
    elif isinstance(node, list):
        for v in node:
            yield from walk(v)


def validate(root: Path = ROOT) -> tuple[Result, list[str]]:
    root = root.resolve()
    result = Result()
    errors: list[str] = []
    try:
        series = json.loads((root / SERIES_FILE).read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        return result, [str(exc)]
    chapters = series.get('chapters', [])
    count = len(chapters)
    if count == 0 or [c.get('number') for c in chapters] != list(range(1, count + 1)):
        errors.append(f'{SERIES_FILE}: expected chapters numbered 1..N in order')
    if len({c['path'] for c in chapters}) != count or len({c['slug'] for c in chapters}) != count:
        errors.append(f'{SERIES_FILE}: chapter paths and slugs must be unique')
    if not (root / series['index']).exists():
        errors.append(f'{SERIES_FILE}: index page {series["index"]} is missing')
    covered = [n for part in series.get('parts', []) for n in range(part['chapters'][0], part['chapters'][1] + 1)]
    if covered != list(range(1, count + 1)):
        errors.append(f'{SERIES_FILE}: parts must cover chapters 1..N exactly once, in order')
    md_paths = [root / 'README.md', *sorted((root / 'guides').glob('*.md')), *[p for p in [root / 'CHANGELOG.md'] if p.exists()], *(root / c['path'] for c in chapters)]
    md_paths = list(dict.fromkeys(md_paths))
    asts = {}
    anchors = {}
    for path in md_paths:
        if not path.exists():
            errors.append(f'{path.relative_to(root)}: missing markdown')
            continue
        text = path.read_text(encoding='utf-8')
        name = path.relative_to(root).as_posix()
        if any(t in text for t in [':::writing', '```svg', '<svg']):
            errors.append(f'{name}: unsupported conversation artifact or inline SVG')
        try:
            ast = parse_markdown(text)
        except (RuntimeError, ValueError) as exc:
            errors.append(f'{name}: {exc}')
            continue
        asts[path.resolve()] = ast
        anchors[path.resolve()] = {n['c'][1][0] for n in walk(ast) if n.get('t') == 'Header'}
        if path.parent.name == 'chapters':
            result.manuscript_characters += len(text)
            result.footnotes += sum(n.get('t') == 'Note' for n in walk(ast))
    for c in chapters:
        path = root / c['path']
        if not path.exists():
            continue
        text = path.read_text(encoding='utf-8')
        result.chapters += 1
        if not text.startswith(f'# 第{c["number"]}回　{c["title"]}\n\n## {c["subtitle"]}\n'):
            errors.append(f'{c["path"]}: title or subtitle mismatch with series.json')
        body = text.split(REFERENCES_HEADING)[0]
        if len(re.sub(r'\s', '', body)) < MIN_BODY_CHARS:
            errors.append(f'{c["path"]}: article is too short for a complete essay')
        if text.count('<!-- NAV:') != 2:
            errors.append(f'{c["path"]}: top/bottom navigation missing')
        if '次回予告' in text:
            errors.append(f'{c["path"]}: remove the next-episode label; the build adds the next title to the bottom navigation')
        definitions = set(re.findall(r'^\[\^([^\]]+)\]:', text, re.M))
        uses = set(re.findall(r'\[\^([^\]]+)\](?!:)', text))
        if definitions != set(c.get('sources', [])):
            errors.append(f'{c["path"]}: footnote list differs from "sources" in series.json')
        if definitions != uses:
            errors.append(f'{c["path"]}: unused or undefined footnote')
        if bool(definitions) != (REFERENCES_HEADING in text):
            errors.append(f'{c["path"]}: "{REFERENCES_HEADING}" must exist exactly when footnotes exist')
        images = re.findall(r'^!\[[^\]]*\]\(([^)\s]+)[^)]*\)\s*$', text, re.M)
        captions = re.findall(r'^\*図(\d+)-(\d+)：(.+)\*$', text, re.M)
        result.figures += len(images)
        if [(int(a), int(b)) for a, b, _ in captions] != [(c['number'], i) for i in range(1, len(images) + 1)]:
            errors.append(f'{c["path"]}: figure captions must be 図{c["number"]}-1 .. 図{c["number"]}-{len(images)} in order, one per image')
        else:
            for url, (_, _, caption) in zip(images, captions):
                if urlsplit(url).scheme and COMMONS_FILE_PAGE not in caption:
                    errors.append(f'{c["path"]}: caption of an external image must link its Wikimedia Commons file page: {url}')
    for path, ast in asts.items():
        for n in walk(ast):
            if n.get('t') not in {'Link', 'Image'}:
                continue
            url = n['c'][-1][0]
            parsed = urlsplit(url)
            if n.get('t') == 'Image' and not n['c'][1]:
                errors.append(f'{path.name}: missing image alt text: {url}')
            if parsed.scheme:
                result.external_links += 1
                if parsed.scheme not in {'https', 'mailto'}:
                    errors.append(f'{path.name}: unsupported URL scheme {parsed.scheme}')
                if parsed.scheme == 'https' and not parsed.netloc:
                    errors.append(f'{path.name}: invalid HTTPS URL')
                if n.get('t') == 'Image' and parsed.netloc not in EXTERNAL_IMAGE_HOSTS:
                    errors.append(f'{path.name}: external image host is not allowed: {parsed.netloc}')
                continue
            target = (path.parent / unquote(parsed.path)).resolve() if parsed.path else path
            result.local_links += 1
            if not target.is_relative_to(root):
                errors.append(f'{path.name}: path escapes repository: {url}')
                continue
            if not target.exists():
                errors.append(f'{path.name}: broken local link: {url}')
                continue
            if parsed.fragment and target.suffix == '.md' and unquote(parsed.fragment) not in anchors.get(target, set()):
                errors.append(f'{path.name}: unknown anchor: {url}')
    for svg in sorted((root / 'assets').rglob('*.svg')):
        result.svg_files += 1
        errors += svg_errors(svg)
    for p in root.rglob('*'):
        if '_site' in p.parts or '.git' in p.parts:
            continue
        if p.suffix.lower() in {'.ttf', '.otf', '.woff', '.woff2'}:
            errors.append(f'font files must not be bundled: {p.name}')
    return result, errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--json', action='store_true')
    parser.parse_args()
    result, errors = validate()
    report = {**asdict(result), 'errors': errors, 'external_url_reachability': 'not checked', 'editorial_correctness': 'requires editorial review'}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == '__main__':
    raise SystemExit(main())
