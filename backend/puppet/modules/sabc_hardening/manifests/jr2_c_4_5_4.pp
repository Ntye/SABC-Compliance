# JR2.C.4.5.4 (CIS Level 1) — Ensure maximum number of same consecutive characters in a password is configured.
# Generated from the SABC referential. Enforcement is the family's own
# Configure procedure, run only when the Validate procedure fails.
class sabc_hardening::jr2_c_4_5_4 {
  if $facts['os']['family'] == 'Debian' {
    exec { 'sabc_jr2_c_4_5_4_debian':
      command  => @(SABC_CMD/L),
        maxrepeat = 3
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        grep -Pi '^\h*maxrepeat\h*=\h*[1-3]\b' /etc/security/pwquality.conf
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
  if $facts['os']['family'] == 'RedHat' {
    exec { 'sabc_jr2_c_4_5_4_redhat':
      command  => @(SABC_CMD/L),
        maxrepeat = 3
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        grep -Pi '^\h*maxrepeat\h*=\h*[1-3]\b' /etc/security/pwquality.conf
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
}
