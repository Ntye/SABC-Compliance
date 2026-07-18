control 'JR2.C.2.2.15' do
  title 'Ensure mail transfer agent is configured for local-only mode.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_2_2_15'
  if os.debian?
    v_debian = command(<<-'SABC_V'.chomp)
ss -lntu | grep -P ':25\b' | grep -Pv '\h+(127\.0\.0\.1|\[?::1\]?):25\b'
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
ss -lntu 2>/dev/null | awk '$5 !~ /^(127\.0\.0\.1|\[?::1\]?):(25|465|587)$/ && $5 ~ /:(25|465|587)$/ {found=1} END {exit found?1:0}'
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
