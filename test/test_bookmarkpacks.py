from unittest import TestCase
import json
import os
import pathlib
import tempfile

from owrx.bookmarks import Bookmark
from owrx import bookmarkpacks
from owrx.bookmarkpacks import (
    sanitizeBookmark,
    validatePack,
    loadPack,
    listPacks,
    installPack,
    removePack,
    exportBookmarks,
    importBookmarks,
)

REPO_PACKS = pathlib.Path(__file__).resolve().parent.parent / "bookmark-packs"


class FakeStore(object):
    """Mimics the parts of Bookmarks used by the pack code."""

    def __init__(self, bookmarks=None):
        self.bookmarks = list(bookmarks or [])
        self.stored = 0

    def getEditableBookmarks(self):
        return list(self.bookmarks)

    def addBookmark(self, b):
        self.bookmarks.append(b)

    def removeBookmark(self, b):
        self.bookmarks.remove(b)

    def store(self):
        self.stored += 1


def bm(name="A", freq=145500000, mod="nfm", **kw):
    d = {"name": name, "frequency": freq, "modulation": mod}
    d.update(kw)
    return d


class BookmarkPackFieldTest(TestCase):
    def testPackRoundTrip(self):
        b = Bookmark(bm(pack="pmr446"))
        self.assertEqual(b.getPack(), "pmr446")
        self.assertEqual(b.__dict__()["pack"], "pmr446")
        self.assertEqual(Bookmark(b.__dict__()).getPack(), "pmr446")

    def testNoPackNotEmitted(self):
        b = Bookmark(bm())
        self.assertEqual(b.getPack(), "")
        self.assertNotIn("pack", b.__dict__())


class SanitizeTest(TestCase):
    def testValid(self):
        d = bm(name="  X  ", freq="145500000")
        self.assertIsNone(sanitizeBookmark(d))
        self.assertEqual(d["name"], "X")
        self.assertEqual(d["frequency"], 145500000)
        self.assertEqual(d["underlying"], "")

    def testInvalid(self):
        self.assertIsNotNone(sanitizeBookmark({"name": "x"}))
        self.assertIsNotNone(sanitizeBookmark(bm(name="  ")))
        self.assertIsNotNone(sanitizeBookmark(bm(freq=0)))
        self.assertIsNotNone(sanitizeBookmark(bm(freq="abc")))
        self.assertIsNotNone(sanitizeBookmark(bm(freq=True)))
        self.assertIsNotNone(sanitizeBookmark(bm(mod="nonsense")))
        self.assertIsNotNone(sanitizeBookmark("string"))
        self.assertIsNotNone(sanitizeBookmark(bm(scannable="yes")))


class ShippedPacksTest(TestCase):
    def testAllShippedPacksValid(self):
        files = sorted(REPO_PACKS.glob("*.json"))
        if not files:
            # e.g. the pybuild copy of the tree used by dpkg-buildpackage has no data files
            self.skipTest("bookmark-packs directory not present in this tree")
        for f in files:
            pack = json.loads(f.read_text(encoding="utf-8"))
            self.assertEqual(pack["id"], f.stem)
            self.assertIsNone(validatePack(pack), f.name)
            self.assertTrue(pack["source"].startswith("http"), f.name)
            freqs = [b["frequency"] for b in pack["bookmarks"]]
            self.assertEqual(len(freqs), len(set(freqs)), "duplicate frequency in " + f.name)

    def testNoEmergencyServicePack(self):
        for f in REPO_PACKS.glob("*.json"):
            text = f.read_text(encoding="utf-8").lower()
            for word in ("police", "policja", "fire brigade", "tetra"):
                self.assertNotIn(word, text)


class PackInstallTest(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = self.tmp.name
        self.write("demo", {"id": "demo", "name": "Demo", "description": "d", "source": "http://x",
                            "bookmarks": [bm("One", 100000000), bm("Two", 101000000, "am")]})

    def write(self, packId, content):
        with open(os.path.join(self.dir, packId + ".json"), "w") as f:
            json.dump(content, f)

    def testValidateRejects(self):
        self.assertIsNotNone(validatePack({"id": "../evil", "name": "x", "bookmarks": [bm()]}))
        self.assertIsNotNone(validatePack({"id": "a", "name": "x", "bookmarks": []}))
        self.assertIsNotNone(validatePack({"id": "a", "name": "x", "bookmarks": [{"name": "n"}]}))
        self.assertIsNone(validatePack({"id": "a", "name": "x", "bookmarks": [bm()]}))

    def testPathTraversalRefused(self):
        self.assertIsNone(loadPack("../demo", self.dir))
        with self.assertRaises(ValueError):
            installPack("../demo", self.dir, FakeStore())

    def testIdMustMatchFile(self):
        self.write("other", {"id": "demo", "name": "x", "bookmarks": [bm()]})
        self.assertIsNone(loadPack("other", self.dir))

    def testInstallTagsAndStores(self):
        store = FakeStore()
        r = installPack("demo", self.dir, store)
        self.assertEqual(r, {"added": 2, "skipped": 0})
        self.assertEqual({b.getPack() for b in store.bookmarks}, {"demo"})
        self.assertEqual(store.stored, 1)

    def testInstallSkipsExistingFrequency(self):
        store = FakeStore([Bookmark(bm("Mine", 100000000))])
        r = installPack("demo", self.dir, store)
        self.assertEqual(r, {"added": 1, "skipped": 1})
        self.assertEqual(len(store.bookmarks), 2)
        # the user bookmark stays untouched
        self.assertEqual(store.bookmarks[0].getName(), "Mine")
        # second install adds nothing
        self.assertEqual(installPack("demo", self.dir, store), {"added": 0, "skipped": 2})

    def testUnknownPack(self):
        with self.assertRaises(ValueError):
            installPack("nope", self.dir, FakeStore())

    def testListShowsInstalledState(self):
        store = FakeStore()
        self.assertEqual(listPacks(self.dir, store)[0]["installed"], 0)
        installPack("demo", self.dir, store)
        info = listPacks(self.dir, store)[0]
        self.assertEqual((info["id"], info["count"], info["installed"]), ("demo", 2, 2))

    def testRemoveOnlyPackBookmarks(self):
        store = FakeStore([Bookmark(bm("Mine", 150000000))])
        installPack("demo", self.dir, store)
        self.assertEqual(removePack("demo", store), 2)
        self.assertEqual([b.getName() for b in store.bookmarks], ["Mine"])
        self.assertEqual(removePack("demo", store), 0)

    def testRepoDirectoryFallback(self):
        if not REPO_PACKS.is_dir():
            self.skipTest("bookmark-packs directory not present in this tree")
        self.assertTrue(os.path.isdir(bookmarkpacks.packDirectory()))


class ImportExportTest(TestCase):
    def testExportContainsPack(self):
        store = FakeStore([Bookmark(bm(pack="demo"))])
        data = json.loads(exportBookmarks(store))
        self.assertEqual(data[0]["pack"], "demo")

    def testImportRoundTrip(self):
        src = FakeStore([Bookmark(bm("A", 100000000)), Bookmark(bm("B", 101000000, "am"))])
        text = exportBookmarks(src)
        dst = FakeStore()
        self.assertEqual(importBookmarks(text, dst), {"added": 2, "skipped": 0, "invalid": 0})
        self.assertEqual(sorted(b.getFrequency() for b in dst.bookmarks), [100000000, 101000000])

    def testImportSkipsExistingAndCountsInvalid(self):
        dst = FakeStore([Bookmark(bm("Mine", 100000000))])
        text = json.dumps([bm("A", 100000000), bm("B", 102000000), {"name": "bad"}, "junk", bm("C", -5)])
        self.assertEqual(importBookmarks(text, dst), {"added": 1, "skipped": 1, "invalid": 3})

    def testImportDropsPackTagAndUnknownKeys(self):
        dst = FakeStore()
        importBookmarks(json.dumps([dict(bm(), pack="evil", srcFile="/etc/passwd")]), dst)
        self.assertEqual(dst.bookmarks[0].getPack(), "")
        self.assertIsNone(dst.bookmarks[0].getSrcFile())

    def testImportRejectsMalformed(self):
        for text in ["not json", "{}", "42", b"\xff\xfe"]:
            with self.assertRaises(ValueError):
                importBookmarks(text, FakeStore())

    def testImportLimit(self):
        old = bookmarkpacks.MAX_IMPORT_BOOKMARKS
        bookmarkpacks.MAX_IMPORT_BOOKMARKS = 2
        try:
            with self.assertRaises(ValueError):
                importBookmarks(json.dumps([bm(freq=i + 1) for i in range(3)]), FakeStore())
        finally:
            bookmarkpacks.MAX_IMPORT_BOOKMARKS = old
