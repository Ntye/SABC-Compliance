control 'JR2.C.4.4.3' do
  title 'Ensure password reuse is limited.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_4_4_3'
  if os[:family] == 'debian'
    describe command(<<-'SABC_V'.chomp) do
      grep -P -- '^\h*password\h+([^#\n\r]+\h+)?(pam_pwhistory\.so|pam_unix\.so)\b' /etc/pam.d/common-password
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
  if os[:family] == 'redhat'
    describe command(<<-'SABC_V'.chomp) do
      grep -P 'pam_faillock\.so' /etc/pam.d/system-auth /etc/pam.d/password-auth
      grep -P '^\h*(deny|unlock_time)' /etc/security/faillock.conf
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
end
