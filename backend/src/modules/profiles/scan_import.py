"""
Parse the bundled CIS .rb profile controls and match them to
referential profile controls by CIS ID prefix + title keywords.
Used by the "Import Scan Commands" action in the UI.
"""
from __future__ import annotations
import glob
import os
import re

_SCAN_PROFILES_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "..",
    "scan-profiles", "sabc-linux-baseline", "controls",
)


def _apply_ruby_tr(s: str, expr: str) -> str:
    """Evaluate .tr('x','y') Ruby string method in a Python context."""
    for src, dst in re.findall(r"\.tr\('([^']*)', '([^']*)'\)", expr):
        for i, c in enumerate(src):
            s = s.replace(c, dst[i] if i < len(dst) else "")
    return s


def _expand_interp(template: str, bindings: dict) -> str:
    """Expand #{ruby_expr} in a Ruby string template using simple bindings."""
    def repl(m):
        expr = m.group(1)
        if expr in bindings:
            return str(bindings[expr])
        for var, val in bindings.items():
            if expr.startswith(var):
                return _apply_ruby_tr(val, expr[len(var):])
        return m.group(0)
    return re.sub(r"#\{([^}]+)\}", repl, template)


def _extract_from_content(content: str) -> dict[str, dict]:
    """Return {control_id: {code, cis_tag}} for all controls in one .rb file."""
    out: dict[str, dict] = {}

    def _add(ctrl_id: str, code: str) -> None:
        tag = re.search(r"tag cis: '([^']+)'", code)
        out[ctrl_id] = {"code": code, "cis_tag": tag.group(1) if tag else None}

    # 1. Static / literal control blocks
    for m in re.finditer(
        r"^(control (?:'|\")([^'\"]+)(?:'|\") do\n(?:(?!^end\b)[\s\S])*?^end)",
        content, re.MULTILINE,
    ):
        ctrl_id = m.group(2)
        if "#{" not in ctrl_id:
            _add(ctrl_id, m.group(1))

    # 2. %w(...).each do |var|  control "tmpl-#{var}" do ... end  end
    for m in re.finditer(
        r"%w\(([^)]+)\)\.each do \|(\w+)\|\n(.*?)^end",
        content, re.MULTILINE | re.DOTALL,
    ):
        items = m.group(1).split()
        var   = m.group(2)
        inner = m.group(3)
        ctrl_tmpl = re.search(
            r'control "([^"]+)" do\n(.*?)^  end', inner, re.MULTILINE | re.DOTALL
        )
        if not ctrl_tmpl:
            continue
        for item in items:
            ctrl_id = _expand_interp(ctrl_tmpl.group(1), {var: item})
            body    = (
                f'control "{ctrl_id}" do\n'
                + _expand_interp(ctrl_tmpl.group(2), {var: item})
                + "  end\nend"
            )
            _add(ctrl_id, body)

    # 3. {...}.each do |key, val|  control "tmpl#{key.method}" do ... end  end
    for m in re.finditer(
        r"\{((?:[^{}]|\n)*)\}\.each do \|(\w+),\s*(\w+)\|\n(.*?)^end",
        content, re.MULTILINE | re.DOTALL,
    ):
        hash_str = m.group(1)
        key_var  = m.group(2)
        val_var  = m.group(3)
        inner    = m.group(4)
        entries  = re.findall(r"'([^']+)'\s*=>\s*%w\(([^)]*)\)", hash_str)
        if not entries:
            entries = [(k, v) for k, v in re.findall(r"'([^']+)'\s*=>\s*'([^']*)'", hash_str)]
        ctrl_tmpl = re.search(
            r'control "([^"]+)" do\n(.*?)^  end', inner, re.MULTILINE | re.DOTALL
        )
        if not ctrl_tmpl:
            continue
        for key, val in entries:
            ctrl_id = _expand_interp(ctrl_tmpl.group(1), {key_var: key, val_var: val})
            body    = (
                f'control "{ctrl_id}" do\n'
                + _expand_interp(ctrl_tmpl.group(2), {key_var: key, val_var: val})
                + "  end\nend"
            )
            _add(ctrl_id, body)

    return out


def load_all_scan_controls() -> dict[str, dict]:
    """Load and parse all .rb control files from the bundled CIS profile."""
    all_controls: dict[str, dict] = {}
    rb_dir = os.path.normpath(_SCAN_PROFILES_DIR)
    for fpath in sorted(glob.glob(os.path.join(rb_dir, "*.rb"))):
        try:
            content = open(fpath, encoding="utf-8").read()
            all_controls.update(_extract_from_content(content))
        except Exception:
            pass
    return all_controls


def match_controls(
    scan_controls: dict[str, dict],
    seed_controls: list[dict],
) -> dict[str, str]:
    """
    Return {seed_control_id -> scan_code} for best-matching pairs.

    Matching rules (in order):
      1. seed.cis_id starts with scan control's cis_tag (or equals it)
      2. At least one keyword from the scan control_id appears in seed.title
    When multiple controls match one seed control, the first (by sort
    order) wins so that the most specific match takes precedence.
    """
    result: dict[str, str] = {}

    for ctrl_id in sorted(scan_controls):
        scan = scan_controls[ctrl_id]
        cis_tag = scan["cis_tag"]
        if not cis_tag:
            continue

        # Keywords: strip the "cis-N.N.N-" prefix from the control ID
        cis_prefix_dash = "cis-" + cis_tag.replace(".", "-") + "-"
        keyword_part = ctrl_id.replace(cis_prefix_dash, "", 1) if ctrl_id.startswith(cis_prefix_dash) else ""
        keywords = [k for k in re.split(r"[-_]", keyword_part) if len(k) > 2]

        for sc in seed_controls:
            seed_cis = (sc.get("cis_id") or "").strip()
            if not (seed_cis == cis_tag or seed_cis.startswith(cis_tag + ".")):
                continue
            title_lower = (sc.get("title") or "").lower()
            if keywords and not any(kw.lower() in title_lower for kw in keywords):
                continue
            sc_id = sc["id"]
            if sc_id not in result:
                result[sc_id] = scan["code"]

    return result
