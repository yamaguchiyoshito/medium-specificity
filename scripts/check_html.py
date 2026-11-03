#!/usr/bin/env python3
"""Verify generated HTML: links, unique IDs, offline assets, no scripts."""
from __future__ import annotations
import argparse
from collections import Counter
from html.parser import HTMLParser
import json
from pathlib import Path
from urllib.parse import unquote, urlsplit

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build import EXTERNAL_IMAGE_HOSTS  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


class Document(HTMLParser):
    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.ids = []
        self.links = []
        self.scripts = 0
        self.images = 0
        self.figcaptions = 0
        self.stray_captions = text.count('<p><em>図')
        self.feed(text)

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if 'id' in attrs:
            self.ids.append(attrs['id'])
        if tag == 'script':
            self.scripts += 1
        if tag == 'img':
            self.images += 1
        if tag == 'figcaption':
            self.figcaptions += 1
        for attr in ['href', 'src']:
            if attr in attrs:
                self.links.append((tag, attr, attrs[attr]))


def check(site: Path) -> dict:
    site = site.resolve()
    errors = []
    docs = {p.resolve(): Document(p.read_text(encoding='utf-8')) for p in sorted(site.rglob('*.html'))}
    for path, doc in docs.items():
        for ident, n in Counter(doc.ids).items():
            if n > 1:
                errors.append(f'{path.name}: duplicate ID {ident}')
        if doc.scripts:
            errors.append(f'{path.name}: unexpected script dependency')
        for tag, attr, url in doc.links:
            parsed = urlsplit(url)
            if parsed.scheme:
                if attr == 'src' and parsed.scheme != 'data' and not (tag == 'img' and parsed.scheme == 'https' and parsed.netloc in EXTERNAL_IMAGE_HOSTS):
                    errors.append(f'{path.name}: external resource dependency {url}')
                continue
            target = (path.parent / unquote(parsed.path)).resolve() if parsed.path else path
            if not target.is_relative_to(site):
                errors.append(f'{path.name}: link escapes output: {url}')
                continue
            if not target.exists():
                errors.append(f'{path.name}: missing target {url}')
                continue
            if parsed.fragment and target in docs and unquote(parsed.fragment) not in docs[target].ids:
                errors.append(f'{path.name}: missing anchor {url}')
    if not docs:
        errors.append('No generated HTML pages found')
    series = json.loads((ROOT / 'series.json').read_text(encoding='utf-8'))
    chapters = [p for p in docs if p.parent.name == 'chapters']
    for path, doc in docs.items():
        if doc.stray_captions:
            errors.append(f'{path.name}: figure caption paragraph was not merged into figcaption')
        if path.parent.name == 'chapters' and doc.figcaptions != doc.images:
            errors.append(f'{path.name}: {doc.images} figures but {doc.figcaptions} figcaptions')
    if len(chapters) != len(series['chapters']):
        errors.append(f'Expected {len(series["chapters"])} chapter HTML pages')
    if (site / 'complete.html').resolve() not in docs:
        errors.append('Missing complete.html')
    return dict(html_pages=len(docs), chapter_pages=len(chapters), errors=errors)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--site', type=Path, default=ROOT / '_site')
    args = parser.parse_args()
    report = check(args.site)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if report['errors'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
