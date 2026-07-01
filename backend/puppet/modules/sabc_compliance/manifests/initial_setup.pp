# == Class: sabc_compliance::initial_setup
#
# CIS Section 1 — Initial Setup. Enforces the deterministic, safe controls:
# process hardening (sysctl), kernel-module blacklisting, AIDE, prelink removal,
# bootloader permissions and warning banners.
#
# Detective-only controls (separate partitions, sticky bit, world-writable dirs)
# are intentionally NOT auto-remediated — repartitioning a live host or blanket
# chmod-ing arbitrary directories is riskier than the finding. They remain
# visible in the scan report.
#
class sabc_compliance::initial_setup {
  include sabc_compliance::params

  # 1.5.1 ASLR, 1.5.2 ptrace scope, 1.5.3 SUID core dumps.
  sabc_compliance::sysctl { '60-sabc-cis-initial':
    settings => {
      'kernel.randomize_va_space' => 2,
      'kernel.yama.ptrace_scope'  => 1,
      'fs.suid_dumpable'          => 0,
    },
  }

  # 1.5.4 prelink must not be installed (it alters binaries and breaks AIDE).
  package { 'prelink':
    ensure => purged,
  }

  # 1.1.1 Disable unused filesystem kernel modules.
  if $sabc_compliance::manage_kernel_modules {
    sabc_compliance::kmod { $sabc_compliance::params::fs_modules: }
  }

  # 1.3.1 File-integrity checking tool (AIDE).
  if $sabc_compliance::manage_aide {
    package { $sabc_compliance::params::aide_package:
      ensure => installed,
    }
  }

  # 1.4.1 Bootloader config permissions (owner root, not readable by others).
  # Path differs between grub2 (RedHat) and grub (Debian); chmod whichever exists
  # without managing its content.
  ['/boot/grub2/grub.cfg', '/boot/grub/grub.cfg'].each |$grub| {
    exec { "sabc-grub-perms-${grub}":
      command => "chown root:root ${grub} && chmod og-rwx ${grub}",
      path    => ['/usr/bin', '/bin'],
      onlyif  => "test -f ${grub}",
    }
  }

  # 1.7.1 / 1.7.2 Warning banners must not leak OS/version via escape sequences.
  file { '/etc/motd':
    ensure  => file,
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    content => "Authorized access only. All activity may be monitored and reported.\n",
  }

  file { '/etc/issue':
    ensure  => file,
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    content => "Authorized access only. All activity may be monitored and reported.\n",
  }
}
