from owrx.controllers.admin import AuthorizationMixin
from owrx.controllers.template import WebpageController
from owrx.controllers.settings import SettingsBreadcrumb
from owrx.breadcrumb import Breadcrumb, BreadcrumbItem, BreadcrumbMixin
from owrx.log import HistoryHandler, GLOBAL_LOGGER_NAME
from owrx.config import Config


class LogsController(AuthorizationMixin, BreadcrumbMixin, WebpageController):
    def get_breadcrumb(self) -> Breadcrumb:
        return SettingsBreadcrumb().append(BreadcrumbItem("Server Logs", "settings/logs"))

    def render_content(self):
        debugHint = (
            ""
            if Config.get()["debug_enabled"]
            else """
                <div class="alert alert-info">
                    Enable "Debug" in General settings for verbose (DEBUG level) log output.
                </div>
            """
        )
        return """
            {debug_hint}
            <div class="card mt-2">
                <div class="card-header">Recent server log messages</div>
                <div class="card-body">
                    <pre class="card-text device-log-messages log-messages">{messages}</pre>
                </div>
            </div>
        """.format(
            debug_hint=debugHint,
            messages=HistoryHandler.getHandler(GLOBAL_LOGGER_NAME).getFormattedHistory(),
        )

    def template_variables(self):
        variables = super().template_variables()
        variables["content"] = self.render_content()
        variables["title"] = "Server Logs"
        variables["modal"] = ""
        variables["error"] = ""
        return variables

    def indexAction(self):
        self.serve_template("settings/general.html", **self.template_variables())

    def data(self):
        text = HistoryHandler.getHandler(GLOBAL_LOGGER_NAME).getFormattedHistory()
        self.send_response(text, content_type="text/plain")
