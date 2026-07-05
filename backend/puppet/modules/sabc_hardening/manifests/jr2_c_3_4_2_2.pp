# JR2.C.3.4.2.2 (CIS Level 1) — Ensure ufw is uninstalled or disabled with nftables.
# Generated from the SABC referential. Enforcement is the family's own
# Configure procedure, run only when the Validate procedure fails.
class sabc_hardening::jr2_c_3_4_2_2 {
  if $facts['os']['family'] == 'Debian' {
    exec { 'sabc_jr2_c_3_4_2_2_debian':
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
    exec { 'sabc_jr2_c_3_4_2_2_redhat':
      command  => @(SABC_CMD/L),
        sed -ri 's/^FirewallBackend=.*/FirewallBackend=nftables/' /etc/firewalld/firewalld.conf
        systemctl restart firewalld
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        grep -P '^\h*FirewallBackend=nftables' /etc/firewalld/firewalld.conf
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
}
