control 'JR2.C.6.2.9' do
  title 'Ensure root PATH Integrity.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_6_2_9'
  if os.debian?
    v_debian = command(<<-'SABC_V'.chomp)
exec /bin/bash <<'SABC_BASH_EOF'
#!/bin/bash

RPCV="$(sudo -Hiu root env | grep '^PATH' | cut -d= -f2)"
echo "$RPCV" | grep -q "::" && echo "root's path contains a empty directory (::)"
echo "$RPCV" | grep -q ":$" && echo "root's path contains a trailing (:)"
for x in $(echo "$RPCV" | tr ":" " "); do
 if [ -d "$x" ]; then
 ls -ldH "$x" | awk '$9 == "." {print "PATH contains current working directory (.)"}
 $3 != "root" {print $9, "is not owned by root"}
 substr($1,6,1) != "-" {print $9, "is group writable"}
 substr($1,9,1) != "-" {print $9, "is world writable"}'
 else
 echo "$x is not a directory"
 fi
done
SABC_BASH_EOF
    SABC_V
    if v_debian.exit_status == 101
      describe 'Not applicable' do
        skip 'Not applicable on this node: the validate procedure reported its prerequisite (package/service) is absent.'
      end
    else
      describe v_debian do
        its('exit_status') { should cmp 0 }
      end
    end
  end
  if os.redhat?
    v_redhat = command(<<-'SABC_V'.chomp)
exec /bin/bash <<'SABC_BASH_EOF'
#!/usr/bin/env bash
p=$(su - root -c 'echo "$PATH"' 2>/dev/null | tail -n1)
[ -n "$p" ] || p="$PATH"
case ":$p:" in *::*|*:.:*) exit 1 ;; esac
case "$p" in *:) exit 1 ;; esac
IFS=:
for d in $p; do
  [ -d "$d" ] || continue
  set -- $(stat -Lc '%a %U %G' "$d")
m=$1 o=$2 g=$3
  [ "$o" = root ] || exit 1
  [ $(( 8#$m & 8#0022 )) -eq 0 ] || exit 1
done
exit 0
SABC_BASH_EOF
    SABC_V
    if v_redhat.exit_status == 101
      describe 'Not applicable' do
        skip 'Not applicable on this node: the validate procedure reported its prerequisite (package/service) is absent.'
      end
    else
      describe v_redhat do
        its('exit_status') { should cmp 0 }
      end
    end
  end
end
