#!/usr/bin/env python3
# Copyright (c) 2022 José Manuel Barroso Galindo <theypsilon@gmail.com>

import json
import re
import time
import sys
import shutil
import io
import os
import sys
import zipfile
import tempfile
import datetime
import configparser
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import subprocess
try:
    import httpimport
    import requests
except ImportError as _:
    subprocess.run(['python3', '-m', 'pip', 'install', 'requests', 'httpimport==1.3.1'])
    import httpimport
    import requests

download_distribution = httpimport.load('download_distribution', 'https://raw.githubusercontent.com/MiSTer-devel/Distribution_MiSTer/main/.github')

def main():

    start = time.time()

    cores = download_distribution.fetch_cores()
    extra_content_urls = download_distribution.fetch_extra_content_urls()
    extra_content_categories = download_distribution.classify_extra_content(extra_content_urls)
    forks = fetch_forks()

    print(f'Cores {len(cores)}:')
    print(cores)
    print()

    download_distribution.validate_cores(cores)

    print(f'Extra Content URLs {len(extra_content_urls)}:')
    print(extra_content_urls)
    print()

    download_distribution.validate_extra_content_urls(extra_content_urls)

    print('Extra Content Categories:')
    print(extra_content_categories)
    print()

    print('Forks:')
    print(forks)
    print()

    inject_fork_only_cores(cores, forks)

    replace_urls(cores, extra_content_categories, forks)

    cores = filter_dead_cores(cores)

    target_dir = download_distribution.read_target_dir()
    download_distribution.process_all(extra_content_categories, cores, target_dir)

    fetch_jotego_bundles(forks, target_dir)

    # [MiSTer-DB9 BEGIN] - overlay v2 forks' newest stable release asset onto whatever
    # process_all() pulled from the (possibly stale) legacy releases/ dir.
    inject_stable_files(target_dir, forks)

    # [MiSTer-DB9 BEGIN] - unstable channel: download newest *_unstable_*.rbf
    # from each UNSTABLE_FORKS entry's "unstable-builds" GitHub Release into
    # target_dir/_Unstable/<flat filename>. Tag rewriting happens later via
    # inject_unstable_tags.py after db_operator.py build.
    inject_unstable_files(target_dir, forks)
    # Forward the parsed Forks.ini to inject_unstable_tags.py so it does not
    # re-fetch the same file mid-workflow (avoids a split-brain race if
    # Forks.ini changes between the two scripts).
    with open(UNSTABLE_FORKS_JSON_PATH, 'w') as f:
        json.dump(forks, f)
    # [MiSTer-DB9 END]

    print()
    print("Time:")
    end = time.time()
    print(end - start)
    print()

def filter_dead_cores(cores):
    # Drop cores whose repo URL returns 404. Upstream Cores.md is
    # hand-maintained and occasionally references a deleted/renamed repo,
    # which would abort the whole pipeline at git-clone time. Skipping
    # them with a loud GitHub Actions warning keeps the rest shipping
    # while leaving the regression visible.
    def probe(core):
        repo_url = core['url'].split('/tree/')[0]
        try:
            r = requests.head(repo_url, allow_redirects=True, timeout=15)
            return core, r.status_code != 404
        except requests.RequestException:
            return core, True

    with ThreadPoolExecutor(max_workers=16) as ex:
        results = list(ex.map(probe, cores))

    surviving = []
    for core, alive in results:
        if alive:
            surviving.append(core)
        else:
            print(f"::warning::Dropping dead core {core['name']!r} ({core['url']}) - repo returned 404")
    dropped = len(cores) - len(surviving)
    if dropped:
        print(f"Filtered {dropped} dead core(s); {len(surviving)} remain.")
    return surviving

def fetch_forks():
    with io.StringIO(download_distribution.fetch_text('https://raw.githubusercontent.com/MiSTer-DB9/Forks_MiSTer/master/Forks.ini')) as buf:
        config = configparser.ConfigParser(inline_comment_prefixes=(';','#'))
        config.read_file(buf)
        forks = {}
        for sec in config.sections():
            forks[sec] = {}
            for key, val in config.items(sec):
                forks[sec][key] = val
        return forks

def inject_fork_only_cores(cores, forks):
    # Synthesize cores-list entries for any [*_DB9] section that opts in via
    # DISTRIBUTION_CATEGORY. Covers two cases that upstream Cores.md doesn't list:
    #   (a) non-master branch of an upstream core (e.g. GBA accuracy)
    #   (b) repos that exist only under MiSTer-DB9 (no upstream counterpart;
    #       UPSTREAM_REPO empty)
    # Synthesized URL points at the fork repo directly so replace_urls leaves
    # it untouched.
    # Dedup keyed on (url, release_core_name): variants that share a fork_repo
    # + main_branch (e.g. Saturn / Saturn_DualSDRAM, both in MiSTer-DB9/Saturn_MiSTer
    # on `main`) get distinct cores entries because their release_core_name differs.
    # The url-only short-circuit (`fork_repo.lower() in existing`) is dropped so
    # a fork-only variant can ride alongside an already-replaced upstream entry.
    existing_keys = {(c['url'].lower(), c.get('name', '').lower()) for c in cores}
    injected = 0
    for fork in forks['Forks']['syncing_forks'].split(' '):
        section = forks[fork]
        category = section.get('distribution_category', '').strip()
        if not category:
            continue
        main_branch = section['main_branch']
        fork_repo = str(Path(section['fork_repo']).with_suffix("")).replace('https:/g', 'https://g')
        url = f"{fork_repo}/tree/{main_branch}"
        release_name = section['release_core_name']
        key = (url.lower(), release_name.lower())
        if key in existing_keys:
            print(f"Skipping {fork} fork-only injection: (url,name) already in cores list ({url}, {release_name})")
            continue
        cores.append({
            'name': release_name,
            'url': url,
            'home': section.get('distribution_home', release_name).strip() or release_name,
            'comments': '',
            'category': category,
        })
        existing_keys.add(key)
        injected += 1
        print(f"Injected fork-only core: {fork} → {url} as '{release_name}' (category={category})")
    if injected:
        print(f"Injected {injected} fork-only core(s).")

# [MiSTer-DB9 BEGIN] - unstable channel file delivery (Hook 1).
# Matches filenames produced by Forks_MiSTer/fork_ci_template/.github/unstable_release.sh.
# Extension is optional so Main_MiSTer's HPS binary (`MiSTer_unstable_<ts>_<sha7>`,
# no extension) is matched alongside FPGA cores' `*.rbf`.
UNSTABLE_ASSET_RE = re.compile(r'^.*_unstable_\d{8}_\d{4}_[0-9a-f]{7}(?:_DB9)?(?:\.[A-Za-z0-9]+)?$')
UNSTABLE_TAG_NAME = 'unstable-builds'
UNSTABLE_FORKS_JSON_PATH = '/tmp/unstable_forks.json'
# Side-channel slice of jotego's authoritative jtbindb manifest produced this
# run: { "by_path": { produced_rel_path: [tag-name, ...] } }. Consumed by
# inject_jtbindb_tags.py (Hook 5) which restores jotego's curated tag taxonomy
# onto the jt entries db_operator emitted (whose path-derived tags would
# otherwise pull jt into default `filter = console` and lose `!jtbeta`).
JTBINDB_SLICE_JSON_PATH = '/tmp/jtbindb_slice.json'
# jotego's official MiSTer Downloader database — single source of truth for the
# jt file/MRA/alternatives/tag set. Overridable per-section via JTBINDB_URL.
JTBINDB_DEFAULT_URL = 'https://raw.githubusercontent.com/jotego/jtcores_mister/main/jtbindb.json.zip'
# jtbindb keys arcade files under this prefix; our on-disk layout mirrors it.
ARCADE_PREFIX = '_Arcade/'
JOTEGO_ASSET_NAME = 'jtcores-mister-db9.zip'
# jtcores nightly release encodes the source commit in its tag (`mister-<sha>`);
# the body's `Built from `<sha>`` line is the fallback when the tag is renamed.
JOTEGO_TAG_SHA_RE = re.compile(r'^mister-([0-9a-f]{7,40})$')
JOTEGO_BODY_SHA_RE = re.compile(r'Built from `([0-9a-f]{40})`')

def _parse_fork_repo(url):
    """Extract (owner, name) from FORK_REPO URL. Mirrors the regex used in
    setup_cicd.sh / sync_unstable.sh."""
    m = re.match(r'^(?:[a-zA-Z]+://)?github\.com(?::\d+)?/([a-zA-Z0-9_-]+)/([a-zA-Z0-9_-]+)(?:\.[a-zA-Z0-9]+)?$', url)
    return (m.group(1), m.group(2)) if m else (None, None)

def _github_api_headers():
    """GitHub REST headers, with the optional GITHUB_TOKEN bearer applied."""
    token = os.environ.get('GITHUB_TOKEN', '').strip()
    headers = {'Accept': 'application/vnd.github+json'}
    if token:
        headers['Authorization'] = f'token {token}'
    return headers

def _stream_to_file(url, out_path, fork_name, what, *, headers=None,
                     allow_redirects=False, mkdir=False):
    """Stream `url` to `out_path` in 1 MiB chunks. On RequestException the
    partial file is unlinked and False returned; True on success. `what` is
    the noun phrase used in the failure log line."""
    out_path = Path(out_path)
    try:
        with requests.get(url, headers=headers, stream=True, timeout=120,
                          allow_redirects=allow_redirects) as r:
            r.raise_for_status()
            if mkdir:
                out_path.parent.mkdir(parents=True, exist_ok=True)
            with open(out_path, 'wb') as fh:
                for chunk in r.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        fh.write(chunk)
    except requests.RequestException as e:
        print(f"::warning::{fork_name}: {what}: {e}")
        try:
            out_path.unlink()
        except OSError:
            pass
        return False
    return True

def _download_asset(asset, out_path, headers, fork_name):
    """Stream a GH release `asset` to `out_path`. See _stream_to_file."""
    dl_url = asset.get('browser_download_url') or asset.get('url')
    return _stream_to_file(dl_url, out_path, fork_name,
                           f"download failed for {asset['name']}",
                           headers=headers)

def _fetch_one_unstable(fork_name, section, out_dir, headers):
    owner, name = _parse_fork_repo(section.get('fork_repo', ''))
    if not owner:
        print(f"::warning::{fork_name}: malformed fork_repo — skipping")
        return

    release_core_name = section.get('release_core_name', '').strip()
    if not release_core_name:
        print(f"::warning::{fork_name}: missing release_core_name — skipping")
        return
    # Multi-branch forks (GBA: master/GBA2P/accuracy, X68000: master/USERIO2)
    # share one `unstable-builds` release with one RBF per variant; filter
    # by this variant's RELEASE_CORE_NAME prefix so each section sees only
    # its own variant's RBFs instead of all sections collapsing onto the
    # globally-newest assets.
    asset_prefix = f"{release_core_name}_unstable_"

    rel_url = f'https://api.github.com/repos/{owner}/{name}/releases/tags/{UNSTABLE_TAG_NAME}'
    try:
        r = requests.get(rel_url, headers=headers, timeout=30)
    except requests.RequestException as e:
        print(f"::warning::{fork_name}: release lookup failed: {e}")
        return
    if r.status_code == 404:
        print(f"{fork_name}: no '{UNSTABLE_TAG_NAME}' release yet — skipping (first build not run)")
        return
    if r.status_code != 200:
        print(f"::warning::{fork_name}: release API returned {r.status_code} — skipping")
        return

    assets = r.json().get('assets', []) or []
    candidates = [a for a in assets
                  if a.get('name', '').startswith(asset_prefix)
                  and UNSTABLE_ASSET_RE.match(a.get('name', ''))]
    if not candidates:
        print(f"::warning::{fork_name}: '{UNSTABLE_TAG_NAME}' has no {asset_prefix}* asset — skipping")
        return
    candidates.sort(key=lambda a: a.get('created_at', ''), reverse=True)

    # Per-variant subdir under _Unstable/ — RELEASE_CORE_NAME is unique
    # across Forks.ini (collision would already break fork-side asset
    # naming), so this is a safe key. Leading underscore matches MiSTer
    # convention for utility dirs that sort to the top of file listings.
    variant_dir = out_dir / f"_{release_core_name}"
    variant_dir.mkdir(parents=True, exist_ok=True)

    keep = set()
    fetched = skipped = 0
    for asset in candidates:
        keep.add(asset['name'])
        out_path = variant_dir / asset['name']
        # Skip re-download if the file is already in place with the same
        # byte size. RBF names embed timestamp+sha7, so identical name +
        # size = identical content; spares the GitHub raw-content bandwidth
        # on every distribution rebuild.
        expected_size = asset.get('size')
        if (out_path.exists() and expected_size is not None
                and out_path.stat().st_size == expected_size):
            skipped += 1
            continue
        if not _download_asset(asset, out_path, headers, fork_name):
            keep.discard(asset['name'])
            continue
        fetched += 1
        print(f"{fork_name}: fetched _Unstable/_{release_core_name}/{asset['name']} ({asset.get('size','?')} bytes)")

    # Sweep stale assets in this variant's subdir — anything no longer in
    # the fork's Release (pruned by unstable_release.sh's RETENTION cap)
    # gets dropped from the distribution too. Scope is one subdir per call
    # so a misconfigured fork can't cause cross-core deletions. Filter on
    # UNSTABLE_ASSET_RE (not glob) so extension-less Main_MiSTer binaries
    # are swept alongside *.rbf, and stray non-asset files are ignored.
    deleted = 0
    for stale in variant_dir.iterdir():
        if not stale.is_file() or not UNSTABLE_ASSET_RE.match(stale.name):
            continue
        if stale.name not in keep:
            try:
                stale.unlink()
                deleted += 1
                print(f"{fork_name}: pruned _Unstable/_{release_core_name}/{stale.name} (not in current Release set)")
            except OSError as e:
                print(f"::warning::{fork_name}: failed to prune {stale.name}: {e}")
    print(f"{fork_name}: _Unstable/_{release_core_name}/ — fetched={fetched} skipped={skipped} deleted={deleted} kept={len(keep)}")

def inject_unstable_files(target_dir, forks):
    """For each fork in Forks[UNSTABLE_FORKS], mirror the fork's
    `unstable-builds` Release into target_dir/_Unstable/_<RELEASE_CORE_NAME>/
    in parallel — up to the newest 7 retained RBFs per variant land on the
    SD card so users have a local rollback set without browsing GitHub.
    Stale RBFs in each variant's subdir are pruned to track Release state."""
    raw = forks.get('Forks', {}).get('unstable_forks', '').strip()
    if not raw:
        print('UNSTABLE_FORKS empty — skipping unstable file injection.')
        return
    unstable_list = raw.split()
    print(f"Unstable forks ({len(unstable_list)}): {unstable_list}")

    out_dir = Path(target_dir) / '_Unstable'
    out_dir.mkdir(parents=True, exist_ok=True)

    headers = _github_api_headers()

    tasks = []
    for fork_name in unstable_list:
        section = forks.get(fork_name)
        if not section:
            print(f"::warning::{fork_name}: section missing in Forks.ini — skipping")
            continue
        tasks.append((fork_name, section))

    # Parallel fetch — matches the ThreadPoolExecutor pattern used by
    # filter_dead_cores() above.
    with ThreadPoolExecutor(max_workers=16) as ex:
        list(ex.map(lambda t: _fetch_one_unstable(t[0], t[1], out_dir, headers), tasks))
# [MiSTer-DB9 END]


# [MiSTer-DB9 BEGIN] - stable channel file delivery (companion to inject_unstable_files).
# Each variant publishes per-commit immutable tags `stable/<MAIN_BRANCH>/<YYYYMMDD>-<sha7>`,
# one GitHub Release per tag. Matches the new `<Core>_<YYYYMMDD>_<sha7>_DB9.<ext>`
# form, the prior `<Core>_<YYYYMMDD>_<sha7>.<ext>` form (for assets predating the
# `_DB9` marker rollout), and the pre-rework legacy `<Core>_<YYYYMMDD>.<ext>` so
# any stale legacy file in the SD-card category dir gets replaced on overlay.
STABLE_ASSET_RE_TAIL = re.compile(r'_\d{8}(?:_[0-9a-f]{7})?(?:_DB9)?(?:\.[A-Za-z0-9]+)?$')

def _build_category_index(target_dir):
    """One-shot scan of target_dir, keyed by '<core>_YYYYMMDD[_<sha7>]'-shaped basenames.
    Replaces a per-fork rglob; at ~140 forks × ~5k tree entries this is the
    difference between O(forks × tree) and O(tree)."""
    index = {}
    for p in Path(target_dir).rglob('*'):
        if not p.is_file():
            continue
        name = p.name
        m = STABLE_ASSET_RE_TAIL.search(name)
        if not m:
            continue
        core = name[:m.start()]
        index.setdefault(core, []).append(p)
    return index

def _fetch_one_stable(fork_name, section, category_index, headers, target_dir):
    owner, name = _parse_fork_repo(section.get('fork_repo', ''))
    if not owner:
        print(f"::warning::{fork_name}: malformed fork_repo — skipping stable")
        return

    release_core_name = section.get('release_core_name', '').strip()
    if not release_core_name:
        print(f"::warning::{fork_name}: missing release_core_name — skipping stable")
        return
    main_branch = section.get('main_branch', '').strip()
    if not main_branch:
        print(f"::warning::{fork_name}: missing main_branch — skipping stable")
        return

    # Mirror upstream `install_arcade_core()` (download_distribution.py:378
    # `latest_release.replace("Arcade-", "")`): arcade RBFs land on SD
    # without the `Arcade-` repo-name prefix, so both the category-index
    # lookup and the on-SD filename must use the stripped form.
    sd_core_name = release_core_name[len('Arcade-'):] if release_core_name.startswith('Arcade-') else release_core_name

    tag_prefix = f'stable/{main_branch}/'
    asset_re = re.compile(rf'^{re.escape(release_core_name)}_\d{{8}}_[0-9a-f]{{7}}(?:_DB9)?(?:\.[A-Za-z0-9]+)?$')

    release = None
    page = 1
    while True:
        list_url = f'https://api.github.com/repos/{owner}/{name}/releases?per_page=100&page={page}'
        try:
            r = requests.get(list_url, headers=headers, timeout=30)
        except requests.RequestException as e:
            print(f"::warning::{fork_name}: stable release listing failed: {e}")
            return
        if r.status_code != 200:
            print(f"::warning::{fork_name}: releases API returned {r.status_code} — skipping stable")
            return

        releases = r.json()
        if not releases:
            break

        matches = [rel for rel in releases
                   if isinstance(rel, dict)
                   and rel.get('tag_name', '').startswith(tag_prefix)]
        if matches:
            matches.sort(key=lambda rel: rel.get('created_at', ''), reverse=True)
            release = matches[0]
            break
        page += 1

    if not release:
        print(f"{fork_name}: no '{tag_prefix}*' release yet — leaving process_all output in place")
        return
    release_tag = release.get('tag_name', '?')

    assets = release.get('assets', []) or []
    candidates = [a for a in assets if asset_re.match(a.get('name', ''))]
    if not candidates:
        print(f"::warning::{fork_name}: release {release_tag} has no {release_core_name}_YYYYMMDD_<sha7>.* asset — skipping")
        return
    asset = candidates[0]

    # Placement fallback when `category_index` has no entry for `release_core_name`
    # (no sibling RBF dropped by upstream `process_all` we can overlay onto):
    #   - DISTRIBUTION_OVERLAY_DIR: for sections shipped via upstream's *extras*
    #     path (e.g. Main_DB9, menu_DB9 → install_main_binary drops bare MiSTer /
    #     menu.rbf at SD root). Read-only by this script; does NOT trigger
    #     inject_fork_only_cores so the section is not synthesised as a core
    #     (which would crash in upstream `process_core` on Main/Menu).
    #   - DISTRIBUTION_CATEGORY: for fork-only cores (PSX_DS, Saturn_DS). Both
    #     synthesises a cores entry (inject_fork_only_cores) AND drives v2
    #     overlay placement here. Kept for backward compat.
    explicit_category = (section.get('distribution_overlay_dir', '').strip()
                        or section.get('distribution_category', '').strip())
    existing = category_index.get(sd_core_name) or []
    # Disambiguate when multiple unrelated forks collapse onto the same
    # `sd_core_name` after the `Arcade-` strip (e.g. Astrocade: the Bally
    # Pro Arcade machine `[Arcade_Astrocade_DB9]` and the Bally home
    # console `[Astrocade_DB9]`). Mirror upstream's routing so each fork
    # claims only the index entries its upstream sibling would have placed:
    #   install_arcade_core (download_distribution.py:378) → _Arcade/cores/
    #   impl_install_generic_core (line 403)               → Cores.md category dir
    if len(existing) > 1:
        is_arcade_section = release_core_name.startswith('Arcade-')
        existing = [p for p in existing
                    if (p.parent.name == 'cores') == is_arcade_section]
    if existing:
        category_dir = existing[0].parent
        for old in existing:
            if old.parent == category_dir:
                try:
                    old.unlink()
                except OSError:
                    pass
    elif explicit_category:
        category_dir = Path(target_dir) / explicit_category
        category_dir.mkdir(parents=True, exist_ok=True)
        print(f"{fork_name}: no process_all placement for {sd_core_name}_*.* (release {release_core_name}) — using overlay dir '{explicit_category}'")
    else:
        print(f"::warning::{fork_name}: process_all did not place any {sd_core_name}_*.* (release {release_core_name}) and no DISTRIBUTION_OVERLAY_DIR / DISTRIBUTION_CATEGORY set — skipping")
        return

    # DISTRIBUTION_FILENAME override: write asset under a fixed on-SD name
    # instead of `<core>_<date>_<sha7>.<ext>`. Used by Main_DB9 to keep the
    # MiSTer binary at SD root as bare `MiSTer` (matching upstream layout
    # and avoiding `MiSTer_<date>_<sha7>` accumulating next to bare `MiSTer`
    # that `process_all` already placed there). The dated/sha-stamped name
    # remains visible on the GitHub Release for provenance.
    # Default on-SD filename uses `sd_core_name` so arcade overlays land
    # as `<Game>_<date>_<sha7>.<ext>` to match upstream's prefix-stripped
    # placement (asset_re at the top guarantees `asset['name']` starts
    # with `release_core_name`, so swapping the prefix is safe).
    default_name = sd_core_name + asset['name'][len(release_core_name):]
    rename_to = section.get('distribution_filename', '').strip() or default_name
    out_path = category_dir / rename_to
    if not _download_asset(asset, out_path, headers, fork_name):
        return
    src_label = asset['name'] if rename_to == asset['name'] else f"{asset['name']} → {rename_to}"
    print(f"{fork_name}: replaced {category_dir.name}/{rename_to} from {release_tag} ({src_label}, {asset.get('size','?')} bytes)")

def inject_stable_files(target_dir, forks):
    raw = forks.get('Forks', {}).get('syncing_forks', '').strip()
    if not raw:
        print('SYNCING_FORKS empty — skipping stable file injection.')
        return
    stable_forks = raw.split()
    print(f"Stable forks ({len(stable_forks)}): {stable_forks}")

    headers = _github_api_headers()

    category_index = _build_category_index(target_dir)

    tasks = []
    for fork_name in stable_forks:
        section = forks.get(fork_name)
        if not section:
            print(f"::warning::{fork_name}: section missing in Forks.ini — skipping")
            continue
        tasks.append((fork_name, section))

    with ThreadPoolExecutor(max_workers=16) as ex:
        list(ex.map(lambda t: _fetch_one_stable(t[0], t[1], category_index, headers, target_dir), tasks))
# [MiSTer-DB9 END]


def replace_urls(cores, extra_content_categories, forks):
    replacements = {}
    for fork in forks['Forks']['syncing_forks'].split(' '):
        main_branch = forks[fork]['main_branch']
        upstream_raw = forks[fork].get('upstream_repo', '').strip()
        if not upstream_raw:
            continue
        upstream_repo = str(Path(upstream_raw).with_suffix("")).replace('https:/g', 'https://g')
        fork_repo = str(Path(forks[fork]['fork_repo']).with_suffix("")).replace('https:/g', 'https://g')
        replacements[upstream_repo.lower()] = fork_repo
        replacements[f"{upstream_repo}/tree/{main_branch}".lower()] = f"{fork_repo}/tree/{main_branch}"

    for core in cores:
        lower = core['url'].lower()
        if lower in replacements and 'menu_mister' not in lower:
            print(f'Replaced core: {core["url"]} = {replacements[lower]}')
            core['url'] = replacements[lower]

    for key in list(extra_content_categories):
        if not isinstance(key, str):
            continue
        lower = key.lower()
        if lower in replacements:
            print(f'Replaced extra content: {replacements[lower]} = {key}')
            extra_content_categories[replacements[lower]] = extra_content_categories[key]
            del extra_content_categories[key]

# [MiSTer-DB9 BEGIN] - jotego/jtcores: jtbindb-driven jt distribution
# (single source of truth = jotego's official jtbindb.json; we overlay our
# DB9 rebuild where available, jotego's official binary otherwise).
def _resolve_jtcores_db9_zip(fork_name, cfg):
    """Resolve the MiSTer-DB9/jtcores release zip URL + its source sha7 from the
    SAME release: a static releases/latest/download URL would race a release
    published between the metadata read and the download, mismatching the sha7
    baked into the filename against the bytes actually shipped."""
    url = cfg.get('release_url', '').strip()
    sha7 = ''
    dl_url = url
    owner, name = _parse_fork_repo(cfg.get('fork_repo', ''))
    if owner:
        rel_url = f'https://api.github.com/repos/{owner}/{name}/releases/latest'
        try:
            rr = requests.get(rel_url, headers=_github_api_headers(), timeout=30)
            if rr.status_code == 200:
                rel = rr.json()
                m = (JOTEGO_TAG_SHA_RE.match(rel.get('tag_name', '') or '')
                     or JOTEGO_BODY_SHA_RE.search(rel.get('body', '') or ''))
                if m:
                    sha7 = m.group(1)[:7]
                for asset in rel.get('assets', []) or []:
                    if asset.get('name') == JOTEGO_ASSET_NAME:
                        dl_url = asset.get('browser_download_url') or url
                        break
            else:
                print(f"::warning::{fork_name}: releases/latest API returned "
                      f"{rr.status_code} — falling back to RELEASE_URL, no sha7")
        except requests.RequestException as e:
            print(f"::warning::{fork_name}: releases/latest API failed ({e}) "
                  f"— falling back to RELEASE_URL, no sha7")
    else:
        print(f"::warning::{fork_name}: malformed/absent FORK_REPO — cannot "
              f"derive sha7, falling back to RELEASE_URL")
    if not sha7:
        print(f"::warning::{fork_name}: could not derive jtcores sha7 — RBF "
              f"names will lack the _<sha7> field this run")
    return dl_url, sha7


def _http_to_file(url, out_path, fork_name):
    """jotego-fallback download (unauthenticated, follows redirects, creates
    parents). See _stream_to_file."""
    return _stream_to_file(url, out_path, fork_name,
                           f"fallback download failed for {url}",
                           allow_redirects=True, mkdir=True)


def fetch_jotego_bundles(forks, target_dir):
    """Single-source-of-truth jt distribution.

    jotego's official jtbindb.json (his MiSTer Downloader database) is the
    authoritative manifest for the jt file / MRA / _alternatives / tag set.
    For every entry in it we:

      - RBF we rebuilt with DB9MD/Saturn/key-gate → write our DB9 build to
        _Arcade/cores/jt<core>_<YYYYMMDD>_<sha7>_DB9.rbf. The date+sha7+_DB9
        name is the fork-wide convention and makes MiSTer get_rbf()'s
        lexicographic pick favour this over jotego's bare jt<core>.rbf
        ('.'(0x2E) < '_'(0x5F)); rel_path differs from jtbindb's so the
        Downloader never flags a dedup collision (unchanged from before).
      - RBF jotego ships but we did not rebuild → jotego's official binary
        from jtbindb's (SHA-pinned) base_files_url, at its bare canonical
        rel_path.
      - MRA / _alternatives → taken from our DB9 zip when present (jotego-
        built, already local), else jotego's base_files_url. Subtree
        preserved so _Arcade/_alternatives/_<Core>/<v>.mra is not flattened.

    Tags are taken verbatim from jtbindb and reapplied to dbencc.json by
    inject_jtbindb_tags.py (Hook 5), so jotego-added games/cores and his
    curated filter taxonomy (`!jtbeta`, controls_*, ...) flow through with no
    parallel definition to maintain here. Appended after process_all() so the
    upstream-driven download stays the source of truth for non-jt content.
    """
    target_dir = Path(target_dir)
    arcade_dir = target_dir / '_Arcade'
    cores_dir = arcade_dir / 'cores'
    by_path = {}  # produced_rel_path -> [jotego tag name, ...] for Hook 5

    for fork_name, cfg in forks.items():
        if cfg.get('is_jotego_bundle', '').strip().lower() != 'true':
            continue

        # --- jotego's authoritative manifest -------------------------------
        jtbindb_url = cfg.get('jtbindb_url', '').strip() or JTBINDB_DEFAULT_URL
        try:
            jr = requests.get(jtbindb_url, timeout=120, allow_redirects=True)
            jr.raise_for_status()
        except requests.RequestException as e:
            print(f"::error::{fork_name}: failed to fetch jtbindb "
                  f"{jtbindb_url}: {e}")
            continue
        try:
            with zipfile.ZipFile(io.BytesIO(jr.content)) as jz:
                jname = next((n for n in jz.namelist()
                              if n.endswith('.json')), None)
                if jname is None:
                    print(f"::error::{fork_name}: no .json inside jtbindb zip")
                    continue
                jtbindb = json.loads(jz.read(jname))
        except (zipfile.BadZipFile, ValueError) as e:
            print(f"::error::{fork_name}: cannot parse jtbindb zip: {e}")
            continue

        base_url = jtbindb.get('base_files_url', '')
        if base_url and not base_url.endswith('/'):
            base_url += '/'
        jt_files = jtbindb.get('files', {})
        id_to_name = {v: k for k, v
                      in jtbindb.get('tag_dictionary', {}).items()}

        def names_for(meta):
            return sorted({id_to_name[i] for i in meta.get('tags', [])
                           if i in id_to_name})

        # --- our DB9 rebuild zip (DB9MD/Saturn/key-gate; still required) ----
        dl_url, sha7 = _resolve_jtcores_db9_zip(fork_name, cfg)
        if not dl_url:
            print(f"::warning::{fork_name}: IS_JOTEGO_BUNDLE without a "
                  f"resolvable RELEASE_URL — skipping")
            continue
        print(f"Fetching jotego DB9 bundle '{fork_name}' from {dl_url}"
              f"{f' (sha7 {sha7})' if sha7 else ''}")
        try:
            resp = requests.get(dl_url, timeout=600, stream=True,
                                allow_redirects=True)
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"::error::{fork_name}: failed to fetch {dl_url}: {e}")
            continue

        date_stamp = datetime.datetime.now().strftime('%Y%m%d')
        last_modified = resp.headers.get('Last-Modified', '')
        if last_modified:
            try:
                date_stamp = datetime.datetime.strptime(
                    last_modified, '%a, %d %b %Y %H:%M:%S %Z'
                ).strftime('%Y%m%d')
            except ValueError:
                pass
        infix = f"{date_stamp}_{sha7}" if sha7 else date_stamp

        with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp:
            for chunk in resp.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    tmp.write(chunk)
            zip_path = tmp.name

        cores_dir.mkdir(parents=True, exist_ok=True)
        arcade_dir.mkdir(parents=True, exist_ok=True)

        rbfs = mras = fb_rbfs = fb_files = 0
        fallbacks = []  # (url, out_path, rel_path, tagnames, is_rbf)
        try:
            with zipfile.ZipFile(zip_path) as zf:
                def _extract(member, out):
                    out.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(member) as src, open(out, 'wb') as dst:
                        shutil.copyfileobj(src, dst)

                # Index the DB9 build: jt<core>.rbf by stem, mra subtree by the
                # path below release/mra/ (mirrors jtbindb's _Arcade/ layout).
                db9_rbf = {}   # stem -> zip member
                db9_mra = {}   # 'Foo.mra' / '_alternatives/_X/y.mra' -> member
                for member in zf.namelist():
                    if member.endswith('/'):
                        continue
                    parts = Path(member).parts
                    nm = Path(member).name
                    parent = '/' + Path(member).parent.as_posix()
                    if nm.endswith('.rbf') and '/mister' in parent:
                        db9_rbf[Path(nm).stem] = member
                    elif nm.endswith('.mra') and 'mra' in parts:
                        rel = Path(*parts[parts.index('mra') + 1:]).as_posix()
                        db9_mra[rel] = member

                # Phase 1: copy what the DB9 build provides straight out of the
                # zip (zf is not thread-safe, so these stay sequential — local
                # extraction is fast). Anything jotego ships that our DB9 build
                # lacks is queued for a parallel fallback download (phase 2).
                for rel_path, meta in jt_files.items():
                    nm = rel_path.rsplit('/', 1)[-1]
                    tagnames = names_for(meta)
                    is_rbf = nm.endswith('.rbf')
                    if is_rbf and nm[:-4] in db9_rbf:
                        out = cores_dir / f"{nm[:-4]}_{infix}_DB9.rbf"
                        _extract(db9_rbf[nm[:-4]], out)
                        rbfs += 1
                        by_path[out.relative_to(target_dir).as_posix()] = tagnames
                        continue
                    if not is_rbf:
                        sub = (rel_path[len(ARCADE_PREFIX):]
                               if rel_path.startswith(ARCADE_PREFIX)
                               else rel_path)
                        if sub in db9_mra:
                            _extract(db9_mra[sub], target_dir / rel_path)
                            mras += 1
                            by_path[rel_path] = tagnames
                            continue
                    fallbacks.append((base_url + rel_path,
                                      target_dir / rel_path,
                                      rel_path, tagnames, is_rbf))

                # Phase 2: jotego-fallback downloads in parallel (mirrors the
                # ThreadPoolExecutor pattern inject_stable_files uses for bulk
                # network I/O). by_path is folded in from the main thread as
                # results arrive, so it is never shared across workers.
                if fallbacks:
                    def _fb(job):
                        url, out, rel_path, tagnames, is_rbf = job
                        return (rel_path, tagnames, is_rbf,
                                _http_to_file(url, out, fork_name))
                    with ThreadPoolExecutor(max_workers=16) as ex:
                        for rel_path, tagnames, is_rbf, ok in ex.map(
                                _fb, fallbacks):
                            if not ok:
                                continue
                            by_path[rel_path] = tagnames
                            if is_rbf:
                                fb_rbfs += 1
                            else:
                                fb_files += 1
        finally:
            try:
                os.unlink(zip_path)
            except OSError:
                pass

        if rbfs == 0 and fb_rbfs == 0:
            print(f"::warning::{fork_name}: no jt*.rbf produced from jtbindb")
        print(f"{fork_name}: {rbfs} DB9 RBF, {fb_rbfs} jotego-fallback RBF, "
              f"{mras} MRA (DB9 zip), {fb_files} jotego-fallback file(s) into "
              f"{arcade_dir}")

    # Side-channel slice for inject_jtbindb_tags.py (Hook 5). Written
    # unconditionally (even when empty) so a stale prior-run slice never
    # leaks into Hook 5.
    try:
        with open(JTBINDB_SLICE_JSON_PATH, 'w') as f:
            json.dump({'by_path': by_path}, f)
    except OSError as e:
        print(f"::warning::failed to write {JTBINDB_SLICE_JSON_PATH}: {e}")
# [MiSTer-DB9 END]


if __name__ == '__main__':
    main()
