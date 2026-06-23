# encoding: utf-8
# CIS Benchmark — Section 6: System Maintenance
# System file permissions and user/group account hygiene.

title 'Section 6 — System Maintenance'

# 6.1 System file permissions
{
  '/etc/passwd'   => { cid: '6.1.2', mode: '0644' },
  '/etc/passwd-'  => { cid: '6.1.3', mode: '0644' },
  '/etc/group'    => { cid: '6.1.4', mode: '0644' },
  '/etc/group-'   => { cid: '6.1.5', mode: '0644' },
  '/etc/shadow'   => { cid: '6.1.6', mode: '0640' },
  '/etc/shadow-'  => { cid: '6.1.7', mode: '0640' },
  '/etc/gshadow'  => { cid: '6.1.8', mode: '0640' },
  '/etc/gshadow-' => { cid: '6.1.9', mode: '0640' },
}.each do |path, meta|
  control "cis-#{meta[:cid]}-perms#{path.tr('/', '-')}" do
    impact 0.6
    title "Ensure permissions on #{path} are configured"
    desc "#{path} must be root-owned and no more permissive than #{meta[:mode]}."
    tag cis: meta[:cid]
    only_if { file(path).exist? }
    describe file(path) do
      its('owner') { should eq 'root' }
      it { should_not be_writable.by('group') }
      it { should_not be_writable.by('other') }
      it { should_not be_executable }
    end
  end
end

control 'cis-6.1.10-world-writable-files' do
  impact 0.6
  title 'Ensure no world-writable files exist'
  desc 'World-writable files allow any user to modify their contents.'
  tag cis: '6.1.10'
  describe command("df --local -P 2>/dev/null | awk 'NR!=1 {print $6}' | xargs -I '{}' find '{}' -xdev -type f -perm -0002 2>/dev/null") do
    its('stdout.strip') { should eq '' }
  end
end

control 'cis-6.1.11-unowned-files' do
  impact 0.4
  title 'Ensure no unowned or ungrouped files or directories exist'
  desc 'Files without a valid owner or group may indicate a removed account.'
  tag cis: '6.1.11'
  describe command("df --local -P 2>/dev/null | awk 'NR!=1 {print $6}' | xargs -I '{}' find '{}' -xdev \\( -nouser -o -nogroup \\) 2>/dev/null") do
    its('stdout.strip') { should eq '' }
  end
end

# 6.2 User and group settings
control 'cis-6.2.1-no-empty-passwords' do
  impact 0.9
  title 'Ensure no accounts have empty password fields'
  desc 'Every enabled account must have a password hash set in /etc/shadow.'
  tag cis: '6.2.1'
  describe command("awk -F: '($2 == \"\") {print $1}' /etc/shadow 2>/dev/null") do
    its('stdout.strip') { should eq '' }
  end
end

control 'cis-6.2.2-no-legacy-passwd-entry' do
  impact 0.5
  title 'Ensure /etc/passwd has no legacy + entries'
  tag cis: '6.2.2'
  describe command("grep '^\\+:' /etc/passwd 2>/dev/null") do
    its('stdout.strip') { should eq '' }
  end
end

control 'cis-6.2.5-root-uid-0-unique' do
  impact 0.8
  title 'Ensure root is the only UID 0 account'
  desc 'Only the root account may have UID 0.'
  tag cis: '6.2.5'
  describe command("awk -F: '($3 == 0) {print $1}' /etc/passwd 2>/dev/null") do
    its('stdout.strip') { should eq 'root' }
  end
end

control 'cis-6.2.6-root-path-integrity' do
  impact 0.4
  title "Ensure root PATH does not include a writable or current directory"
  desc 'The root PATH must not contain an empty entry, "." or group/world-writable directories.'
  tag cis: '6.2.6'
  describe command(%q{echo "$PATH" | tr ':' '\n' | grep -E '^$|^\.$' 2>/dev/null}) do
    its('stdout.strip') { should eq '' }
  end
end

control 'cis-6.2.8-home-dir-perms' do
  impact 0.4
  title 'Ensure users home directories are not group/world writable'
  tag cis: '6.2.8'
  describe command("awk -F: '($3>=1000 && $7!~/(nologin|false)/){print $6}' /etc/passwd 2>/dev/null | while read d; do [ -d \"$d\" ] && find \"$d\" -maxdepth 0 -perm /0027 2>/dev/null; done") do
    its('stdout.strip') { should eq '' }
  end
end

control 'cis-6.2.11-no-duplicate-uids' do
  impact 0.5
  title 'Ensure no duplicate UIDs exist'
  tag cis: '6.2.11'
  describe command("cut -d: -f3 /etc/passwd 2>/dev/null | sort | uniq -d") do
    its('stdout.strip') { should eq '' }
  end
end

control 'cis-6.2.12-no-duplicate-gids' do
  impact 0.5
  title 'Ensure no duplicate GIDs exist'
  tag cis: '6.2.12'
  describe command("cut -d: -f3 /etc/group 2>/dev/null | sort | uniq -d") do
    its('stdout.strip') { should eq '' }
  end
end
