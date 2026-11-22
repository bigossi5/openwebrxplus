from owrx.reporting.reporter import FilteredReporter
import logging

logger = logging.getLogger(__name__)


class ActivityReporter(FilteredReporter):
    def __init__(self, store=None):
        self.store = store
        if self.store is None:
            try:
                from owrx.activity import ActivityStore

                self.store = ActivityStore.getSharedInstance()
            except Exception:
                logger.exception("Could not initialize activity log")

    def stop(self):
        pass

    def getSupportedModes(self):
        return ["signal_alert", "FT8", "FT4", "WSPR", "FST4W", "FST4", "Q65", "JT65", "JT9", "JS8"]

    def spot(self, spot):
        if self.store is None:
            return
        try:
            ts = int(spot.get("timestamp", 0) / 1000) if spot.get("timestamp") else None
            if ts is None:
                import time

                ts = int(time.time())
            mode = spot.get("mode")
            if mode == "signal_alert":
                self.store.addEvent(
                    ts, spot.get("name") or "Signal Alert", spot.get("freq"), "signal_alert", spot.get("duration", 0)
                )
            elif spot.get("callsign"):
                self.store.addSpot(
                    ts, mode, spot["callsign"], spot.get("locator"), spot.get("freq"), spot.get("db"), spot.get("msg")
                )
        except Exception:
            logger.exception("Could not log activity")
