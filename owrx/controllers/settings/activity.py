from owrx.controllers.admin import AuthorizationMixin
from owrx.controllers.template import WebpageController
from owrx.controllers.settings import SettingsBreadcrumb
from owrx.breadcrumb import Breadcrumb, BreadcrumbItem, BreadcrumbMixin
from owrx.config import Config
from owrx.activity import ActivityStore, adifDocument
from datetime import datetime, timezone, timedelta
from html import escape
import time
import logging

logger = logging.getLogger(__name__)

PERIODS = [1, 7, 30, 90]


def _localOffsetMinutes():
    try:
        return int((time.localtime().tm_gmtoff or 0) // 60)
    except Exception:
        return 0


def cellColor(count, maxCount):
    if not count or not maxCount:
        return "transparent"
    alpha = 0.1 + 0.9 * (count / maxCount)
    return "rgba(220, 53, 69, {:.2f})".format(alpha)


class ActivityController(AuthorizationMixin, BreadcrumbMixin, WebpageController):
    def get_breadcrumb(self) -> Breadcrumb:
        return SettingsBreadcrumb().append(BreadcrumbItem("Activity statistics", "settings/activity"))

    def _param(self, name, default=None):
        try:
            return self.request.query.get(name, [default])[0]
        except Exception:
            return default

    def _days(self):
        try:
            days = int(self._param("days", 7))
        except (TypeError, ValueError):
            days = 7
        return max(1, min(days, 3650))

    def render_content(self):
        days = self._days()
        tz = "local" if self._param("tz", "utc") == "local" else "utc"
        offset = _localOffsetMinutes() if tz == "local" else 0
        enabled = bool(Config.get()["activity_enabled"])

        store = ActivityStore.getSharedInstance()
        heat = store.heatmap(days, offset)
        since = int(time.time() - days * 86400)
        spotCount = store.countSpots(since)

        notice = (
            '<div class="alert alert-success">Activity log is <strong>enabled</strong>.</div>'
            if enabled
            else '<div class="alert alert-warning">Activity log is <strong>disabled</strong>. '
            "Set <code>activity_enabled</code> to true in the JSON file editor (config_webrx.py) to record activity.</div>"
        )

        def link(label, d, t, active):
            return '<a class="btn btn-sm btn-{} mr-1" href="settings/activity?days={}&amp;tz={}">{}</a>'.format(
                "primary" if active else "secondary", d, t, label
            )

        periods = "".join(link("{} d".format(p), p, tz, p == days) for p in PERIODS)
        zones = link("UTC", days, "utc", tz == "utc") + link(
            "Local (server, UTC{:+.1f}h)".format(_localOffsetMinutes() / 60), days, "local", tz == "local"
        )

        header = "<th></th>" + "".join("<th>{:02d}</th>".format(h) for h in range(24))
        rows = ""
        for band in sorted(heat["bands"].keys()):
            counts = heat["bands"][band]
            cells = "".join(
                '<td style="background-color: {}; min-width: 1.6em; text-align: center;" title="{}">{}</td>'.format(
                    cellColor(c, heat["max"]), "{}: {} alert(s) at {:02d}h".format(escape(band), c, h), c or ""
                )
                for h, c in enumerate(counts)
            )
            rows += "<tr><th>{}</th>{}</tr>".format(escape(band), cells)
        if rows:
            table = (
                '<div style="overflow-x: auto;"><table class="table table-sm table-bordered">'
                "<thead><tr>{}</tr></thead><tbody>{}</tbody></table></div>"
            ).format(header, rows)
        else:
            table = '<p class="text-muted">No signal alerts recorded in this period.</p>'

        legend = (
            '<div class="mt-2">Legend: '
            + "".join(
                '<span style="display:inline-block;width:2.5em;text-align:center;background-color:{}">{}</span>'.format(
                    cellColor(f * heat["max"], heat["max"]) if heat["max"] else "transparent",
                    int(round(f * heat["max"])),
                )
                for f in (0.1, 0.25, 0.5, 0.75, 1.0)
            )
            + " (alerts per hour cell)</div>"
        )

        return """
            {notice}
            <div class="mb-2">Period: {periods}</div>
            <div class="mb-2">Time zone: {zones}</div>
            <p>Signal alerts: <strong>{alerts}</strong> &nbsp; Heard stations: <strong>{spots}</strong></p>
            <div class="card mt-2">
                <div class="card-header">Signal alerts by band and hour</div>
                <div class="card-body">{table}{legend}</div>
            </div>
            <div class="mt-3">
                <a class="btn btn-secondary" href="settings/activity/adif?days={days}">Export heard stations (ADIF)</a>
            </div>
        """.format(
            notice=notice,
            periods=periods,
            zones=zones,
            alerts=heat["total"],
            spots=spotCount,
            table=table,
            legend=legend,
            days=days,
        )

    def template_variables(self):
        variables = super().template_variables()
        variables["content"] = self.render_content()
        variables["title"] = "Activity statistics"
        variables["modal"] = ""
        variables["error"] = ""
        return variables

    def indexAction(self):
        self.serve_template("settings/general.html", **self.template_variables())

    def _parseDate(self, name):
        value = self._param(name)
        if not value:
            return None
        try:
            return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            return None

    def adif(self):
        start = self._parseDate("from")
        end = self._parseDate("to")
        if start is not None or end is not None:
            since = int(start.timestamp()) if start else 0
            until = int((end + timedelta(days=1)).timestamp()) - 1 if end else None
        else:
            since = int(time.time() - self._days_adif() * 86400)
            until = None
        myGrid = None
        try:
            from owrx.locator import Locator

            myGrid = Locator.fromCoordinates(Config.get()["receiver_gps"], 3)
        except Exception:
            pass
        spots = ActivityStore.getSharedInstance().spots(since, until)
        self.send_response(
            adifDocument(spots, myGrid),
            content_type="text/plain",
            headers={"Content-Disposition": 'attachment; filename="owrx-heard.adi"'},
        )

    def _days_adif(self):
        try:
            return max(1, min(int(self._param("days", 30)), 3650))
        except (TypeError, ValueError):
            return 30
