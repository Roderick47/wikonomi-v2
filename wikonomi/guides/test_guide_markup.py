from django.test import SimpleTestCase

from .templatetags.guide_markup import guide_markdown


class GuideRichMarkupTests(SimpleTestCase):
    def test_renders_structured_styled_blocks(self):
        rendered = str(guide_markdown(
            '## Before you start\n\n- Bring ID\n- Bring a photo\n\n> Keep copies of everything.\n\n---\n\n### Fees'
        ))

        self.assertIn('<h2 class=', rendered)
        self.assertIn('Before you start</h2>', rendered)
        self.assertIn('list-disc', rendered)
        self.assertIn('<blockquote class=', rendered)
        self.assertIn('<hr class=', rendered)
        self.assertIn('<h3 class=', rendered)

    def test_preserves_safe_inline_markup_and_rejects_raw_html(self):
        rendered = str(guide_markdown(
            '<script>alert(1)</script> **Important** *note* [official site](https://example.com)'
        ))

        self.assertNotIn('<script', rendered)
        self.assertIn('<strong>Important</strong>', rendered)
        self.assertIn('<em>note</em>', rendered)
        self.assertIn('href="https://example.com"', rendered)
        self.assertIn('rel="noopener noreferrer"', rendered)

    def test_does_not_create_non_http_links(self):
        rendered = str(guide_markdown('[unsafe](javascript:alert(1))'))

        self.assertNotIn('href=', rendered)
