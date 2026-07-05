# JR2.C.2.1.3.1 (CIS Level 1) — Ensure systemd-timesyncd configured with authorized timeserver.
# Generated from the SABC referential. Enforcement is the family's own
# Configure procedure, run only when the Validate procedure fails.
class sabc_hardening::jr2_c_2_1_3_1 {
  if $facts['os']['family'] == 'Debian' {
    exec { 'sabc_jr2_c_2_1_3_1_debian':
      command  => @(SABC_CMD/L),
        [Time]
        NTP=time.nist.gov # Uses the generic name for NIST's time servers 
        -AND/OR-
        FallbackNTP=time-a-g.nist.gov time-b-g.nist.gov time-c-g.nist.gov # Space separated list of NIST time servers
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        grep -Ph '^\h*(NTP|FallbackNTP)=\H+' /etc/systemd/timesyncd.conf
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
  if $facts['os']['family'] == 'RedHat' {
    exec { 'sabc_jr2_c_2_1_3_1_redhat':
      command  => @(SABC_CMD/L),
        [Time]
        NTP=time.nist.gov # Uses the generic name for NIST's time servers 
        -AND/OR-
        FallbackNTP=time-a-g.nist.gov time-b-g.nist.gov time-c-g.nist.gov # Space separated list of NIST time servers
      | SABC_CMD
      provider => 'shell',
      path     => ['/usr/sbin', '/usr/bin', '/sbin', '/bin'],
    unless   => @(SABC_CHK/L),
        grep -Ph '^\h*(NTP|FallbackNTP)=\H+' /etc/systemd/timesyncd.conf
    | SABC_CHK
      logoutput => 'on_failure',
    }
  }
}
