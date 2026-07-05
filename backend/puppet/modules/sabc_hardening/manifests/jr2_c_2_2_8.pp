# JR2.C.2.2.8 (CIS Level 1) — Ensure HTTP server is not installed.
# Generated from the SABC referential. Enforcement is the family's own
# Configure procedure, run only when the Validate procedure fails.
class sabc_hardening::jr2_c_2_2_8 {
  if $facts['os']['family'] == 'Debian' {
    exec { 'sabc_jr2_c_2_2_8_debian':
      command  => @(SABC_CMD/L),
        apt purge apache2
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        dpkg-query -W -f='${binary:Package}\t${Status}\t${db:Status-Status}\n' apache2
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
  if $facts['os']['family'] == 'RedHat' {
    exec { 'sabc_jr2_c_2_2_8_redhat':
      command  => @(SABC_CMD/L),
        dnf remove -y apache2
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        rpm -q apache2
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
}
