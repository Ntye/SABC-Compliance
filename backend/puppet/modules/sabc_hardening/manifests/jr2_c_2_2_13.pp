# JR2.C.2.2.13 (CIS Level 1) — Ensure NIS Server is not installed.
# Generated from the SABC referential. Enforcement is the family's own
# Configure procedure, run only when the Validate procedure fails.
class sabc_hardening::jr2_c_2_2_13 {
  if $facts['os']['family'] == 'Debian' {
    exec { 'sabc_jr2_c_2_2_13_debian':
      command  => @(SABC_CMD/L),
        apt purge nis
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        dpkg-query -W -f='${binary:Package}\t${Status}\t${db:Status-Status}\n' nis
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
  if $facts['os']['family'] == 'RedHat' {
    exec { 'sabc_jr2_c_2_2_13_redhat':
      command  => @(SABC_CMD/L),
        dnf remove -y nis
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        rpm -q nis
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
}
