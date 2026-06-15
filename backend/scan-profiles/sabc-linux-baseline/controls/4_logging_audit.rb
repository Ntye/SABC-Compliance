# encoding: utf-8
# CIS Benchmark — Section 4: Logging and Auditing
# System auditing (auditd) and system logging (rsyslog / journald).

title 'Section 4 — Logging and Auditing'

# 4.1.1 Ensure auditing is enabled
control 'cis-4.1.1.1-auditd-installed' do
  impact 0.6
  title 'Ensure auditd is installed'
  desc 'The audit daemon records security-relevant events for detection and forensics.'
  tag cis: '4.1.1.1'
  describe.one do
    describe package('auditd') do
      it { should be_installed }
    end
    describe package('audit') do
      it { should be_installed }
    end
  end
end

control 'cis-4.1.1.2-auditd-enabled' do
  impact 0.6
  title 'Ensure auditd service is enabled and running'
  desc 'auditd must start at boot and be running to capture audit events.'
  tag cis: '4.1.1.2'
  describe service('auditd') do
    it { should be_enabled }
    it { should be_running }
  end
end

# 4.1.2 Configure data retention
control 'cis-4.1.2.1-audit-log-size' do
  impact 0.4
  title 'Ensure audit log storage size is configured'
  desc 'max_log_file in /etc/audit/auditd.conf bounds the size of each audit log.'
  tag cis: '4.1.2.1'
  describe auditd_conf do
    its('max_log_file') { should cmp >= 8 }
  end
end

control 'cis-4.1.2.2-audit-log-full-action' do
  impact 0.4
  title 'Ensure audit logs are not automatically deleted'
  desc 'max_log_file_action should keep logs (keep_logs) rather than rotate-and-delete.'
  tag cis: '4.1.2.2'
  describe auditd_conf do
    its('max_log_file_action') { should match(/keep_logs|rotate/) }
  end
end

# 4.1.3 Key audit watch rules
{
  'identity'      => %w(/etc/group /etc/passwd /etc/shadow /etc/gshadow),
  'sudoers'       => %w(/etc/sudoers),
  'login-records' => %w(/var/log/lastlog /var/log/faillog),
}.each do |label, files|
  control "cis-4.1.3-watch-#{label}" do
    impact 0.4
    title "Ensure audit watches monitor #{label} files"
    desc "auditd should have watch rules covering: #{files.join(', ')}."
    tag cis: '4.1.3'
    files.each do |f|
      describe command('auditctl -l 2>/dev/null') do
        its('stdout') { should include f }
      end
    end
  end
end

control 'cis-4.1.3-scope-time-change' do
  impact 0.4
  title 'Ensure events that modify date and time are collected'
  desc 'auditd should monitor time-change syscalls (adjtimex, settimeofday, clock_settime).'
  tag cis: '4.1.3'
  describe command('auditctl -l 2>/dev/null') do
    its('stdout') { should match(/time-change|adjtimex|clock_settime/) }
  end
end

# 4.2 Configure logging
control 'cis-4.2.1-rsyslog-or-journald' do
  impact 0.5
  title 'Ensure a system logging service is installed and active'
  desc 'rsyslog or systemd-journald must be running so that events are recorded.'
  tag cis: '4.2.1'
  describe.one do
    describe service('rsyslog') do
      it { should be_running }
    end
    describe service('systemd-journald') do
      it { should be_running }
    end
  end
end

control 'cis-4.2.3-log-file-perms' do
  impact 0.4
  title 'Ensure permissions on all logfiles are configured'
  desc 'Files under /var/log must not be world-writable or world-readable where sensitive.'
  tag cis: '4.2.3'
  describe command("find /var/log -type f -perm /0137 2>/dev/null") do
    its('stdout.strip') { should eq '' }
  end
end
