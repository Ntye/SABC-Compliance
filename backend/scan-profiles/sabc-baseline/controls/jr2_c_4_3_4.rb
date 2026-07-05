control 'JR2.C.4.3.4' do
  title 'Ensure re-authentication for privilege escalation is not disabled globally.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_4_3_4'
  if os[:family] == 'debian'
    describe command(<<-'SABC_V'.chomp) do
      grep -r "^[^#].*\!authenticate" /etc/sudoers*
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
  if os[:family] == 'redhat'
    describe command(<<-'SABC_V'.chomp) do
      grep -r "^[^#].*\!authenticate" /etc/sudoers*
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
end
