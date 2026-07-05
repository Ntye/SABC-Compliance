# JR2.C.4.3.2 (CIS Level 1) — Ensure sudo commands use pty.
# Generated from the SABC referential. Enforcement is the family's own
# Configure procedure, run only when the Validate procedure fails.
class sabc_hardening::jr2_c_4_3_2 {
  if $facts['os']['family'] == 'Debian' {
    exec { 'sabc_jr2_c_4_3_2_debian':
      command  => @(SABC_CMD/L),
        Defaults use_pty
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        grep -rPi '^\h*Defaults\h+([^#\n\r]+,)?use_pty(,\h*\h+\h*)*\h*(#.*)?$' /etc/sudoers*
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
  if $facts['os']['family'] == 'RedHat' {
    exec { 'sabc_jr2_c_4_3_2_redhat':
      command  => @(SABC_CMD/L),
        Defaults use_pty
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        grep -rPi '^\h*Defaults\h+([^#\n\r]+,)?use_pty(,\h*\h+\h*)*\h*(#.*)?$' /etc/sudoers*
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
}
