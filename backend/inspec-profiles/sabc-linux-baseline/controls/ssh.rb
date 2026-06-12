# encoding: utf-8
# SSH daemon hardening — CIS Section 5.2

control 'sshd-01' do
  impact 0.7
  title 'Disable SSH root login'
  desc 'The SSH daemon must not permit direct authentication as root. ' \
       'Administrators should log in as an unprivileged user and escalate.'
  tag cis: '5.2.8'
  tag iso27001: 'A.9.2.3'
  tag pci_dss: '8.2'
  describe sshd_config do
    its('PermitRootLogin') { should cmp 'no' }
  end
end

control 'sshd-02' do
  impact 1.0
  title 'Disallow SSH logins to accounts with empty passwords'
  desc 'PermitEmptyPasswords must be set to no so accounts with blank ' \
       'passwords cannot be used to authenticate over SSH.'
  tag cis: '5.2.10'
  tag iso27001: 'A.9.4.3'
  tag pci_dss: '8.2.3'
  describe sshd_config do
    its('PermitEmptyPasswords') { should cmp 'no' }
  end
end

control 'sshd-03' do
  impact 0.4
  title 'Disable SSH X11 forwarding'
  desc 'X11 forwarding exposes the X11 display and should be disabled unless ' \
       'explicitly required.'
  tag cis: '5.2.4'
  describe sshd_config do
    its('X11Forwarding') { should cmp 'no' }
  end
end

control 'sshd-04' do
  impact 0.5
  title 'Limit SSH authentication attempts'
  desc 'MaxAuthTries should be 4 or fewer to slow down brute-force attempts.'
  tag cis: '5.2.5'
  describe sshd_config do
    its('MaxAuthTries') { should cmp <= 4 }
  end
end

control 'sshd-05' do
  impact 0.5
  title 'Restrict sshd_config permissions'
  desc 'The SSH server configuration file must be owned by root and not ' \
       'writable by group or other.'
  tag cis: '5.2.1'
  describe file('/etc/ssh/sshd_config') do
    it { should exist }
    its('owner') { should eq 'root' }
    its('group') { should eq 'root' }
    it { should_not be_writable.by('group') }
    it { should_not be_writable.by('other') }
  end
end
