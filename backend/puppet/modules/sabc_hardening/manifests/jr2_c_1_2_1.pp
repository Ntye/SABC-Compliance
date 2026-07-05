# JR2.C.1.2.1 (CIS Level 1) — Ensure AIDE is installed.
# Generated from the SABC referential. Enforcement is the family's own
# Configure procedure, run only when the Validate procedure fails.
class sabc_hardening::jr2_c_1_2_1 {
  if $facts['os']['family'] == 'Debian' {
    exec { 'sabc_jr2_c_1_2_1_debian':
      command  => @(SABC_CMD/L),
        apt install aide aide-common
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        dpkg-query -W -f='${binary:Package}\t${Status}\t${db:Status-Status}\n' aide aide-common
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
  if $facts['os']['family'] == 'RedHat' {
    exec { 'sabc_jr2_c_1_2_1_redhat':
      command  => @(SABC_CMD/L),
        dnf install -y aide aide-common
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        rpm -q aide aide-common
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
}
