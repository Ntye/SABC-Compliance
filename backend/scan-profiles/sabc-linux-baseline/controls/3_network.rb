# encoding: utf-8
# CIS Benchmark — Section 3: Network Configuration
# Host network parameters, kernel network hardening, uncommon protocols and a
# host firewall.

title 'Section 3 — Network Configuration'

# 3.1 / 3.2 Network kernel parameters (sysctl)
{
  'net.ipv4.ip_forward'                        => 0, # 3.1.1
  'net.ipv4.conf.all.send_redirects'           => 0, # 3.1.2
  'net.ipv4.conf.default.send_redirects'       => 0,
  'net.ipv4.conf.all.accept_source_route'      => 0, # 3.2.1
  'net.ipv4.conf.default.accept_source_route'  => 0,
  'net.ipv4.conf.all.accept_redirects'         => 0, # 3.2.2
  'net.ipv4.conf.default.accept_redirects'     => 0,
  'net.ipv4.conf.all.secure_redirects'         => 0, # 3.2.3
  'net.ipv4.conf.all.log_martians'             => 1, # 3.2.4
  'net.ipv4.conf.default.log_martians'         => 1,
  'net.ipv4.icmp_echo_ignore_broadcasts'       => 1, # 3.2.5
  'net.ipv4.icmp_ignore_bogus_error_responses' => 1, # 3.2.6
  'net.ipv4.conf.all.rp_filter'                => 1, # 3.2.7
  'net.ipv4.tcp_syncookies'                    => 1, # 3.2.8
  'net.ipv6.conf.all.accept_ra'                => 0, # 3.2.9
  'net.ipv6.conf.all.accept_redirects'         => 0,
}.each do |param, expected|
  control "cis-3.x-#{param}" do
    impact 0.5
    title "Ensure #{param} is set to #{expected}"
    desc "Kernel network parameter #{param} must equal #{expected} to harden the host's network stack."
    tag cis: '3.2'
    describe kernel_parameter(param) do
      its('value') { should eq expected }
    end
  end
end

# 3.3 Uncommon network protocols
%w(dccp sctp rds tipc).each do |proto|
  control "cis-3.3-#{proto}" do
    impact 0.3
    title "Ensure the #{proto} protocol is disabled"
    desc "The uncommon #{proto} protocol module should not be loadable."
    tag cis: '3.3'
    describe kernel_module(proto) do
      it { should_not be_loaded }
      it { should be_disabled }
    end
  end
end

# 3.5 Host based firewall
control 'cis-3.5.1-firewall-installed' do
  impact 0.6
  title 'Ensure a host firewall package is installed'
  desc 'firewalld, ufw, nftables or iptables must be available to filter traffic.'
  tag cis: '3.5.1'
  describe.one do
    describe package('firewalld') do
      it { should be_installed }
    end
    describe package('ufw') do
      it { should be_installed }
    end
    describe package('nftables') do
      it { should be_installed }
    end
    describe package('iptables') do
      it { should be_installed }
    end
  end
end

control 'cis-3.5.2-firewall-active' do
  impact 0.7
  title 'Ensure a host firewall is active'
  desc 'A firewall service (firewalld, ufw or nftables) must be running.'
  tag cis: '3.5.2'
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
