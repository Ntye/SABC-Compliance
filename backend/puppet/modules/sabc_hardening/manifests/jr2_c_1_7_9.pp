# JR2.C.1.7.9 (CIS Level 1) — Ensure XDCMP is not enabled.
# Generated from the SABC referential. Enforcement is the family's own
# Configure procedure, run only when the Validate procedure fails.
class sabc_hardening::jr2_c_1_7_9 {
  if $facts['os']['family'] == 'Debian' {
    exec { 'sabc_jr2_c_1_7_9_debian':
      command  => @(SABC_CMD/L),
        Enable=true
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        grep -Eis '^\s*Enable\s*=\s*true' /etc/gdm3/custom.conf
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
  if $facts['os']['family'] == 'RedHat' {
    exec { 'sabc_jr2_c_1_7_9_redhat':
      command  => @(SABC_CMD/L),
        Enable=true
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        grep -Eis '^\s*Enable\s*=\s*true' /etc/gdm3/custom.conf
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
}
