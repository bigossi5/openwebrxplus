"""
Persistent activity log (signal alert events and heard stations), kept in a small
sqlite database, plus pure helpers for ADIF export.

This module deliberately has no dependency on pycsdr or other heavy modules.
"""
import sqlite3
import threading
import time
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

PRUNE_INTERVAL = 3600
DEFAULT_RETENTION_DAYS = 90

# (label, lower MHz, upper MHz)
_BANDS = [
    ("160m", 1.8, 2.0),
    ("80m", 3.5, 4.0),
    ("60m", 5.25, 5.45),
    ("40m", 7.0, 7.3),
    ("30m", 10.1, 10.15),
    ("20m", 14.0, 14.35),
    ("17m", 18.068, 18.168),
    ("15m", 21.0, 21.45),
    ("12m", 24.89, 24.99),
    ("10m", 28.0, 29.7),
    ("6m", 50.0, 54.0),
    ("4m", 70.0, 70.5),
    ("2m", 144.0, 148.0),
    ("70cm", 420.0, 450.0),
]


def bandFromFrequency(freq):
    """Coarse amateur band label for a frequency in Hz, or "other"."""
    try:
        mhz = float(freq) / 1e6
    except (TypeError, ValueError):
        return "other"
    for name, low, high in _BANDS:
        if low <= mhz <= high:
            return name
    return "other"


class ActivityStore(object):
    sharedInstance = None
    sharedLock = threading.Lock()

    @staticmethod
    def getSharedInstance():
        with ActivityStore.sharedLock:
            if ActivityStore.sharedInstance is None:
                import os
                from owrx.config.core import CoreConfig

                path = os.path.join(CoreConfig().get_data_directory(), "activity.db")
                retention = DEFAULT_RETENTION_DAYS
                try:
                    from owrx.config import Config

                    retention = int(Config.get()["activity_retention_days"])
                except Exception:
                    pass
                ActivityStore.sharedInstance = ActivityStore(path, retention)
            return ActivityStore.sharedInstance

    def __init__(self, path, retentionDays=DEFAULT_RETENTION_DAYS):
        self.path = path
        self.retentionDays = retentionDays
        self.lock = threading.Lock()
        self.conn = None
        self.lastPrune = 0

    def _connect(self):
        # caller holds the lock
        if self.conn is None:
            conn = sqlite3.connect(self.path, check_same_thread=False)
            conn.execute(
                "CREATE TABLE IF NOT EXISTS events("
                "id INTEGER PRIMARY KEY, ts INTEGER, band TEXT, freq INTEGER, kind TEXT, duration REAL)"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS spots("
                "id INTEGER PRIMARY KEY, ts INTEGER, mode TEXT, callsign TEXT, locator TEXT, "
                "freq INTEGER, db REAL, msg TEXT)"
            )
            conn.execute("CREATE TABLE IF NOT EXISTS listeners(ts INTEGER, count INTEGER, freq INTEGER, mod TEXT)")
            conn.execute("CREATE INDEX IF NOT EXISTS listeners_ts ON listeners(ts)")
            conn.execute("CREATE INDEX IF NOT EXISTS events_ts ON events(ts)")
            conn.execute("CREATE INDEX IF NOT EXISTS spots_ts ON spots(ts)")
            conn.commit()
            self.conn = conn
        return self.conn

    def close(self):
        with self.lock:
            if self.conn is not None:
                try:
                    self.conn.close()
                finally:
                    self.conn = None

    def _maybePrune(self, conn, now):
        if now - self.lastPrune < PRUNE_INTERVAL:
            return
        self.lastPrune = now
        cutoff = int(now - self.retentionDays * 86400)
        conn.execute("DELETE FROM events WHERE ts < ?", (cutoff,))
        conn.execute("DELETE FROM spots WHERE ts < ?", (cutoff,))
        conn.execute("DELETE FROM listeners WHERE ts < ?", (cutoff,))
        conn.commit()

    def addEvent(self, ts, band, freq, kind="signal_alert", duration=0.0, now=None):
        try:
            with self.lock:
                conn = self._connect()
                conn.execute(
                    "INSERT INTO events(ts, band, freq, kind, duration) VALUES (?,?,?,?,?)",
                    (int(ts), band, None if freq is None else int(freq), kind, duration),
                )
                conn.commit()
                self._maybePrune(conn, time.time() if now is None else now)
            return True
        except Exception:
            logger.exception("Could not write activity event")
            return False

    def addSpot(self, ts, mode, callsign, locator, freq, db=None, msg=None, now=None):
        try:
            with self.lock:
                conn = self._connect()
                conn.execute(
                    "INSERT INTO spots(ts, mode, callsign, locator, freq, db, msg) VALUES (?,?,?,?,?,?,?)",
                    (int(ts), mode, callsign, locator, None if freq is None else int(freq), db, msg),
                )
                conn.commit()
                self._maybePrune(conn, time.time() if now is None else now)
            return True
        except Exception:
            logger.exception("Could not write activity spot")
            return False

    def addListenerSample(self, ts, count, tuned, now=None):
        """
        Stores one listener sample: `count` connected clients, `tuned` is a list of
        (frequency, modulation) pairs, one per client that has a frequency. No client
        identifying data is stored. With no tuned client a single row without frequency is written.
        """
        rows = [(int(ts), int(count), int(f), m) for f, m in tuned] or [(int(ts), int(count), None, None)]
        try:
            with self.lock:
                conn = self._connect()
                conn.executemany("INSERT INTO listeners(ts, count, freq, mod) VALUES (?,?,?,?)", rows)
                conn.commit()
                self._maybePrune(conn, time.time() if now is None else now)
            return True
        except Exception:
            logger.exception("Could not write listener sample")
            return False

    def listenerRows(self, since_ts):
        """Returns list of (ts, count, freq, mod) rows since the timestamp."""
        with self.lock:
            conn = self._connect()
            return conn.execute(
                "SELECT ts, count, freq, mod FROM listeners WHERE ts >= ? ORDER BY ts ASC", (int(since_ts),)
            ).fetchall()

    def heatmap(self, days, tz_offset_minutes=0, now=None):
        """
        Returns {"bands": {band: [24 counts]}, "total": n, "max": n} for signal alert events
        of the last `days` days. Hours are shifted by tz_offset_minutes.
        """
        now = time.time() if now is None else now
        since = int(now - days * 86400)
        bands = {}
        total = 0
        with self.lock:
            conn = self._connect()
            rows = conn.execute("SELECT ts, band FROM events WHERE ts >= ?", (since,)).fetchall()
        for ts, band in rows:
            hour = int(((ts + tz_offset_minutes * 60) // 3600) % 24)
            counts = bands.setdefault(band or "other", [0] * 24)
            counts[hour] += 1
            total += 1
        maxCount = max((max(c) for c in bands.values()), default=0)
        return {"bands": bands, "total": total, "max": maxCount}

    def spots(self, since_ts, until_ts=None, limit=None):
        sql = "SELECT ts, mode, callsign, locator, freq, db, msg FROM spots WHERE ts >= ?"
        params = [int(since_ts)]
        if until_ts is not None:
            sql += " AND ts <= ?"
            params.append(int(until_ts))
        sql += " ORDER BY ts ASC"
        if limit is not None:
            sql += " LIMIT ?"
            params.append(int(limit))
        with self.lock:
            conn = self._connect()
            rows = conn.execute(sql, params).fetchall()
        keys = ["ts", "mode", "callsign", "locator", "freq", "db", "msg"]
        return [dict(zip(keys, r)) for r in rows]

    def countEvents(self, since_ts):
        with self.lock:
            return self._connect().execute("SELECT COUNT(*) FROM events WHERE ts >= ?", (int(since_ts),)).fetchone()[0]

    def countSpots(self, since_ts):
        with self.lock:
            return self._connect().execute("SELECT COUNT(*) FROM spots WHERE ts >= ?", (int(since_ts),)).fetchone()[0]


# ---------------------------------------------------------------- ADIF

def adifField(name, value):
    """One ADIF data specifier; the length is the UTF-8 byte length."""
    value = str(value)
    return "<{}:{}>{}".format(name, len(value.encode("utf-8")), value)


def _adifMode(mode):
    """returns (MODE, SUBMODE or None)"""
    if mode == "JS8":
        return "MFSK", "JS8"
    if mode in ("FST4W", "FST4"):
        return "MFSK", "FST4"
    return mode, None


def adifHeader():
    return "OpenWebRX+ heard stations export\n{}{}{}\n<EOH>\n".format(
        adifField("ADIF_VER", "3.1.4"),
        adifField("PROGRAMID", "OpenWebRX+"),
        adifField("CREATED_TIMESTAMP", datetime.now(timezone.utc).strftime("%Y%m%d %H%M%S")),
    )


def adifRecord(spot, myGrid=None):
    dt = datetime.fromtimestamp(spot["ts"], tz=timezone.utc)
    mode, submode = _adifMode(spot["mode"])
    freq = spot.get("freq")
    fields = [adifField("CALL", spot["callsign"])]
    fields.append(adifField("QSO_DATE", dt.strftime("%Y%m%d")))
    fields.append(adifField("TIME_ON", dt.strftime("%H%M%S")))
    band = bandFromFrequency(freq)
    if band != "other":
        fields.append(adifField("BAND", band))
    if freq:
        fields.append(adifField("FREQ", "{:.6f}".format(freq / 1e6)))
    fields.append(adifField("MODE", mode))
    if submode:
        fields.append(adifField("SUBMODE", submode))
    if spot.get("locator"):
        fields.append(adifField("GRIDSQUARE", spot["locator"]))
    if myGrid:
        fields.append(adifField("MY_GRIDSQUARE", myGrid))
    db = spot.get("db")
    if db is not None:
        fields.append(adifField("RST_RCVD", "{:g}".format(db)))
        comment = "Heard by OpenWebRX+ (receive only, SNR {:g} dB)".format(db)
    else:
        comment = "Heard by OpenWebRX+ (receive only)"
    fields.append(adifField("COMMENT", comment))
    return "".join(fields) + "<EOR>\n"


def adifRecords(spots, myGrid=None):
    return "".join(adifRecord(s, myGrid) for s in spots)


def adifDocument(spots, myGrid=None):
    return adifHeader() + adifRecords(spots, myGrid)
