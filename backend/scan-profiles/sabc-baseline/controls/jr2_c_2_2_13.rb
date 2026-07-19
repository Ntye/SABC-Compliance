control 'JR2.C.2.2.13' do
  title 'Ensure NIS Server is not installed.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_2_2_13'
  if os.debian?
    describe package('nis') do
      it { should_not be_installed }
    end
  end
  if os.redhat?
    v_redhat = command(<<-'SABC_V'.chomp)
exec /bin/bash <<'SABC_BASH_EOF'
#!/usr/bin/env bash
installed=0
for p in ypserv; do rpm -q "$p" >/dev/null 2>&1 && installed=1; done
[ "$installed" -eq 0 ] && exit 0
# Package present (may be a dependency): its units must be neither enabled nor active.
systemctl is-enabled ypserv.service 2>/dev/null | grep -q '^enabled' && exit 1
systemctl is-active ypserv.service 2>/dev/null | grep -q '^active' && exit 1
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
