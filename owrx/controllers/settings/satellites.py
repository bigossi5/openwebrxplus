from owrx.controllers.admin import AuthorizationMixin
from owrx.controllers.template import WebpageController
from owrx.controllers.settings import SettingsBreadcrumb
from owrx.breadcrumb import Breadcrumb, BreadcrumbItem, BreadcrumbMixin
from owrx.config import Config
from owrx.satellites import (
    PRESET_SATELLITES,
    SGP4_MISSING,
    TleDownloader,
    listProfileOptions,
    planEntry,
    sgp4Available,
)
from datetime import datetime, timezone
from html import escape
from urllib.parse import parse_qs
import json
import logging

logger = logging.getLogger(__name__)

MAX_BODY_SIZE = 64 * 1024


class SatellitesController(AuthorizationMixin, BreadcrumbMixin, WebpageController):
    def get_breadcrumb(self) -> Breadcrumb:
        return SettingsBreadcrumb().append(BreadcrumbItem("Satellite passes", "settings/satellites"))

    def _profileOptions(self):
        """List of (value, label) for all configured SDR profiles."""
        return listProfileOptions(Config.get()["sdrs"])

    def _renderRow(self, entry, profileOptions):
        profile = entry.get("profile", "")
        options = "".join(
            '<option value="{0}"{1}>{2}</option>'.format(
                escape(v, quote=True), " selected" if v == profile else "", escape(label)
            )
            for v, label in profileOptions
        )
        if profile and profile not in [v for v, _ in profileOptions]:
            options = '<option value="{0}" selected>{0} (missing)</option>'.format(escape(profile, quote=True)) + options
        return """
            <tr class="satpass-row">
                <td><input type="text" class="form-control satpass-name" list="satpass-presets" value="{name}"></td>
                <td><select class="form-control satpass-profile">{options}</select></td>
                <td><input type="number" class="form-control satpass-minel" min="0" max="90" value="{minel}"></td>
                <td><button type="button" class="btn btn-danger satpass-remove">Remove</button></td>
            </tr>
        """.format(
            name=escape(str(entry.get("name", "")), quote=True),
            options=options,
            minel=int(entry.get("min_elevation", 10) or 0),
        )

    def _renderPasses(self, entries):
        if not sgp4Available():
            return '<div class="alert alert-warning">{0}</div>'.format(escape(SGP4_MISSING))
        if not entries:
            return '<div class="alert alert-info">No satellites configured.</div>'
        tleData = TleDownloader.getSharedInstance().getAll()
        if not tleData:
            return '<div class="alert alert-warning">No orbit data downloaded yet, please try again in a few minutes.</div>'
        now = datetime.now(timezone.utc)
        rows = []
        messages = []
        for entry in entries:
            name, passes, error = planEntry(entry, tleData, now)
            if error:
                messages.append("{0}: {1}".format(entry.get("name", ""), error))
                continue
            for p in passes:
                rows.append((p["aos"], name, p, entry))
        rows.sort(key=lambda r: r[0])
        html = ""
        for m in messages:
            html += '<div class="alert alert-warning">{0}</div>'.format(escape(m))
        if not rows:
            return html + '<div class="alert alert-info">No passes in the next 48 hours.</div>'
        body = ""
        for aos, name, p, entry in rows[:30]:
            duration = int((p["los"] - p["aos"]).total_seconds())
            body += "<tr><td>{0}</td><td>{1}</td><td>{2}</td><td>{3}</td><td>{4}:{5:02d}</td><td>{6}&deg;</td></tr>".format(
                escape(name),
                p["aos"].strftime("%Y-%m-%d %H:%M:%S"),
                p["los"].strftime("%H:%M:%S"),
                escape(entry.get("profile", "").replace("|", " / ")),
                duration // 60,
                duration % 60,
                p["max_elevation"],
            )
        return (
            html
            + '<table class="table table-sm"><thead><tr><th>Satellite</th><th>AOS (UTC)</th><th>LOS (UTC)</th>'
            + "<th>Profile</th><th>Duration</th><th>Max elevation</th></tr></thead><tbody>"
            + body
            + "</tbody></table>"
        )

    def render_content(self):
        config = Config.get()
        entries = list(config["satpass_entries"] or [])
        profileOptions = self._profileOptions()
        presets = "".join('<option value="{0}">'.format(escape(p, quote=True)) for p in PRESET_SATELLITES)
        rows = "".join(self._renderRow(e, profileOptions) for e in entries)
        template = self._renderRow({"name": "", "profile": "", "min_elevation": 10}, profileOptions)
        return """
            <div class="alert alert-info">
                At the start of a pass the selected SDR is switched to the given profile, and switched back
                when the satellite has set. A pass is skipped when listeners are connected to that SDR at its
                start. Background decoding (for example SSTV on 145.800 MHz for the ISS) only works if the profile
                covers a suitable frequency and the decoder is enabled in the background decoding settings.
            </div>
            <form method="POST" action="settings/satellites" id="satpass-form">
                <div class="form-check mb-3">
                    <input type="checkbox" class="form-check-input" id="satpass-enabled" name="enabled" value="1"{checked}>
                    <label class="form-check-label" for="satpass-enabled">Enable satellite pass scheduling</label>
                </div>
                <datalist id="satpass-presets">{presets}</datalist>
                <table class="table">
                    <thead><tr><th>Satellite</th><th>SDR profile</th><th>Min. elevation</th><th></th></tr></thead>
                    <tbody id="satpass-rows">{rows}</tbody>
                </table>
                <input type="hidden" name="entries" id="satpass-entries" value="">
                <button type="button" class="btn btn-secondary" id="satpass-add">Add satellite</button>
                <button type="submit" class="btn btn-primary">Apply</button>
            </form>
            <table style="display:none"><tbody id="satpass-template">{template}</tbody></table>
            <h2 class="mt-4">Upcoming passes</h2>
            {passes}
            <script>
            (function() {{
                var rows = document.getElementById("satpass-rows");
                document.getElementById("satpass-add").addEventListener("click", function() {{
                    var tpl = document.getElementById("satpass-template").querySelector("tr");
                    rows.appendChild(tpl.cloneNode(true));
                }});
                rows.addEventListener("click", function(e) {{
                    if (e.target.classList.contains("satpass-remove")) {{
                        var tr = e.target.closest("tr");
                        tr.parentNode.removeChild(tr);
                    }}
                }});
                document.getElementById("satpass-form").addEventListener("submit", function() {{
                    var out = [];
                    rows.querySelectorAll("tr.satpass-row").forEach(function(tr) {{
                        var name = tr.querySelector(".satpass-name").value.trim();
                        if (!name) return;
                        out.push({{
                            name: name,
                            profile: tr.querySelector(".satpass-profile").value,
                            min_elevation: parseInt(tr.querySelector(".satpass-minel").value || "0", 10)
                        }});
                    }});
                    document.getElementById("satpass-entries").value = JSON.stringify(out);
                }});
            }})();
            </script>
        """.format(
            checked=" checked" if config["satpass_enabled"] else "",
            presets=presets,
            rows=rows,
            template=template,
            passes=self._renderPasses(entries),
        )

    def template_variables(self):
        variables = super().template_variables()
        variables["content"] = self.render_content()
        variables["title"] = "Satellite passes"
        variables["modal"] = ""
        variables["error"] = ""
        return variables

    def indexAction(self):
        self.serve_template("settings/general.html", **self.template_variables())

    @staticmethod
    def sanitizeEntries(raw, validProfiles):
        """Validate entries coming from the browser; returns a clean list."""
        result = []
        if not isinstance(raw, list):
            return result
        for e in raw:
            if not isinstance(e, dict):
                continue
            name = str(e.get("name", "")).strip()[:80]
            profile = e.get("profile", "")
            if not name or profile not in validProfiles:
                continue
            try:
                minEl = int(e.get("min_elevation", 10))
            except (TypeError, ValueError):
                minEl = 10
            result.append({"name": name, "profile": profile, "min_elevation": max(0, min(90, minEl))})
        return result

    def save(self):
        try:
            body = (self.get_body(MAX_BODY_SIZE) or b"").decode("utf-8")
            data = parse_qs(body)
            enabled = "enabled" in data
            raw = json.loads(data.get("entries", ["[]"])[0] or "[]")
        except Exception:
            self.send_response("Invalid request", code=400, content_type="text/plain")
            return
        validProfiles = [v for v, _ in self._profileOptions()]
        config = Config.get()
        config["satpass_entries"] = self.sanitizeEntries(raw, validProfiles)
        config["satpass_enabled"] = enabled
        config.store()
        self.send_redirect("{}settings/satellites".format(self.get_document_root()))
