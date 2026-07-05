# JR2.C.2.1.4.2 (CIS Level 1) — Ensure ntp is running as user ntp.
# Generated from the SABC referential. Enforcement is the family's own
# Configure procedure, run only when the Validate procedure fails.
class sabc_hardening::jr2_c_2_1_4_2 {
  if $facts['os']['family'] == 'Debian' {
    exec { 'sabc_jr2_c_2_1_4_2_debian':
      command  => @(SABC_CMD/L),
        RUNASUSER=ntp
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        ps -ef | awk '(/[n]tpd/ && $1!="ntp") { print $1 }'
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
  if $facts['os']['family'] == 'RedHat' {
    exec { 'sabc_jr2_c_2_1_4_2_redhat':
      command  => @(SABC_CMD/L),
        RUNASUSER=ntp
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        ps -ef | awk '(/[n]tpd/ && $1!="ntp") { print $1 }'
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
}
