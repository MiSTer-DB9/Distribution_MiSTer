#!/usr/bin/env python3
# Stable channel per-game slug cleanup (Hook 4).
#
# Runs AFTER db_operator.py build emits dbencc.json, AFTER inject_unstable_tags
# (Hook 2) and AFTER inject_distribution_filters (Hook 3).
#
# Upstream db_operator's `split_on_date()` only strips a 9-char `_<YYYYMMDD>`
# tail before deriving the per-RBF "core" tag via `Tags._clean_term(nodates)`.
# Fork stable RBFs land as `<core>_<YYYYMMDD>_<sha7>_DB9.<ext>` (the trailing
# `_DB9` is appended by `release.sh` for end-user provenance), so split_on_date
# fails to match → `nodates` = whole stem → the resulting tag bakes in the
# date / sha7 / DB9 suffix. Example: `_Arcade/cores/Arkanoid_20260502_9246dfe_DB9.rbf`
# gets tagged `arcadearkanoid202605029246dfedb9` instead of `arcadearkanoid`.
#
# This hook walks every stable fork RBF entry, removes the polluted tag id
# from `entry['tags']`, and appends the canonical `slugify(release_core_name)`
# id (matching the convention used by inject_unstable_tags.py for the unstable
# channel). All other tags db_operator emitted (`cores`, `arcade-rbfs-only`,
# category like `console`) are preserved so default `filter = console` still
# pulls fork stable consoles.
#
# The polluted names this hook replaced are dropped from `tag_dictionary` in a
# second pass (db_operator's `_used` set is finalised at build time, so without
# explicit pruning they would linger in the dict forever). Only those names are
# pruned; see the pass 2 comment for why a full reachability sweep is unsafe.
#
# Sections that declare DISTRIBUTION_FILTERS are skipped: Hook 3 already
# replaced their `entry['tags']` with explicit tokens; the polluted tag id
# has already been dropped from those entries.
#
# `_Unstable/*` entries are skipped: Hook 2 owns those and asserts its own
# invariant.
#
# Once upstream `MiSTer-devel/Distribution_MiSTer` extends `split_on_date()`
# to also strip `_<sha7>_DB9` (or equivalent), this hook degrades to a no-op
# (pass 1 finds zero polluted tags) and can be removed.

import io
import json
import os
import re
import sys
import configparser

# Mandatory `_DB9` anchor: this hook only ever touches fork-built stable RBFs.
STABLE_ASSET_RE = re.compile(r'^(?P<core>.+?)_\d{8}_[0-9a-f]{7}_DB9(?:\.[A-Za-z0-9]+)?$')

# Side channel from download_encc_distribution.py — already populated by the
# Hook 1 step (inject_unstable_files) so we don't re-fetch Forks.ini.
FORKS_JSON_CACHE = '/tmp/unstable_forks.json'

# jt cores are no longer special-cased here: download_encc_distribution.
# fetch_jotego_bundles() now drives the jt set from jotego's jtbindb and
# inject_jtbindb_tags.py (Hook 5) positively reasserts jotego's tags, so there
# is nothing for this hook to skip.


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


# Mirrors upstream db_operator.Tags._clean_term (db_operator.py line 658-667):
#   1. drop spaces
#   2. keep only [-_a-z0-9.]
#   3. strip `-` and `_`
# Caller passes an already-lowercased term (matches db_operator's path:
# `path.stem.lower()` feeds `nodates` which feeds `_clean_term`).
_CLEAN_ALLOWED = set('abcdefghijklmnopqrstuvwxyz0123456789-_.')


def clean_term(term):
    kept = ''.join(c for c in term.replace(' ', '') if c in _CLEAN_ALLOWED)
    return kept.replace('-', '').replace('_', '')


def main(db_path):
    with open(db_path) as f:
        db = json.load(f)

    if 'files' not in db or 'tag_dictionary' not in db:
        print("::error::dbencc.json missing 'files' or 'tag_dictionary'")
        sys.exit(1)

    forks = load_forks()
    forks_list = forks.get('Forks', {}).get('syncing_forks', '').strip().split()
    if not forks_list:
        print('SYNCING_FORKS empty — nothing to clean.')
        return

    # Build the core_key -> clean_slug map. Two distinct keys point at the same
    # slug for arcade sections, because `_fetch_one_stable` strips the
    # `Arcade-` prefix when placing the file on disk (matches upstream
    # `install_arcade_core`'s `latest_release.replace("Arcade-", "")`):
    #   release_core_name = `Arcade-Arkanoid`  → STABLE_ASSET_RE.group('core') on disk = `Arkanoid`
    #   release_core_name = `Arcade-Astrocade` → on-disk core = `Astrocade`
    #   release_core_name = `NES`              → on-disk core = `NES` (no strip)
    core_to_slug = {}
    hook3_owned = set()  # core_keys whose entry['tags'] was rewritten by Hook 3
    seen_slugs = {}
    skipped_filtered = 0
    for fork_name in forks_list:
        section = forks.get(fork_name)
        if not section:
            print(f"::warning::{fork_name}: missing section in Forks.ini")
            continue
        release_core_name = section.get('release_core_name', '').strip()
        if not release_core_name:
            print(f"::warning::{fork_name}: missing release_core_name")
            continue
        # Sections owned by Hook 3 — they already replaced entry['tags']
        # with explicit DISTRIBUTION_FILTERS tokens; the polluted tag was
        # dropped along with everything else. Track core_keys so pass 1
        # can silently skip the matching files instead of warning about
        # them as orphans.
        if section.get('distribution_filters', '').strip():
            skipped_filtered += 1
            hook3_owned.add(release_core_name)
            if release_core_name.startswith('Arcade-'):
                hook3_owned.add(release_core_name[len('Arcade-'):])
            continue
        slug = slugify(release_core_name)
        if slug in seen_slugs and seen_slugs[slug] != fork_name:
            print(f"::error::slug collision '{slug}' between {seen_slugs[slug]} and {fork_name}")
            sys.exit(1)
        seen_slugs[slug] = fork_name
        # release_core_name as-is and the Arcade- stripped form both map to
        # the same clean slug. Distinct sections with overlapping stripped
        # forms (e.g. `Arcade-Astrocade` vs `Astrocade`) are caught by the
        # slug-collision guard above because their slugs differ.
        core_to_slug[release_core_name] = slug
        if release_core_name.startswith('Arcade-'):
            core_to_slug.setdefault(release_core_name[len('Arcade-'):], slug)

    if not core_to_slug:
        print('No SYNCING_FORKS section to clean (all filtered or empty).')
        return

    # Pass 1: rewrite polluted tag id → clean slug id on each matching file.
    touched = 0
    unmatched_core = 0
    missing_polluted = 0
    affected = []  # [(path, polluted_id, clean_id)] for the invariant assertion
    for path, entry in db['files'].items():
        if path.startswith('_Unstable/'):
            continue
        basename = path.rsplit('/', 1)[-1]
        m = STABLE_ASSET_RE.match(basename)
        if not m:
            continue
        core_key = m.group('core')
        if core_key in hook3_owned:
            # Hook 3 already rewrote entry['tags']; the polluted tag is gone.
            continue
        slug = core_to_slug.get(core_key)
        if not slug:
            print(f"::warning::{path}: core '{core_key}' has no SYNCING_FORKS section — skipping")
            unmatched_core += 1
            continue

        stem = basename.rsplit('.', 1)[0].lower()
        # Mirror db_operator's parent-segment derivation (db_operator.py
        # line 426-430): take path.parts[0], strip leading `_`/`|`, lowercase.
        parent = path.split('/', 1)[0].lstrip('_|').lower()
        if parent == 'arcade' or stem.startswith('arcade-'):
            polluted_term = clean_term('arcade-' + stem)
        else:
            polluted_term = clean_term(stem)

        polluted_id = db['tag_dictionary'].get(polluted_term)
        if polluted_id is None:
            clean_id_existing = db['tag_dictionary'].get(slug)
            if clean_id_existing is not None and clean_id_existing in entry.get('tags', []):
                # Already cleaned (idempotent rerun on the same db, or upstream
                # fixed split_on_date and the entry happens to land on the same
                # slug). Quiet skip.
                missing_polluted += 1
                continue
            # Polluted tag absent AND clean slug not yet on the entry. Either
            # upstream db_operator emits a different polluted shape now (fix
            # the heuristic) or some intermediary already mangled the entry.
            # Don't blindly append the slug — surface the drift loudly.
            print(f"::warning::{path}: expected polluted tag '{polluted_term}' not in tag_dictionary — leaving entry as-is")
            missing_polluted += 1
            continue

        clean_id = reserve_tag_id(db['tag_dictionary'], slug)
        entry['tags'] = [t for t in entry.get('tags', []) if t != polluted_id]
        if clean_id not in entry['tags']:
            entry['tags'].append(clean_id)
        affected.append((path, polluted_id, clean_id))
        touched += 1

    # Pass 2: prune the polluted tag names this hook just replaced, and only
    # those.
    #
    # Deliberately NOT a whole-dictionary reachability sweep. Such a sweep has
    # to enumerate every place a tag id can be referenced, and db_operator keeps
    # moving those places: `summary_file_content` is stripped out of the db into
    # external `<archive_id>_summary.json.zip` files, and upstream renamed the
    # `zips` section to `archives` (2026-07), which silently turned the sweep's
    # summary walk into a no-op. The sweep then deleted every id referenced only
    # from an archive summary (Filters / Shadow_Masks / fonts / mra_alternatives),
    # and the next CI run, whose `get_url_db()` repopulates those summaries from
    # their external URLs, died inside `mut_diff_db` with `KeyError: 428`.
    #
    # Pruning only the ids we removed ourselves needs no knowledge of the db
    # schema. Leftover unreferenced names elsewhere are harmless (a filter term
    # that matches nothing); a MISSING name is what breaks the db.
    used = set()
    for entry in db.get('files', {}).values():
        used.update(entry.get('tags', []) or [])
    for entry in db.get('folders', {}).values():
        used.update(entry.get('tags', []) or [])

    inverse = {v: k for k, v in db['tag_dictionary'].items()}
    pruned = 0
    for polluted_id in {pid for _, pid, _ in affected}:
        if polluted_id in used:
            continue
        name = inverse.get(polluted_id)
        if name is not None:
            del db['tag_dictionary'][name]
            pruned += 1

    # Pass 3: invariant assertion. Every entry we touched must now carry the
    # clean slug id and none of the polluted id. Fails loud on drift so the
    # next CI run surfaces an upstream-behavior change immediately.
    bad = []
    for path, polluted_id, clean_id in affected:
        tags = db['files'][path].get('tags', [])
        if clean_id not in tags or polluted_id in tags:
            bad.append((path, polluted_id, clean_id, tags))
    if bad:
        print('::error::Stable slug-cleanup invariant violated:')
        for p, pid, cid, tags in bad:
            print(f"  {p}: polluted_id={pid} clean_id={cid} tags={tags}")
        sys.exit(1)

    print(
        f"Stable slug cleanup: {touched} entries rewritten, "
        f"{pruned} orphan tag(s) pruned "
        f"({skipped_filtered} section(s) deferred to Hook 3, "
        f"{unmatched_core} file(s) with no SYNCING_FORKS section, "
        f"{missing_polluted} file(s) with no polluted tag to remove)"
    )

    with open(db_path, 'w') as f:
        json.dump(db, f, sort_keys=True)


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print('Usage: inject_stable_clean_slugs.py <path-to-dbencc.json>')
        sys.exit(2)
    main(sys.argv[1])
