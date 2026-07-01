#!/usr/bin/env bash
# =============================================================================
# SABC Compliance — server test script
# =============================================================================
# Exercises the platform's HTTP API with NORMAL (happy-path) and UNUSUAL
# (edge-case / malformed / hostile) inputs, focusing on the closed remediation
# loop and its neighbours. Prints PASS/FAIL per case against the expected HTTP
# status and exits non-zero if anything fails.
#
# SAFETY: by default only read-only and NEGATIVE/validation cases run — nothing
# that changes a node. The positive closed-loop and webhook-accepted cases
# actually trigger `puppet agent -t` on real nodes, so they are OPT-IN via
# RUN_ENFORCE=1.
#
# Usage:
#   BASE_URL=https://server:8443 API_KEY=... ./deploy/test-server.sh
#   # include the real-enforcement happy paths (mutates nodes!):
#   RUN_ENFORCE=1 NODE_ID=... GROUP_ID=... AGENT_NAME=host1 \
#     WEBHOOK_SECRET=... ./deploy/test-server.sh
#
# Configuration (environment variables):
#   BASE_URL         platform base URL           (default https://localhost:8443)
#   API_PREFIX       path prefix                 (default /api; use "" against backend :3000)
#   API_KEY          operator API key (X-API-Key)  — required for authed cases
#   WEBHOOK_SECRET   wazuh_webhook_secret          — required for webhook cases
#   NODE_ID          a real node id                — for closed-loop node cases
#   GROUP_ID         a real node group id          — for closed-loop group cases
#   AGENT_NAME       a real node hostname          — for the webhook-accepted case
#   RUN_ENFORCE=1    also run the mutating happy paths
# =============================================================================
set -u

BASE_URL="${BASE_URL:-https://localhost:8443}"
# Use ${VAR-default} (no colon) so an intentional empty API_PREFIX="" (hitting
# the backend directly on :3000) is respected rather than forced back to /api.
API_PREFIX="${API_PREFIX-/api}"
API_KEY="${API_KEY:-}"
WEBHOOK_SECRET="${WEBHOOK_SECRET:-}"
NODE_ID="${NODE_ID:-}"
GROUP_ID="${GROUP_ID:-}"
AGENT_NAME="${AGENT_NAME:-}"
RUN_ENFORCE="${RUN_ENFORCE:-0}"

CURL_OPTS=(-sk --max-time 30)   # -k tolerates the self-signed TLS cert
pass=0; fail=0; skip=0

c_grn=$'\033[32m'; c_red=$'\033[31m'; c_yel=$'\033[33m'; c_dim=$'\033[2m'; c_rst=$'\033[0m'

url()  { printf '%s%s%s' "$BASE_URL" "$API_PREFIX" "$1"; }
auth() { [ -n "$API_KEY" ] && printf 'X-API-Key: %s' "$API_KEY"; }

section() { printf '\n%s── %s ──%s\n' "$c_dim" "$1" "$c_rst"; }

# check <name> <expected-codes> <curl args...>
# expected-codes is a space separated whitelist, e.g. "200" or "401 403".
check() {
  local name="$1" expected="$2"; shift 2
  local out code body
  out=$(curl "${CURL_OPTS[@]}" -w $'\n%{http_code}' "$@" 2>/dev/null)
  code=$(printf '%s' "$out" | tail -n1)
  body=$(printf '%s' "$out" | sed '$d')
  if printf '%s' "$expected" | tr ' ' '\n' | grep -qx "$code"; then
    printf "  ${c_grn}PASS${c_rst} %-50s → %s\n" "$name" "$code"; pass=$((pass+1))
  else
    printf "  ${c_red}FAIL${c_rst} %-50s → %s (expected %s)\n" "$name" "$code" "$expected"
    [ -n "$body" ] && printf "       ${c_dim}%s${c_rst}\n" "$(printf '%s' "$body" | tr -d '\n' | head -c 220)"
    fail=$((fail+1))
  fi
}
skip() { printf "  ${c_yel}SKIP${c_rst} %-50s (%s)\n" "$1" "$2"; skip=$((skip+1)); }

printf '%s\n' "SABC Compliance server test — ${BASE_URL}${API_PREFIX}"
[ -z "$API_KEY" ] && printf '%s! No API_KEY set — authenticated cases will be skipped.%s\n' "$c_yel" "$c_rst"

# ── 1. Health & authentication ───────────────────────────────────────────────
section "Health & auth"
check "GET /health (no auth)"                 "200"       "$(url /health)"
check "GET /compliance/summary (no key)"      "401 403"   "$(url /compliance/summary)"
if [ -n "$API_KEY" ]; then
  check "GET /compliance/summary (valid key)" "200"       "$(url /compliance/summary)" -H "$(auth)"
  check "GET / with a BOGUS key"              "401 403"   "$(url /compliance/summary)" -H "X-API-Key: bogus-key-00000"
else
  skip "authenticated summary" "no API_KEY"
fi

# ── 2. Discovery (normal reads) ──────────────────────────────────────────────
section "Discovery"
if [ -n "$API_KEY" ]; then
  check "GET /nodes"                          "200"       "$(url /nodes)"        -H "$(auth)"
  check "GET /node-groups"                    "200"       "$(url /node-groups)"  -H "$(auth)"
else
  skip "discovery" "no API_KEY"
fi

# ── 3. Closed loop — UNUSUAL / validation (safe, non-mutating) ───────────────
section "Closed loop — validation (unusual inputs)"
if [ -n "$API_KEY" ]; then
  H=(-H "$(auth)" -H "Content-Type: application/json")
  check "POST /closed-loop {}  (neither id)"       "422" -X POST "${H[@]}" -d '{}'                                   "$(url /compliance/closed-loop)"
  check "POST /closed-loop {both ids}"             "422" -X POST "${H[@]}" -d '{"node_id":"a","group_id":"b"}'       "$(url /compliance/closed-loop)"
  check "POST /closed-loop {unknown node}"         "404" -X POST "${H[@]}" -d '{"node_id":"nope-does-not-exist"}'    "$(url /compliance/closed-loop)"
  check "POST /closed-loop {unknown group}"        "404" -X POST "${H[@]}" -d '{"group_id":"nope-does-not-exist"}'   "$(url /compliance/closed-loop)"
  check "POST /closed-loop malformed JSON"         "422 400" -X POST "${H[@]}" -d 'not-json{'                        "$(url /compliance/closed-loop)"
  check "POST /closed-loop injection-ish id"       "404" -X POST "${H[@]}" -d '{"node_id":"1; DROP TABLE nodes;--"}' "$(url /compliance/closed-loop)"
  check "POST /closed-loop unicode/huge desc"      "404 422" -X POST "${H[@]}" \
        -d '{"node_id":"missing","description":"éàü 你好 '"$(head -c 500 /dev/zero | tr '\0' 'X')"'"}'                "$(url /compliance/closed-loop)"
  check "GET /compliance/nodes/UNKNOWN"            "404" "$(url /compliance/nodes/unknown-node-xyz)" -H "$(auth)"
else
  skip "closed-loop validation" "no API_KEY"
fi

# ── 4. Webhook — UNUSUAL / security (safe: unmatched/ignored do not enforce) ─
section "Wazuh webhook — security & malformed"
WH="$(url /webhooks/wazuh)"
check "POST /webhooks/wazuh no token"            "401 503" -X POST -H "Content-Type: application/json" -d '{}'       "$WH"
if [ -n "$WEBHOOK_SECRET" ]; then
  WT=(-H "X-Wazuh-Webhook-Token: $WEBHOOK_SECRET" -H "Content-Type: application/json")
  check "POST /webhooks/wazuh WRONG token"        "401" -X POST -H "X-Wazuh-Webhook-Token: wrong" -H "Content-Type: application/json" -d '{}' "$WH"
  check "POST /webhooks/wazuh non-JSON body"      "400" -X POST "${WT[@]}" -d 'garbage-not-json'                     "$WH"
  check "POST /webhooks/wazuh JSON array body"    "400" -X POST "${WT[@]}" -d '[1,2,3]'                              "$WH"
  check "POST /webhooks/wazuh empty alert"        "200" -X POST "${WT[@]}" -d '{}'                                  "$WH"
  check "POST /webhooks/wazuh low-level alert"    "200" -X POST "${WT[@]}" -d '{"id":"1","rule":{"level":2,"description":"noise"},"agent":{"name":"whatever"}}' "$WH"
  check "POST /webhooks/wazuh unknown agent"      "200" -X POST "${WT[@]}" -d '{"id":"2","rule":{"level":12,"description":"crit"},"agent":{"name":"ghost-host-zzz","ip":"203.0.113.9"}}' "$WH"
else
  skip "webhook authed cases" "no WEBHOOK_SECRET"
fi

# ── 5. Positive / MUTATING happy paths (opt-in) ──────────────────────────────
section "Closed loop — real enforcement (opt-in RUN_ENFORCE=1)"
if [ "$RUN_ENFORCE" = "1" ] && [ -n "$API_KEY" ]; then
  H=(-H "$(auth)" -H "Content-Type: application/json")
  if [ -n "$NODE_ID" ]; then
    check "POST /closed-loop {node_id} (REAL)"    "200" -X POST "${H[@]}" -d "{\"node_id\":\"$NODE_ID\"}"           "$(url /compliance/closed-loop)"
  else skip "closed-loop node happy path" "no NODE_ID"; fi
  if [ -n "$GROUP_ID" ]; then
    check "POST /closed-loop {group_id} (REAL)"   "200" -X POST "${H[@]}" -d "{\"group_id\":\"$GROUP_ID\"}"         "$(url /compliance/closed-loop)"
  else skip "closed-loop group happy path" "no GROUP_ID"; fi
  if [ -n "$WEBHOOK_SECRET" ] && [ -n "$AGENT_NAME" ]; then
    WT=(-H "X-Wazuh-Webhook-Token: $WEBHOOK_SECRET" -H "Content-Type: application/json")
    check "POST /webhooks/wazuh known agent (REAL)" "202 200" -X POST "${WT[@]}" \
          -d "{\"id\":\"9\",\"rule\":{\"level\":12,\"description\":\"cis drift\"},\"agent\":{\"name\":\"$AGENT_NAME\"}}" "$WH"
  else skip "webhook accepted happy path" "need WEBHOOK_SECRET + AGENT_NAME"; fi
else
  skip "real enforcement suite" "set RUN_ENFORCE=1 (mutates nodes)"
fi

# ── Summary ──────────────────────────────────────────────────────────────────
printf '\n%s─────────────────────────────%s\n' "$c_dim" "$c_rst"
printf 'Result: %sPASS %d%s  %sFAIL %d%s  %sSKIP %d%s\n' \
  "$c_grn" "$pass" "$c_rst" "$c_red" "$fail" "$c_rst" "$c_yel" "$skip" "$c_rst"
[ "$fail" -eq 0 ] && exit 0 || exit 1
