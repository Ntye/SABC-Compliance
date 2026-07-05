control 'JR2.C.4.4.4' do
  title 'Ensure strong password hashing algorithm is configured.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_4_4_4'
  if os[:family] == 'debian'
    describe command(<<-'SABC_V'.chomp) do
      grep -Pi -- '^\h*password\h+[^#\n\r]+\h+pam_unix.so([^#\n\r]+\h+)?(sha512|yescrypt)\b' /etc/pam.d/common-password
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
  if os[:family] == 'redhat'
    describe command(<<-'SABC_V'.chomp) do
      grep -P 'pam_pwhistory\.so' /etc/pam.d/system-auth /etc/pam.d/password-auth
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
end
