# JR2.C.2.3.2 (CIS Level 1) — Ensure rsh client is not installed.
# Generated from the SABC referential. Enforcement is the family's own
# Configure procedure, run only when the Validate procedure fails.
class sabc_hardening::jr2_c_2_3_2 {
  if $facts['os']['family'] == 'Debian' {
    exec { 'sabc_jr2_c_2_3_2_debian':
      command  => @(SABC_CMD/L),
        apt purge rsh-client
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        dpkg-query -W -f='${binary:Package}\t${Status}\t${db:Status-Status}\n' rsh-client
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
  if $facts['os']['family'] == 'RedHat' {
    exec { 'sabc_jr2_c_2_3_2_redhat':
      command  => @(SABC_CMD/L),
        dnf remove -y rsh-client
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        rpm -q rsh-client
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
}
