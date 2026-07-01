# == Class: sabc_compliance::network
#
# CIS Section 3 — Network Configuration. Network-stack sysctl hardening,
# blacklisting of uncommon protocol modules, and (opt-out) a host firewall that
# is ALWAYS configured to allow the SSH port before it is enabled — so turning
# on a default-deny firewall can never lock the platform out of the node.
#
class sabc_compliance::network {
  include sabc_compliance::params

  # 3.1 / 3.2 Network kernel parameters.
  sabc_compliance::sysctl { '61-sabc-cis-network':
    settings => {
      'net.ipv4.ip_forward'                        => 0,
      'net.ipv4.conf.all.send_redirects'           => 0,
      'net.ipv4.conf.default.send_redirects'       => 0,
      'net.ipv4.conf.all.accept_source_route'      => 0,
      'net.ipv4.conf.default.accept_source_route'  => 0,
      'net.ipv4.conf.all.accept_redirects'         => 0,
      'net.ipv4.conf.default.accept_redirects'     => 0,
      'net.ipv4.conf.all.secure_redirects'         => 0,
      'net.ipv4.conf.all.log_martians'             => 1,
      'net.ipv4.conf.default.log_martians'         => 1,
      'net.ipv4.icmp_echo_ignore_broadcasts'       => 1,
      'net.ipv4.icmp_ignore_bogus_error_responses' => 1,
      'net.ipv4.conf.all.rp_filter'                => 1,
      'net.ipv4.tcp_syncookies'                    => 1,
      'net.ipv6.conf.all.accept_ra'                => 0,
      'net.ipv6.conf.all.accept_redirects'         => 0,
    },
  }

  # 3.3 Uncommon network protocols disabled.
  if $sabc_compliance::manage_kernel_modules {
    sabc_compliance::kmod { $sabc_compliance::params::net_modules: }
  }

  # 3.5 Host firewall — install + active, SSH allowed first.
  if $sabc_compliance::manage_firewall {
    $port = $sabc_compliance::ssh_port

    package { $sabc_compliance::params::firewall_package:
      ensure => installed,
    }

    if $facts['os']['family'] == 'Debian' {
      # ufw: allow SSH, THEN enable. `ufw --force enable` also starts+enables it.
      # The `test -x` guard on the absolute binary path means a host without ufw
      # (or a noop run before the package installs) skips cleanly, never fails.
      exec { 'sabc-ufw-allow-ssh':
        command  => "/usr/sbin/ufw allow ${port}/tcp",
        onlyif   => 'test -x /usr/sbin/ufw',
        unless   => "/usr/sbin/ufw status verbose 2>/dev/null | grep -Eq '(^|[[:space:]])${port}/tcp'",
        provider => 'shell',
        require  => Package[$sabc_compliance::params::firewall_package],
      }
      exec { 'sabc-ufw-enable':
        command  => '/usr/sbin/ufw --force enable',
        onlyif   => 'test -x /usr/sbin/ufw',
        unless   => '/usr/sbin/ufw status 2>/dev/null | grep -qw active',
        provider => 'shell',
        require  => Exec['sabc-ufw-allow-ssh'],
      }
    } else {
      # firewalld: ensure running, then allow SSH permanently and reload.
      service { $sabc_compliance::params::firewall_service:
        ensure  => running,
        enable  => true,
        require => Package[$sabc_compliance::params::firewall_package],
      }
      exec { 'sabc-firewalld-allow-ssh':
        command  => "/usr/bin/firewall-cmd --permanent --add-service=ssh; /usr/bin/firewall-cmd --permanent --add-port=${port}/tcp; /usr/bin/firewall-cmd --reload",
        onlyif   => 'test -x /usr/bin/firewall-cmd',
        unless   => "/usr/bin/firewall-cmd --query-port=${port}/tcp",
        provider => 'shell',
        require  => Service[$sabc_compliance::params::firewall_service],
      }
    }
  }
}
