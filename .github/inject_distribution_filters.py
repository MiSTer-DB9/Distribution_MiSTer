#!/usr/bin/env python3
# [MiSTer-DB9 BEGIN] - per-fork DISTRIBUTION_FILTERS tag rewrite (Hook 3).
#
# Runs AFTER db_operator.py build emits dbencc.json and AFTER inject_unstable_tags.
# For every SYNCING_FORKS section in Forks.ini that declares a non-empty
# DISTRIBUTION_FILTERS key, overwrites the matching stable RBF entry's `tags`
# array with EXACTLY the tokens listed there. Path-derived tags db_operator may
# have added are dropped deliberately so default `filter = console` no longer
# pulls those entries — opt-in is via the declared tokens only (mirrors how
# inject_unstable_tags.py gates the unstable channel).
#
# Example Forks.ini stanza:
#   [PSX_DS_DB9]
#   RELEASE_CORE_NAME    = PSX_DualSDRAM
#   DISTRIBUTION_CATEGORY = _Console
#   DISTRIBUTION_FILTERS  = dualsdram dualsdram-psx
#
# _Unstable/* entries are skipped — the unstable hook owns those and asserts
# its own invariant on them.

import io
import json
import os
import re
import sys
import configparser

STABLE_ASSET_RE = re.compile(r'^(?P<core>.+?)_\d{8}_[0-9a-f]{7}(?:_DB9)?(?:\.[A-Za-z0-9]+)?$')

# Side channel from download_encc_distribution.py — already populated by the
# Hook 1 step (inject_unstable_files) so we don't re-fetch Forks.ini.
FORKS_JSON_CACHE = '/tmp/unstable_forks.json'


def load_forks():
    if os.path.isfile(FORKS_JSON_CACHE):
        with open(FORKS_JSON_CACHE) as f:
            return json.load(f)
    # Fallback for standalone invocations (manual reruns, local dev).
    try:
        import requests
    except ImportError:
        import subprocess
        subprocess.run([sys.executable, '-m', 'pip', 'install', 'requests'], check=True)
        import requests
    url = 'https://raw.githubusercontent.com/MiSTer-DB9/Forks_MiSTer/master/Forks.ini'
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    config = configparser.ConfigParser(inline_comment_prefixes=(';', '#'))
    config.read_file(io.StringIO(r.text))
    return {sec: dict(config.items(sec)) for sec in config.sections()}


def reserve_tag_id(tag_dict, name):
    if name in tag_dict:
        return tag_dict[name]
    next_id = (max(tag_dict.values()) + 1) if tag_dict else 0
    tag_dict[name] = next_id
    return next_id


def main(db_path):
    with open(db_path) as f:
        db = json.load(f)

    if 'files' not in db or 'tag_dictionary' not in db:
        print("::error::dbencc.json missing 'files' or 'tag_dictionary'")
        sys.exit(1)

    forks = load_forks()
    forks_list = forks.get('Forks', {}).get('syncing_forks', '').strip().split()
    if not forks_list:
        print('SYNCING_FORKS empty — nothing to filter.')
        return

    # release_core_name -> list of token ids (interned in tag_dictionary).
    core_to_token_ids = {}
    sections_with_filters = 0
    for fork_name in forks_list:
        section = forks.get(fork_name)
        if not section:
            print(f"::warning::{fork_name}: missing section in Forks.ini")
            continue
        release_core_name = section.get('release_core_name', '').strip()
        if not release_core_name:
            print(f"::warning::{fork_name}: missing release_core_name")
            continue
        tokens = section.get('distribution_filters', '').strip().split()
        if not tokens:
            continue
        if release_core_name in core_to_token_ids:
            print(f"::warning::duplicate release_core_name '{release_core_name}' across SYNCING_FORKS — last wins")
        core_to_token_ids[release_core_name] = [
            reserve_tag_id(db['tag_dictionary'], t) for t in tokens
        ]
        sections_with_filters += 1

    if not core_to_token_ids:
        print('No SYNCING_FORKS section declares DISTRIBUTION_FILTERS — nothing to rewrite.')
        return

    touched = 0
    for path, entry in db['files'].items():
        if path.startswith('_Unstable/'):
            continue
        basename = path.rsplit('/', 1)[-1]
        m = STABLE_ASSET_RE.match(basename)
        if not m:
            continue
        token_ids = core_to_token_ids.get(m.group('core'))
        if not token_ids:
            continue
        entry['tags'] = list(token_ids)
        touched += 1

    print(f"Distribution filters: {touched} entries rewritten across {sections_with_filters} section(s)")

    with open(db_path, 'w') as f:
        json.dump(db, f, sort_keys=True)


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print('Usage: inject_distribution_filters.py <path-to-dbencc.json>')
        sys.exit(2)
    main(sys.argv[1])
# [MiSTer-DB9 END]
