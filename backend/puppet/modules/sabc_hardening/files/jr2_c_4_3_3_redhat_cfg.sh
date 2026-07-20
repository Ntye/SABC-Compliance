#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
printf 'Defaults logfile="/var/log/sudo.log"\n' > /etc/sudoers.d/60-criclo-logfile
chmod 440 /etc/sudoers.d/60-criclo-logfile
visudo -cf /etc/sudoers >/dev/null || { rm -f /etc/sudoers.d/60-criclo-logfile; exit 1; }
exit 0
