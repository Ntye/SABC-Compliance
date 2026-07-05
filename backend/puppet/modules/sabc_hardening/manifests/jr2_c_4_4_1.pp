# JR2.C.4.4.1 (CIS Level 1) — Ensure password creation requirements are configured.
# Generated from the SABC referential. Enforcement is the family's own
# Configure procedure, run only when the Validate procedure fails.
class sabc_hardening::jr2_c_4_4_1 {
  if $facts['os']['family'] == 'Debian' {
    exec { 'sabc_jr2_c_4_4_1_debian':
      command  => @(SABC_CMD/L),
        apt install libpam-pwquality
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        grep '^\s*minlen\s*' /etc/security/pwquality.conf
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
  if $facts['os']['family'] == 'RedHat' {
    exec { 'sabc_jr2_c_4_4_1_redhat':
      command  => @(SABC_CMD/L),
        dnf install -y libpwquality
        authselect enable-feature with-pwquality
        authselect apply-changes
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        grep -P 'pam_pwquality\.so' /etc/pam.d/system-auth /etc/pam.d/password-auth
        rpm -q libpwquality
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
}
