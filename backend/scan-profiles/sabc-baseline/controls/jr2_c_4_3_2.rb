control 'JR2.C.4.3.2' do
  title 'Ensure sudo commands use pty.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_4_3_2'
  if os[:family] == 'debian'
    describe command(<<-'SABC_V'.chomp) do
      grep -rPi '^\h*Defaults\h+([^#\n\r]+,)?use_pty(,\h*\h+\h*)*\h*(#.*)?$' /etc/sudoers*
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
  if os[:family] == 'redhat'
    describe command(<<-'SABC_V'.chomp) do
      grep -rPi '^\h*Defaults\h+([^#\n\r]+,)?use_pty(,\h*\h+\h*)*\h*(#.*)?$' /etc/sudoers*
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
end
