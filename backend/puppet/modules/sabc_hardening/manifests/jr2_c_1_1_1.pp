# JR2.C.1.1.1 (CIS Level 1) — Disable Automounting.
# Generated from the SABC referential. Enforcement is the family's own
# Configure procedure, run only when the Validate procedure fails.
class sabc_hardening::jr2_c_1_1_1 {
  if $facts['os']['family'] == 'Debian' {
    exec { 'sabc_jr2_c_1_1_1_debian':
      command  => @(SABC_CMD/L),
        apt purge autofs
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        dpkg-query -W -f='${binary:Package}\t${Status}\t${db:Status-Status}\n' autofs
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
  if $facts['os']['family'] == 'RedHat' {
    exec { 'sabc_jr2_c_1_1_1_redhat':
      command  => @(SABC_CMD/L),
        dnf remove -y autofs
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        rpm -q autofs
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
}
