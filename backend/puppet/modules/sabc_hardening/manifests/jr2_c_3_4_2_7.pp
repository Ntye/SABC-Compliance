# JR2.C.3.4.2.7 (CIS Level 1) — Ensure nftables service is enabled.
# Generated from the SABC referential. Enforcement is the family's own
# Configure procedure, run only when the Validate procedure fails.
class sabc_hardening::jr2_c_3_4_2_7 {
  if $facts['os']['family'] == 'Debian' {
    exec { 'sabc_jr2_c_3_4_2_7_debian':
      command  => @(SABC_CMD/L),
        systemctl enable nftables
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        systemctl is-enabled nftables
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
  if $facts['os']['family'] == 'RedHat' {
    exec { 'sabc_jr2_c_3_4_2_7_redhat':
      command  => @(SABC_CMD/L),
        systemctl enable nftables
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        systemctl is-enabled nftables
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
}
