"""
Callsign watchlist and new-country alerts.

Decoders (WSJT-X, JS8, APRS) call Watchlist.check() for every heard callsign.
Hits are emitted as "watchlist" / "newcountry" spots through the ReportingEngine
(currently only consumed by the Discord reporter).

This module is deliberately dependency-light: heavy modules are imported lazily.
"""
from owrx.alertcooldown import AlertCooldown
from owrx.lookup import HamCallsign
import json
import logging
import os
import re
import threading
import time

logger = logging.getLogger(__name__)

# modes (not APRS) for which the new-country check is done
NEWCOUNTRY_MODES = ["FT8", "FT4", "WSPR", "JS8", "FST4W", "FST4", "Q65", "JT65", "JT9", "MSK144"]

SEEN_FILE = "seen_countries.json"

_SSID = re.compile(r"-\d{1,2}$")
_PORTABLE = re.compile(r"/(P|M|QRP|MM|AM)$")


def normalizeCallsign(callsign):
    """Upper-case and strip -SSID and portable suffixes (/P, /M, /QRP, /MM, /AM)."""
    call = (callsign or "").strip().upper()
    call = _SSID.sub("", call)
    previous = None
    while previous != call:
        previous = call
        call = _PORTABLE.sub("", call)
        call = _SSID.sub("", call)
    return call


def parsePatterns(text):
    """Compile a multi-line watchlist string into a list of (patternText, regex)."""
    patterns = []
    for line in (text or "").splitlines():
        line = line.split("#", 1)[0].strip().upper()
        if not line:
            continue
        regex = re.compile("^" + ".*".join(re.escape(part) for part in line.split("*")) + "$")
        patterns.append((line, regex))
    return patterns


class Watchlist(object):
    sharedInstance = None
    creationLock = threading.Lock()

    @staticmethod
    def getSharedInstance():
        with Watchlist.creationLock:
            if Watchlist.sharedInstance is None:
                Watchlist.sharedInstance = Watchlist()
        return Watchlist.sharedInstance

    def __init__(self, config=None, dataDir=None, emit=None, clock=None, bandNamer=None):
        # all injectable for tests
        self._config = config
        self._dataDir = dataDir
        self._emit = emit
        self._clock = clock or time.time
        self._bandNamer = bandNamer
        self._lock = threading.RLock()
        self._patternText = None
        self._patterns = []
        self._seen = None
        self._created = None

    # --- helpers -------------------------------------------------------

    def _cfg(self, key, default=None):
        try:
            if self._config is not None:
                return self._config.get(key, default)
            from owrx.config import Config

            return Config.get()[key]
        except Exception:
            return default

    def _getDataDir(self):
        if self._dataDir is not None:
            return self._dataDir
        from owrx.config.core import CoreConfig

        return CoreConfig().get_data_directory()

    def _seenPath(self):
        return os.path.join(self._getDataDir(), SEEN_FILE)

    def _getPatterns(self):
        text = self._cfg("watchlist_calls", "") or ""
        with self._lock:
            if text != self._patternText:
                try:
                    self._patterns = parsePatterns(text)
                except Exception:
                    logger.exception("Invalid watchlist")
                    self._patterns = []
                self._patternText = text
            return self._patterns

    def _matches(self, callsign):
        raw = (callsign or "").strip().upper()
        norm = normalizeCallsign(raw)
        for _, regex in self._getPatterns():
            if regex.match(norm) or regex.match(raw):
                return True
        return False

    def _send(self, spot):
        if self._emit is not None:
            self._emit(spot)
            return
        from owrx.reporting import ReportingEngine

        ReportingEngine.getSharedInstance().spot(spot)

    def _bandName(self, freq):
        if freq is None:
            return None
        try:
            if self._bandNamer is not None:
                return self._bandNamer(freq)
            from owrx.bands import Bandplan

            band = Bandplan.getSharedInstance().findBand(freq)
            return band.getName() if band is not None else None
        except Exception:
            return None

    # --- persistence ---------------------------------------------------

    def _loadSeen(self, now):
        """must be called with the lock held"""
        if self._seen is not None:
            return
        self._seen = set()
        self._created = now
        path = self._seenPath()
        exists = os.path.exists(path)
        if exists:
            try:
                with open(path, "r") as f:
                    data = json.load(f)
                self._seen = set(str(c) for c in data["countries"])
                self._created = float(data["created"])
                return
            except Exception:
                logger.warning("Could not read %s, starting a new learning period", path)
                self._seen = set()
                self._created = now
        # new (or unreadable) file: persist the creation time right away so the
        # learning period survives restarts
        self._saveSeen()

    def _saveSeen(self):
        """must be called with the lock held"""
        path = self._seenPath()
        tmp = path + ".tmp"
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(tmp, "w") as f:
                json.dump({"created": self._created, "countries": sorted(self._seen)}, f)
            os.replace(tmp, path)
        except Exception:
            logger.exception("Could not write %s", path)

    # --- public API ----------------------------------------------------

    def check(self, mode, callsign, freq=None, db=None, locator=None, msg=None, timestamp=None, extra=None):
        watchEnabled = bool(self._cfg("watchlist_enabled", False))
        countryEnabled = bool(self._cfg("newcountry_enabled", False))
        if not (watchEnabled or countryEnabled) or not callsign:
            return
        now = self._clock()
        norm = normalizeCallsign(callsign)
        if not norm:
            return
        if timestamp is None:
            timestamp = int(now * 1000)

        if watchEnabled and self._matches(callsign):
            cooldown = float(self._cfg("watchlist_cooldown_min", 30) or 0) * 60
            if AlertCooldown.shouldAlert(("watch", norm), cooldown, now):
                self._send(
                    {
                        "mode": "watchlist",
                        "callsign": norm,
                        "heard_mode": mode,
                        "freq": freq,
                        "db": db,
                        "locator": locator,
                        "msg": msg,
                        "timestamp": timestamp,
                    }
                )

        if countryEnabled and mode in NEWCOUNTRY_MODES:
            self._checkCountry(mode, norm, freq, timestamp, now)

    def _checkCountry(self, mode, norm, freq, timestamp, now):
        country = HamCallsign.getCountry(norm)
        if not country or not country[1]:
            return
        ccode, name = country
        with self._lock:
            self._loadSeen(now)
            if name in self._seen:
                return
            self._seen.add(name)
            self._saveSeen()
            learningSeconds = float(self._cfg("newcountry_learning_hours", 24) or 0) * 3600
            if now - self._created < learningSeconds:
                return
        self._send(
            {
                "mode": "newcountry",
                "country": name,
                "ccode": ccode,
                "callsign": norm,
                "heard_mode": mode,
                "freq": freq,
                "band": self._bandName(freq),
                "timestamp": timestamp,
            }
        )
