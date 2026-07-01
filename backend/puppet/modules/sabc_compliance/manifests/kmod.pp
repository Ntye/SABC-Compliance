# == Define: sabc_compliance::kmod
#
# Disables a kernel module (CIS 1.1.1 filesystem modules, 3.3 network protocols)
# by writing a modprobe drop-in that neutralises loading, and best-effort
# unloading it if currently loaded. Dependency-free.
#
define sabc_compliance::kmod (
  String $module = $title,
) {
  file { "/etc/modprobe.d/sabc-cis-${module}.conf":
    ensure  => file,
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    content => "# Managed by SABC Compliance (CIS). Disable ${module}.\ninstall ${module} /bin/true\nblacklist ${module}\n",
  }

  # Unload if loaded. returns [0,1] so a module that is in use (rc 1) does not
  # fail the whole Puppet run — the drop-in still prevents future loads.
  # provider => shell so a system without lsmod/modprobe (rare) makes the guard
  # return non-zero and simply skips, rather than failing the whole Puppet run.
  exec { "sabc-rmmod-${module}":
    command  => "modprobe -r ${module}",
    path     => ['/usr/sbin', '/sbin', '/usr/bin', '/bin'],
    onlyif   => "lsmod 2>/dev/null | grep -qw ${module}",
    returns  => [0, 1],
    provider => 'shell',
    require  => File["/etc/modprobe.d/sabc-cis-${module}.conf"],
  }
}
