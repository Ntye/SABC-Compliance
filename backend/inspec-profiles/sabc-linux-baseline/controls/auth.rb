# encoding: utf-8
# Password policy — CIS Section 5.4.1

control 'auth-01' do
  impact 0.5
  title 'Password expiration is 365 days or less'
  desc 'PASS_MAX_DAYS in /etc/login.defs limits how long a password remains ' \
       'valid and should be 365 days or fewer.'
  tag cis: '5.4.1.1'
  tag iso27001: 'A.9.4.3'
  tag pci_dss: '8.2.4'
  describe login_defs do
    its('PASS_MAX_DAYS') { should cmp <= 365 }
  end
end

control 'auth-02' do
  impact 0.4
  title 'Minimum days between password changes is configured'
  desc 'PASS_MIN_DAYS should be at least 1 to prevent users from cycling ' \
       'through passwords to defeat history requirements.'
  tag cis: '5.4.1.2'
  describe login_defs do
    its('PASS_MIN_DAYS') { should cmp >= 1 }
  end
end

control 'auth-03' do
  impact 0.4
  title 'Password change warning is configured'
  desc 'PASS_WARN_AGE should be 7 or more days so users are warned before ' \
       'their password expires.'
  tag cis: '5.4.1.3'
  describe login_defs do
    its('PASS_WARN_AGE') { should cmp >= 7 }
  end
end
