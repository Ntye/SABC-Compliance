#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
systemctl stop dovecot.socket dovecot.service cyrus-imapd.service 2>/dev/null || true
systemctl mask dovecot.socket dovecot.service cyrus-imapd.service 2>/dev/null || true
dnf remove -y dovecot cyrus-imapd
