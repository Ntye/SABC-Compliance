# JR2.C.1.5.3 (CIS Level 1) — Ensure all AppArmor Profiles are in enforce or complain mode.
# Generated from the SABC referential. Enforcement is the family's own
# Configure procedure, run only when the Validate procedure fails.
class sabc_hardening::jr2_c_1_5_3 {
  if $facts['os']['family'] == 'Debian' {
    exec { 'sabc_jr2_c_1_5_3_debian':
      command  => @(SABC_CMD/L),
        aa-enforce /etc/apparmor.d/*
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        apparmor_status | grep profiles
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
  if $facts['os']['family'] == 'RedHat' {
    exec { 'sabc_jr2_c_1_5_3_redhat':
      command  => @(SABC_CMD/L),
        setenforce 1
        sed -ri 's/^SELINUX=.*/SELINUX=enforcing/' /etc/selinux/config
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        getenforce
        grep -Pi '^\h*SELINUX=enforcing' /etc/selinux/config
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
}
