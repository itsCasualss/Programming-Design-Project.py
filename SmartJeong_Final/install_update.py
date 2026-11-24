"""Copy this release into an existing project, preserving local settings/data."""
import argparse
from datetime import datetime
from pathlib import Path
import shutil


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('destination',type=Path)
    args=parser.parse_args();source=Path(__file__).resolve().parent;target=args.destination.expanduser().resolve()
    if source==target or source in target.parents or target in source.parents:
        raise SystemExit('Extract release beside the existing project, not inside it.')
    if not target.is_dir() or not (target/'main.py').exists():raise SystemExit('Destination must be the existing Briefing_Box_Project folder.')
    backup=target.parent/(target.name+'_backup_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    ignored=shutil.ignore_patterns('.venv','__pycache__','models','.git','logs','.lgd-nfy*')
    shutil.copytree(target,backup,ignore=ignored)
    for path in source.rglob('*'):
        relative=path.relative_to(source)
        if any(x in ('__pycache__','.venv','models','.git','logs') for x in relative.parts) or not path.is_file():continue
        dest=target/relative
        if dest.exists() and (relative.parts[0]=='data' or str(relative) in ('config.json','config.local.json')):continue
        dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,dest)
    print('Updated:',target,'\nBackup:',backup,'\nExisting config, data, models and virtual environment preserved.')

if __name__=='__main__':main()
