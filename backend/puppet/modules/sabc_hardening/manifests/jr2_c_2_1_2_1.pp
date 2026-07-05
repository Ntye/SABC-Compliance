# JR2.C.2.1.2.1 (CIS Level 1) — Ensure chrony is running as user _chrony.
# Generated from the SABC referential. Enforcement is the family's own
# Configure procedure, run only when the Validate procedure fails.
class sabc_hardening::jr2_c_2_1_2_1 {
  if $facts['os']['family'] == 'Debian' {
    exec { 'sabc_jr2_c_2_1_2_1_debian':
      command  => @(SABC_CMD/L),
        user _chrony
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        ps -ef | awk '(/[c]hronyd/ && $1!="_chrony") { print $1 }'
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
  if $facts['os']['family'] == 'RedHat' {
    exec { 'sabc_jr2_c_2_1_2_1_redhat':
      command  => @(SABC_CMD/L),
        user _chrony
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        ps -ef | awk '(/[c]hronyd/ && $1!="_chrony") { print $1 }'
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
}
