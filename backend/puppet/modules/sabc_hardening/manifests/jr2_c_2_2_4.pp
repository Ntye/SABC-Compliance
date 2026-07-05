# JR2.C.2.2.4 (CIS Level 1) — Ensure LDAP server is not installed.
# Generated from the SABC referential. Enforcement is the family's own
# Configure procedure, run only when the Validate procedure fails.
class sabc_hardening::jr2_c_2_2_4 {
  if $facts['os']['family'] == 'Debian' {
    exec { 'sabc_jr2_c_2_2_4_debian':
      command  => @(SABC_CMD/L),
        apt purge slapd
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        dpkg-query -W -f='${binary:Package}\t${Status}\t${db:Status-Status}\n' slapd
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
  if $facts['os']['family'] == 'RedHat' {
    exec { 'sabc_jr2_c_2_2_4_redhat':
      command  => @(SABC_CMD/L),
        dnf remove -y slapd
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        rpm -q slapd
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
}
