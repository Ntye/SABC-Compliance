"""External Node Classifier (ENC) generation for Puppet Core (open source).

Puppet Enterprise classifies nodes through the commercial Node Classifier +
RBAC HTTP APIs. Open-source Puppet (Puppet Core) has neither — classification
there is done by an **External Node Classifier**: an executable the master runs
once per node that prints a YAML document describing the node's environment,
classes and parameters.

This module turns the SABC node-group tree + resolved memberships into a set of
ENC artifacts that the platform deploys to a Puppet Core master:

  <enc_dir>/classify            a tiny POSIX script the master calls per node
  <enc_dir>/nodes/<certname>.yaml   one ENC document per managed node
  <enc_dir>/default.yaml        fallback for nodes we don't manage

The ``classify`` script just ``cat``s the per-node file (or the default),
so the master needs no YAML parser, Ruby gem, or particular Python version —
it works on any Puppet Core master. The platform regenerates ``nodes/`` on
every sync and pushes it over SSH.

Design choice — why we don't emit ``classes`` directly: returning a class the
master's control repo doesn't define makes catalog compilation fail. Group
membership is therefore exposed as a parameter (``sabc_groups``) plus the bound
InSpec profile (``sabc_inspec_profile``); the operator's ``site.pp``/Hiera can
``lookup`` those and ``include`` whatever classes they want, with zero risk of
breaking compilation when a class is absent. This mirrors the PE integration,
which also sends empty classes and relies on membership + environment.
"""
from __future__ import annotations
import re

# Marker block delimiters so puppet.conf edits are idempotent and reversible.
PUPPET_CONF_BEGIN = "# >>> SABC Compliance ENC (managed) >>>"
PUPPET_CONF_END = "# <<< SABC Compliance ENC (managed) <<<"


def sanitize_certname(certname: str) -> str:
    """Make a certname safe to use as a filename.

    Certnames are normally DNS-ish (letters, digits, dots, hyphens). Anything
    outside that set is replaced with ``_`` so a hostile or malformed certname
    can never escape the ``nodes/`` directory via path traversal.
    """
    name = (certname or "").strip()
    # Strip any path separators first, then whitelist.
    name = name.replace("/", "_").replace("\\", "_")
    name = re.sub(r"[^A-Za-z0-9._-]", "_", name)
    # Never allow a leading dot (hidden file) or empty name.
    name = name.lstrip(".") or "_unnamed"
    return name


def _yaml_quote(value: str) -> str:
    """Double-quote a scalar for YAML, escaping backslashes and quotes."""
    s = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{s}"'


def render_node_doc(
    environment: str,
    groups: list[str],
    inspec_profile: str | None = None,
) -> str:
    """Render one node's ENC YAML document.

    Always emits ``environment`` and an (empty) ``classes`` map so the document
    is a valid ENC response even with no classes assigned. Group membership and
    the bound InSpec profile are surfaced under ``parameters`` for the control
    repo to consume.
    """
    lines = ["---"]
    lines.append(f"environment: {_yaml_quote(environment or 'production')}")
    lines.append("classes: {}")
    lines.append("parameters:")
    if groups:
        lines.append("  sabc_groups:")
        for g in groups:
            lines.append(f"    - {_yaml_quote(g)}")
    else:
        lines.append("  sabc_groups: []")
    if inspec_profile:
        lines.append(f"  sabc_inspec_profile: {_yaml_quote(inspec_profile)}")
    return "\n".join(lines) + "\n"


def render_classify_script(enc_dir: str) -> str:
    """Render the POSIX ENC executable the master runs per node.

    Puppet invokes ``external_nodes <certname>``; the script prints the matching
    per-node document, or the default when the node is unmanaged. Pure shell —
    no interpreter or parser dependency on the master.
    """
    d = enc_dir.rstrip("/")
    return (
        "#!/bin/sh\n"
        "# SABC Compliance — Puppet Core External Node Classifier.\n"
        "# Generated and deployed by the SABC Compliance platform. Do not edit.\n"
        'certname="$1"\n'
        "# Strip path separators defensively before building the path.\n"
        'safe=$(printf "%s" "$certname" | tr "/\\\\" "__")\n'
        f'node_file="{d}/nodes/${{safe}}.yaml"\n'
        f'default_file="{d}/default.yaml"\n'
        'if [ -n "$safe" ] && [ -f "$node_file" ]; then\n'
        '  cat "$node_file"\n'
        'elif [ -f "$default_file" ]; then\n'
        '  cat "$default_file"\n'
        "else\n"
        '  printf -- "---\\nenvironment: production\\nclasses: {}\\n"\n'
        "fi\n"
    )


def build_enc_artifacts(
    classifications: list[dict],
    enc_dir: str = "/etc/puppetlabs/puppet/enc",
    default_environment: str = "production",
) -> dict[str, str]:
    """Build all ENC files as a {relative_path: content} map.

    ``classifications`` is a list of dicts, one per managed node::

        {"certname": "web01.sabc.cm",
         "environment": "production",
         "groups": ["SABC Managed Nodes", "Ubuntu", "Ubuntu 22.04"],
         "inspec_profile": "sabc-linux-baseline"}

    Returns paths relative to ``enc_dir`` (``classify``, ``default.yaml`` and
    ``nodes/<certname>.yaml``) so the caller can write them anywhere.
    """
    artifacts: dict[str, str] = {}
    artifacts["classify"] = render_classify_script(enc_dir)
    artifacts["default.yaml"] = render_node_doc(default_environment, [], None)

    seen: set[str] = set()
    for c in classifications:
        certname = (c.get("certname") or "").strip()
        if not certname:
            continue
        fname = sanitize_certname(certname)
        # Guard against two certnames colliding after sanitisation.
        if fname in seen:
            continue
        seen.add(fname)
        artifacts[f"nodes/{fname}.yaml"] = render_node_doc(
            c.get("environment") or default_environment,
            c.get("groups") or [],
            c.get("inspec_profile"),
        )
    return artifacts


def puppet_conf_block(enc_dir: str) -> str:
    """The marker-delimited puppet.conf block enabling the exec ENC.

    Placed under [server] (puppetserver 6+/7 uses [server]; older [master] is
    still honoured, but [server] is the current section name).
    """
    d = enc_dir.rstrip("/")
    return (
        f"{PUPPET_CONF_BEGIN}\n"
        "[server]\n"
        "node_terminus = exec\n"
        f"external_nodes = {d}/classify\n"
        f"{PUPPET_CONF_END}\n"
    )
