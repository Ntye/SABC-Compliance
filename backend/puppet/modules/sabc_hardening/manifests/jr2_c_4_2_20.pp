# JR2.C.4.2.20 (CIS Level 1) — Ensure SSH Idle Timeout Interval is configured.
# Generated from the SABC referential. Enforcement is the family's own
# Configure procedure, run only when the Validate procedure fails.
class sabc_hardening::jr2_c_4_2_20 {
  if $facts['os']['family'] == 'Debian' {
    exec { 'sabc_jr2_c_4_2_20_debian':
      command  => @(SABC_CMD/L),
        ClientAliveInterval 15
        ClientAliveCountMax 3
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        sshd -T -C user=root -C host="$(hostname)" -C addr="$(grep $(hostname) /etc/hosts | awk '{print $1}')" | grep clientaliveinterval
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
  if $facts['os']['family'] == 'RedHat' {
    exec { 'sabc_jr2_c_4_2_20_redhat':
      command  => @(SABC_CMD/L),
        ClientAliveInterval 15
        ClientAliveCountMax 3
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        sshd -T -C user=root -C host="$(hostname)" -C addr="$(grep $(hostname) /etc/hosts | awk '{print $1}')" | grep clientaliveinterval
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
}
