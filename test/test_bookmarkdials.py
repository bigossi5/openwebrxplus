from unittest import TestCase
from unittest.mock import patch

from owrx.bookmarkdials import selectBookmarkDials
from owrx.bookmarks import Bookmark, Bookmarks


def bm(freq, mod="nfm", **kw):
    d = {"name": "bm%d" % freq, "frequency": freq, "modulation": mod}
    d.update(kw)
    return Bookmark(d)


class SelectBookmarkDialsTest(TestCase):
    def test_basic(self):
        dials = selectBookmarkDials([bm(100, "usb")], [], 100, 32)
        self.assertEqual(dials, [{"mode": "signal_alert", "frequency": 100, "underlying": "usb"}])

    def test_filters_unscannable(self):
        bms = [bm(1, "nfm", scannable=False), bm(2, "packet"), bm(3, "am")]
        dials = selectBookmarkDials(bms, [], 0, 32)
        self.assertEqual([d["frequency"] for d in dials], [3])

    def test_scannable_flag_with_unscannable_mode(self):
        self.assertEqual(selectBookmarkDials([bm(1, "ft8", scannable=True)], [], 0, 32), [])

    def test_dedupe_against_existing_any_mode(self):
        existing = [{"mode": "ft8", "frequency": 5, "underlying": "usb"}]
        dials = selectBookmarkDials([bm(5), bm(6)], existing, 0, 32)
        self.assertEqual([d["frequency"] for d in dials], [6])

    def test_dedupe_among_bookmarks(self):
        dials = selectBookmarkDials([bm(5), bm(5, "am")], [], 0, 32)
        self.assertEqual(len(dials), 1)

    def test_cap_nearest_first(self):
        bms = [bm(f) for f in (10, 1000, 490, 520, 200)]
        with self.assertLogs("owrx.bookmarkdials", level="WARNING"):
            dials = selectBookmarkDials(bms, [], 500, 3)
        self.assertEqual([d["frequency"] for d in dials], [490, 520, 200])

    def test_no_warning_when_within_cap(self):
        with self.assertNoLogs("owrx.bookmarkdials", level="WARNING"):
            selectBookmarkDials([bm(1), bm(2)], [], 0, 2)


class BookmarkSubscribeTest(TestCase):
    def _bookmarks(self):
        with patch.object(Bookmarks, "_getBookmarkFiles", return_value=[]), patch("owrx.bookmarks.Config"):
            return Bookmarks()

    def test_subscribe_and_cancel(self):
        b = self._bookmarks()
        calls = []
        sub = b.subscribe((0, 1000), lambda: calls.append(1))
        self.assertIn(sub, b.subscriptions)
        b.notifySubscriptions(bm(500))
        self.assertEqual(calls, [1])
        b.notifySubscriptions(bm(5000))
        self.assertEqual(calls, [1])
        sub.cancel()
        self.assertEqual(b.subscriptions, [])
        b.notifySubscriptions(bm(500))
        self.assertEqual(calls, [1])
