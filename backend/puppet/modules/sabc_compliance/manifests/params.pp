# == Class: sabc_compliance::params
#
# OS-family-aware defaults. Package and service names differ between the Debian
# and RedHat families, so every other class reads its names from here rather
# than branching on $facts['os']['family'] in a dozen places.
#
class sabc_compliance::params {

  case $facts['os']['family'] {
    'Debian': {
      $sshd_service      = 'ssh'
      $cron_service      = 'cron'
      $chrony_package    = 'chrony'
      $chrony_service    = 'chrony'
      $auditd_package    = 'auditd'
      $firewall_package  = 'ufw'
      $firewall_service  = 'ufw'
      $aide_package      = 'aide'
      $pwquality_package = 'libpam-pwquality'
      # Insecure client packages as named on Debian/Ubuntu.
      $insecure_clients  = ['telnet', 'rsh-client', 'talk', 'ldap-utils', 'nis', 'tftp']
      # Server packages CIS wants absent (only removed when purge_insecure_servers).
      # xinetd is handled by its own always-on resource, so it is NOT listed here.
      $insecure_servers  = ['telnetd', 'vsftpd', 'tftpd-hpa', 'rsh-server']
    }
    'RedHat': {
      $sshd_service      = 'sshd'
      $cron_service      = 'crond'
      $chrony_package    = 'chrony'
      $chrony_service    = 'chronyd'
      $auditd_package    = 'audit'
      $firewall_package  = 'firewalld'
      $firewall_service  = 'firewalld'
      $aide_package      = 'aide'
      $pwquality_package = 'libpwquality'
      $insecure_clients  = ['telnet', 'rsh', 'talk', 'openldap-clients', 'ypbind', 'tftp']
      $insecure_servers  = ['telnet-server', 'vsftpd', 'tftp-server', 'rsh-server']
    }
    default: {
      # Sensible fallbacks; the classes still converge on unknown families.
      $sshd_service      = 'sshd'
      $cron_service      = 'crond'
      $chrony_package    = 'chrony'
      $chrony_service    = 'chronyd'
      $auditd_package    = 'auditd'
      $firewall_package  = 'firewalld'
      $firewall_service  = 'firewalld'
      $aide_package      = 'aide'
      $pwquality_package = 'libpwquality'
      $insecure_clients  = ['telnet']
      $insecure_servers  = ['xinetd']
    }
  }

  # Kernel filesystem modules to blacklist (CIS 1.1.1). squashfs backs snapd on
  # Ubuntu, so exclude it there to avoid breaking snaps; keep it elsewhere.
  $fs_modules_base = ['cramfs', 'freevxfs', 'jffs2', 'hfs', 'hfsplus', 'udf', 'usb-storage']
  if $facts['os']['name'] == 'Ubuntu' {
    $fs_modules = $fs_modules_base
  } else {
    $fs_modules = $fs_modules_base + ['squashfs']
  }

  # Uncommon network protocol modules to blacklist (CIS 3.3).
  $net_modules = ['dccp', 'sctp', 'rds', 'tipc']
}
