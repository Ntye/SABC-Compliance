#!/bin/bash
shopt -s globstar 2>/dev/null || true
printf 'TMOUT=900\nreadonly TMOUT\nexport TMOUT\n' > /etc/profile.d/50-sabc-tmout.sh
chmod 644 /etc/profile.d/50-sabc-tmout.sh
exit 0
