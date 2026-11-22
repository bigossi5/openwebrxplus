from unittest import TestCase
from urllib.parse import urljoin
import pathlib
import re

SETTINGS_DIR = pathlib.Path(__file__).resolve().parent.parent / "owrx" / "controllers" / "settings"

# Pages served from /settings/<name> must not use relative URLs that start with
# "settings/": the browser resolves them against /settings/ and ends up on
# /settings/settings/<name> (a 404). Only the landing page /settings itself
# (htdocs/settings.html and the logs button in settings/__init__.py) may use
# the "settings/..." form.
BAD = re.compile(r"""(?:href|action|src)=["']settings/""")


class RelativeUrlTest(TestCase):
    def testResolutionRule(self):
        page = "https://host/settings/satellites"
        self.assertEqual(urljoin(page, "satellites"), "https://host/settings/satellites")
        self.assertEqual(urljoin(page, "settings/satellites"), "https://host/settings/settings/satellites")

    def testSettingsSubpagesDoNotUseLandingPageUrls(self):
        offenders = []
        for path in sorted(SETTINGS_DIR.glob("*.py")):
            if path.name == "__init__.py":
                continue
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if BAD.search(line):
                    offenders.append("{0}:{1}: {2}".format(path.name, number, line.strip()))
        self.assertEqual(offenders, [], "relative 'settings/...' URL on a /settings/<page> page")
