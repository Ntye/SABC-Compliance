control 'JR2.C.4.4.4' do
  title 'Ensure strong password hashing algorithm is configured.'
  impact 0.5
  tag cis_level: 1
  tag control_key: 'jr2_c_4_4_4'
  if os.debian?
    v_debian = command(<<-'SABC_V'.chomp)
/bin/bash <<'SABC_BASH_EOF'
grep -Pi -- '^\h*password\h+[^#\n\r]+\h+pam_unix.so([^#\n\r]+\h+)?(sha512|yescrypt)\b' /etc/pam.d/common-password
SABC_BASH_EOF
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
/bin/bash <<'SABC_BASH_EOF'
#!/usr/bin/env bash
grep -Eiq '^\s*ENCRYPT_METHOD\s+(SHA512|YESCRYPT)\b' /etc/login.defs || exit 1
grep -E 'pam_unix\.so' /etc/pam.d/system-auth /etc/pam.d/password-auth 2>/dev/null | grep -Eq '\b(md5|des|bigcrypt|blowfish)\b' && exit 1
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
