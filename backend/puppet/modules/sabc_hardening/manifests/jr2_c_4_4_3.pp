# JR2.C.4.4.3 (CIS Level 1) — Ensure password reuse is limited.
# Generated from the SABC referential. Enforcement is the family's own
# Configure procedure, run only when the Validate procedure fails.
class sabc_hardening::jr2_c_4_4_3 {
  if $facts['os']['family'] == 'Debian' {
    exec { 'sabc_jr2_c_4_4_3_debian':
      command  => @(SABC_CMD/L),
        password required pam_pwhistory.so remember=5
        password [success=1 default=ignore] pam_unix.so obscure sha512 use_authtok
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        grep -P -- '^\h*password\h+([^#\n\r]+\h+)?(pam_pwhistory\.so|pam_unix\.so)\b' /etc/pam.d/common-password
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
  if $facts['os']['family'] == 'RedHat' {
    exec { 'sabc_jr2_c_4_4_3_redhat':
      command  => @(SABC_CMD/L),
        authselect enable-feature with-faillock
        authselect apply-changes
        printf 'deny = 5\nunlock_time = 900\n' >> /etc/security/faillock.conf
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        grep -P 'pam_faillock\.so' /etc/pam.d/system-auth /etc/pam.d/password-auth
        grep -P '^\h*(deny|unlock_time)' /etc/security/faillock.conf
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
}
