"""
Satellite TLE downloader, pass prediction and pass scheduler.

At the start of a configured satellite pass the scheduler switches an SDR to a
given profile (so that background decoders such as SSTV can run) and restores
the previous profile when the satellite has set. Passes are skipped when
listeners are connected to the SDR.

The "sgp4" library is imported lazily, so this module can always be imported.
"""

from owrx.config import Config
from owrx.web import WebAgent
from datetime import datetime, timedelta, timezone
import math
import threading
import logging

logger = logging.getLogger(__name__)

SGP4_MISSING = "orbit library not installed (sudo apt install python3-sgp4)"

# Satellite groups and single objects downloaded from celestrak.org
TLE_URLS = [
    "https://celestrak.org/NORAD/elements/gp.php?GROUP=stations&FORMAT=tle",
    "https://celestrak.org/NORAD/elements/gp.php?GROUP=weather&FORMAT=tle",
    "https://celestrak.org/NORAD/elements/gp.php?GROUP=amateur&FORMAT=tle",
    # NOAA 15/18/19 are not listed in the weather group any more
    "https://celestrak.org/NORAD/elements/gp.php?CATNR=25338&FORMAT=tle",
    "https://celestrak.org/NORAD/elements/gp.php?CATNR=28654&FORMAT=tle",
    "https://celestrak.org/NORAD/elements/gp.php?CATNR=33591&FORMAT=tle",
]

# Preset satellite names for the settings page (matched against TLE names)
PRESET_SATELLITES = [
    "ISS (ZARYA)",
    "NOAA 15",
    "NOAA 18",
    "NOAA 19",
    "METEOR-M2 3",
    "METEOR-M2 4",
    "SO-50",
    "AO-91",
    "AO-95",
]

# How far ahead passes are planned
PLAN_HOURS = 48

# WGS84
_WGS84_A = 6378.137
_WGS84_F = 1 / 298.257223563
_WGS84_E2 = _WGS84_F * (2 - _WGS84_F)


def sgp4Available() -> bool:
    try:
        import sgp4.api  # noqa: F401
        import sgp4.propagation  # noqa: F401

        return True
    except Exception:
        return False


#
# TLE parsing / lookup
#
def parseTle(text: str) -> dict:
    """Parse 3-line TLE text into {name: (line1, line2)}."""
    lines = [l.rstrip() for l in text.splitlines() if l.strip()]
    result = {}
    i = 0
    while i + 2 < len(lines):
        name, l1, l2 = lines[i].strip(), lines[i + 1], lines[i + 2]
        if l1.startswith("1 ") and l2.startswith("2 "):
            result[name] = (l1.strip(), l2.strip())
            i += 3
        else:
            i += 1
    return result


def findTle(tleData: dict, name: str):
    """Find a satellite by name: exact (case-insensitive) first, then by substring.
    Returns (tleName, (line1, line2)) or None."""
    if not tleData or not name:
        return None
    wanted = name.strip().lower()
    for k, v in tleData.items():
        if k.lower() == wanted:
            return k, v
    for k in sorted(tleData.keys()):
        if wanted in k.lower():
            return k, tleData[k]
    return None


#
# Geometry
#
def _observerEcef(lat: float, lon: float, altM: float):
    """Observer ECEF position in km."""
    la, lo = math.radians(lat), math.radians(lon)
    h = altM / 1000.0
    n = _WGS84_A / math.sqrt(1 - _WGS84_E2 * math.sin(la) ** 2)
    return (
        (n + h) * math.cos(la) * math.cos(lo),
        (n + h) * math.cos(la) * math.sin(lo),
        (n * (1 - _WGS84_E2) + h) * math.sin(la),
    )


def elevationFromTeme(posTeme, gmst: float, lat: float, lon: float, altM: float) -> float:
    """Elevation (degrees) of a satellite at the given TEME position (km)."""
    c, s = math.cos(gmst), math.sin(gmst)
    # TEME -> ECEF (rotation about Z by GMST)
    x = c * posTeme[0] + s * posTeme[1]
    y = -s * posTeme[0] + c * posTeme[1]
    z = posTeme[2]
    ox, oy, oz = _observerEcef(lat, lon, altM)
    rx, ry, rz = x - ox, y - oy, z - oz
    la, lo = math.radians(lat), math.radians(lon)
    # Up component of the range vector in the local ENU frame
    up = math.cos(la) * math.cos(lo) * rx + math.cos(la) * math.sin(lo) * ry + math.sin(la) * rz
    rng = math.sqrt(rx * rx + ry * ry + rz * rz)
    if rng == 0:
        return 90.0
    return math.degrees(math.asin(max(-1.0, min(1.0, up / rng))))


def _toUtc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def makeElevationFunction(line1: str, line2: str, lat: float, lon: float, altM: float):
    """Return f(datetime_utc) -> elevation in degrees (or None on propagation error)."""
    from sgp4.api import Satrec, jday
    from sgp4.propagation import gstime

    sat = Satrec.twoline2rv(line1, line2)

    def elevation(t: datetime):
        t = _toUtc(t)
        jd, fr = jday(t.year, t.month, t.day, t.hour, t.minute, t.second + t.microsecond / 1e6)
        err, pos, _ = sat.sgp4(jd, fr)
        if err != 0:
            return None
        return elevationFromTeme(pos, gstime(jd + fr), lat, lon, altM)

    return elevation


def predictPasses(
    line1: str,
    line2: str,
    lat: float,
    lon: float,
    altM: float,
    now: datetime,
    hours: float = PLAN_HOURS,
    minElevation: float = 0.0,
    step: int = 30,
) -> list:
    """
    Predict passes within [now, now + hours]. Returns a list of dicts with
    "aos", "los" (aware UTC datetimes) and "max_elevation" (degrees), only for
    passes reaching at least minElevation. A pass that is already in progress
    at "now" starts at "now".
    """
    elev = makeElevationFunction(line1, line2, lat, lon, altM)
    now = _toUtc(now)
    end = now + timedelta(hours=hours)
    dt = timedelta(seconds=step)

    def refine(lo: datetime, hi: datetime) -> datetime:
        # lo and hi have different sign of elevation; bisect to about 1 second
        eLo = elev(lo)
        while (hi - lo).total_seconds() > 1:
            mid = lo + (hi - lo) / 2
            e = elev(mid)
            if e is None:
                break
            if (e >= 0) == (eLo >= 0):
                lo, eLo = mid, e
            else:
                hi = mid
        return hi

    passes = []
    t = now
    prevE = elev(t)
    inPass = prevE is not None and prevE >= 0
    aos = now if inPass else None
    maxE = prevE if inPass else -90.0
    maxT = now
    while t < end:
        t2 = t + dt
        e = elev(t2)
        if e is None:
            t = t2
            continue
        if prevE is not None:
            if not inPass and prevE < 0 <= e:
                aos = refine(t, t2)
                inPass = True
                maxE, maxT = e, t2
            elif inPass and prevE >= 0 > e:
                los = refine(t, t2)
                # refine maximum elevation around the peak
                peak = _refinePeak(elev, maxT, step)
                maxE = max(maxE, peak)
                if maxE >= minElevation:
                    passes.append({"aos": aos, "los": los, "max_elevation": round(maxE, 1)})
                inPass = False
                aos = None
                maxE = -90.0
        if inPass and e > maxE:
            maxE, maxT = e, t2
        prevE = e
        t = t2
    # Pass still in progress at the end of the window
    if inPass and aos is not None and maxE >= minElevation:
        passes.append({"aos": aos, "los": end, "max_elevation": round(maxE, 1)})
    return passes


def _refinePeak(elev, around: datetime, step: int) -> float:
    best = -90.0
    for i in range(-step, step + 1, 2):
        e = elev(around + timedelta(seconds=i))
        if e is not None and e > best:
            best = e
    return best


#
# TLE downloader
#
class TleDownloader(WebAgent):
    sharedInstance = None
    creationLock = threading.Lock()

    @staticmethod
    def getSharedInstance():
        with TleDownloader.creationLock:
            if TleDownloader.sharedInstance is None:
                TleDownloader.sharedInstance = TleDownloader("tle.json")
        return TleDownloader.sharedInstance

    @staticmethod
    def start():
        agent = TleDownloader.getSharedInstance()
        agent.startThread()
        # Do not wait for the hourly check when there is no data at all
        if not agent.getAll():
            threading.Thread(target=agent.refresh, name="TleDownloaderInit", daemon=True).start()

    @staticmethod
    def stop():
        TleDownloader.getSharedInstance().stopThread()

    def __init__(self, dataName: str):
        super().__init__(dataName)
        # Update twice a day
        self.refreshPeriod = 12 * 60 * 60
        self.listeners = []

    def addListener(self, callback):
        self.listeners.append(callback)

    def _sortData(self, data):
        # Data is a dictionary {name: [line1, line2]}, not a sorted list
        return data if isinstance(data, dict) else {}

    def _loadFromWeb(self):
        # Keep what we have, overlay with newly downloaded data
        result = dict(self.getAll())
        count = 0
        for url in TLE_URLS:
            try:
                text = self._openUrl(url).read().decode("utf-8", errors="replace")
                parsed = parseTle(text)
                for k, v in parsed.items():
                    result[k] = list(v)
                count += len(parsed)
            except Exception as e:
                logger.error("TLE download from {0} failed: {1}".format(url, e))
        if count == 0:
            # Keep cached data
            return None
        return result

    def refresh(self):
        done = super().refresh()
        if done:
            for cb in list(self.listeners):
                try:
                    cb()
                except Exception:
                    logger.exception("TLE listener failed")
        return done


#
# Helpers shared with the settings page
#
def getObserver():
    pm = Config.get()
    gps = pm["receiver_gps"]
    return float(gps["lat"]), float(gps["lon"]), float(pm["receiver_asl"] or 0)


def planEntry(entry: dict, tleData: dict, now: datetime, hours: float = PLAN_HOURS):
    """
    Compute passes for one satellite entry. Returns (tleName, passes, error)
    where error is a human readable string or None.
    """
    if not sgp4Available():
        return None, [], SGP4_MISSING
    found = findTle(tleData, entry.get("name", ""))
    if found is None:
        return None, [], "no orbit data for '{0}' (yet)".format(entry.get("name", ""))
    name, (l1, l2) = found
    try:
        lat, lon, alt = getObserver()
        passes = predictPasses(
            l1, l2, lat, lon, alt, now, hours=hours, minElevation=float(entry.get("min_elevation", 0) or 0)
        )
    except Exception as e:
        logger.exception("Pass prediction failed for {0}".format(name))
        return name, [], "pass prediction failed: {0}".format(e)
    return name, passes, None


def _userClientClass():
    from owrx.source import SdrClientClass

    return SdrClientClass.USER


def splitProfile(value: str):
    """'<sdr_id>|<profile_id>' -> (sdr_id, profile_id) or (None, None)."""
    if not isinstance(value, str) or "|" not in value:
        return None, None
    sdrId, profileId = value.split("|", 1)
    if not sdrId or not profileId:
        return None, None
    return sdrId, profileId


#
# Scheduler
#
class PassScheduler(object):
    sharedInstance = None
    creationLock = threading.Lock()

    @staticmethod
    def getSharedInstance():
        with PassScheduler.creationLock:
            if PassScheduler.sharedInstance is None:
                PassScheduler.sharedInstance = PassScheduler()
        return PassScheduler.sharedInstance

    @staticmethod
    def start():
        PassScheduler.getSharedInstance().startScheduler()

    @staticmethod
    def stop():
        PassScheduler.getSharedInstance().stopScheduler()

    def __init__(self, getSource=None, now=None):
        self.lock = threading.RLock()
        self.timers = []
        self.replanTimer = None
        self.running = False
        self.subs = []
        # active passes: sdr id -> {"restore": profile id, "profile": profile id}
        self.active = {}
        self._getSource = getSource
        self._now = now or (lambda: datetime.now(timezone.utc))

    # --- lifecycle
    def startScheduler(self):
        with self.lock:
            if self.running:
                return
            self.running = True
        try:
            config = Config.get()
            self.subs = [
                config.wireProperty("satpass_enabled", lambda v: self.requestReplan()),
                config.wireProperty("satpass_entries", lambda v: self.requestReplan()),
            ]
            TleDownloader.getSharedInstance().addListener(self.requestReplan)
            TleDownloader.start()
        except Exception:
            logger.exception("Cannot start satellite pass scheduler")

    def stopScheduler(self):
        with self.lock:
            self.running = False
            self._cancelAll()
            if self.replanTimer is not None:
                self.replanTimer.cancel()
                self.replanTimer = None
        try:
            for s in self.subs:
                Config.get().unwire(s)
            self.subs = []
            TleDownloader.stop()
        except Exception:
            logger.exception("Error stopping satellite pass scheduler")

    # --- planning
    def requestReplan(self, delay: float = 3.0):
        """Debounced re-planning (config changes arrive in bursts)."""
        with self.lock:
            if not self.running:
                return
            if self.replanTimer is not None:
                self.replanTimer.cancel()
            self.replanTimer = threading.Timer(delay, self._safe(self.replan))
            self.replanTimer.daemon = True
            self.replanTimer.start()

    def _cancelAll(self):
        for t in self.timers:
            t.cancel()
        self.timers = []

    def _schedule(self, delay: float, fn, *args):
        timer = threading.Timer(max(0.0, delay), self._safe(fn), args)
        timer.daemon = True
        with self.lock:
            if not self.running:
                return None
            self.timers.append(timer)
        timer.start()
        return timer

    def _safe(self, fn):
        def wrapper(*args):
            try:
                fn(*args)
            except Exception:
                logger.exception("Satellite pass scheduler error")

        return wrapper

    def replan(self):
        with self.lock:
            if not self.running:
                return
            self._cancelAll()
        config = Config.get()
        if not config["satpass_enabled"]:
            logger.info("Satellite pass scheduling is disabled.")
            return
        if not sgp4Available():
            logger.warning("Satellite pass scheduling: " + SGP4_MISSING)
            return
        tleData = TleDownloader.getSharedInstance().getAll()
        now = self._now()
        planned = 0
        for entry in config["satpass_entries"] or []:
            try:
                sdrId, profileId = splitProfile(entry.get("profile"))
                if sdrId is None:
                    logger.warning("Satellite entry {0} has no valid profile".format(entry))
                    continue
                name, passes, error = planEntry(entry, tleData, now)
                if error:
                    logger.warning("Satellite '{0}': {1}".format(entry.get("name"), error))
                    continue
                for p in passes:
                    self._schedule((p["aos"] - now).total_seconds(), self.startPass, entry, name, p, sdrId, profileId)
                    planned += 1
            except Exception:
                logger.exception("Cannot plan passes for {0}".format(entry))
        logger.info("Satellite pass scheduler: {0} passes planned.".format(planned))
        # Refresh the plan periodically so that the planning window keeps moving
        self._schedule(6 * 3600, self.replan)

    # --- pass handling
    def _source(self, sdrId):
        if self._getSource is not None:
            return self._getSource(sdrId)
        from owrx.sdr import SdrService

        return SdrService.getSource(sdrId)

    def startPass(self, entry, tleName, p, sdrId, profileId):
        label = "{0} (max {1} deg)".format(tleName or entry.get("name"), p.get("max_elevation"))
        with self.lock:
            if sdrId in self.active:
                logger.info("Satellite pass {0} skipped: SDR '{1}' is used by another pass.".format(label, sdrId))
                return False
            source = self._source(sdrId)
            if source is None:
                logger.info("Satellite pass {0} skipped: SDR '{1}' is not available.".format(label, sdrId))
                return False
            if source.hasClients(_userClientClass()):
                logger.info("Satellite pass {0} skipped: SDR '{1}' has connected listeners.".format(label, sdrId))
                return False
            current = source.getProfileId()
            self.active[sdrId] = {"restore": current, "profile": profileId}
        logger.info("Satellite pass {0} started: switching '{1}' to profile '{2}'.".format(label, sdrId, profileId))
        if current != profileId:
            source.activateProfile(profileId)
        los = p["los"]
        self._schedule((los - self._now()).total_seconds(), self.endPass, label, sdrId)
        return True

    def endPass(self, label, sdrId):
        with self.lock:
            state = self.active.pop(sdrId, None)
        if state is None:
            return False
        source = self._source(sdrId)
        if source is None:
            return False
        current = source.getProfileId()
        if current != state["profile"]:
            logger.info(
                "Satellite pass {0} ended: profile of '{1}' was changed meanwhile, not restoring.".format(label, sdrId)
            )
            return False
        if state["restore"] != current:
            logger.info(
                "Satellite pass {0} ended: restoring profile '{1}' on '{2}'.".format(label, state["restore"], sdrId)
            )
            source.activateProfile(state["restore"])
        return True
