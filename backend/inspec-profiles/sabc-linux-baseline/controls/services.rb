# encoding: utf-8
# Auditing, firewall and unwanted services — CIS Sections 2, 3.5, 4.1

control 'svc-01' do
  impact 0.6
  title 'auditd is installed and running'
  desc 'The audit daemon records security-relevant events and must be active ' \
       'to support detection and forensic investigation.'
  tag cis: '4.1.1.1'
  tag iso27001: 'A.12.4.1'
  tag pci_dss: '10.2'
  describe service('auditd') do
    it { should be_installed }
    it { should be_enabled }
    it { should be_running }
  end
end

control 'svc-02' do
  impact 0.7
  title 'Telnet server is not installed'
  desc 'The telnet server transmits credentials in clear text and must not be ' \
       'installed.'
  tag cis: '2.2.1'
  tag pci_dss: '2.2.3'
  describe.one do
    describe package('telnet-server') do
      it { should_not be_installed }
    end
    describe package('telnetd') do
      it { should_not be_installed }
    end
  end
end

control 'svc-03' do
  impact 0.6
  title 'A host firewall is active'
  desc 'At least one host firewall (firewalld, ufw or nftables) must be ' \
       'running to filter inbound traffic.'
  tag cis: '3.5.1'
  tag iso27001: 'A.13.1.1'
  describe.one do
    describe service('firewalld') do
      it { should be_running }
    end
    describe service('ufw') do
      it { should be_running }
    end
    describe service('nftables') do
      it { should be_running }
    end
  end
end

control 'svc-04' do
  impact 0.5
  title 'Time synchronization service is active'
  desc 'A time synchronization daemon (chronyd or systemd-timesyncd) must be ' \
       'running so that log timestamps are accurate.'
  tag cis: '2.1.1'
  describe.one do
    describe service('chronyd') do
      it { should be_running }
    end
    describe service('systemd-timesyncd') do
      it { should be_running }
    end
    describe service('ntpd') do
      it { should be_running }
    end
  end
end
