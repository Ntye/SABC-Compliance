# encoding: utf-8
# Critical file permissions — CIS Section 6.1

control 'file-01' do
  impact 0.6
  title 'Secure /etc/passwd permissions'
  desc '/etc/passwd must be owned by root and set to mode 0644.'
  tag cis: '6.1.2'
  tag iso27001: 'A.9.2.3'
  describe file('/etc/passwd') do
    it { should exist }
    its('owner') { should eq 'root' }
    its('group') { should eq 'root' }
    its('mode') { should cmp '0644' }
  end
end

control 'file-02' do
  impact 0.8
  title 'Secure /etc/shadow permissions'
  desc '/etc/shadow holds password hashes and must be tightly restricted: ' \
       'root-owned and no broader than mode 0640.'
  tag cis: '6.1.3'
  tag iso27001: 'A.9.4.3'
  tag pci_dss: '8.2.1'
  describe file('/etc/shadow') do
    it { should exist }
    its('owner') { should eq 'root' }
    it { should_not be_readable.by('other') }
    it { should_not be_writable.by('other') }
    it { should_not be_executable }
  end
end

control 'file-03' do
  impact 0.5
  title 'Secure /etc/gshadow permissions'
  desc '/etc/gshadow must be root-owned and not accessible by other users.'
  tag cis: '6.1.5'
  describe file('/etc/gshadow') do
    its('owner') { should eq 'root' }
    it { should_not be_readable.by('other') }
    it { should_not be_writable.by('other') }
  end
end
