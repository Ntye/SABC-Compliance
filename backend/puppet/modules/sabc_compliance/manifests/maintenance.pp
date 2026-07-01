# == Class: sabc_compliance::maintenance
#
# CIS Section 6 — System Maintenance. Enforces the deterministic system-file
# permissions (passwd/shadow/group and their backups).
#
# Detective-only controls (world-writable files, unowned files, duplicate
# UIDs/GIDs, empty passwords, extra UID-0 accounts) are intentionally NOT
# auto-remediated: blindly chmod-ing arbitrary files, deleting accounts or
# blanking UIDs on a live host is far more dangerous than the finding, which
# stays visible in the scan report for an operator to action deliberately.
#
class sabc_compliance::maintenance {

  # 6.1.2–6.1.9 Permissions on the account databases and their backups.
  $perms = {
    '/etc/passwd'   => '0644',
    '/etc/passwd-'  => '0644',
    '/etc/group'    => '0644',
    '/etc/group-'   => '0644',
    '/etc/shadow'   => '0640',
    '/etc/shadow-'  => '0640',
    '/etc/gshadow'  => '0640',
    '/etc/gshadow-' => '0640',
  }

  # shadow/gshadow are root:shadow on Debian, root:root on RedHat. Owner is root
  # everywhere and the mode is what the control checks, so manage owner+mode and
  # leave group to the OS default by not forcing it.
  $perms.each |$path, $mode| {
    exec { "sabc-perms-${path}":
      command => "chown root ${path} && chmod ${mode} ${path}",
      path    => ['/usr/bin', '/bin'],
      onlyif  => "test -e ${path}",
      unless  => "[ \"\$(stat -c '%U %a' ${path})\" = \"root ${mode.regsubst('^0', '')}\" ]",
      provider => 'shell',
    }
  }
}
