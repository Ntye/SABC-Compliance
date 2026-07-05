# JR2.C.3.1.2 (CIS Level 2) — Ensure bluetooth is disabled.
# Generated from the SABC referential. Enforcement is the family's own
# Configure procedure, run only when the Validate procedure fails.
class sabc_hardening::jr2_c_3_1_2 {
  if $facts['os']['family'] == 'Debian' {
    exec { 'sabc_jr2_c_3_1_2_debian':
      command  => @(SABC_CMD/L),
        systemctl stop bluetooth.service
        systemctl mask bluetooth.service
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        systemctl is-enabled bluetooth.service | grep '^enabled'
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
  if $facts['os']['family'] == 'RedHat' {
    exec { 'sabc_jr2_c_3_1_2_redhat':
      command  => @(SABC_CMD/L),
        systemctl stop bluetooth.service
        systemctl mask bluetooth.service
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        systemctl is-enabled bluetooth.service | grep '^enabled'
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
}
