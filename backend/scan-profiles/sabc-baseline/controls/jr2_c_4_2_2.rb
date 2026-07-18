control 'JR2.C.4.2.2' do
  title 'Ensure permissions on SSH private host key files are configured.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_4_2_2'
  if os.debian?
    v_debian = command(<<-'SABC_V'.chomp)
#!/bin/bash
bad=0
for f in /etc/ssh/ssh_host_*_key; do
  [ -e "$f" ] || continue
  [ "$(stat -c '%U:%G' "$f")" = "root:root" ] || bad=1
  case "$(stat -c '%a' "$f")" in
    600|400|0) : ;;
    *) bad=1 ;;
  esac
done
exit $bad
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
#!/usr/bin/env bash
found=0
for f in /etc/ssh/ssh_host_*_key; do
  [ -e "$f" ] || continue
  found=1
  set -- $(stat -Lc '%a %U %G' "$f")
m=$1 o=$2 g=$3
  [ "$o" = root ] || exit 1
  if [ "$g" = "ssh_keys" ]; then
    [ $(( 8#$m & 8#0137 )) -eq 0 ] || exit 1
  else
    [ "$g" = root ] && [ $(( 8#$m & 8#0177 )) -eq 0 ] || exit 1
  fi
done
[ "$found" -eq 1 ] && exit 0 || exit 101
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
