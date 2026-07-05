control 'JR2.C.3.4.2.8' do
  title 'Ensure nftables rules are permanent.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_3_4_2_8'
  if os[:family] == 'debian'
    describe command(<<-'SABC_V'.chomp) do
      [ -n "$(grep -E '^\s*include' /etc/nftables.conf)" ] && awk '/hook input/,/}/' $(awk '$1 ~ /^\s*include/ { gsub("\"","",$2);print $2 }' /etc/nftables.conf)
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
  if os[:family] == 'redhat'
    describe command(<<-'SABC_V'.chomp) do
      [ -n "$(grep -E '^\s*include' /etc/nftables.conf)" ] && awk '/hook input/,/}/' $(awk '$1 ~ /^\s*include/ { gsub("\"","",$2);print $2 }' /etc/nftables.conf)
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
end
