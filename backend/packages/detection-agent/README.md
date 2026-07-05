# detection-agent/ — airgap wheels

For nodes with no internet access, drop `watchdog` wheels here (matching the
node's Python version/architecture). `install_detection_agent.yml` copies and
installs them with `pip --no-index` before falling back to online pip.

```bash
# On a machine with internet access (pick the target's platform):
pip3 download watchdog -d .
```
