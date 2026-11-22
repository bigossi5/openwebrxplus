from unittest import TestCase
import json
import os
import tempfile

from owrx.alertcooldown import AlertCooldown
from owrx.watchlist import Watchlist, normalizeCallsign, parsePatterns


class WatchlistTestBase(TestCase):
    def setUp(self):
        AlertCooldown._lastAlert = {}
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.now = 1000000.0
        self.spots = []
        self.config = {
            "watchlist_enabled": True,
            "watchlist_calls": "",
            "watchlist_cooldown_min": 30,
            "newcountry_enabled": False,
            "newcountry_learning_hours": 24,
        }

    def make(self):
        return Watchlist(
            config=self.config,
            dataDir=self.tmp.name,
            emit=self.spots.append,
            clock=lambda: self.now,
            bandNamer=lambda f: "20m",
        )


class MatchingTest(WatchlistTestBase):
    def testNormalize(self):
        self.assertEqual("SP3ABC", normalizeCallsign("sp3abc-9"))
        self.assertEqual("SP3ABC", normalizeCallsign("SP3ABC/P"))
        self.assertEqual("SP3ABC", normalizeCallsign("SP3ABC/QRP"))
        self.assertEqual("SP3ABC", normalizeCallsign("SP3ABC/M-7"))
        self.assertEqual("DL/SP3ABC", normalizeCallsign("DL/SP3ABC"))

    def testParsePatternsIgnoresCommentsAndBlanks(self):
        patterns = parsePatterns("# header\n\nsp3abc  # me\n   \nW1*\n")
        self.assertEqual(["SP3ABC", "W1*"], [p[0] for p in patterns])

    def testExactAndCase(self):
        self.config["watchlist_calls"] = "sp3abc\n"
        w = self.make()
        w.check("FT8", "SP3ABC", freq=14074000)
        self.assertEqual(1, len(self.spots))
        self.assertEqual("watchlist", self.spots[0]["mode"])
        self.assertEqual("FT8", self.spots[0]["heard_mode"])
        self.assertEqual("SP3ABC", self.spots[0]["callsign"])

    def testSsidAndPortableStripped(self):
        self.config["watchlist_calls"] = "SP3ABC"
        w = self.make()
        w.check("APRS", "SP3ABC-9")
        w.check("FT8", "sp3abc/p")
        # cooldown is keyed on the normalised call, so only one spot
        self.assertEqual(1, len(self.spots))

    def testWildcards(self):
        self.config["watchlist_calls"] = "SP3*\n*/P\nK1?BC"
        w = self.make()
        w.check("FT8", "SP3XYZ")
        w.check("FT8", "DL1ABC/P")  # raw value matches */P
        w.check("FT8", "SP4XYZ")
        w.check("FT8", "K1?BC")  # '?' is literal, not a wildcard
        self.assertEqual(["SP3XYZ", "DL1ABC"], [s["callsign"] for s in self.spots[:2]])
        self.assertEqual(3, len(self.spots))

    def testNoMatchNoSpot(self):
        self.config["watchlist_calls"] = "SP3ABC"
        self.make().check("FT8", "SP3ABD")
        self.assertEqual([], self.spots)

    def testConfigChangeRecompiles(self):
        w = self.make()
        w.check("FT8", "SP3ABC")
        self.assertEqual([], self.spots)
        self.config["watchlist_calls"] = "SP3ABC"
        w.check("FT8", "SP3ABC")
        self.assertEqual(1, len(self.spots))

    def testDisabledIsNoop(self):
        self.config["watchlist_calls"] = "*"
        self.config["watchlist_enabled"] = False
        self.make().check("FT8", "SP3ABC")
        self.assertEqual([], self.spots)


class CooldownTest(WatchlistTestBase):
    def testCooldownSuppression(self):
        self.config["watchlist_calls"] = "SP3ABC"
        w = self.make()
        w.check("FT8", "SP3ABC")
        self.now += 10 * 60
        w.check("FT8", "SP3ABC")
        self.assertEqual(1, len(self.spots))
        self.now += 21 * 60
        w.check("FT8", "SP3ABC")
        self.assertEqual(2, len(self.spots))


class NewCountryTest(WatchlistTestBase):
    def setUp(self):
        super().setUp()
        self.config["watchlist_enabled"] = False
        self.config["newcountry_enabled"] = True

    def testLearningPeriodIsSilentButRecords(self):
        w = self.make()
        w.check("FT8", "JA1XYZ", freq=21074000)
        self.assertEqual([], self.spots)
        self.now += 25 * 3600
        w.check("FT8", "JA2XYZ", freq=21074000)  # Japan already recorded
        self.assertEqual([], self.spots)
        w.check("FT8", "SP3ABC", freq=21074000)  # Poland is new after the learning period
        self.assertEqual(1, len(self.spots))
        s = self.spots[0]
        self.assertEqual("newcountry", s["mode"])
        self.assertEqual("Poland", s["country"])
        self.assertEqual("PL", s["ccode"])
        self.assertEqual("FT8", s["heard_mode"])
        self.assertEqual("20m", s["band"])
        w.check("FT4", "SP9ABC", freq=14080000)
        self.assertEqual(1, len(self.spots))

    def testZeroLearningHoursAlertsImmediately(self):
        self.config["newcountry_learning_hours"] = 0
        self.make().check("FT8", "JA1XYZ", freq=21074000)
        self.assertEqual(1, len(self.spots))

    def testAprsIgnored(self):
        self.config["newcountry_learning_hours"] = 0
        self.make().check("APRS", "JA1XYZ-9")
        self.assertEqual([], self.spots)

    def testUnknownCountryIgnored(self):
        self.config["newcountry_learning_hours"] = 0
        self.make().check("FT8", "<...>")
        self.assertEqual([], self.spots)

    def testPersistenceRoundTrip(self):
        w = self.make()
        w.check("FT8", "JA1XYZ")
        path = os.path.join(self.tmp.name, "seen_countries.json")
        with open(path) as f:
            data = json.load(f)
        self.assertEqual(["Japan"], data["countries"])
        self.assertEqual(self.now, data["created"])
        self.assertFalse(os.path.exists(path + ".tmp"))

        # a new instance (restart) keeps the creation time and the seen set
        self.now += 25 * 3600
        w2 = self.make()
        w2.check("FT8", "JA1XYZ")
        self.assertEqual([], self.spots)
        w2.check("FT8", "SP3ABC")
        self.assertEqual(["Poland"], [s["country"] for s in self.spots])
        with open(path) as f:
            self.assertEqual(["Japan", "Poland"], json.load(f)["countries"])

    def testRestartDuringLearningKeepsLearning(self):
        self.make().check("FT8", "JA1XYZ")
        self.now += 3600
        w2 = self.make()
        w2.check("FT8", "SP3ABC")
        self.assertEqual([], self.spots)

    def testCorruptFileTolerated(self):
        path = os.path.join(self.tmp.name, "seen_countries.json")
        with open(path, "w") as f:
            f.write("{not json")
        w = self.make()
        w.check("FT8", "JA1XYZ")  # must not raise
        self.assertEqual([], self.spots)  # fresh learning period
        with open(path) as f:
            self.assertEqual(["Japan"], json.load(f)["countries"])
