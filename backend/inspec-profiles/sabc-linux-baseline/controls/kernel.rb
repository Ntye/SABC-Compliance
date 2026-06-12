# encoding: utf-8
# Kernel / network hardening — CIS Sections 1.5 and 3.x

control 'sysctl-01' do
  impact 0.5
  title 'Enable full address space layout randomization (ASLR)'
  desc 'kernel.randomize_va_space must be set to 2 to randomize the memory ' \
       'layout of processes, mitigating memory-corruption exploits.'
  tag cis: '1.5.3'
  tag iso27001: 'A.12.6.1'
  describe kernel_parameter('kernel.randomize_va_space') do
    its('value') { should eq 2 }
  end
end

control 'sysctl-02' do
  impact 0.4
  title 'Disable IPv4 forwarding'
  desc 'net.ipv4.ip_forward should be 0 on hosts that are not acting as ' \
       'routers, to avoid unintended packet forwarding.'
  tag cis: '3.1.1'
  describe kernel_parameter('net.ipv4.ip_forward') do
    its('value') { should eq 0 }
  end
end

control 'sysctl-03' do
  impact 0.4
  title 'Ignore ICMP broadcast requests'
  desc 'net.ipv4.icmp_echo_ignore_broadcasts must be 1 to prevent the host ' \
       'from participating in Smurf-style amplification attacks.'
  tag cis: '3.2.5'
  describe kernel_parameter('net.ipv4.icmp_echo_ignore_broadcasts') do
    its('value') { should eq 1 }
  end
end

control 'sysctl-04' do
  impact 0.4
  title 'Do not accept ICMP redirects'
  desc 'net.ipv4.conf.all.accept_redirects must be 0 so the routing table ' \
       'cannot be altered by malicious ICMP redirect messages.'
  tag cis: '3.3.2'
  describe kernel_parameter('net.ipv4.conf.all.accept_redirects') do
    its('value') { should eq 0 }
  end
end
