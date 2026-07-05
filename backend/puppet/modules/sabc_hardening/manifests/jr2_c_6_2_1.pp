# JR2.C.6.2.1 (CIS Level 1) — Ensure accounts in /etc/passwd use shadowed passwords.
# Generated from the SABC referential. Enforcement is the family's own
# Configure procedure, run only when the Validate procedure fails.
class sabc_hardening::jr2_c_6_2_1 {
  if $facts['os']['family'] == 'Debian' {
    exec { 'sabc_jr2_c_6_2_1_debian':
      command  => @(SABC_CMD/L),
        sed -e 's/^\([a-zA-Z0-9_]*\):[^:]*:/\1:x:/' -i /etc/passwd
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        awk -F: '($2 != "x" ) { print $1 " is not set to shadowed passwords "}' /etc/passwd
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
  if $facts['os']['family'] == 'RedHat' {
    exec { 'sabc_jr2_c_6_2_1_redhat':
      command  => @(SABC_CMD/L),
        sed -e 's/^\([a-zA-Z0-9_]*\):[^:]*:/\1:x:/' -i /etc/passwd
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        awk -F: '($2 != "x" ) { print $1 " is not set to shadowed passwords "}' /etc/passwd
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
}
