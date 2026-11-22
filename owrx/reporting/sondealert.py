from owrx.reporting.reporter import FilteredReporter
from owrx.alertcooldown import AlertCooldown
from owrx import geo
import time
import logging

logger = logging.getLogger(__name__)

DESCENT_VSPEED = -5.0  # m/s, below this the sonde counts as descending
TRACK_TTL = 3600  # seconds a serial stays in the tracker without updates
TRACK_MAX = 500


class SondeAlertLogic(object):
    """Pure alert logic: no Config, no engine. Easy to unit test."""

    def __init__(self):
        # serial -> {"time", "altitude", "descending"}
        self.tracks = {}

    def _track(self, serial, altitude, descending, now):
        for s in [s for s, t in self.tracks.items() if now - t["time"] > TRACK_TTL]:
            del self.tracks[s]
        while len(self.tracks) >= TRACK_MAX and serial not in self.tracks:
            oldest = min(self.tracks, key=lambda s: self.tracks[s]["time"])
            del self.tracks[oldest]
        self.tracks[serial] = {"time": now, "altitude": altitude, "descending": descending}

    @staticmethod
    def isDescending(vspeed, altitude, ground):
        return vspeed is not None and altitude is not None and vspeed < DESCENT_VSPEED and altitude > ground

    @staticmethod
    def landingPoint(lat, lon, altitude, vspeed, speed, course, ground):
        """Approximate landing point, no wind model: current horizontal speed
        and heading are simply extrapolated for the remaining fall time."""
        t = (altitude - ground) / abs(vspeed)
        driftKm = (speed or 0) / 3.6 * t / 1000.0
        return geo.destinationPoint(lat, lon, course or 0, driftKm)

    def process(self, spot, rx, radiusKm, cooldownSec, ground=0, now=None):
        """Returns a list of alert spots (possibly empty) for a SONDE spot."""
        if now is None:
            now = time.time()
        serial = spot.get("source")
        if not serial or serial == "xxxxxxxx":
            return []
        lat, lon = spot.get("lat"), spot.get("lon")
        if lat is None or lon is None or not rx:
            return []
        try:
            rxLat, rxLon = float(rx["lat"]), float(rx["lon"])
        except (KeyError, TypeError, ValueError):
            return []
        altitude = spot.get("altitude")
        vspeed = spot.get("vspeed")
        descending = self.isDescending(vspeed, altitude, ground)
        self._track(serial, altitude, descending, now)

        distance = geo.haversineKm(rxLat, rxLon, lat, lon)
        landing = None
        if descending:
            llat, llon = self.landingPoint(
                lat, lon, altitude, vspeed, spot.get("speed"), spot.get("course"), ground
            )
            landing = {
                "lat": llat,
                "lon": llon,
                "distance_km": geo.haversineKm(rxLat, rxLon, llat, llon),
            }

        base = {
            "mode": "sonde_alert",
            "serial": serial,
            "device": spot.get("device"),
            "distance_km": distance,
            "lat": lat,
            "lon": lon,
            "altitude": altitude,
            "vspeed": vspeed,
            "landing": landing,
            "timestamp": spot.get("timestamp") or int(now * 1000),
        }
        out = []
        if distance <= radiusKm and AlertCooldown.shouldAlert(("sonde-near", serial), cooldownSec, now):
            out.append(dict(base, kind="near"))
        if landing is not None and landing["distance_km"] <= radiusKm:
            if AlertCooldown.shouldAlert(("sonde-land", serial), cooldownSec, now):
                out.append(dict(base, kind="landing"))
        return out


class SondeAlertReporter(FilteredReporter):
    def __init__(self):
        self.logic = SondeAlertLogic()

    def getSupportedModes(self):
        return ["SONDE"]

    def stop(self):
        pass

    def spot(self, spot):
        try:
            from owrx.config import Config

            config = Config.get()
            alerts = self.logic.process(
                spot,
                config["receiver_gps"],
                config["sonde_alert_radius_km"],
                config["sonde_alert_cooldown_min"] * 60,
                config["receiver_asl"] or 0,
            )
            if alerts:
                # lazy import: owrx.reporting imports this module
                from owrx.reporting import ReportingEngine

                engine = ReportingEngine.getSharedInstance()
                for a in alerts:
                    engine.spot(a)
        except Exception:
            logger.exception("error processing radiosonde alert")
