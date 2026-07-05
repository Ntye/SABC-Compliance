# JR2.C.5.1.2.1 (CIS Level 1) — Ensure rsyslog is installed.
# Generated from the SABC referential. Enforcement is the family's own
# Configure procedure, run only when the Validate procedure fails.
class sabc_hardening::jr2_c_5_1_2_1 {
  if $facts['os']['family'] == 'Debian' {
    exec { 'sabc_jr2_c_5_1_2_1_debian':
      command  => @(SABC_CMD/L),
        apt install rsyslog
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        dpkg-query -W -f='${binary:Package}\t${Status}\t${db:Status-Status}\n' rsyslog
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
  if $facts['os']['family'] == 'RedHat' {
    exec { 'sabc_jr2_c_5_1_2_1_redhat':
      command  => @(SABC_CMD/L),
        dnf install -y rsyslog
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        rpm -q rsyslog
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
}
