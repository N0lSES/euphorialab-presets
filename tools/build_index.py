#!/usr/bin/env python3
"""Validate every preset in presets/ and regenerate index.xml.

Run from the repo root:  python tools/build_index.py
Exit code 1 if any preset is invalid (the GitHub Action then fails and nothing is published).
"""
import os, sys, subprocess, datetime
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRESETS = os.path.join(ROOT, "presets")
MAX_BYTES = 2 * 1024 * 1024
PARAM_TYPES = {"Bool", "Int", "Float", "Vector", "String"}
NM_PARAM_TYPES = {"CNmParameterBool", "CNmParameterInt", "CNmParameterFloat", "CNmParameterVector",
                  "CNmParameterString", "CNmParameterRandomFloat", "CNmParameterRandomInt",
                  "CNmParameterResetMessage"}


def git_date(path):
    try:
        out = subprocess.check_output(["git", "log", "-1", "--format=%cI", "--", path], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()
        if out:
            return out
    except Exception:
        pass
    return datetime.datetime.fromtimestamp(os.path.getmtime(path), datetime.timezone.utc).replace(microsecond=0, tzinfo=None).isoformat() + "Z"


def text(el, tag, required=True, limit=300):
    v = (el.findtext(tag) or "").strip()
    if required and not v:
        raise ValueError(f"missing <{tag}>")
    if len(v) > limit:
        raise ValueError(f"<{tag}> is longer than {limit} characters")
    return v


def validate(path):
    if os.path.getsize(path) > MAX_BYTES:
        raise ValueError(f"file is larger than {MAX_BYTES // 1024} KB")
    root = ET.parse(path).getroot()
    if root.tag != "EuphoriaLabPreset":
        raise ValueError("root element must be <EuphoriaLabPreset>")
    if root.get("format") != "1":
        raise ValueError('format must be "1"')
    meta = {
        "name": text(root, "Name", limit=60),
        "author": text(root, "Author", limit=40),
        "description": text(root, "Description", required=False, limit=300),
        "modVersion": text(root, "ModVersion", required=False, limit=20),
        "tags": text(root, "Tags", required=False, limit=120),
    }
    stack, sets = root.find("Stack"), root.find("PhysicsSets")
    if (stack is None) == (sets is None):
        raise ValueError("a preset needs exactly one of <Stack> or <PhysicsSets>")
    if stack is not None:
        entries = stack.findall("Entry")
        if not entries:
            raise ValueError("<Stack> has no <Entry>")
        for e in entries:
            if not e.get("behavior"):
                raise ValueError("<Entry> without behavior")
            int(e.get("delay", "0"))
            for p in e.findall("Param"):
                if p.get("type") not in PARAM_TYPES or not p.get("name") or p.get("value") is None:
                    raise ValueError(f"bad <Param> in {e.get('behavior')}")
        meta["type"], meta["count"] = "stack", len(entries)
    else:
        all_sets = sets.findall("Set")
        if not all_sets:
            raise ValueError("<PhysicsSets> has no <Set>")
        for s in all_sets:
            if not s.get("task") or not s.get("label"):
                raise ValueError("<Set> needs task and label")
            msgs = s.find("Messages")
            if msgs is None:
                raise ValueError(f"set {s.get('label')} has no <Messages>")
            for m in msgs.findall("Item"):
                if m.get("type") != "CNmMessage" or not (m.findtext("Name") or "").strip():
                    raise ValueError(f"bad message in set {s.get('label')}")
                for p in m.find("Params") if m.find("Params") is not None else []:
                    if p.get("type") not in NM_PARAM_TYPES:
                        raise ValueError(f"unknown parameter type {p.get('type')}")
        meta["type"], meta["count"] = "physics", len(all_sets)
    return meta


def main():
    entries, errors = [], []
    for dirpath, _, files in os.walk(PRESETS):
        for f in sorted(files):
            if not f.lower().endswith(".elpreset"):
                continue
            full = os.path.join(dirpath, f)
            rel = os.path.relpath(full, ROOT).replace(os.sep, "/")
            try:
                meta = validate(full)
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
