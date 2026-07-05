# JR2.C.3.4.3.1.3 (CIS Level 1) — Ensure ufw is uninstalled or disabled with iptables.
# Generated from the SABC referential. Enforcement is the family's own
# Configure procedure, run only when the Validate procedure fails.
class sabc_hardening::jr2_c_3_4_3_1_3 {
  if $facts['os']['family'] == 'Debian' {
    exec { 'sabc_jr2_c_3_4_3_1_3_debian':
      command  => @(SABC_CMD/L),
        apt purge ufw
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        dpkg-query -W -f='${binary:Package}\t${Status}\t${db:Status-Status}\n' ufw
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
  if $facts['os']['family'] == 'RedHat' {
    exec { 'sabc_jr2_c_3_4_3_1_3_redhat':
      command  => @(SABC_CMD/L),
        systemctl --now enable firewalld
        systemctl --now mask nftables 2>/dev/null || true
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        systemctl is-active firewalld
        systemctl is-enabled nftables 2>/dev/null || echo 'nftables service masked/inactive (managed by firewalld)'
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
}
