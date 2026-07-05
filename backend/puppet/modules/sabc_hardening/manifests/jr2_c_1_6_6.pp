# JR2.C.1.6.6 (CIS Level 1) — Ensure permissions on /etc/issue.net are configured.
# Generated from the SABC referential. Enforcement is the family's own
# Configure procedure, run only when the Validate procedure fails.
class sabc_hardening::jr2_c_1_6_6 {
  if $facts['os']['family'] == 'Debian' {
    exec { 'sabc_jr2_c_1_6_6_debian':
      command  => @(SABC_CMD/L),
        chown root:root $(readlink -e /etc/issue.net)
        chmod u-x,go-wx $(readlink -e /etc/issue.net)
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        stat -Lc 'Access: (%#a/%A) Uid: ( %u/ %U) Gid: { %g/ %G)' /etc/issue.net
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
  if $facts['os']['family'] == 'RedHat' {
    exec { 'sabc_jr2_c_1_6_6_redhat':
      command  => @(SABC_CMD/L),
        chown root:root $(readlink -e /etc/issue.net)
        chmod u-x,go-wx $(readlink -e /etc/issue.net)
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        stat -Lc 'Access: (%#a/%A) Uid: ( %u/ %U) Gid: { %g/ %G)' /etc/issue.net
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
}
