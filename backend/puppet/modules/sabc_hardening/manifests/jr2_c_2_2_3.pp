# JR2.C.2.2.3 (CIS Level 1) — Ensure DHCP Server is not installed.
# Generated from the SABC referential. Enforcement is the family's own
# Configure procedure, run only when the Validate procedure fails.
class sabc_hardening::jr2_c_2_2_3 {
  if $facts['os']['family'] == 'Debian' {
    exec { 'sabc_jr2_c_2_2_3_debian':
      command  => @(SABC_CMD/L),
        apt purge isc-dhcp-server
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        dpkg-query -W -f='${binary:Package}\t${Status}\t${db:Status-Status}\n' isc-dhcp-server
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
  if $facts['os']['family'] == 'RedHat' {
    exec { 'sabc_jr2_c_2_2_3_redhat':
      command  => @(SABC_CMD/L),
        dnf remove -y isc-dhcp-server
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        rpm -q isc-dhcp-server
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
}
