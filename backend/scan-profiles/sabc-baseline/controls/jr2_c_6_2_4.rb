control 'JR2.C.6.2.4' do
  title 'Ensure shadow group is empty.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_6_2_4'
  if os[:family] == 'debian'
    describe command(<<-'SABC_V'.chomp) do
      awk -F: '($1=="shadow") {print $NF}' /etc/group
      awk -F: -v GID="$(awk -F: '($1=="shadow") {print $3}' /etc/group)" '($4==GID) {print $1}' /etc/passwd
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
  if os[:family] == 'redhat'
    describe command(<<-'SABC_V'.chomp) do
      awk -F: '($1=="shadow") {print $NF}' /etc/group
      awk -F: -v GID="$(awk -F: '($1=="shadow") {print $3}' /etc/group)" '($4==GID) {print $1}' /etc/passwd
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
end
