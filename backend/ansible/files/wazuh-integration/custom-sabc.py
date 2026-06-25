#!/usr/bin/env python3
"""
Wazuh → SABC Compliance Platform integration.

Installed as /var/ossec/integrations/custom-sabc.py on the Wazuh manager and
invoked by the Wazuh integrator daemon for every alert that matches the
<integration> rule in ossec.conf. It POSTs the full alert JSON to the platform's
webhook, which then drives the closed remediation loop (Puppet enforcement +
compliance re-scan).

Invocation (set by the Wazuh integrator):
    custom-sabc.py <alert_file> <api_key> <hook_url> [options]

  argv[1]  path to a temp file containing the alert as JSON
  argv[2]  the <api_key> from ossec.conf  → sent as X-Wazuh-Webhook-Token
  argv[3]  the <hook_url> from ossec.conf → the platform webhook endpoint

This script has no third-party dependencies (urllib only) so it runs inside the
stock wazuh/wazuh-manager image without extra packages.
"""
import json
import logging
import ssl
import sys
import urllib.request

LOG_FILE = "/var/ossec/logs/integrations.log"

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s custom-sabc[%(process)d] %(levelname)s: %(message)s",
)
log = logging.getLogger("custom-sabc")


def main(argv: list[str]) -> int:
    if len(argv) < 4:
        log.error("usage: custom-sabc.py <alert_file> <api_key> <hook_url>")
        return 1

    alert_file, api_key, hook_url = argv[1], argv[2], argv[3]

    try:
        with open(alert_file, "r", encoding="utf-8") as fh:
            alert = json.load(fh)
    except Exception as exc:  # noqa: BLE001
        log.error("could not read alert file %s: %s", alert_file, exc)
        return 1

    body = json.dumps(alert).encode("utf-8")
    req = urllib.request.Request(hook_url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    if api_key:
        req.add_header("X-Wazuh-Webhook-Token", api_key)

    # The platform serves the webhook over HTTPS with a self-signed cert by
    # default; the secret token is the authentication boundary, so TLS chain
    # verification is intentionally relaxed for this manager→platform hop.
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    try:
        with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
            status = resp.getcode()
            payload = resp.read(2048).decode("utf-8", "replace")
            log.info("posted alert → %s [%s] %s", hook_url, status, payload)
    except urllib.error.HTTPError as exc:
        log.error("webhook returned HTTP %s: %s", exc.code, exc.read(512))
        return 1
    except Exception as exc:  # noqa: BLE001
        log.error("failed to POST alert to %s: %s", hook_url, exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
