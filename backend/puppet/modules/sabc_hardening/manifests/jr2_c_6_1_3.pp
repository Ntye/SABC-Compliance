# JR2.C.6.1.3 (CIS Level 1) — Ensure permissions on /etc/group are configured.
# Generated from the SABC referential. Enforcement is the family's own
# Configure procedure, run only when the Validate procedure fails.
class sabc_hardening::jr2_c_6_1_3 {
  if $facts['os']['family'] == 'Debian' {
    exec { 'sabc_jr2_c_6_1_3_debian':
      command  => @(SABC_CMD/L),
        chmod u-x,go-wx /etc/group
        chown root:root /etc/group
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        stat -Lc "%n %a %u/%U %g/%G" /etc/group
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
  if $facts['os']['family'] == 'RedHat' {
    exec { 'sabc_jr2_c_6_1_3_redhat':
      command  => @(SABC_CMD/L),
        chmod u-x,go-wx /etc/group
        chown root:root /etc/group
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        stat -Lc "%n %a %u/%U %g/%G" /etc/group
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
}
