control 'JR2.C.4.5.2' do
  title 'Ensure default user umask is 027 or more restrictive.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_4_5_2'
  if os[:family] == 'debian'
    describe command(<<-'SABC_V'.chomp) do
      #!/bin/bash
      
      passing=""
      grep -Eiq '^\s*UMASK\s+(0[0-7][2-7]7|[0-7][2-7]7)\b' /etc/login.defs && grep -Eqi '^\s*USERGROUPS_ENAB\s*"?no"?\b' /etc/login.defs && grep -Eq '^\s*session\s+(optional|requisite|required)\s+pam_umask\.so\b' /etc/pam.d/common-session && passing=true
      grep -REiq '^\s*UMASK\s+\s*(0[0-7][2-7]7|[0-7][2-7]7|u=(r?|w?|x?)(r?|w?|x?)(r?|w?|x?),g=(r?x?|x?r?),o=)\b' /etc/profile* /etc/bash.bashrc* && passing=true
      [ "$passing" = true ] && echo "Default user umask is set"
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
  if os[:family] == 'redhat'
    describe command(<<-'SABC_V'.chomp) do
      grep -P '^\h*ENCRYPT_METHOD' /etc/login.defs
      grep -P 'pam_unix\.so.*(sha512|yescrypt)' /etc/pam.d/system-auth /etc/pam.d/password-auth
    SABC_V
      its('exit_status') { should cmp 0 }
    end
  end
end
