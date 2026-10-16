"""Screenshots of CareQueue running on Kubernetes (kind), with headless Chromium.

    pip install playwright && python -m playwright install chromium
    kubectl -n monitoring port-forward svc/kps-prometheus 19090:9090 &
    kubectl -n monitoring port-forward svc/kps-grafana 13001:80 &
    GRAFANA_PASSWORD="$(kubectl -n monitoring get secret kps-grafana \
        -o jsonpath='{.data.admin-password}' | base64 -d)" \
      python scripts/k8s-screenshots.py ui prometheus grafana

    # terminal output as images (for "screenshot of kubectl get pods" etc.):
    python scripts/k8s-screenshots.py terminal k8s-get-pods.png docs/evidence/k8s-get-pods.txt

Env: APP_URL (default http://localhost:8088), INGRESS_HOST (carequeue.local),
PROM_URL (http://localhost:19090), GRAFANA_URL (http://localhost:13001),
GRAFANA_USER (admin), GRAFANA_PASSWORD (required for "grafana"; read it from the
Secret into the environment, never write it to a file), OUT_DIR (docs/screenshots).

"carequeue.local" is resolved to 127.0.0.1 inside Chromium only
(--host-resolver-rules), so no /etc/hosts edit is needed and the address bar
still shows the real Ingress host name.
"""
import html
import os
import sys
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import quote, urlparse

from playwright.sync_api import Browser, Page, sync_playwright

APP_URL = os.environ.get("APP_URL", "http://localhost:8088").rstrip("/")
INGRESS_HOST = os.environ.get("INGRESS_HOST", "carequeue.local")
PROM_URL = os.environ.get("PROM_URL", "http://localhost:19090").rstrip("/")
GRAFANA_URL = os.environ.get("GRAFANA_URL", "http://localhost:13001").rstrip("/")
OUT = Path(os.environ.get("OUT_DIR", "docs/screenshots"))


def shot(page: Page, name: str, full_page: bool = True) -> None:
    page.wait_for_timeout(500)
    page.screenshot(path=str(OUT / name), full_page=full_page)
    print("saved", OUT / name)


def host_url() -> str:
    port = urlparse(APP_URL).port
    return f"http://{INGRESS_HOST}{f':{port}' if port else ''}"


def ui(browser: Browser) -> None:
    # 1. Plain localhost (the Ingress' host-less rule), desktop.
    page = browser.new_page(viewport={"width": 1366, "height": 900})
    page.goto(f"{APP_URL}/#queue")
    page.get_by_text("Now serving").first.wait_for()
    shot(page, "k8s-01-ui-ingress-localhost-queue.png")

    # 2. The carequeue.local host rule, desktop: booking view.
    page.goto(f"{host_url()}/#book")
    page.get_by_label("Doctor").wait_for()
    page.get_by_label("Doctor").select_option(label="Dr. Ananya Iyer - General Medicine")
    page.get_by_label("Date").fill((date.today() + timedelta(days=1)).isoformat())
    page.get_by_role("option", name="10:30 AM").wait_for()
    shot(page, "k8s-02-ui-ingress-carequeue-local-booking.png")
    page.goto(f"{host_url()}/#patients")
    page.get_by_text("Priya Sharma").wait_for()
    shot(page, "k8s-03-ui-ingress-carequeue-local-patients.png")

    # 3. Phone width through the Ingress host.
    mobile = browser.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=2,
                              is_mobile=True, has_touch=True)
    mobile.goto(f"{host_url()}/#queue")
    mobile.get_by_text("Now serving").first.wait_for()
    shot(mobile, "k8s-04-ui-ingress-mobile-390-queue.png")


def prometheus(browser: Browser) -> None:
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    page.goto(f"{PROM_URL}/targets?search=carequeue")
    page.get_by_text("carequeue-backend").first.wait_for()
    page.wait_for_timeout(1500)
    shot(page, "mon-01-prometheus-targets-carequeue-up.png")

    page.goto(f"{PROM_URL}/targets")
    page.get_by_text("carequeue-backend").first.wait_for()
    page.wait_for_timeout(1500)
    shot(page, "mon-02-prometheus-all-targets.png")

    expr = 'sum by (handler) (rate(http_requests_total{namespace="carequeue"}[1m]))'
    page.goto(f"{PROM_URL}/query?g0.expr={quote(expr)}&g0.tab=graph&g0.range_input=30m")
    page.wait_for_timeout(3000)
    shot(page, "mon-03-prometheus-query-request-rate.png", full_page=False)

    page.goto(f"{PROM_URL}/alerts?search=carequeue")
    page.get_by_text("CareQueueBackendDown").first.wait_for()
    page.wait_for_timeout(1000)
    shot(page, "mon-04-prometheus-carequeue-alert-rules.png")


def grafana(browser: Browser) -> None:
    password = os.environ.get("GRAFANA_PASSWORD")
    if not password:
        sys.exit("GRAFANA_PASSWORD is not set (read it from the kps-grafana Secret)")
    page = browser.new_page(viewport={"width": 1600, "height": 1500})
    page.goto(f"{GRAFANA_URL}/login")
    page.get_by_label("Email or username").fill(os.environ.get("GRAFANA_USER", "admin"))
    page.get_by_label("Password").first.fill(password)
    page.get_by_role("button", name="Log in").click()
    page.wait_for_url(lambda url: "/login" not in url, timeout=20000)
    page.goto(f"{GRAFANA_URL}/d/carequeue/carequeue-clinic-api?orgId=1&from=now-30m&to=now&refresh=")
    page.get_by_text("HTTP request rate by handler").wait_for(timeout=30000)
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(6000)  # let every panel finish its queries
    shot(page, "mon-05-grafana-carequeue-dashboard.png")


def terminal(png_name: str, text_file: str) -> None:
    """Render a text transcript as a terminal-style image (a real screenshot of an HTML <pre>)."""
    text = Path(text_file).read_text()
    page_html = (
        "<html><body style='margin:0;background:#1e1e1e'>"
        "<pre style=\"margin:0;padding:18px 22px;color:#e6e6e6;background:#1e1e1e;"
        "font:14px/1.45 Menlo,'DejaVu Sans Mono',monospace;white-space:pre\">"
        f"{html.escape(text)}</pre></body></html>"
    )
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 800, "height": 200})
        page.set_content(page_html)
        width = page.evaluate("document.querySelector('pre').scrollWidth")
        page.set_viewport_size({"width": max(800, width + 4), "height": 200})
        shot(page, png_name)
        browser.close()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    if sys.argv[1:2] == ["terminal"]:
        terminal(sys.argv[2], sys.argv[3])
        return
    what = sys.argv[1:] or ["ui", "prometheus", "grafana"]
    with sync_playwright() as p:
        browser = p.chromium.launch(args=[f"--host-resolver-rules=MAP {INGRESS_HOST} 127.0.0.1"])
        for name in what:
            {"ui": ui, "prometheus": prometheus, "grafana": grafana}[name](browser)
        browser.close()


if __name__ == "__main__":
    main()
