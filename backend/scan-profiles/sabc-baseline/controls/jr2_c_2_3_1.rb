control 'JR2.C.2.3.1' do
  title 'Ensure NIS Client is not installed.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_2_3_1'
  if os.debian?
    describe package('nis') do
      it { should_not be_installed }
    end
  end
  if os.redhat?
    v_redhat = command(<<-'SABC_V'.chomp)
exec /bin/bash <<'SABC_BASH_EOF'
#!/usr/bin/env bash
for p in ypbind; do
  rpm -q "$p" >/dev/null 2>&1 && exit 1
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
