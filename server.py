import importlib
import json
import os
import re
from pathlib import Path
from wsgiref.simple_server import make_server


ROOT = Path(__file__).resolve().parent
WEB_ROOT = ROOT / "web"
MAX_CODE_LENGTH = 20000


def _load_adapter():
    """Load an optional production model adapter from an importable module."""
    adapter_name = os.environ.get("CODESC_MODEL_ADAPTER", "").strip()
    if not adapter_name:
        return None
    module = importlib.import_module(adapter_name)
    summarize = getattr(module, "summarize", None)
    if not callable(summarize):
        raise RuntimeError("CODESC_MODEL_ADAPTER must expose summarize(code)")
    return summarize


MODEL_ADAPTER = _load_adapter()


def preview_summary(code):
    """Provide a useful local preview when a trained checkpoint is unavailable."""
    compact = " ".join(code.split())
    class_match = re.search(r"\b(?:class|interface|enum)\s+([A-Za-z_$][\w$]*)", compact)
    method_match = re.search(
        r"\b([A-Za-z_$][\w$]*)\s*\([^;{}]*\)\s*(?:throws [^{]+)?\s*\{", compact
    )
    control_words = []
    if re.search(r"\b(for|while|do)\b", compact):
        control_words.append("iterates over data")
    if re.search(r"\b(if|switch)\b", compact):
        control_words.append("applies conditional logic")
    if re.search(r"\breturn\b", compact):
        control_words.append("returns a result")
    if re.search(r"\bnew\s+\w+", compact):
        control_words.append("creates an object")
    if re.search(r"\.filter\s*\(", compact):
        control_words.append("filters the input")
    if re.search(r"\.map\s*\(", compact):
        control_words.append("transforms each item")
    if re.search(r"\.collect\s*\(", compact):
        control_words.append("collects the output")

    subject = "in {}".format(class_match.group(1)) if class_match else "in the provided code"
    action = method_match.group(1) if method_match else "the method"
    behavior = ", ".join(control_words) or "performs its defined operation"
    return "Summarizes {} by {} {}.".format(action, behavior, subject)


def summarize(code):
    if MODEL_ADAPTER is not None:
        result = MODEL_ADAPTER(code)
        if not isinstance(result, str) or not result.strip():
            raise RuntimeError("The model adapter returned an empty summary")
        return {"summary": result.strip(), "mode": "model"}
    return {"summary": preview_summary(code), "mode": "preview"}


def json_response(start_response, payload, status="200 OK"):
    body = json.dumps(payload).encode("utf-8")
    start_response(status, [("Content-Type", "application/json"),
                            ("Content-Length", str(len(body))),
                            ("Cache-Control", "no-store")])
    return [body]


def application(environ, start_response):
    path = environ.get("PATH_INFO", "/")
    method = environ.get("REQUEST_METHOD", "GET")

    if path == "/api/health" and method == "GET":
        return json_response(start_response, {"ok": True, "mode": "model" if MODEL_ADAPTER else "preview"})

    if path == "/api/summarize" and method == "POST":
        try:
            length = int(environ.get("CONTENT_LENGTH") or 0)
            payload = json.loads(environ["wsgi.input"].read(length) or b"{}")
            code = payload.get("code", "")
            if not isinstance(code, str) or not code.strip():
                return json_response(start_response, {"error": "Paste a code sample first."}, "400 Bad Request")
            if len(code) > MAX_CODE_LENGTH:
                return json_response(start_response, {"error": "Code is limited to 20,000 characters."}, "413 Request Entity Too Large")
            return json_response(start_response, summarize(code))
        except (ValueError, json.JSONDecodeError):
            return json_response(start_response, {"error": "Request body must be valid JSON."}, "400 Bad Request")
        except Exception as exc:
            return json_response(start_response, {"error": str(exc)}, "500 Internal Server Error")

    if path == "/" or path == "/index.html":
        file_path = WEB_ROOT / "index.html"
        content_type = "text/html; charset=utf-8"
    elif path.startswith("/web/"):
        file_path = (ROOT / path.lstrip("/")).resolve()
        content_type = {".css": "text/css; charset=utf-8", ".js": "text/javascript; charset=utf-8"}.get(file_path.suffix, "application/octet-stream")
        if WEB_ROOT not in file_path.parents:
            return json_response(start_response, {"error": "Not found"}, "404 Not Found")
    else:
        return json_response(start_response, {"error": "Not found"}, "404 Not Found")

    try:
        body = file_path.read_bytes()
    except FileNotFoundError:
        return json_response(start_response, {"error": "Not found"}, "404 Not Found")
    start_response("200 OK", [("Content-Type", content_type), ("Content-Length", str(len(body)))])
    return [body]


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    with make_server("0.0.0.0", port, application) as httpd:
        print("CoDesc web app listening on http://localhost:{}".format(port))
        httpd.serve_forever()