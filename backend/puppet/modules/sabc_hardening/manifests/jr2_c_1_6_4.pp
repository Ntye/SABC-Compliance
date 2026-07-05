# JR2.C.1.6.4 (CIS Level 1) — Ensure permissions on /etc/motd are configured.
# Generated from the SABC referential. Enforcement is the family's own
# Configure procedure, run only when the Validate procedure fails.
class sabc_hardening::jr2_c_1_6_4 {
  if $facts['os']['family'] == 'Debian' {
    exec { 'sabc_jr2_c_1_6_4_debian':
      command  => @(SABC_CMD/L),
        chown root:root $(readlink -e /etc/motd)
        chmod u-x,go-wx $(readlink -e /etc/motd)
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        [ -e /etc/motd ] && stat -Lc 'Access: (%#a/%A) Uid: ( %u/ %U) Gid: { %g/ %G)' /etc/motd
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
  if $facts['os']['family'] == 'RedHat' {
    exec { 'sabc_jr2_c_1_6_4_redhat':
      command  => @(SABC_CMD/L),
        chown root:root $(readlink -e /etc/motd)
        chmod u-x,go-wx $(readlink -e /etc/motd)
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        [ -e /etc/motd ] && stat -Lc 'Access: (%#a/%A) Uid: ( %u/ %U) Gid: { %g/ %G)' /etc/motd
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
}
