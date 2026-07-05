# JR2.C.2.1.4.3 (CIS Level 1) — Ensure ntp is enabled and running.
# Generated from the SABC referential. Enforcement is the family's own
# Configure procedure, run only when the Validate procedure fails.
class sabc_hardening::jr2_c_2_1_4_3 {
  if $facts['os']['family'] == 'Debian' {
    exec { 'sabc_jr2_c_2_1_4_3_debian':
      command  => @(SABC_CMD/L),
        systemctl unmask ntp.service
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        systemctl is-enabled ntp.service
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
  if $facts['os']['family'] == 'RedHat' {
    exec { 'sabc_jr2_c_2_1_4_3_redhat':
      command  => @(SABC_CMD/L),
        systemctl unmask ntp.service
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        systemctl is-enabled ntp.service
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
}
