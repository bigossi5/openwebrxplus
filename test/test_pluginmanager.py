from unittest import TestCase
import tempfile
import shutil
import os
import io
import zipfile

from owrx.pluginmanager import PluginManager


def _makeZip(entries):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in entries.items():
            zf.writestr(name, content)
    return buf.getvalue()


class PluginManagerInstallTest(TestCase):
    def setUp(self):
        self.tmpDir = tempfile.mkdtemp()
        # bypass __init__ (which wires Config) since install() itself
        # doesn't touch Config at all
        self.manager = PluginManager.__new__(PluginManager)
        self.manager._pluginsDir = lambda: self.tmpDir

    def tearDown(self):
        shutil.rmtree(self.tmpDir, ignore_errors=True)

    def testValidPackageInstalls(self):
        data = _makeZip({"myplugin/myplugin.js": "console.log('hi');"})
        name = self.manager.install(data)
        self.assertEqual(name, "myplugin")
        self.assertTrue(os.path.isfile(os.path.join(self.tmpDir, "myplugin", "myplugin.js")))

    def testReinstallReplacesExisting(self):
        data1 = _makeZip({"myplugin/myplugin.js": "console.log('v1');"})
        self.manager.install(data1)
        data2 = _makeZip({"myplugin/myplugin.js": "console.log('v2');", "myplugin/extra.txt": "hi"})
        self.manager.install(data2)
        with open(os.path.join(self.tmpDir, "myplugin", "myplugin.js")) as f:
            self.assertIn("v2", f.read())
        self.assertTrue(os.path.isfile(os.path.join(self.tmpDir, "myplugin", "extra.txt")))

    def testRejectsMultipleTopLevelFolders(self):
        data = _makeZip({"a/a.js": "x", "b/b.js": "y"})
        with self.assertRaises(ValueError):
            self.manager.install(data)

    def testRejectsPathTraversal(self):
        data = _makeZip({"evil/evil.js": "x", "evil/../../etc/passwd": "y"})
        with self.assertRaises(ValueError):
            self.manager.install(data)

    def testRejectsDisallowedExtension(self):
        data = _makeZip({"myplugin/myplugin.js": "x", "myplugin/evil.py": "import os"})
        with self.assertRaises(ValueError):
            self.manager.install(data)

    def testRejectsReservedName(self):
        data = _makeZip({"utils/utils.js": "x"})
        with self.assertRaises(ValueError):
            self.manager.install(data)

    def testRejectsInvalidName(self):
        data = _makeZip({"../evil/evil.js": "x"})
        with self.assertRaises(ValueError):
            self.manager.install(data)

    def testRejectsMissingMainJs(self):
        data = _makeZip({"myplugin/readme.md": "hello"})
        with self.assertRaises(ValueError):
            self.manager.install(data)

    def testRejectsBadZip(self):
        with self.assertRaises(ValueError):
            self.manager.install(b"not a zip file")

    def testRejectsOversizedUncompressed(self):
        big = b"0" * (25 * 1024 * 1024)
        data = _makeZip({"myplugin/myplugin.js": big})
        with self.assertRaises(ValueError):
            self.manager.install(data)

    def testUninstallRejectsReservedName(self):
        with self.assertRaises(ValueError):
            self.manager.uninstall("utils")
