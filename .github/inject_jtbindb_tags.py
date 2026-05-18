#!/usr/bin/env python3
# jtbindb tag splice (Hook 5).
#
# Runs AFTER db_operator.py build emits dbencc.json. download_encc_distribution.
# fetch_jotego_bundles() drives the whole jt file/MRA/_alternatives set from
# jotego's authoritative jtbindb.json (overlaying our DB9 rebuild where we have
# one). db_operator then re-derives path tags for those files, which would pull
# jt into the default `filter = console` and lose jotego's curated taxonomy
# (`jtbeta`, controls_*, ...). This hook restores jotego's exact tags.
#
# Input side channel: /tmp/jtbindb_slice.json, written by fetch_jotego_bundles:
#   { "by_path": { "<dbencc rel_path>": ["<jotego tag name>", ...], ... } }
# Keyed by the rel_path we actually produced on disk (the DB9 rebuild's
# <stem>_<YYYYMMDD>_<sha7>_DB9.rbf for cores we rebuilt, jotego's bare
# canonical path otherwise; MRAs/_alternatives keep their jtbindb rel_path).
#
# This replaces the old negative jotego-skip path in inject_stable_clean_slugs
# (Hook 4): with tags positively reasserted here, there is nothing to skip.

import json
import sys

SLICE_PATH = '/tmp/jtbindb_slice.json'


def reserve_tag_id(tag_dict, name):
    if name in tag_dict:
        return tag_dict[name]
    next_id = (max(tag_dict.values()) + 1) if tag_dict else 0
    tag_dict[name] = next_id
    return next_id


def main(db_path):
    try:
        with open(SLICE_PATH) as f:
            slice_data = json.load(f)
    except (OSError, ValueError) as e:
        print(f"::warning::cannot read {SLICE_PATH} ({e}) — "
              f"no jtbindb tags to apply")
        return

    by_path = slice_data.get('by_path', {})
    if not by_path:
        print('jtbindb slice empty — nothing to splice.')
        return

    with open(db_path) as f:
        db = json.load(f)

    if 'files' not in db or 'tag_dictionary' not in db:
        print("::error::dbencc.json missing 'files' or 'tag_dictionary'")
        sys.exit(1)

    tag_dict = db['tag_dictionary']
    touched = missing = 0
    for path, names in by_path.items():
        entry = db['files'].get(path)
        if entry is None:
            missing += 1
            continue
        entry['tags'] = [reserve_tag_id(tag_dict, n) for n in names]
        touched += 1

    print(f"jtbindb tags: {touched} entr(y/ies) rewritten, "
          f"{missing} slice path(s) absent from dbencc "
          f"(expected for filtered/beta cores not shipped)")

    with open(db_path, 'w') as f:
        json.dump(db, f, sort_keys=True)


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print('Usage: inject_jtbindb_tags.py <path-to-dbencc.json>')
        sys.exit(2)
    main(sys.argv[1])
