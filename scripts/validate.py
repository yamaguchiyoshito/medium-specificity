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

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build import ROOT, SERIES_FILE, parse_markdown  # noqa: E402

MIN_BODY_CHARS = 1500


@dataclass
class Result:
    chapters: int = 0
    local_links: int = 0
    external_links: int = 0
    manuscript_characters: int = 0


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
    for c in chapters:
        path = root / c['path']
        if not path.exists():
            continue
        text = path.read_text(encoding='utf-8')
        result.chapters += 1
        if not text.startswith(f'# 第{c["number"]}回　{c["title"]}\n\n## {c["subtitle"]}\n'):
            errors.append(f'{c["path"]}: title or subtitle mismatch with series.json')
        if len(re.sub(r'\s', '', text)) < MIN_BODY_CHARS:
            errors.append(f'{c["path"]}: article is too short for a complete essay')
        if text.count('<!-- NAV:') != 2:
            errors.append(f'{c["path"]}: top/bottom navigation missing')
        if '次回予告' in text:
            errors.append(f'{c["path"]}: remove the next-episode label; the build adds the next title to the bottom navigation')
    for path, ast in asts.items():
        for n in walk(ast):
            if n.get('t') not in {'Link', 'Image'}:
                continue
            url = n['c'][-1][0]
            parsed = urlsplit(url)
            if parsed.scheme:
                result.external_links += 1
                if parsed.scheme not in {'https', 'mailto'}:
                    errors.append(f'{path.name}: unsupported URL scheme {parsed.scheme}')
                if parsed.scheme == 'https' and not parsed.netloc:
                    errors.append(f'{path.name}: invalid HTTPS URL')
                continue
            target = (path.parent / unquote(parsed.path)).resolve() if parsed.path else path
            result.local_links += 1
            if not target.is_relative_to(root):
                errors.append(f'{path.name}: path escapes repository: {url}')
                continue
            if not target.exists():
                errors.append(f'{path.name}: broken local link: {url}')
                continue
            if n.get('t') == 'Image' and not n['c'][1]:
                errors.append(f'{path.name}: missing image alt text')
            if parsed.fragment and target.suffix == '.md' and unquote(parsed.fragment) not in anchors.get(target, set()):
                errors.append(f'{path.name}: unknown anchor: {url}')
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
