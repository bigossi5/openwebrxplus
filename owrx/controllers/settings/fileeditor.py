import os
import json
import shutil
import tempfile
import subprocess
from owrx.controllers.template import WebpageController
from owrx.controllers.admin import AuthorizationMixin
from owrx.controllers.settings import SettingsBreadcrumb
from owrx.breadcrumb import Breadcrumb, BreadcrumbItem, BreadcrumbMixin

import logging

logger = logging.getLogger(__name__)

CONFIG_DIR = "/etc/openwebrx"


def list_json_files():
    files = []
    for fname in sorted(os.listdir(CONFIG_DIR)):
        if fname.endswith(".json") and os.path.isfile(os.path.join(CONFIG_DIR, fname)):
            files.append((fname, fname))
    bookmarks_dir = os.path.join(CONFIG_DIR, "bookmarks.d")
    if os.path.isdir(bookmarks_dir):
        for fname in sorted(os.listdir(bookmarks_dir)):
            if fname.endswith(".json") and os.path.isfile(os.path.join(bookmarks_dir, fname)):
                files.append(("bookmarks.d/" + fname, "bookmarks.d/" + fname))
    return files


def resolve_path(relative):
    parts = relative.replace("\\", "/").split("/")
    if len(parts) == 1:
        safe = parts[0]
    elif len(parts) == 2 and parts[0] == "bookmarks.d":
        safe = os.path.join("bookmarks.d", parts[1])
    else:
        return None
    if not safe.endswith(".json"):
        return None
    full = os.path.join(CONFIG_DIR, safe)
    if not os.path.abspath(full).startswith(os.path.abspath(CONFIG_DIR) + os.sep):
        return None
    return full


class FileEditorController(AuthorizationMixin, BreadcrumbMixin, WebpageController):
    def get_breadcrumb(self) -> Breadcrumb:
        return SettingsBreadcrumb().append(BreadcrumbItem("JSON File Editor", "settings/fileeditor"))

    def template_variables(self):
        variables = super().template_variables()
        files = list_json_files()
        options_html = ""
        for label, rel in files:
            options_html += '<option value="{rel}">{label}</option>\n'.format(rel=rel, label=label)
        variables["file_options"] = options_html
        return variables

    def load(self):
        rel = self.request.query.get("file", [None])[0]
        if not rel:
            self.send_response("Missing file parameter", content_type="text/plain", code=400)
            return
        full = resolve_path(rel)
        if full is None or not os.path.isfile(full):
            self.send_response("File not found or not allowed", content_type="text/plain", code=404)
            return
        try:
            with open(full, "r", encoding="utf-8") as f:
                content = f.read()
            parsed = json.loads(content)
            pretty = json.dumps(parsed, indent=2, ensure_ascii=False)
            self.send_response(pretty, content_type="application/json", code=200)
        except Exception as e:
            self.send_response(str(e), content_type="text/plain", code=500)

    def save(self):
        rel = self.request.query.get("file", [None])[0]
        if not rel:
            self.send_response("Missing file parameter", content_type="text/plain", code=400)
            return
        full = resolve_path(rel)
        if full is None:
            self.send_response("File not allowed", content_type="text/plain", code=403)
            return
        try:
            body = self.get_body()
            if body is None:
                raise ValueError("Empty request body")
            content = body.decode("utf-8")
            parsed = json.loads(content)
            pretty = json.dumps(parsed, indent=2, ensure_ascii=False)

            fd, tmp_path = tempfile.mkstemp(suffix=".json", dir="/tmp")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as tmp:
                    tmp.write(pretty)
                shutil.copyfile(tmp_path, full)
            finally:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)

            logger.info("Saved %s", full)
            self.send_response("File saved successfully!", content_type="text/plain", code=200)
        except json.JSONDecodeError as e:
            self.send_response("Invalid JSON: " + str(e), content_type="text/plain", code=400)
        except Exception as e:
            logger.exception("Error saving %s", full)
            self.send_response("Error saving file: " + str(e), content_type="text/plain", code=500)

    def restart(self):
        # Send response BEFORE restarting — process will die during systemctl restart
        self.send_response("Restarting...", content_type="text/plain", code=200)
        try:
            subprocess.Popen(
                ["/usr/bin/sudo", "/bin/systemctl", "restart", "openwebrx"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
        except Exception as e:
            logger.exception("Error restarting openwebrx")

    def indexAction(self):
        self.serve_template("settings/fileeditor.html", **self.template_variables())
