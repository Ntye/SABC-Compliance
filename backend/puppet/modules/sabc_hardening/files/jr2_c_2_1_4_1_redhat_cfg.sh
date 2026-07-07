#!/bin/bash
shopt -s globstar 2>/dev/null || true
rpm -q ntp >/dev/null 2>&1 || rpm -q ntpsec >/dev/null 2>&1 || exit 0
f=/etc/ntpsec/ntp.conf; [ -e "$f" ] || f=/etc/ntp.conf
[ -e "$f" ] || exit 0
grep -Eq '^[[:space:]]*restrict[[:space:]]+(-4[[:space:]]+)?default' "$f" \
  && sed -ri 's|^[[:space:]]*restrict[[:space:]]+(-4[[:space:]]+)?default.*|restrict -4 default kod nomodify notrap nopeer noquery|' "$f" \
  || printf 'restrict -4 default kod nomodify notrap nopeer noquery\n' >> "$f"
grep -Eq '^[[:space:]]*restrict[[:space:]]+-6[[:space:]]+default' "$f" \
  && sed -ri 's|^[[:space:]]*restrict[[:space:]]+-6[[:space:]]+default.*|restrict -6 default kod nomodify notrap nopeer noquery|' "$f" \
  || printf 'restrict -6 default kod nomodify notrap nopeer noquery\n' >> "$f"
systemctl try-restart ntp >/dev/null 2>&1 || systemctl try-restart ntpsec >/dev/null 2>&1
exit 0
