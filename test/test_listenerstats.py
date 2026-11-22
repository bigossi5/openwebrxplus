from unittest import TestCase
from unittest.mock import patch, MagicMock
import json
import os
import tempfile

from owrx.activity import ActivityStore
from owrx.listenerstats import (
    bucketFrequency,
    aggregate,
    buildStats,
    collectSamples,
    ListenerSampler,
)

NOW = 1_800_000_000


class FakeProps(dict):
    pass


def fakeClient(center, offset, mod="nfm", ip="203.0.113.7"):
    c = MagicMock()
    c.ip = ip
    c.conn.handler.client_address = (ip, 1234)
    c.dsp.props = FakeProps(center_freq=center, offset_freq=offset, mod=mod)
    return c


class BucketTest(TestCase):
    def testRounding(self):
        self.assertEqual(bucketFrequency(145_500_400), 145_500_000)
        self.assertEqual(bucketFrequency(145_500_600), 145_501_000)
        self.assertEqual(bucketFrequency(145_502_600, 5000), 145_505_000)
        self.assertEqual(bucketFrequency(145_502_400, 5000), 145_500_000)


class AggregateTest(TestCase):
    def testAggregate(self):
        rows = [
            (100, 2, 145_500_100, "nfm"),
            (100, 2, 145_500_300, "nfm"),
            (160, 1, 145_500_200, "nfm"),
            (220, 0, None, None),
            (280, 1, 7_100_400, "lsb"),
        ]
        a = aggregate(rows)
        self.assertEqual(a["peak"], 2)
        self.assertEqual(a["samples"], 4)
        self.assertAlmostEqual(a["average"], (2 + 1 + 0 + 1) / 4)
        self.assertEqual(a["top"][0], {"freq": 145_500_000, "mod": "nfm", "minutes": 3})
        self.assertEqual(a["top"][1]["freq"], 7_100_000)

    def testEmpty(self):
        a = aggregate([])
        self.assertEqual((a["peak"], a["average"], a["top"]), (0, 0.0, []))

    def testTopLimit(self):
        rows = [(i, 1, 1_000_000 + i * 1000, "am") for i in range(30)]
        self.assertEqual(len(aggregate(rows, top=5)["top"]), 5)


class StoreTest(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = ActivityStore(os.path.join(self.tmp.name, "a.db"), 90)
        self.addCleanup(self.store.close)

    def testWindowsAndStats(self):
        # 2 hours ago and 3 days ago and 100 days ago
        self.store.addListenerSample(NOW - 7200, 1, [(145_500_000, "nfm")], now=NOW)
        self.store.addListenerSample(NOW - 3 * 86400, 2, [(7_100_000, "lsb"), (7_100_300, "lsb")], now=NOW)
        stats = buildStats(self.store, current=4, startedAt=NOW - 5000, now=NOW)
        self.assertEqual(stats["current"], 4)
        self.assertEqual(stats["uptime"], 5000)
        self.assertEqual(stats["periods"]["24h"]["peak"], 1)
        self.assertEqual(stats["periods"]["24h"]["top"][0]["freq"], 145_500_000)
        self.assertEqual(stats["periods"]["7d"]["peak"], 2)
        self.assertEqual(stats["periods"]["7d"]["top"][0]["freq"], 7_100_000)

    def testPrune(self):
        self.store.addListenerSample(NOW - 100 * 86400, 1, [(1_000_000, "am")], now=NOW - 100 * 86400)
        self.store.addListenerSample(NOW, 1, [(2_000_000, "am")], now=NOW + 7200)
        rows = self.store.listenerRows(0)
        self.assertEqual([r[2] for r in rows], [2_000_000])

    def testNoClientsWritesZeroRow(self):
        self.store.addListenerSample(NOW, 0, [], now=NOW)
        self.assertEqual(self.store.listenerRows(0), [(NOW, 0, None, None)])

    def testNoIpData(self):
        ip = "203.0.113.7"
        clients = [fakeClient(145_000_000, 500_000, ip=ip), fakeClient(7_000_000, 100_000, "lsb", ip=ip)]
        sampler = ListenerSampler()
        sampler.sampleOnce(store=self.store, clients=clients, now=NOW)
        # the database contains only the four anonymous columns
        cols = [r[1] for r in self.store.conn.execute("PRAGMA table_info(listeners)").fetchall()]
        self.assertEqual(cols, ["ts", "count", "freq", "mod"])
        dump = json.dumps(self.store.listenerRows(0)) + json.dumps(buildStats(self.store, 2, NOW - 10, now=NOW))
        self.assertNotIn(ip, dump)
        self.assertNotIn("ip", json.loads(json.dumps(buildStats(self.store, 2, NOW - 10, now=NOW))).keys())


class CollectTest(TestCase):
    def testCollect(self):
        a = fakeClient(145_000_000, 500_000)
        b = fakeClient(7_000_000, 100_000, "lsb")
        idle = MagicMock()
        idle.dsp = None
        broken = MagicMock()
        broken.dsp.props = {}
        count, tuned = collectSamples([a, b, idle, broken])
        self.assertEqual(count, 4)
        self.assertEqual(tuned, [(145_500_000, "nfm"), (7_100_000, "lsb")])

    def testDoesNotCreateDsp(self):
        c = MagicMock()
        c.dsp = None
        collectSamples([c])
        c.getDsp.assert_not_called()


class DisabledTest(TestCase):
    def testSamplerDoesNotStartWhenDisabled(self):
        s = ListenerSampler(interval=0.01)
        s.apply(False)
        self.assertIsNone(s.thread)

    def testSamplerStartsAndStops(self):
        s = ListenerSampler(interval=0.01)
        with patch.object(ListenerSampler, "sampleOnce", return_value=True):
            s.apply(True)
            self.assertTrue(s.thread.is_alive())
            thread = s.thread
            s.apply(False)
            thread.join(2)
            self.assertFalse(thread.is_alive())

    def testIsEnabledFollowsConfig(self):
        fake = MagicMock()
        fake.get.return_value = {"stats_page_enabled": False}
        with patch("owrx.config.Config", fake):
            self.assertFalse(ListenerSampler.isEnabled())
        fake.get.return_value = {"stats_page_enabled": True}
        with patch("owrx.config.Config", fake):
            self.assertTrue(ListenerSampler.isEnabled())

    def testControllerAnswers404WhenDisabled(self):
        from owrx.controllers.stats import StatsController

        sent = {}
        c = StatsController.__new__(StatsController)
        c.send_response = lambda content, code=200, **kw: sent.update(code=code)
        with patch.object(StatsController, "isEnabled", staticmethod(lambda: False)):
            c.indexAction()
        self.assertEqual(sent["code"], 404)
