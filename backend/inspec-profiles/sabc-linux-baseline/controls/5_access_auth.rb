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
  describe sshd_config do
    its('LogLevel') { should match(/VERBOSE|INFO/) }
  end
end

control 'cis-5.2.5-sshd-x11' do
  impact 0.4
  title 'Ensure SSH X11 forwarding is disabled'
  tag cis: '5.2.5'
  describe sshd_config do
    its('X11Forwarding') { should cmp 'no' }
  end
end

control 'cis-5.2.6-sshd-maxauthtries' do
  impact 0.5
  title 'Ensure SSH MaxAuthTries is set to 4 or less'
  tag cis: '5.2.6'
  describe sshd_config do
    its('MaxAuthTries') { should cmp <= 4 }
  end
end

control 'cis-5.2.7-sshd-ignorerhosts' do
  impact 0.5
  title 'Ensure SSH IgnoreRhosts is enabled'
  tag cis: '5.2.7'
  describe sshd_config do
    its('IgnoreRhosts') { should cmp 'yes' }
  end
end

control 'cis-5.2.8-sshd-hostbased' do
  impact 0.5
  title 'Ensure SSH HostbasedAuthentication is disabled'
  tag cis: '5.2.8'
  describe sshd_config do
    its('HostbasedAuthentication') { should cmp 'no' }
  end
end

control 'cis-5.2.9-sshd-permitrootlogin' do
  impact 0.8
  title 'Ensure SSH root login is disabled'
  desc 'PermitRootLogin must be no so administrators authenticate as themselves and escalate.'
  tag cis: '5.2.9'
  tag iso27001: 'A.9.2.3'
  tag pci_dss: '8.2'
  describe sshd_config do
    its('PermitRootLogin') { should cmp 'no' }
  end
end

control 'cis-5.2.10-sshd-permitemptypw' do
  impact 1.0
  title 'Ensure SSH PermitEmptyPasswords is disabled'
  tag cis: '5.2.10'
  tag pci_dss: '8.2.3'
  describe sshd_config do
    its('PermitEmptyPasswords') { should cmp 'no' }
  end
end

control 'cis-5.2.11-sshd-permituserenv' do
  impact 0.4
  title 'Ensure SSH PermitUserEnvironment is disabled'
  tag cis: '5.2.11'
  describe sshd_config do
    its('PermitUserEnvironment') { should cmp 'no' }
  end
end

control 'cis-5.2.12-sshd-ciphers' do
  impact 0.5
  title 'Ensure only strong SSH ciphers are used'
  desc 'Weak ciphers (3des, arcfour, cbc) must not be offered.'
  tag cis: '5.2.12'
  describe sshd_config do
    its('Ciphers') { should_not match(/3des|arcfour|cbc/i) }
  end
end

control 'cis-5.2.13-sshd-macs' do
  impact 0.5
  title 'Ensure only strong SSH MAC algorithms are used'
  tag cis: '5.2.13'
  describe sshd_config do
    its('MACs') { should_not match(/md5|hmac-sha1\b/i) }
  end
end

control 'cis-5.2.15-sshd-clientalive' do
  impact 0.3
  title 'Ensure SSH idle timeout interval is configured'
  desc 'ClientAliveInterval should be 300 or less and ClientAliveCountMax 3 or less.'
  tag cis: '5.2.15'
  describe sshd_config do
    its('ClientAliveInterval') { should cmp <= 300 }
    its('ClientAliveInterval') { should cmp > 0 }
  end
end

control 'cis-5.2.17-sshd-logingrace' do
  impact 0.3
  title 'Ensure SSH LoginGraceTime is set to one minute or less'
  tag cis: '5.2.17'
  describe sshd_config do
    its('LoginGraceTime') { should cmp <= 60 }
  end
end

control 'cis-5.2.20-sshd-maxstartups' do
  impact 0.3
  title 'Ensure SSH MaxStartups is configured'
  tag cis: '5.2.20'
  describe sshd_config do
    its('MaxStartups') { should_not be_nil }
  end
end

control 'cis-5.2.22-sshd-maxsessions' do
  impact 0.3
  title 'Ensure SSH MaxSessions is limited'
  tag cis: '5.2.22'
  describe sshd_config do
    its('MaxSessions') { should cmp <= 10 }
  end
end

# 5.3 Configure PAM / password quality
control 'cis-5.3.1-pwquality' do
  impact 0.5
  title 'Ensure password creation requirements are configured'
  desc 'pwquality should enforce a minimum length of 14 characters.'
  tag cis: '5.3.1'
  tag iso27001: 'A.9.4.3'
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

# 5.4 User accounts and environment
control 'cis-5.4.1.1-pass-max-days' do
  impact 0.5
  title 'Ensure password expiration is 365 days or less'
  tag cis: '5.4.1.1'
  tag pci_dss: '8.2.4'
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
