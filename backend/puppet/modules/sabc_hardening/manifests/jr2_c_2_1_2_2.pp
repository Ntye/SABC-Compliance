# JR2.C.2.1.2.2 (CIS Level 1) — Ensure chrony is enabled and running.
# Generated from the SABC referential. Enforcement is the family's own
# Configure procedure, run only when the Validate procedure fails.
class sabc_hardening::jr2_c_2_1_2_2 {
  if $facts['os']['family'] == 'Debian' {
    exec { 'sabc_jr2_c_2_1_2_2_debian':
      command  => @(SABC_CMD/L),
        systemctl unmask chrony.service
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        systemctl is-enabled chrony.service
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
  if $facts['os']['family'] == 'RedHat' {
    exec { 'sabc_jr2_c_2_1_2_2_redhat':
      command  => @(SABC_CMD/L),
        systemctl unmask chrony.service
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        systemctl is-enabled chrony.service
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
}
