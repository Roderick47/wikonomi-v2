"""Public staging HTTP smoke test with no real user credentials or writes."""
import json
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, build_opener

HOST = "https://wikonomi-mobile-staging.onrender.com"


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


opener = build_opener(NoRedirect())
paths = {
    "/healthz/": 200,
    "/app/staging-db-status/": 200,
    "/app/": 302,
    "/app/submit/": 302,
    "/app/manifest.webmanifest": 200,
    "/app/sw.js": 200,
    "/static/mobile/app.css": 200,
    "/static/mobile/app.js": 200,
    "/static/mobile/icons/icon.svg": 200,
}
for path, expected in paths.items():
    last_error = None
    for attempt in range(6):
        try:
            try:
                response = opener.open(HOST + path, timeout=30)
            except HTTPError as e:
                response = e
            with response:
                code = response.status
                body = response.read()
                location = response.headers.get("Location", "")
                if code == 302 and not location.startswith("/users/login/"):
                    raise AssertionError(f"{path}: unexpected login redirect: {location}")
                if code != expected:
                    raise AssertionError(f"{path}: HTTP {code}, expected {expected}")
                if path == "/healthz/" and body.strip() != b"ok":
                    raise AssertionError("health endpoint did not return ok")
                if path == "/app/staging-db-status/":
                    readiness = json.loads(body)
                    if readiness != {
                        "staging_database_ready": True,
                        "mobile_migrations_ready": True,
                    }:
                        raise AssertionError("staging Postgres/migrations not ready")
                if path.endswith("manifest.webmanifest"):
                    manifest = json.loads(body)
                    if manifest.get("scope") != "/app/":
                        raise AssertionError("bad manifest scope")
                if path.endswith(".svg") and b"<svg" not in body:
                    raise AssertionError("SVG icon body missing")
                print(f"OK {path}: HTTP {code}, {len(body)} bytes")
                last_error = None
                break
        except (URLError, TimeoutError, AssertionError) as exc:
            last_error = exc
            print(f"attempt {attempt + 1} for {path}: {exc}", file=sys.stderr)
            time.sleep(8)
    if last_error:
        raise SystemExit(f"FAILED {path}: {last_error}")
print("Public staging smoke test passed (no authenticated requests or writes).")
