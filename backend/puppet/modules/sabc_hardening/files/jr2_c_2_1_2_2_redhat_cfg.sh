#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true

{
    [ ! -d "/etc/sources.d/" ] && mkdir /etc/sources.d/
    printf '%s\n' "" "#The maxsources option is unique to the pool directive"
\
   "pool time.nist.gov iburst maxsources 4" >> /etc/sources.d/60-
sources.sources
   chronyc reload sources &>/dev/null
}
Example script to add a drop-in configuration for the server directive:
#!/usr/bin/env bash

{
   [ ! -d "/etc/sources.d/" ] && mkdir /etc/sources.d/
   printf '%s\n' "" "server time-a-g.nist.gov iburst" "server 132.163.97.3
iburst" \
   "server time-d-b.nist.gov iburst" >> /etc/sources.d/60-sources.sources
   chronyc reload sources &>/dev/null
}
Run the following command to reload the chronyd config:
# systemctl reload-or-restart chronyd
