# JR2.C.4.3.3 (CIS Level 1) — Ensure sudo log file exists.
# Generated from the SABC referential. Enforcement is the family's own
# Configure procedure, run only when the Validate procedure fails.
class sabc_hardening::jr2_c_4_3_3 {
  if $facts['os']['family'] == 'Debian' {
    exec { 'sabc_jr2_c_4_3_3_debian':
      command  => @(SABC_CMD/L),
        Defaults logfile="/var/log/sudo.log"
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        grep -rPsi "^\h*Defaults\h+([^#]+,\h*)?logfile\h*=\h*(\"|\')?\H+(\"|\')?(,\h*\H+\h*)*\h*(#.*)?$" /etc/sudoers*
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
  if $facts['os']['family'] == 'RedHat' {
    exec { 'sabc_jr2_c_4_3_3_redhat':
      command  => @(SABC_CMD/L),
        Defaults logfile="/var/log/sudo.log"
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        grep -rPsi "^\h*Defaults\h+([^#]+,\h*)?logfile\h*=\h*(\"|\')?\H+(\"|\')?(,\h*\H+\h*)*\h*(#.*)?$" /etc/sudoers*
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
}
