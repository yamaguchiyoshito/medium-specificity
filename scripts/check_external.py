#!/usr/bin/env python3
"""Check that the externally hosted images in chapters/ are still reachable (network required)."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re
import sys
import urllib.error
import urllib.request
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build import EXTERNAL_IMAGE_HOSTS, ROOT  # noqa: E402

IMAGE = re.compile(r'^!\[[^\]]*\]\((https://[^)\s]+)[^)]*\)\s*$', re.M)
USER_AGENT = 'medium-specificity-link-check/1.0 (https://github.com/yamaguchiyoshito/medium-specificity)'


def external_images() -> list[tuple[str, str]]:
    found = []
    for path in sorted((ROOT / 'chapters').glob('*.md')):
        for url in IMAGE.findall(path.read_text(encoding='utf-8')):
            found.append((path.name, url))
    return found


def probe(url: str, timeout: float = 20) -> str | None:
    """Return an error message, or None when the URL answers with an image."""
    request = urllib.request.Request(url, method='HEAD', headers={'User-Agent': USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            kind = response.headers.get_content_type()
            return None if kind.startswith('image/') else f'not an image: {kind}'
    except urllib.error.HTTPError as exc:
        return f'HTTP {exc.code}'
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return f'unreachable: {exc}'


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    errors = []
    images = external_images()
    for name, url in images:
        if urlsplit(url).netloc not in EXTERNAL_IMAGE_HOSTS:
            errors.append(f'{name}: host is not allowed: {url}')
            continue
        problem = probe(url)
        if problem:
            errors.append(f'{name}: {problem}: {url}')
    print(json.dumps({'external_images': len(images), 'errors': errors}, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == '__main__':
    raise SystemExit(main())
