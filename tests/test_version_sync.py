from pathlib import Path
from unittest import TestCase

from update_version import normalize_version, replace_version_badges


class VersionSyncTests(TestCase):
    def test_normalizes_supported_versions(self):
        self.assertEqual(normalize_version("0.8.1\n"), "v0.8.1")
        self.assertEqual(normalize_version("v1.2.3.4"), "v1.2.3.4")
        with self.assertRaises(ValueError):
            normalize_version("release-8")

    def test_badge_replacement_does_not_touch_svg_numbers(self):
        html = (
            '<span class="navbar__badge">v0.7.0</span>'
            '<path d="M20.317 4.37a19.791 19.791" />'
        )
        result = replace_version_badges(html, "v0.8.0")
        self.assertIn('<span class="navbar__badge">v0.8.0</span>', result)
        self.assertIn('d="M20.317 4.37a19.791 19.791"', result)

class SiteAuthCtaContractTests(TestCase):
    def test_homepage_has_auth_aware_dashboard_cta(self):
        root = Path(__file__).resolve().parents[1]
        html = (root / "docs" / "index.html").read_text(encoding="utf-8")
        javascript = (root / "docs" / "js" / "app.js").read_text(encoding="utf-8")
        self.assertIn('id="heroSecondaryCta"', html)
        self.assertIn("ПЕРЕЙТИ К НАСТРОЙКАМ БОТА", javascript)
        self.assertIn("await initHomeAuthCta()", javascript)
