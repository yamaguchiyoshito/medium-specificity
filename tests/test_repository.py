from pathlib import Path
import json
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from build import parse_markdown, render, map_url, build, site_index_text
from validate import validate, walk, svg_errors
from check_html import check, Document

SERIES = json.loads((ROOT / 'series.json').read_text(encoding='utf-8'))
CHAPTERS = len(SERIES['chapters'])


class RepositoryTests(unittest.TestCase):
    def test_entire_repository(self):
        result, errors = validate()
        self.assertEqual(errors, [])
        self.assertEqual(result.chapters, CHAPTERS)

    def test_footnotes_render_as_notes(self):
        output = render('本文[^a]。\n\n[^a]: 注記。\n')
        self.assertIn('class="footnotes', output)
        self.assertNotIn('<script', output)

    def test_tables_are_wrapped_and_unsized(self):
        output = render('| 回 | 文章 |\n| --- | --- |\n| 01 | 本文 |\n')
        self.assertIn('<div class="table-wrap"><table', output)
        self.assertIn('</table></div>', output)
        self.assertNotIn('<col style', output)

    def test_nav_markers_become_nav_cards(self):
        text = '<!-- NAV:TOP -->\n[← 第4回](a.md) | [連載目次](../README.md) | [第6回 →](b.md)\n<!-- /NAV -->\n\n本文\n\n<!-- NAV:BOTTOM -->\n---\n\n[← 第4回](a.md) | [連載目次](../README.md)\n<!-- /NAV -->\n'
        output = render(text, next_note='次回　第6回「題名」')
        self.assertEqual(output.count('<nav class="chapter-nav'), 2)
        self.assertIn('chapter-nav-next">次回　第6回「題名」', output)
        self.assertNotIn('<!-- NAV:', output)
        self.assertNotIn('<h2', output)
        self.assertIn('class="sep"', output)

    def test_parts_tile_the_series(self):
        covered = [n for p in SERIES['parts'] for n in range(p['chapters'][0], p['chapters'][1] + 1)]
        self.assertEqual(covered, list(range(1, CHAPTERS + 1)))

    def test_dollar_signs_are_not_math(self):
        ast = parse_markdown('価格は $5 と $7 です。\n')
        self.assertFalse(any(n.get('t') == 'Math' for n in walk(ast)))

    def test_site_index_stops_at_marker(self):
        text = '# T\n\n本文\n\n<!-- SITE-INDEX-END -->\n\n## GitHubで読む\n\n運用\n'
        self.assertEqual(site_index_text(text), '# T\n\n本文\n')
        self.assertEqual(site_index_text('# T\n\n本文\n'), '# T\n\n本文\n')
        readme = (ROOT / 'README.md').read_text(encoding='utf-8')
        self.assertIn(f'## 全{CHAPTERS}回の目次', site_index_text(readme))
        self.assertNotIn('## GitHubで読む', site_index_text(readme))

    def test_relative_links(self):
        self.assertEqual(map_url('../README.md'), '../index.html')
        self.assertEqual(map_url('one.md#test'), 'one.html#test')
        self.assertEqual(map_url('https://example.org/a.md'), 'https://example.org/a.md')

    def test_build_refuses_source_overwrite(self):
        with self.assertRaises(RuntimeError):
            build(ROOT)

    def test_chapter_slugs_are_unique(self):
        self.assertEqual(len({c['slug'] for c in SERIES['chapters']}), CHAPTERS)

    def test_complete_reader_links(self):
        with tempfile.TemporaryDirectory() as d:
            output = Path(d) / 'reader'
            build(output)
            report = check(output)
            self.assertEqual(report['errors'], [])
            self.assertEqual(report['chapter_pages'], CHAPTERS)

    def test_combined_footnote_ids_are_namespaced(self):
        text = 'A[^a].\n\n[^a]: A note.\n'
        doc = Document(render(text, prefix='a-') + render(text, prefix='b-'))
        self.assertEqual(len(doc.ids), len(set(doc.ids)))

    def test_html_checker_detects_missing_target(self):
        with tempfile.TemporaryDirectory() as d:
            output = Path(d)
            (output / 'index.html').write_text('<html><a href="missing.html">Link</a></html>')
            self.assertTrue(any('missing target' in e for e in check(output)['errors']))

    def test_caption_with_link_becomes_figcaption(self):
        text = '![代替テキスト](https://commons.wikimedia.org/wiki/Special:FilePath/A.jpg?width=800)\n\n*図1-1：説明。出典：[Wikimedia Commons](https://commons.wikimedia.org/wiki/File:A.jpg)。*\n\n次の段落。\n'
        output = render(text)
        self.assertEqual(output.count('<figcaption'), 1)
        self.assertIn('<figcaption>図1-1：説明。出典：<a href="https://commons.wikimedia.org/wiki/File:A.jpg">Wikimedia Commons</a>。</figcaption>', output)
        self.assertNotIn('<p><em>図1-1', output)
        self.assertIn('alt="代替テキスト"', output)

    def test_alt_only_figure_has_no_caption(self):
        output = render('![表紙の説明](../assets/illustrations/x.svg)\n')
        self.assertEqual(output.count('<figcaption'), 0)
        self.assertIn('alt="表紙の説明"', output)

    def test_svg_figures_get_scroll_container_and_full_size_link(self):
        output = render('![説明](../assets/illustrations/x.svg)\n\n*図1-1：説明。*\n')
        self.assertIn('<div class="figure-scroll"><a class="figure-link" href="../assets/illustrations/x.svg"', output)
        self.assertEqual(output.count('<figcaption'), 1)
        photo = render('![説明](https://commons.wikimedia.org/wiki/Special:FilePath/A.jpg)\n\n*図1-1：説明。*\n')
        self.assertNotIn('figure-scroll', photo)

    def test_footnotes_move_before_bottom_nav(self):
        text = '本文[^a]。\n\n## 参考文献・注記\n\n[^a]: 注記。\n\n<!-- NAV:BOTTOM -->\n---\n\n[← 第1回](a.md) | [連載目次](../README.md)\n<!-- /NAV -->\n'
        output = render(text)
        self.assertLess(output.index('class="footnotes'), output.index('chapter-nav-bottom'))
        self.assertEqual(output.count('class="footnotes'), 1)

    def test_site_has_no_footer(self):
        with tempfile.TemporaryDirectory() as d:
            output = Path(d) / 'reader'
            build(output)
            for page in output.rglob('*.html'):
                self.assertNotIn('<footer', page.read_text(encoding='utf-8'))

    def test_html_checker_allows_only_listed_image_hosts(self):
        with tempfile.TemporaryDirectory() as d:
            output = Path(d)
            (output / 'index.html').write_text('<html><figure><img src="https://commons.wikimedia.org/wiki/Special:FilePath/A.jpg"><figcaption>c</figcaption></figure></html>')
            self.assertFalse(any('external resource' in e for e in check(output)['errors']))
            (output / 'index.html').write_text('<html><img src="https://example.org/a.jpg"></html>')
            self.assertTrue(any('external resource' in e for e in check(output)['errors']))

    def test_svg_rejects_executable_content(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'x.svg'
            p.write_text('<svg viewBox="0 0 10 10" role="img"><title>X</title><desc>Y</desc><script>alert(1)</script></svg>')
            self.assertTrue(any('forbidden SVG' in x for x in svg_errors(p)))

    def test_html_checker_rejects_network_images(self):
        with tempfile.TemporaryDirectory() as d:
            output = Path(d)
            (output / 'index.html').write_text('<html><img src="https://example.org/image.svg"></html>')
            self.assertTrue(any('external resource' in e for e in check(output)['errors']))


if __name__ == '__main__':
    unittest.main()
