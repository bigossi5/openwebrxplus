from owrx.controllers.admin import AuthorizationMixin
from owrx.controllers.template import WebpageController
from owrx.controllers import BodySizeError
from owrx.controllers.settings import SettingsBreadcrumb
from owrx.breadcrumb import Breadcrumb, BreadcrumbItem, BreadcrumbMixin
from owrx.pluginmanager import PluginManager
from urllib.parse import quote, unquote
import json

import logging

logger = logging.getLogger(__name__)

# max size for an uploaded plugin package
MAX_UPLOAD_SIZE = 2 * 1024 * 1024


class PluginManagerController(AuthorizationMixin, BreadcrumbMixin, WebpageController):
    def get_breadcrumb(self) -> Breadcrumb:
        return SettingsBreadcrumb().append(BreadcrumbItem("Plugins", "settings/plugins"))

    def render_plugins(self):
        def render_plugin(p):
            statusBadge = (
                '<span class="badge badge-success">enabled</span>'
                if p["enabled"]
                else '<span class="badge badge-secondary">disabled</span>'
            )
            toggleLabel = "Disable" if p["enabled"] else "Enable"
            toggleAction = "disable" if p["enabled"] else "enable"
            description = "<div>{}</div>".format(p["description"]) if p["description"] else ""
            version = " <small class=\"text-muted\">v{}</small>".format(p["version"]) if p["version"] else ""

            return """
                <li class="list-group-item">
                    <div class="row">
                        <div class="col-6">
                            <h3>{title}{version} {status}</h3>
                            {description}
                        </div>
                        <div class="col-6 text-right">
                            <a class="btn btn-secondary" href="plugins/{toggle_action}/{name_q}">{toggle_label}</a>
                            <a class="btn btn-danger" href="plugins/uninstall/{name_q}"
                               onclick="return confirm('Uninstall plugin &quot;{title}&quot;? This cannot be undone.');">
                               Uninstall</a>
                        </div>
                    </div>
                </li>
            """.format(
                title=p["title"],
                version=version,
                status=statusBadge,
                description=description,
                toggle_action=toggleAction,
                toggle_label=toggleLabel,
                name_q=quote(p["name"]),
            )

        plugins = PluginManager.getSharedInstance().listPlugins()
        emptyText = """
            <li class="list-group-item">No plugins installed yet. Upload a plugin package below.</li>
        """
        return """
            <ul class="list-group list-group-flush">
                {plugins}
            </ul>
            <div class="buttons container mt-3">
                <input type="file" id="plugin-upload-input" accept=".zip" style="display:none" />
                <button type="button" class="btn btn-success" id="plugin-upload-button">Upload plugin package...</button>
                <span id="plugin-upload-status" class="ml-3"></span>
            </div>
        """.format(
            plugins="".join(render_plugin(p) for p in plugins) if plugins else emptyText
        )

    def template_variables(self):
        variables = super().template_variables()
        variables["content"] = self.render_plugins()
        variables["title"] = "Plugins"
        variables["modal"] = ""
        variables["error"] = ""
        return variables

    def indexAction(self):
        self.serve_template("settings/general.html", **self.template_variables())

    def upload(self):
        try:
            data = self.get_body(MAX_UPLOAD_SIZE)
        except BodySizeError:
            self.send_json_response({"error": "Package too large"}, code=400)
            return
        if not data:
            self.send_json_response({"error": "Empty upload"}, code=400)
            return
        try:
            name = PluginManager.getSharedInstance().install(data)
        except ValueError as e:
            self.send_json_response({"error": str(e)}, code=400)
            return
        except Exception as e:
            logger.exception("Error installing plugin")
            self.send_json_response({"error": "Server error: " + str(e)}, code=500)
            return
        self.send_json_response({"name": name}, code=200)

    def enable(self):
        name = unquote(self.request.matches.group(1))
        PluginManager.getSharedInstance().setEnabled(name, True)
        self.send_redirect("{}settings/plugins".format(self.get_document_root()))

    def disable(self):
        name = unquote(self.request.matches.group(1))
        PluginManager.getSharedInstance().setEnabled(name, False)
        self.send_redirect("{}settings/plugins".format(self.get_document_root()))

    def uninstall(self):
        name = unquote(self.request.matches.group(1))
        try:
            PluginManager.getSharedInstance().uninstall(name)
        except ValueError:
            pass
        self.send_redirect("{}settings/plugins".format(self.get_document_root()))

    def send_json_response(self, obj, code):
        self.send_response(json.dumps(obj), code=code, content_type="application/json")
