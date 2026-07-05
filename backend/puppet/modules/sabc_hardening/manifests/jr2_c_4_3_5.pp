# JR2.C.4.3.5 (CIS Level 1) — Ensure sudo authentication timeout is configured correctly.
# Generated from the SABC referential. Enforcement is the family's own
# Configure procedure, run only when the Validate procedure fails.
class sabc_hardening::jr2_c_4_3_5 {
  if $facts['os']['family'] == 'Debian' {
    exec { 'sabc_jr2_c_4_3_5_debian':
      command  => @(SABC_CMD/L),
        Defaults env_reset, timestamp_timeout=15
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        grep -roP "timestamp_timeout=\K[0-9]*" /etc/sudoers*
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
  if $facts['os']['family'] == 'RedHat' {
    exec { 'sabc_jr2_c_4_3_5_redhat':
      command  => @(SABC_CMD/L),
        Defaults env_reset, timestamp_timeout=15
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        grep -roP "timestamp_timeout=\K[0-9]*" /etc/sudoers*
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
}
