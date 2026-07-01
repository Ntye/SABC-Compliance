# == Class: sabc_compliance::services
#
# CIS Section 2 — Services. Ensures time synchronization is running, removes the
# legacy xinetd super-server, always removes insecure *clients* (telnet, rsh,
# talk, …), and — only when purge_insecure_servers is set — removes server
# packages CIS wants absent (a host may legitimately run one, so that is opt-in).
#
class sabc_compliance::services {
  include sabc_compliance::params

  # 2.1.1 Time synchronization daemon in use (chrony is the modern default).
  package { $sabc_compliance::params::chrony_package:
    ensure => installed,
  }
  service { $sabc_compliance::params::chrony_service:
    ensure  => running,
    enable  => true,
    require => Package[$sabc_compliance::params::chrony_package],
  }

  # 2.1.2 xinetd must not be installed.
  package { 'xinetd':
    ensure => purged,
  }

  # 2.3 Insecure/unneeded clients — always removed (never required on a host).
  package { $sabc_compliance::params::insecure_clients:
    ensure => purged,
  }

  # 2.2 Special-purpose SERVER packages — opt-in removal only.
  if $sabc_compliance::purge_insecure_servers {
    package { $sabc_compliance::params::insecure_servers:
      ensure => purged,
    }
  }
}
