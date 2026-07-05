# JR2.C.2.2.1 (CIS Level 1) — Ensure Avahi Server is not installed.
# Generated from the SABC referential. Enforcement is the family's own
# Configure procedure, run only when the Validate procedure fails.
class sabc_hardening::jr2_c_2_2_1 {
  if $facts['os']['family'] == 'Debian' {
    exec { 'sabc_jr2_c_2_2_1_debian':
      command  => @(SABC_CMD/L),
        systemctl stop avahi-daaemon.service
        systemctl stop avahi-daemon.socket
        apt purge avahi-daemon
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        dpkg-query -W -f='${binary:Package}\t${Status}\t${db:Status-Status}\n' avahi-daemon
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
  if $facts['os']['family'] == 'RedHat' {
    exec { 'sabc_jr2_c_2_2_1_redhat':
      command  => @(SABC_CMD/L),
        systemctl stop avahi-daaemon.service
        systemctl stop avahi-daemon.socket
        dnf remove -y avahi-daemon
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        rpm -q avahi-daemon
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
}
