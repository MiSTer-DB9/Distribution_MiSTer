#!/usr/bin/env python3
# Unstable channel tag rewrite (Hook 2).
#
# Runs AFTER db_operator.py build emits dbencc.json. Walks every file entry
# whose path matches `_Unstable/_<CoreDir>/.*_unstable_<ts>_<sha>.rbf` (per-
# variant subdir layout mirroring the fork's `unstable-builds` Release),
# overwrites its `tags` array with ['unstable', 'unstable-<slug>'] followed by
# one `unstable-<token>` per token in the section's DISTRIBUTION_FILTERS (the
# same key the stable hook reads — reused here, `unstable-` prefixed so the
# unstable channel stays isolated and the all-tags-start-with-unstable
# invariant holds), and extends the tag_dictionary. Path-derived tags
# db_operator may have added are dropped deliberately so `filter = console`
# does not pull in unstable consoles — opt-in is via explicit `unstable*`
# tokens only (e.g. `filter = !unstable unstable-dualsdram`).

import io
import json
import os
import re
import sys
import configparser

# Extension is optional so Main_MiSTer's HPS binary (`MiSTer_unstable_<ts>_<sha7>`,
# no extension) is tagged alongside FPGA cores' `*.rbf`.
UNSTABLE_ASSET_RE = re.compile(r'^(?P<core>.+?)_unstable_\d{8}_\d{4}_[0-9a-f]{7}(?:_DB9)?(?:\.[A-Za-z0-9]+)?$')
UNSTABLE_PATH_RE = re.compile(r'^_Unstable/_[^/]+/(?P<filename>[^/]+)$')

# Side channel from download_encc_distribution.py — set by the Hook 1 step so
# Hook 2 doesn't re-fetch Forks.ini over the network.
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

def slugify(release_core_name):
    return re.sub(r'[^a-z0-9]', '', release_core_name.lower())

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
    unstable_list = forks.get('Forks', {}).get('unstable_forks', '').strip().split()
    if not unstable_list:
        print('UNSTABLE_FORKS empty — nothing to inject.')
        return

    core_to_slug = {}
    core_to_filters = {}  # release_core_name -> ['dualsdram', ...] (raw tokens)
    seen_slugs = {}
    for fork_name in unstable_list:
        section = forks.get(fork_name)
        if not section:
            print(f"::warning::{fork_name}: missing section in Forks.ini")
            continue
        release_core_name = section.get('release_core_name', '').strip()
        if not release_core_name:
            print(f"::warning::{fork_name}: missing release_core_name")
            continue
        slug = slugify(release_core_name)
        if slug in seen_slugs and seen_slugs[slug] != fork_name:
            print(f"::error::slug collision '{slug}' between {seen_slugs[slug]} and {fork_name}")
            sys.exit(1)
        seen_slugs[slug] = fork_name
        core_to_slug[release_core_name] = slug
        # Reuse the stable hook's DISTRIBUTION_FILTERS key. Tokens are NOT
        # slugified — only `unstable-` prefixed below — so hyphens survive
        # (`dualsdram-saturn` -> `unstable-dualsdram-saturn`).
        tokens = section.get('distribution_filters', '').strip().split()
        if tokens:
            core_to_filters[release_core_name] = tokens

    unstable_id = reserve_tag_id(db['tag_dictionary'], 'unstable')
    slug_ids = {slug: reserve_tag_id(db['tag_dictionary'], f'unstable-{slug}')
                for slug in core_to_slug.values()}
    # release_core_name -> ordered list of `unstable-<token>` tag ids.
    filter_ids = {
        core: [reserve_tag_id(db['tag_dictionary'], f'unstable-{t}') for t in tokens]
        for core, tokens in core_to_filters.items()
    }

    touched = unmatched = 0
    inverse = None  # lazy-built for invariant pass

    for path, entry in db['files'].items():
        m = UNSTABLE_PATH_RE.match(path)
        if not m:
            continue
        am = UNSTABLE_ASSET_RE.match(m.group('filename'))
        if not am:
            print(f"::warning::{path}: filename does not match _unstable_ pattern")
            unmatched += 1
            continue
        core = am.group('core')
        slug = core_to_slug.get(core)
        if not slug:
            # Stale entry: fork removed from UNSTABLE_FORKS but file still on
            # disk from a prior run. Leave tags alone so the downloader still
            # serves it; warn so maintainer notices.
            print(f"::warning::{path}: core '{core}' not in UNSTABLE_FORKS — leaving tags as db_operator emitted")
            unmatched += 1
            continue
        tags = [unstable_id, slug_ids[slug]]
        # Append DISTRIBUTION_FILTERS-derived ids; de-dup defensively so a
        # token colliding with the slug can't double-list.
        for fid in filter_ids.get(core, []):
            if fid not in tags:
                tags.append(fid)
        entry['tags'] = tags
        touched += 1

    # Invariant: every _Unstable/*.rbf this hook touched must now lead with
    # ['unstable', 'unstable-<slug>'] and carry only `unstable`-prefixed tags
    # (the optional DISTRIBUTION_FILTERS-derived tail is `unstable-` prefixed
    # too). Fails loud if upstream db_operator behavior on _Unstable/ ever
    # drifts. Stale entries (core not in UNSTABLE_FORKS) are left as-is above,
    # so skip them here too.
    inverse = {v: k for k, v in db['tag_dictionary'].items()}
    bad = []
    for path, entry in db['files'].items():
        m = UNSTABLE_PATH_RE.match(path)
        if not m:
            continue
        am = UNSTABLE_ASSET_RE.match(m.group('filename'))
        slug = core_to_slug.get(am.group('core')) if am else None
        if not slug:
            continue
        tags = entry.get('tags', [])
        names = [inverse.get(t, f'?{t}') for t in tags]
        if (len(tags) < 2
                or names[0] != 'unstable'
                or names[1] != f'unstable-{slug}'
                or not all(n.startswith('unstable') for n in names)):
            bad.append((path, names))
    if bad:
        print('::error::Unstable tag invariant violated:')
        for p, n in bad:
            print(f"  {p}: tags={n}")
        sys.exit(1)

    print(f"Unstable tag rewrite: {touched} touched, {unmatched} unmatched")

    with open(db_path, 'w') as f:
        json.dump(db, f, sort_keys=True)

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print('Usage: inject_unstable_tags.py <path-to-dbencc.json>')
        sys.exit(2)
    main(sys.argv[1])
