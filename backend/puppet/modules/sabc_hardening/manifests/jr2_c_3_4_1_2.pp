# JR2.C.3.4.1.2 (CIS Level 1) — Ensure iptables-persistent is not installed with ufw.
# Generated from the SABC referential. Enforcement is the family's own
# Configure procedure, run only when the Validate procedure fails.
class sabc_hardening::jr2_c_3_4_1_2 {
  if $facts['os']['family'] == 'Debian' {
    exec { 'sabc_jr2_c_3_4_1_2_debian':
      command  => @(SABC_CMD/L),
        apt purge iptables-persistent
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        dpkg-query -s iptables-persistent
        package 'iptables-persistent' is not installed and no information is available
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
  if $facts['os']['family'] == 'RedHat' {
    exec { 'sabc_jr2_c_3_4_1_2_redhat':
      command  => @(SABC_CMD/L),
        dnf remove -y iptables-persistent
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        dpkg-query -s iptables-persistent
        package 'iptables-persistent' is not installed and no information is available
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
}
