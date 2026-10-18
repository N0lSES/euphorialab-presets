#!/usr/bin/env python3
"""Validate every preset in presets/ and regenerate index.xml.

A preset (.elpreset) is a copy of physicstasks.xml, with an optional comment at the top:
  <!-- EuphoriaLab preset
  name: My shots
  author: matt..
  description: ...
  modVersion: 1.5.0
  -->
Old-format presets (<EuphoriaLabPreset> with <PhysicsSets>) are still listed.

Run from the repo root:  python tools/build_index.py
Exit code 1 if any preset is invalid (the GitHub Action then fails and nothing is published).
"""
import os, re, sys, subprocess, datetime
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRESETS = os.path.join(ROOT, "presets")

MAX_BYTES = 2 * 1024 * 1024


class PresetError(Exception):
    pass


def _meta_comment(text):
    """name/author/description/modVersion from the '<!-- EuphoriaLab preset ... -->' comment."""
    meta = {}
    m = re.search(r"<!--(.*?)-->", text, re.S)
    if m and "euphorialab preset" in m.group(1).lower():
        for line in m.group(1).splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip().lower()] = v.strip()
    return meta


def _clip(v, limit):
    v = (v or "").strip()
    return v[:limit]


def parse_preset(data, filename="preset.elpreset", fallback_author="", allow_legacy=False):
    """Validate an .elpreset (a copy of physicstasks.xml). Returns metadata or raises PresetError."""
    if len(data) > MAX_BYTES:
        raise PresetError(f"file is larger than {MAX_BYTES // (1024 * 1024)} MB")
    if b"<!DOCTYPE" in data or b"<!ENTITY" in data:
        raise PresetError("DOCTYPE / ENTITY declarations are not allowed")
    try:
        root = ET.fromstring(data)
    except ET.ParseError as ex:
        raise PresetError(f"not valid XML ({ex})")
    text = data.decode("utf-8", "replace")
    if root.tag == "EuphoriaLabPreset" and allow_legacy:
        sets = root.find("PhysicsSets")
        if sets is None:
            raise PresetError("old-format preset without <PhysicsSets>")
        return {"name": _clip(root.findtext("Name"), 60) or "preset", "author": _clip(root.findtext("Author"), 40) or "unknown",
                "description": _clip(root.findtext("Description"), 300), "modVersion": _clip(root.findtext("ModVersion"), 20),
                "tags": "physics", "type": "physics", "count": len(sets.findall("Set"))}
    if root.tag != "CTuningFile":
        raise PresetError("a preset must be a copy of physicstasks.xml (root <CTuningFile>) - export it again from Euphoria Lab")
    tunables = root.find("Tunables")
    if tunables is None or not [i for i in tunables.findall("Item") if (i.get("type") or "").endswith("__Tunables")]:
        raise PresetError("no <Tunables> items - is this really physicstasks.xml?")
    filled = 0
    for task in tunables.findall("Item"):
        for s in task.iter("Messages"):
            items = s.findall("Item")
            for m in items:
                if m.get("type") != "CNmMessage" or not (m.findtext("Name") or "").strip():
                    raise PresetError("bad NM message (needs type CNmMessage and a <Name>)")
                params = m.find("Params")
                for p in (params if params is not None else []):
                    if not (p.get("type") or "").startswith("CNmParameter"):
                        raise PresetError(f"unknown parameter type {p.get('type')}")
            if items:
                filled += 1
    meta = _meta_comment(text)
    stem = re.sub(r"\.elpreset$", "", filename, flags=re.I)
    return {"name": _clip(meta.get("name") or stem.replace("_", " "), 60) or "preset",
            "author": _clip(meta.get("author") or fallback_author, 40) or "unknown",
            "description": _clip(meta.get("description"), 300),
            "modVersion": _clip(meta.get("modversion"), 20),
            "tags": "physics", "type": "physics", "count": filled}


def safe_name(s):
    s = re.sub(r"[^A-Za-z0-9_-]+", "_", s).strip("_")
    return (s or "preset")[:60]


def git_date(path):
    try:
        out = subprocess.check_output(["git", "log", "-1", "--format=%cI", "--", path], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()
        if out:
            return out
    except Exception:
        pass
    return datetime.datetime.fromtimestamp(os.path.getmtime(path), datetime.timezone.utc).replace(microsecond=0, tzinfo=None).isoformat() + "Z"


def main():
    entries, errors = [], []
    for dirpath, _, files in os.walk(PRESETS):
        for f in sorted(files):
            if not f.lower().endswith(".elpreset"):
                continue
            full = os.path.join(dirpath, f)
            rel = os.path.relpath(full, ROOT).replace(os.sep, "/")
            try:
                with open(full, "rb") as fh:
                    meta = parse_preset(fh.read(), f, "", allow_legacy=True)
            except Exception as ex:
                errors.append(f"{rel}: {ex}")
                continue
            meta["file"], meta["date"] = rel, git_date(full)
            entries.append(meta)
    if errors:
        print("Invalid presets:\n  " + "\n  ".join(errors))
        sys.exit(1)
    entries.sort(key=lambda e: e["date"], reverse=True)
    lines = ['<?xml version="1.0" encoding="utf-8"?>', '<EuphoriaLabIndex format="1" count="%d">' % len(entries)]
    for e in entries:
        attrs = " ".join('%s="%s"' % (k, escape(str(e[k]), {'"': "&quot;"}))
                         for k in ("type", "file", "date", "modVersion", "count"))
        lines.append("  <Preset %s>" % attrs)
        for k, tag in (("name", "Name"), ("author", "Author"), ("description", "Description"), ("tags", "Tags")):
            lines.append("    <%s>%s</%s>" % (tag, escape(e[k]), tag))
        lines.append("  </Preset>")
    lines.append("</EuphoriaLabIndex>")
    with open(os.path.join(ROOT, "index.xml"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"index.xml: {len(entries)} presets")


if __name__ == "__main__":
    main()
