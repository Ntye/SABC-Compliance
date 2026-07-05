# JR2.C.4.5.1.1 (CIS Level 1) — Ensure minimum days between password changes is configured.
# Generated from the SABC referential. Enforcement is the family's own
# Configure procedure, run only when the Validate procedure fails.
class sabc_hardening::jr2_c_4_5_1_1 {
  if $facts['os']['family'] == 'Debian' {
    exec { 'sabc_jr2_c_4_5_1_1_debian':
      command  => @(SABC_CMD/L),
        PASS_MIN_DAYS 1
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        grep PASS_MIN_DAYS /etc/login.defs
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
  if $facts['os']['family'] == 'RedHat' {
    exec { 'sabc_jr2_c_4_5_1_1_redhat':
      command  => @(SABC_CMD/L),
        PASS_MIN_DAYS 1
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        grep PASS_MIN_DAYS /etc/login.defs
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
}
