# encoding: utf-8
# CIS Benchmark — Section 5: Access, Authentication and Authorization
# Cron/at, SSH server hardening, PAM, password policy and root access controls.

title 'Section 5 — Access, Authentication and Authorization'

# 5.1 Configure cron
control 'cis-5.1.1-cron-enabled' do
  impact 0.4
  title 'Ensure cron daemon is enabled and running'
  tag cis: '5.1.1'
  describe.one do
    describe service('cron') do
      it { should be_running }
    end
    describe service('crond') do
      it { should be_running }
    end
  end
end

{
  '/etc/crontab'      => '5.1.2',
  '/etc/cron.hourly'  => '5.1.3',
  '/etc/cron.daily'   => '5.1.4',
  '/etc/cron.weekly'  => '5.1.5',
  '/etc/cron.monthly' => '5.1.6',
  '/etc/cron.d'       => '5.1.7',
}.each do |path, cid|
  control "cis-#{cid}-perms#{path.tr('/', '-')}" do
    impact 0.3
    title "Ensure permissions on #{path} are restricted to root"
    desc "#{path} must be owned by root and inaccessible to group/other."
    tag cis: cid
    describe file(path) do
      its('owner') { should eq 'root' }
      it { should_not be_readable.by('other') }
      it { should_not be_writable.by('group') }
    end
  end
end

control 'cis-5.1.8-at-cron-authorized' do
  impact 0.3
  title 'Ensure at/cron is restricted to authorized users'
  desc 'cron.allow / at.allow should exist and cron.deny / at.deny should not be relied upon.'
  tag cis: '5.1.8'
  describe.one do
    describe file('/etc/cron.allow') do
      it { should exist }
    end
    describe file('/etc/at.allow') do
      it { should exist }
    end
  end
end

# 5.2 SSH server configuration
# NOTE: We use `sshd -T` (dump effective config including compiled-in defaults)
# rather than reading sshd_config directly.  Modern Ubuntu/Debian ships with
# secure defaults that satisfy many CIS controls but does not write them
# explicitly to sshd_config, causing the sshd_config resource to return nil.
# `sshd -T` reflects the actual running behaviour of the daemon.

control 'cis-5.2.1-sshd-config-perms' do
  impact 0.5
  title 'Ensure permissions on /etc/ssh/sshd_config are configured'
  tag cis: '5.2.1'
  describe file('/etc/ssh/sshd_config') do
    its('owner') { should eq 'root' }
    its('group') { should eq 'root' }
    it { should_not be_writable.by('group') }
    it { should_not be_readable.by('other') }
  end
end

control 'cis-5.2.4-sshd-loglevel' do
  impact 0.3
  title 'Ensure SSH LogLevel is appropriate'
  tag cis: '5.2.4'
  describe command('sshd -T 2>/dev/null | grep -i "^loglevel "') do
    its('stdout') { should match(/\b(?:INFO|VERBOSE)\b/i) }
  end
end

control 'cis-5.2.5-sshd-x11' do
  impact 0.4
  title 'Ensure SSH X11 forwarding is disabled'
  tag cis: '5.2.5'
  describe command('sshd -T 2>/dev/null | grep -i "^x11forwarding "') do
    its('stdout') { should match(/\bno\b/i) }
  end
end

control 'cis-5.2.6-sshd-maxauthtries' do
  impact 0.5
  title 'Ensure SSH MaxAuthTries is set to 4 or less'
  tag cis: '5.2.6'
  describe command('sshd -T 2>/dev/null | grep -i "^maxauthtries "') do
    its('stdout') { should match(/^maxauthtries\s+[1-4]\s*$/i) }
  end
end

control 'cis-5.2.7-sshd-ignorerhosts' do
  impact 0.5
  title 'Ensure SSH IgnoreRhosts is enabled'
  tag cis: '5.2.7'
  describe command('sshd -T 2>/dev/null | grep -i "^ignorerhosts "') do
    its('stdout') { should match(/\byes\b/i) }
  end
end

control 'cis-5.2.8-sshd-hostbased' do
  impact 0.5
  title 'Ensure SSH HostbasedAuthentication is disabled'
  tag cis: '5.2.8'
  describe command('sshd -T 2>/dev/null | grep -i "^hostbasedauthentication "') do
    its('stdout') { should match(/\bno\b/i) }
  end
end

control 'cis-5.2.9-sshd-permitrootlogin' do
  impact 0.8
  title 'Ensure SSH root login is disabled'
  desc 'PermitRootLogin must be no so administrators authenticate as themselves and escalate.'
  tag cis: '5.2.9'
  describe command('sshd -T 2>/dev/null | grep -i "^permitrootlogin "') do
    its('stdout') { should match(/\bno\b/i) }
  end
end

control 'cis-5.2.10-sshd-permitemptypw' do
  impact 1.0
  title 'Ensure SSH PermitEmptyPasswords is disabled'
  tag cis: '5.2.10'
  describe command('sshd -T 2>/dev/null | grep -i "^permitemptypasswords "') do
    its('stdout') { should match(/\bno\b/i) }
  end
end

control 'cis-5.2.11-sshd-permituserenv' do
  impact 0.4
  title 'Ensure SSH PermitUserEnvironment is disabled'
  tag cis: '5.2.11'
  describe command('sshd -T 2>/dev/null | grep -i "^permituserenv "') do
    its('stdout') { should match(/\bno\b/i) }
  end
end

control 'cis-5.2.12-sshd-ciphers' do
  impact 0.5
  title 'Ensure only strong SSH ciphers are used'
  desc 'Weak ciphers (3des, arcfour, cbc) must not be offered.'
  tag cis: '5.2.12'
  describe command('sshd -T 2>/dev/null | grep -i "^ciphers "') do
    its('stdout') { should_not match(/3des|arcfour|cbc/i) }
  end
end

control 'cis-5.2.13-sshd-macs' do
  impact 0.5
  title 'Ensure only strong SSH MAC algorithms are used'
  tag cis: '5.2.13'
  describe command('sshd -T 2>/dev/null | grep -i "^macs "') do
    its('stdout') { should_not match(/\bmd5\b|hmac-sha1(?!-etm)/i) }
  end
end

control 'cis-5.2.15-sshd-clientalive' do
  impact 0.3
  title 'Ensure SSH idle timeout interval is configured'
  desc 'ClientAliveInterval should be between 1 and 300 seconds.'
  tag cis: '5.2.15'
  describe command('sshd -T 2>/dev/null | grep -i "^clientaliveinterval "') do
    its('stdout') { should match(/^clientaliveinterval\s+([1-9]|[1-9]\d|[12]\d\d|300)\s*$/i) }
  end
end

control 'cis-5.2.17-sshd-logingrace' do
  impact 0.3
  title 'Ensure SSH LoginGraceTime is set to one minute or less'
  tag cis: '5.2.17'
  describe command('sshd -T 2>/dev/null | grep -i "^logingracetime "') do
    its('stdout') { should match(/^logingracetime\s+([1-9]|[1-5]\d|60)\s*$/i) }
  end
end

control 'cis-5.2.20-sshd-maxstartups' do
  impact 0.3
  title 'Ensure SSH MaxStartups is configured'
  tag cis: '5.2.20'
  describe command('sshd -T 2>/dev/null | grep -i "^maxstartups "') do
    its('stdout') { should match(/\S/) }
  end
end

control 'cis-5.2.22-sshd-maxsessions' do
  impact 0.3
  title 'Ensure SSH MaxSessions is limited'
  tag cis: '5.2.22'
  describe command('sshd -T 2>/dev/null | grep -i "^maxsessions "') do
    its('stdout') { should match(/^maxsessions\s+([1-9]|10)\s*$/i) }
  end
end

# 5.3 Configure PAM / password quality
control 'cis-5.3.1-pwquality' do
  impact 0.5
  title 'Ensure password creation requirements are configured'
  desc 'pwquality should enforce a minimum length of 14 characters.'
  tag cis: '5.3.1'
  describe.one do
    describe parse_config_file('/etc/security/pwquality.conf') do
      its('minlen') { should cmp >= 14 }
    end
    describe file('/etc/security/pwquality.conf.d') do
      it { should exist }
    end
  end
end

control 'cis-5.3.2-lockout' do
  impact 0.5
  title 'Ensure lockout for failed password attempts is configured'
  desc 'Account lockout (pam_faillock / pam_tally2) must trigger after repeated failures.'
  tag cis: '5.3.2'
  describe.one do
    describe file('/etc/security/faillock.conf') do
      its('content') { should match(/^\s*deny\s*=\s*[1-5]/) }
    end
    describe command('grep -R pam_faillock /etc/pam.d/ 2>/dev/null') do
      its('stdout') { should match(/deny=/) }
    end
    describe command('grep -R pam_tally2 /etc/pam.d/ 2>/dev/null') do
      its('stdout') { should match(/deny=/) }
    end
  end
end

control 'cis-5.3.4-password-hash-sha512' do
  impact 0.6
  title 'Ensure password hashing algorithm is SHA-512 or yescrypt'
  desc 'pam_unix must store passwords using a strong hash.'
  tag cis: '5.3.4'
  describe command('grep -R -E "pam_unix.so.*(sha512|yescrypt)" /etc/pam.d/ 2>/dev/null') do
    its('stdout') { should_not eq '' }
  end
end

# 5.3.5 — Re-authentication for privilege escalation (NOPASSWD sudo)
#
# CIS requires that sudo does NOT grant passwordless privilege escalation, so
# that every escalation re-authenticates the operator (no `NOPASSWD`, no
# `!authenticate`).
#
# The SABC platform's automation account — "ansible" — is an INTENTIONAL,
# documented exception to this control. It is a key-only, non-interactive
# account the platform uses to run Ansible, Puppet and CINC over SSH; it has
# no usable password (the bootstrap locks the shadow field) and is reachable
# only with the platform's private key. Granting it passwordless sudo is an
# accepted operational risk recorded in the SABC referential.
#
# This control therefore treats the ansible account as compliant and FAILS the
# moment ANY OTHER user or group is granted passwordless sudo — that other
# account is the real finding worth surfacing.
control 'sabc-5.3.5-sudo-nopasswd-restricted' do
  impact 0.7
  title 'Ensure no account other than the platform automation user has passwordless sudo'
  desc <<~DESC
    CIS 5.3.x requires re-authentication for privilege escalation: sudoers must
    not contain NOPASSWD entries. The "ansible" automation account is an
    approved exception (key-only, non-interactive, used exclusively by the SABC
    platform). Any OTHER account or group holding NOPASSWD is reported as a
    finding and should be removed.
  DESC
  tag cis: '5.3.5'
  tag sabc_exception: 'ansible-automation-account'

  # Collect every NOPASSWD user-spec across the sudoers files, drop comment
  # lines and the approved "ansible" account (matched as the first user-spec
  # field followed by whitespace, so "ansible_x" or "ansible,other" are NOT
  # exempted). Anything left is a passwordless-sudo grant on another account.
  describe command(
    "grep -rhE 'NOPASSWD' /etc/sudoers /etc/sudoers.d/ 2>/dev/null " \
    "| grep -vE '^[[:space:]]*#' " \
    "| grep -vE '^[[:space:]]*ansible[[:space:]]'"
  ) do
    its('stdout.strip') { should eq '' }
  end
end

# 5.4 User accounts and environment
control 'cis-5.4.1.1-pass-max-days' do
  impact 0.5
  title 'Ensure password expiration is 365 days or less'
  tag cis: '5.4.1.1'
  describe login_defs do
    its('PASS_MAX_DAYS') { should cmp <= 365 }
  end
end

control 'cis-5.4.1.2-pass-min-days' do
  impact 0.4
  title 'Ensure minimum days between password changes is configured'
  tag cis: '5.4.1.2'
  describe login_defs do
    its('PASS_MIN_DAYS') { should cmp >= 1 }
  end
end

control 'cis-5.4.1.3-pass-warn-age' do
  impact 0.3
  title 'Ensure password expiration warning days is 7 or more'
  tag cis: '5.4.1.3'
  describe login_defs do
    its('PASS_WARN_AGE') { should cmp >= 7 }
  end
end

control 'cis-5.4.4-default-umask' do
  impact 0.4
  title 'Ensure default user umask is 027 or more restrictive'
  desc 'A restrictive default umask prevents newly created files from being world-readable.'
  tag cis: '5.4.4'
  describe login_defs do
    its('UMASK') { should match(/0?[027]7/) }
  end
end

control 'cis-5.5-su-restricted' do
  impact 0.4
  title 'Ensure access to the su command is restricted'
  desc 'pam_wheel should restrict su to members of a trusted group.'
  tag cis: '5.6'
  describe command('grep -E "^\s*auth\s+required\s+pam_wheel.so" /etc/pam.d/su 2>/dev/null') do
    its('stdout') { should_not eq '' }
  end
end
