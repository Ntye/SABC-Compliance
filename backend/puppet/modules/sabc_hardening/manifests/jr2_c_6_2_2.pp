# JR2.C.6.2.2 (CIS Level 1) — Ensure /etc/shadow password fields are not empty.
# Generated from the SABC referential. Enforcement is the family's own
# Configure procedure, run only when the Validate procedure fails.
class sabc_hardening::jr2_c_6_2_2 {
  if $facts['os']['family'] == 'Debian' {
    exec { 'sabc_jr2_c_6_2_2_debian':
      command  => @(SABC_CMD/L),
        passwd -l <username>
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        awk -F: '($2 == "" ) { print $1 " does not have a password "}' /etc/shadow
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
  if $facts['os']['family'] == 'RedHat' {
    exec { 'sabc_jr2_c_6_2_2_redhat':
      command  => @(SABC_CMD/L),
        passwd -l <username>
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        awk -F: '($2 == "" ) { print $1 " does not have a password "}' /etc/shadow
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
}
