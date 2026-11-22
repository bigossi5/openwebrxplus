from owrx.controllers.admin import AuthorizationMixin
from owrx.controllers.template import WebpageController
from owrx.controllers import BodySizeError
from owrx.controllers.settings import SettingsBreadcrumb
from owrx.breadcrumb import Breadcrumb, BreadcrumbItem, BreadcrumbMixin
from owrx.bookmarkpacks import listPacks, installPack, removePack, exportBookmarks, importBookmarks
from datetime import datetime, timezone
from html import escape
from urllib.parse import parse_qs
import json
import logging

logger = logging.getLogger(__name__)

MAX_FORM_SIZE = 4 * 1024
MAX_IMPORT_SIZE = 512 * 1024


class BookmarkPacksController(AuthorizationMixin, BreadcrumbMixin, WebpageController):
    def get_breadcrumb(self) -> Breadcrumb:
        return SettingsBreadcrumb().append(BreadcrumbItem("Bookmark packs", "settings/bookmarkpacks"))

    def _renderPack(self, pack):
        installed = pack["installed"] > 0
        if installed:
            status = '<span class="badge badge-success">{0} installed</span>'.format(pack["installed"])
            button = "Remove"
            op = "remove"
            css = "btn-danger"
        else:
            status = '<span class="badge badge-secondary">not installed</span>'
            button = "Install"
            op = "install"
            css = "btn-primary"
        source = ""
        if pack["source"]:
            source = '<div><small class="text-muted">Source: {0}</small></div>'.format(escape(pack["source"]))
        return """
            <li class="list-group-item">
                <div class="row">
                    <div class="col-8">
                        <h3>{name} {status}</h3>
                        <div>{description}</div>
                        <div><small>{count} bookmarks</small></div>
                        {source}
                    </div>
                    <div class="col-4 text-right">
                        <form method="POST" action="bookmarkpacks">
                            <input type="hidden" name="op" value="{op}">
                            <input type="hidden" name="id" value="{id}">
                            <button type="submit" class="btn {css}">{button}</button>
                        </form>
                    </div>
                </div>
            </li>
        """.format(
            name=escape(pack["name"]),
            status=status,
            description=escape(pack["description"]),
            count=pack["count"],
            source=source,
            op=op,
            id=escape(pack["id"], quote=True),
            css=css,
            button=button,
        )

    def render_content(self):
        packs = listPacks()
        message = ""
        if "msg" in self.request.query:
            message = '<div class="alert alert-info">{0}</div>'.format(escape(self.request.query["msg"][0][:200]))
        items = "".join(self._renderPack(p) for p in packs) or (
            '<li class="list-group-item">No bookmark packs found.</li>'
        )
        return """
            {message}
            <div class="alert alert-info">
                Packs add ready-made bookmarks to the bookmark editor. Frequencies that already have a
                bookmark are skipped. Removing a pack deletes the bookmarks that came from it.
            </div>
            <ul class="list-group list-group-flush">{items}</ul>
            <h2 class="mt-4">Export and import</h2>
            <div class="d-flex align-items-center">
                <a class="btn btn-secondary" href="bookmarkpacks/export">Export all bookmarks (JSON)</a>
                <input type="file" id="bmimport-input" accept=".json,application/json" style="display:none">
                <button type="button" class="btn btn-secondary ml-2" id="bmimport-button">Import bookmarks (JSON)...</button>
                <span id="bmimport-status" class="ml-3"></span>
            </div>
            <script>
            (function() {{
                var input = document.getElementById("bmimport-input");
                var status = document.getElementById("bmimport-status");
                document.getElementById("bmimport-button").addEventListener("click", function() {{ input.click(); }});
                input.addEventListener("change", function() {{
                    var file = input.files[0];
                    if (!file) return;
                    status.textContent = "Uploading...";
                    var xhr = new XMLHttpRequest();
                    xhr.open("POST", "bookmarkpacks/import");
                    xhr.onload = function() {{
                        var r = {{}};
                        try {{ r = JSON.parse(xhr.responseText); }} catch (e) {{}}
                        if (xhr.status === 200) {{
                            status.textContent = "Added " + r.added + ", skipped " + r.skipped + ", invalid " + r.invalid + ".";
                        }} else {{
                            status.textContent = "Import failed: " + (r.error || xhr.status);
                        }}
                    }};
                    xhr.onerror = function() {{ status.textContent = "Import failed."; }};
                    xhr.send(file);
                    input.value = "";
                }});
            }})();
            </script>
        """.format(
            message=message,
            items=items,
        )

    def template_variables(self):
        variables = super().template_variables()
        variables["content"] = self.render_content()
        variables["title"] = "Bookmark packs"
        variables["modal"] = ""
        variables["error"] = ""
        return variables

    def indexAction(self):
        self.serve_template("settings/general.html", **self.template_variables())

    def _redirect(self, message):
        from urllib.parse import quote

        self.send_redirect("{0}settings/bookmarkpacks?msg={1}".format(self.get_document_root(), quote(message)))

    def save(self):
        try:
            body = (self.get_body(MAX_FORM_SIZE) or b"").decode("utf-8")
            data = parse_qs(body)
            op = data.get("op", [""])[0]
            packId = data.get("id", [""])[0]
        except Exception:
            self.send_response("Invalid request", code=400, content_type="text/plain")
            return
        try:
            if op == "install":
                r = installPack(packId)
                self._redirect("Added {0} bookmarks, skipped {1} existing.".format(r["added"], r["skipped"]))
            elif op == "remove":
                n = removePack(packId)
                self._redirect("Removed {0} bookmarks.".format(n))
            else:
                self.send_response("Invalid request", code=400, content_type="text/plain")
        except ValueError as e:
            self._redirect(str(e))
        except Exception:
            logger.exception("Error while changing bookmark pack")
            self.send_response("Server error", code=500, content_type="text/plain")

    def export(self):
        name = "openwebrx-bookmarks-{0}.json".format(datetime.now(timezone.utc).strftime("%Y%m%d"))
        self.send_response(
            exportBookmarks(),
            content_type="application/json",
            headers={"Content-Disposition": 'attachment; filename="{0}"'.format(name)},
        )

    def importAction(self):
        try:
            data = self.get_body(MAX_IMPORT_SIZE)
        except BodySizeError:
            self._json({"error": "File too large"}, 400)
            return
        if not data:
            self._json({"error": "Empty upload"}, 400)
            return
        try:
            result = importBookmarks(data)
        except ValueError as e:
            self._json({"error": str(e)}, 400)
            return
        except Exception:
            logger.exception("Error importing bookmarks")
            self._json({"error": "Server error"}, 500)
            return
        self._json(result, 200)

    def _json(self, obj, code):
        self.send_response(json.dumps(obj), code=code, content_type="application/json")
