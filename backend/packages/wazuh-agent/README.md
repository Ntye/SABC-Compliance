# Wazuh agent packages (airgap / no-NAT targets)

Drop `wazuh-agent_<VERSION>-1_<arch>.deb` (Debian/Ubuntu) or
`wazuh-agent-<VERSION>-1.<arch>.rpm` (RHEL/Rocky/CentOS) files here and the
install job uses them instead of downloading on the target.

You normally do NOT need to do this by hand: when the target has no internet
but the platform does, `install_wazuh_agent.yml` downloads the package matching
the manager's version into this directory automatically.

The agent version must be <= the manager version.
