# JR2.C.3.4.1.3 (CIS Level 1) — Ensure ufw service is enabled.
# Generated from the SABC referential. Enforcement is the family's own
# Configure procedure, run only when the Validate procedure fails.
class sabc_hardening::jr2_c_3_4_1_3 {
  if $facts['os']['family'] == 'Debian' {
    exec { 'sabc_jr2_c_3_4_1_3_debian':
      command  => @(SABC_CMD/L),
        systemctl unmask ufw.service
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        systemctl is-enabled ufw.service
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
  if $facts['os']['family'] == 'RedHat' {
    exec { 'sabc_jr2_c_3_4_1_3_redhat':
      command  => @(SABC_CMD/L),
        systemctl --now enable firewalld
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        systemctl is-enabled firewalld
        systemctl is-active firewalld
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
}
