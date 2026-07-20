#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
printf 'Defaults use_pty\n' > /etc/sudoers.d/60-criclo-use-pty
chmod 440 /etc/sudoers.d/60-criclo-use-pty
visudo -cf /etc/sudoers >/dev/null || { rm -f /etc/sudoers.d/60-criclo-use-pty; exit 1; }
exit 0
