# JR2.C.4.5.1.4 (CIS Level 1) — Ensure inactive password lock is 30 days or less.
# Generated from the SABC referential. Enforcement is the family's own
# Configure procedure, run only when the Validate procedure fails.
class sabc_hardening::jr2_c_4_5_1_4 {
  if $facts['os']['family'] == 'Debian' {
    exec { 'sabc_jr2_c_4_5_1_4_debian':
      command  => @(SABC_CMD/L),
        useradd -D -f 30
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        useradd -D | grep INACTIVE
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
  if $facts['os']['family'] == 'RedHat' {
    exec { 'sabc_jr2_c_4_5_1_4_redhat':
      command  => @(SABC_CMD/L),
        useradd -D -f 30
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        useradd -D | grep INACTIVE
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
}
