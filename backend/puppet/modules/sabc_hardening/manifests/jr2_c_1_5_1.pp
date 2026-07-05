# JR2.C.1.5.1 (CIS Level 1) — Ensure AppArmor is installed.
# Generated from the SABC referential. Enforcement is the family's own
# Configure procedure, run only when the Validate procedure fails.
class sabc_hardening::jr2_c_1_5_1 {
  if $facts['os']['family'] == 'Debian' {
    exec { 'sabc_jr2_c_1_5_1_debian':
      command  => @(SABC_CMD/L),
        apt install apparmor apparmor-utils
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        dpkg-query -W -f='${binary:Package}\t${Status}\t${db:Status-Status}\n' apparmor apparmor-utils
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
  if $facts['os']['family'] == 'RedHat' {
    exec { 'sabc_jr2_c_1_5_1_redhat':
      command  => @(SABC_CMD/L),
        dnf install -y libselinux selinux-policy-targeted policycoreutils
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        rpm -q libselinux selinux-policy-targeted
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
}
