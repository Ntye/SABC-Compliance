# JR2.C.4.4.4 (CIS Level 1) — Ensure strong password hashing algorithm is configured.
# Generated from the SABC referential. Enforcement is the family's own
# Configure procedure, run only when the Validate procedure fails.
class sabc_hardening::jr2_c_4_4_4 {
  if $facts['os']['family'] == 'Debian' {
    exec { 'sabc_jr2_c_4_4_4_debian':
      command  => @(SABC_CMD/L),
        password [success=1 default=ignore] pam_unix.so obscure sha512 use_authtok
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        grep -Pi -- '^\h*password\h+[^#\n\r]+\h+pam_unix.so([^#\n\r]+\h+)?(sha512|yescrypt)\b' /etc/pam.d/common-password
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
  if $facts['os']['family'] == 'RedHat' {
    exec { 'sabc_jr2_c_4_4_4_redhat':
      command  => @(SABC_CMD/L),
        authselect enable-feature with-pwhistory
        authselect apply-changes
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        grep -P 'pam_pwhistory\.so' /etc/pam.d/system-auth /etc/pam.d/password-auth
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
}
