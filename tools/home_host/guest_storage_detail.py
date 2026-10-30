"""Inspect disk blocks under fixed CI and model paths without reading source data."""
import collections
import json
import os
from pathlib import Path
import subprocess


def sizes(path, depth):
    if path.is_symlink() or not path.is_dir():
        return {}
    result = subprocess.run(['du','-x','-B1','--max-depth='+str(depth),'--',str(path)],capture_output=True,timeout=95)
    values = {}
    for line in result.stdout.splitlines():
        amount, separator, name = line.partition(b'\t')
        if separator and amount.isdigit():
            values[Path(os.fsdecode(name))] = int(amount)
    return values


if __name__ == '__main__':
    root = Path('/opt/analyst-ci/runs')
    inventory = sizes(root,2)
    prefixes, sections = collections.Counter(), collections.Counter()
    for p,v in inventory.items():
        if p.parent == root:
            prefixes[p.name.split('-')[0]] += v
        elif p.parent.parent == root:
            sections[p.name] += v
    found = {}
    for p in ['/home/analyst-ci/.cache/analyst-local-research','/opt/analyst-ci','/var/cache/apt/archives']:
        d=Path(p)
        try:
            found[p] = sizes(d,0).get(d)
        except subprocess.TimeoutExpired:
            found[p] = None
    stat=os.statvfs('/')
    print(json.dumps({'runs_total':inventory.get(root),'prefixes':prefixes,'sections':dict(sections.most_common(20)),
                      'known':found,'guest_used':(stat.f_blocks-stat.f_bfree)*stat.f_frsize}))
