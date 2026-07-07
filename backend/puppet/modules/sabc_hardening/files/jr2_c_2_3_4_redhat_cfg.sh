#!/bin/bash
shopt -s globstar 2>/dev/null || true
for p in telnet inetutils-telnet; do
  rpm -q "$p" >/dev/null 2>&1 && DEBIAN_FRONTEND=noninteractive apt-get -y purge "$p" >/dev/null
done
exit 0
