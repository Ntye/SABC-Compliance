# JR2.C.1.4.4 (CIS Level 1) — Ensure Automatic Error Reporting is not enabled.
# Generated from the SABC referential. Enforcement is the family's own
# Configure procedure, run only when the Validate procedure fails.
class sabc_hardening::jr2_c_1_4_4 {
  if $facts['os']['family'] == 'Debian' {
    exec { 'sabc_jr2_c_1_4_4_debian':
      command  => @(SABC_CMD/L),
        enabled=0
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        dpkg-query -s apport > /dev/null 2>&1 && grep -Psi -- '^\h*enabled\h*=\h*[^0]\b' /etc/default/apport
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
  if $facts['os']['family'] == 'RedHat' {
    exec { 'sabc_jr2_c_1_4_4_redhat':
      command  => @(SABC_CMD/L),
        enabled=0
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        dpkg-query -s apport > /dev/null 2>&1 && grep -Psi -- '^\h*enabled\h*=\h*[^0]\b' /etc/default/apport
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
}
