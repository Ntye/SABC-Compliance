# JR2.C.4.5.1.3 (CIS Level 1) — Ensure password expiration warning days is 7 or more.
# Generated from the SABC referential. Enforcement is the family's own
# Configure procedure, run only when the Validate procedure fails.
class sabc_hardening::jr2_c_4_5_1_3 {
  if $facts['os']['family'] == 'Debian' {
    exec { 'sabc_jr2_c_4_5_1_3_debian':
      command  => @(SABC_CMD/L),
        PASS_WARN_AGE 7
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        grep PASS_WARN_AGE /etc/login.defs
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
  if $facts['os']['family'] == 'RedHat' {
    exec { 'sabc_jr2_c_4_5_1_3_redhat':
      command  => @(SABC_CMD/L),
        PASS_WARN_AGE 7
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        grep PASS_WARN_AGE /etc/login.defs
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
}
