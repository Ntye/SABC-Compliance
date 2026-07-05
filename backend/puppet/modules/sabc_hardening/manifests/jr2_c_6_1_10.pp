# JR2.C.6.1.10 (CIS Level 1) — Ensure permissions on /etc/opasswd are configured.
# Generated from the SABC referential. Enforcement is the family's own
# Configure procedure, run only when the Validate procedure fails.
class sabc_hardening::jr2_c_6_1_10 {
  if $facts['os']['family'] == 'Debian' {
    exec { 'sabc_jr2_c_6_1_10_debian':
      command  => @(SABC_CMD/L),
        [ -e "/etc/security/opasswd" ] && chmod u-x,go-rwx /etc/security/opasswd
        [ -e "/etc/security/opasswd" ] && chown root:root /etc/security/opasswd
        [ -e "/etc/security/opasswd.old" ] && chmod u-x,go-rwx /etc/security/opasswd.old
        [ -e "/etc/security/opasswd.old" ] && chown root:root /etc/security/opasswd.old
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        [ -e "/etc/security/opasswd" ] && stat -Lc "%n %a %u/%U %g/%G" /etc/security/opasswd
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
  if $facts['os']['family'] == 'RedHat' {
    exec { 'sabc_jr2_c_6_1_10_redhat':
      command  => @(SABC_CMD/L),
        [ -e "/etc/security/opasswd" ] && chmod u-x,go-rwx /etc/security/opasswd
        [ -e "/etc/security/opasswd" ] && chown root:root /etc/security/opasswd
        [ -e "/etc/security/opasswd.old" ] && chmod u-x,go-rwx /etc/security/opasswd.old
        [ -e "/etc/security/opasswd.old" ] && chown root:root /etc/security/opasswd.old
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        [ -e "/etc/security/opasswd" ] && stat -Lc "%n %a %u/%U %g/%G" /etc/security/opasswd
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
}
