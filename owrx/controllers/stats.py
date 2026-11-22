from owrx.controllers.template import WebpageController
from owrx.config import Config
from owrx.listenerstats import buildStats
from html import escape
import time
import logging

logger = logging.getLogger(__name__)


def formatFrequency(freq):
    if freq >= 1000000:
        return "{0:.3f} MHz".format(freq / 1e6)
    return "{0:.1f} kHz".format(freq / 1e3)


def formatDuration(seconds):
    days, rest = divmod(int(seconds), 86400)
    hours, rest = divmod(rest, 3600)
    minutes = rest // 60
    if days:
        return "{0}d {1}h {2}m".format(days, hours, minutes)
    return "{0}h {1}m".format(hours, minutes)


def renderPeriod(title, data):
    if data["top"]:
        rows = "".join(
            "<tr><td>{0}</td><td>{1}</td><td>{2}</td></tr>".format(
                formatFrequency(t["freq"]), escape(t["mod"].upper()), t["minutes"]
            )
            for t in data["top"]
        )
    else:
        rows = '<tr><td colspan="3">No data yet.</td></tr>'
    return """
        <h3>{label}</h3>
        <p>Peak listeners: <b>{peak}</b>, average: <b>{average}</b></p>
        <table class="table table-sm">
            <tr><th>Frequency</th><th>Mode</th><th>Listener minutes</th></tr>
            {rows}
        </table>
    """.format(label=escape(title), peak=data["peak"], average=data["average"], rows=rows)


class StatsController(WebpageController):
    """Public statistics page. Deliberately without AuthorizationMixin."""

    @staticmethod
    def isEnabled():
        return bool(Config.get()["stats_page_enabled"])

    def indexAction(self):
        if not self.isEnabled():
            self.send_response("Not found", code=404, content_type="text/plain")
            return
        from owrx.activity import ActivityStore
        from owrx.client import ClientRegistry

        try:
            from owrx.controllers.services import ServiceController

            started = ServiceController.lastStarted()
        except Exception:
            started = time.time()
        stats = buildStats(
            ActivityStore.getSharedInstance(), ClientRegistry.getSharedInstance().clientCount(), started
        )
        variables = self.template_variables()
        variables["current"] = stats["current"]
        variables["uptime"] = formatDuration(stats["uptime"])
        variables["periods"] = renderPeriod("Last 24 hours", stats["periods"]["24h"]) + renderPeriod(
            "Last 7 days", stats["periods"]["7d"]
        )
        self.serve_template("stats.html", **variables)
