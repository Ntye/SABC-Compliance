# == Class: sabc_compliance::access_auth
#
# CIS Section 5 — Access, Authentication and Authorization. cron hardening, a
# VALIDATED sshd hardening drop-in (self-heals if it would break sshd), password
# policy (login.defs / pwquality / faillock), and sudo NOPASSWD hygiene.
#
# SAFETY:
#   * sshd hardening never disables password auth and never touches host keys —
#     only the CIS directives that are safe under the platform's key-based
#     access. The drop-in is validated with `sshd -t`; if the combined config is
#     invalid the drop-in is removed and the run fails loudly, so a bad edit can
#     never survive to break the next sshd restart.
#   * The "ansible" automation account's passwordless sudo is an APPROVED
#     referential exception (sabc-5.3.5) and is NEVER modified. Only when
#     remove_other_nopasswd is explicitly true do we strip NOPASSWD from OTHER
#     accounts, and only after `visudo -c` validates the result.
#
class sabc_compliance::access_auth {
  include sabc_compliance::params

  $sshd_service    = $sabc_compliance::params::sshd_service
  $cron_service    = $sabc_compliance::params::cron_service
  $automation_user = $sabc_compliance::automation_user

  # ── 5.1 cron ───────────────────────────────────────────────────────────────
  service { $cron_service:
    ensure => running,
    enable => true,
  }

  # 5.1.2 /etc/crontab and 5.1.3–5.1.7 cron directories: root-owned, restricted.
  file { '/etc/crontab':
    ensure => file,
    owner  => 'root',
    group  => 'root',
    mode   => '0600',
  }
  ['/etc/cron.hourly', '/etc/cron.daily', '/etc/cron.weekly',
  '/etc/cron.monthly', '/etc/cron.d'].each |$dir| {
    file { $dir:
      ensure => directory,
      owner  => 'root',
      group  => 'root',
      mode   => '0700',
    }
  }

  # 5.1.8 Restrict cron to authorized users (cron.allow present, root allowed).
  file { '/etc/cron.allow':
    ensure  => file,
    owner   => 'root',
    group   => 'root',
    mode    => '0640',
    replace => false,           # don't clobber an operator-maintained allow list
    content => "root\n",
  }

  # ── 5.2 sshd ───────────────────────────────────────────────────────────────
  if $sabc_compliance::manage_sshd {
    # 5.2.1 sshd_config permissions (metadata only — content untouched).
    file { '/etc/ssh/sshd_config':
      ensure => file,
      owner  => 'root',
      group  => 'root',
      mode   => '0600',
    }

    file { '/etc/ssh/sshd_config.d':
      ensure => directory,
      owner  => 'root',
      group  => 'root',
      mode   => '0755',
    }

    # Ensure sshd actually includes the drop-in directory (older configs may not).
    exec { 'sabc-sshd-ensure-include':
      command => "sed -i '1i Include /etc/ssh/sshd_config.d/*.conf' /etc/ssh/sshd_config",
      path    => ['/usr/bin', '/bin'],
      onlyif  => "test -f /etc/ssh/sshd_config",
      unless  => "grep -Eq 'sshd_config.d/\\*.conf' /etc/ssh/sshd_config",
      require => File['/etc/ssh/sshd_config'],
    }

    # The hardening drop-in (5.2.4–5.2.22). Does NOT disable password auth.
    file { '/etc/ssh/sshd_config.d/60-sabc-cis.conf':
      ensure  => file,
      owner   => 'root',
      group   => 'root',
      mode    => '0600',
      content => @("SSHD"),
        # Managed by SABC Compliance (CIS Section 5.2). Do not edit.
        LogLevel VERBOSE
        X11Forwarding no
        MaxAuthTries 4
        IgnoreRhosts yes
        HostbasedAuthentication no
        PermitRootLogin no
        PermitEmptyPasswords no
        PermitUserEnvironment no
        Ciphers aes256-gcm@openssh.com,chacha20-poly1305@openssh.com,aes256-ctr,aes192-ctr,aes128-ctr
        MACs hmac-sha2-512-etm@openssh.com,hmac-sha2-256-etm@openssh.com,umac-128-etm@openssh.com
        ClientAliveInterval 300
        ClientAliveCountMax 3
        LoginGraceTime 60
        MaxStartups 10:30:60
        MaxSessions 10
        | SSHD
      require => [File['/etc/ssh/sshd_config.d'], Exec['sabc-sshd-ensure-include']],
      notify  => Exec['sabc-sshd-validate-reload'],
    }

    # Validate the COMBINED config, then reload. If invalid, remove our drop-in
    # and fail — never leave a config that would break the next sshd restart.
    exec { 'sabc-sshd-validate-reload':
      command     => "sshd -t && systemctl reload ${sshd_service} || { rm -f /etc/ssh/sshd_config.d/60-sabc-cis.conf; echo 'sabc: sshd config invalid, drop-in reverted' >&2; exit 1; }",
      path        => ['/usr/sbin', '/sbin', '/usr/bin', '/bin'],
      refreshonly => true,
      provider    => 'shell',
    }
  }

  # ── 5.3 PAM / password quality ──────────────────────────────────────────────
  if $sabc_compliance::manage_pam {
    # 5.3.1 Password creation requirements (minlen >= 14).
    package { $sabc_compliance::params::pwquality_package:
      ensure => installed,
    }
    file { '/etc/security/pwquality.conf':
      ensure  => present,
      owner   => 'root',
      group   => 'root',
      mode    => '0644',
      require => Package[$sabc_compliance::params::pwquality_package],
    }
    sabc_compliance::set_line { 'pwquality-minlen':
      path    => '/etc/security/pwquality.conf',
      key     => 'minlen',
      value   => String($sabc_compliance::pwquality_minlen),
      require => File['/etc/security/pwquality.conf'],
    }

    # 5.3.2 Account lockout on repeated failures (faillock deny <= 5).
    file { '/etc/security/faillock.conf':
      ensure => present,
      owner  => 'root',
      group  => 'root',
      mode   => '0644',
    }
    sabc_compliance::set_line { 'faillock-deny':
      path    => '/etc/security/faillock.conf',
      key     => 'deny',
      value   => '5',
      require => File['/etc/security/faillock.conf'],
    }

    # 5.3.4 Strong password hashing for NEW passwords (login.defs, safe — does
    # not touch the live PAM stack).
    sabc_compliance::set_line { 'login-defs-encrypt-method':
      path  => '/etc/login.defs',
      key   => 'ENCRYPT_METHOD',
      value => 'SHA512',
      sep   => ' ',
    }
  }

  # ── 5.4 User accounts and environment (login.defs) ──────────────────────────
  sabc_compliance::set_line { 'login-defs-pass-max-days':
    path  => '/etc/login.defs',
    key   => 'PASS_MAX_DAYS',
    value => String($sabc_compliance::pass_max_days),
    sep   => ' ',
  }
  sabc_compliance::set_line { 'login-defs-pass-min-days':
    path  => '/etc/login.defs',
    key   => 'PASS_MIN_DAYS',
    value => String($sabc_compliance::pass_min_days),
    sep   => ' ',
  }
  sabc_compliance::set_line { 'login-defs-pass-warn-age':
    path  => '/etc/login.defs',
    key   => 'PASS_WARN_AGE',
    value => String($sabc_compliance::pass_warn_age),
    sep   => ' ',
  }
  sabc_compliance::set_line { 'login-defs-umask':
    path  => '/etc/login.defs',
    key   => 'UMASK',
    value => $sabc_compliance::login_umask,
    sep   => ' ',
  }

  # ── 5.5 Restrict su to a trusted group (opt-in — PAM change) ─────────────────
  if $sabc_compliance::restrict_su {
    exec { 'sabc-su-pam-wheel':
      command => "sed -ri 's|^#\\s*(auth\\s+required\\s+pam_wheel.so.*)|\\1|' /etc/pam.d/su; grep -Eq '^auth[[:space:]]+required[[:space:]]+pam_wheel.so' /etc/pam.d/su || echo 'auth required pam_wheel.so use_uid' >> /etc/pam.d/su",
      path    => ['/usr/bin', '/bin'],
      onlyif  => 'test -f /etc/pam.d/su',
      unless  => "grep -Eq '^auth[[:space:]]+required[[:space:]]+pam_wheel.so' /etc/pam.d/su",
      provider => 'shell',
    }
  }

  # ── 5.3.5 sudo NOPASSWD hygiene (ansible account NEVER touched) ──────────────
  # Off by default. When enabled, comment out NOPASSWD user-specs in
  # /etc/sudoers.d/* whose first field is NOT the approved automation user, then
  # validate; if validation fails, restore the backups.
  if $sabc_compliance::remove_other_nopasswd {
    exec { 'sabc-strip-other-nopasswd':
      command  => "for f in /etc/sudoers.d/*; do [ -f \"\$f\" ] || continue; cp -a \"\$f\" \"\$f.sabcbak\"; sed -ri '/NOPASSWD/{/^[[:space:]]*#/!{/^[[:space:]]*${automation_user}[[:space:]]/!s/^/# sabc-disabled /}}' \"\$f\"; done; if visudo -c >/dev/null 2>&1; then rm -f /etc/sudoers.d/*.sabcbak; else for b in /etc/sudoers.d/*.sabcbak; do [ -f \"\$b\" ] && mv \"\$b\" \"\${b%.sabcbak}\"; done; echo 'sabc: sudoers invalid after NOPASSWD strip, reverted' >&2; exit 1; fi",
      path     => ['/usr/sbin', '/sbin', '/usr/bin', '/bin'],
      onlyif   => "grep -rlE 'NOPASSWD' /etc/sudoers.d/ 2>/dev/null | grep -q .",
      unless   => "test -z \"\$(grep -rhE 'NOPASSWD' /etc/sudoers.d/ 2>/dev/null | grep -vE '^[[:space:]]*#' | grep -vE '^[[:space:]]*${automation_user}[[:space:]]')\"",
      provider => 'shell',
    }
  }
}
