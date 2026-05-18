#!/usr/bin/env python3
# dbencc default_options.filter (Hook 6).
#
# Runs AFTER db_operator.py build. db_operator leaves `default_options` absent;
# the MiSTer Downloader applies a DB's default_options.filter ONLY when the
# user has set no `filter` for this DB in downloader.ini. Users who configured
# a filter (e.g. `filter = console`) are unaffected — unstable / dualsdram /
# jtbeta entries are already opt-in for them via the tag system (those entries
# carry only `unstable*` / `dualsdram*` / `jtbeta` tags, no `console`/path
# tags). This hook only fixes the no-filter cohort, who would otherwise get
# nightly unstable builds, Dual-SDRAM variants and jotego's beta-key-gated
# MRAs all mixed into the stable set.
#
# Mirrors jotego's own `default_options: {filter: "[MiSTer] !jtbeta"}` and
# completes the opt-in model the inject_unstable_tags / inject_distribution_
# filters / inject_jtbindb_tags hooks already imply: each token stays opt-in
# (set `filter = ... unstable` / `dualsdram` / `jtbeta` to pull them back in).

import json
import sys

DEFAULT_FILTER = '!unstable !jtbeta !dualsdram'


def main(db_path):
    with open(db_path) as f:
        db = json.load(f)

    opts = db.get('default_options')
    if not isinstance(opts, dict):
        opts = {}
    opts['filter'] = DEFAULT_FILTER
    db['default_options'] = opts

    print(f"default_options.filter set to {DEFAULT_FILTER!r}")

    with open(db_path, 'w') as f:
        json.dump(db, f, sort_keys=True)


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print('Usage: inject_default_options.py <path-to-dbencc.json>')
        sys.exit(2)
    main(sys.argv[1])
