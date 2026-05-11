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
    existing = {c['url'].lower() for c in cores}
    injected = 0
    for fork in forks['Forks']['syncing_forks'].split(' '):
        section = forks[fork]
        category = section.get('distribution_category', '').strip()
        if not category:
            continue
        main_branch = section['main_branch']
        fork_repo = str(Path(section['fork_repo']).with_suffix("")).replace('https:/g', 'https://g')
        url = f"{fork_repo}/tree/{main_branch}"
        if url.lower() in existing or fork_repo.lower() in existing:
            print(f"Skipping {fork} fork-only injection: URL already in cores list ({url})")
            continue
        release_name = section['release_core_name']
        cores.append({
            'name': section.get('distribution_name', release_name).strip() or release_name,
            'url': url,
            'home': section.get('distribution_home', release_name).strip() or release_name,
            'comments': '',
            'category': category,
        })
        existing.add(url.lower())
        injected += 1
        print(f"Injected fork-only core: {fork} → {url} (category={category})")
    if injected:
        print(f"Injected {injected} fork-only core(s).")

# [MiSTer-DB9 BEGIN] - unstable channel file delivery (Hook 1).
# Matches filenames produced by Forks_MiSTer/fork_ci_template/.github/unstable_release.sh.
UNSTABLE_ASSET_RE = re.compile(r'^.*_unstable_\d{8}_\d{4}_[0-9a-f]{7}\.rbf$')
UNSTABLE_TAG_NAME = 'unstable-builds'
UNSTABLE_FORKS_JSON_PATH = '/tmp/unstable_forks.json'

def _parse_fork_repo(url):
    """Extract (owner, name) from FORK_REPO URL. Mirrors the regex used in
    setup_cicd.sh / sync_unstable.sh."""
    m = re.match(r'^(?:[a-zA-Z]+://)?github\.com(?::\d+)?/([a-zA-Z0-9_-]+)/([a-zA-Z0-9_-]+)(?:\.[a-zA-Z0-9]+)?$', url)
    return (m.group(1), m.group(2)) if m else (None, None)

def _fetch_one_unstable(fork_name, section, out_dir, headers):
    owner, name = _parse_fork_repo(section.get('fork_repo', ''))
    if not owner:
        print(f"::warning::{fork_name}: malformed fork_repo — skipping")
        return

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
    candidates = [a for a in assets if UNSTABLE_ASSET_RE.match(a.get('name', ''))]
    if not candidates:
        print(f"::warning::{fork_name}: '{UNSTABLE_TAG_NAME}' has no *_unstable_*.rbf asset — skipping")
        return
    candidates.sort(key=lambda a: a.get('created_at', ''), reverse=True)
    asset = candidates[0]

    dl_url = asset.get('browser_download_url') or asset.get('url')
    out_path = out_dir / asset['name']
    try:
        with requests.get(dl_url, headers=headers, stream=True, timeout=120) as dr:
            dr.raise_for_status()
            with open(out_path, 'wb') as fh:
                for chunk in dr.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        fh.write(chunk)
    except requests.RequestException as e:
        print(f"::warning::{fork_name}: download failed for {asset['name']}: {e}")
        try:
            out_path.unlink()
        except OSError:
            pass
        return
    print(f"{fork_name}: fetched _Unstable/{asset['name']} ({asset.get('size','?')} bytes)")

def inject_unstable_files(target_dir, forks):
    """For each fork in Forks[UNSTABLE_FORKS], download the newest unstable
    RBF asset into target_dir/_Unstable/<filename> in parallel. Flat folder
    layout mirrors MiSTer-unstable-nightlies's _Unstable/ convention."""
    raw = forks.get('Forks', {}).get('unstable_forks', '').strip()
    if not raw:
        print('UNSTABLE_FORKS empty — skipping unstable file injection.')
        return
    unstable_list = raw.split()
    print(f"Unstable forks ({len(unstable_list)}): {unstable_list}")

    out_dir = Path(target_dir) / '_Unstable'
    out_dir.mkdir(parents=True, exist_ok=True)

    token = os.environ.get('GITHUB_TOKEN', '').strip()
    headers = {'Accept': 'application/vnd.github+json'}
    if token:
        headers['Authorization'] = f'token {token}'

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

def fetch_jotego_bundles(forks, target_dir):
    """For each Forks.ini section with IS_JOTEGO_BUNDLE = true, download the
    GH release ZIP at RELEASE_URL and unpack it into the distribution:

      release/mister/jt<core>.rbf  → <target>/_Arcade/cores/<core>_<YYYYMMDD>.rbf
      release/mra/<game>.mra        → <target>/_Arcade/<game>.mra

    The date stamp comes from the ZIP's HTTP Last-Modified header so reruns
    are stable as long as the underlying release is unchanged. Bundles are
    intentionally appended after process_all() so the upstream-driven
    download stays the source of truth for non-jotego content; jotego
    cores live alongside the MiSTer-devel arcade lineup, never replacing
    a same-named upstream core (none exist).
    """
    target_dir = Path(target_dir)
    arcade_dir = target_dir / '_Arcade'
    cores_dir = arcade_dir / 'cores'
    for fork_name, cfg in forks.items():
        if cfg.get('is_jotego_bundle', '').strip().lower() != 'true':
            continue
        url = cfg.get('release_url', '').strip()
        if not url:
            print(f"::warning::{fork_name}: IS_JOTEGO_BUNDLE without RELEASE_URL — skipping")
            continue
        print(f"Fetching jotego bundle '{fork_name}' from {url}")
        try:
            resp = requests.get(url, timeout=600, stream=True, allow_redirects=True)
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"::error::{fork_name}: failed to fetch {url}: {e}")
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

        with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp:
            for chunk in resp.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    tmp.write(chunk)
            zip_path = tmp.name

        cores_dir.mkdir(parents=True, exist_ok=True)
        arcade_dir.mkdir(parents=True, exist_ok=True)

        rbfs = mras = 0
        try:
            with zipfile.ZipFile(zip_path) as zf:
                for member in zf.namelist():
                    if member.endswith('/'):
                        continue
                    name = Path(member).name
                    parent = Path(member).parent.as_posix()
                    if name.endswith('.rbf') and '/mister' in '/' + parent:
                        out = cores_dir / f"{Path(name).stem}_{date_stamp}.rbf"
                        with zf.open(member) as src, open(out, 'wb') as dst:
                            shutil.copyfileobj(src, dst)
                        rbfs += 1
                    elif name.endswith('.mra'):
                        out = arcade_dir / name
                        with zf.open(member) as src, open(out, 'wb') as dst:
                            shutil.copyfileobj(src, dst)
                        mras += 1
        finally:
            try:
                os.unlink(zip_path)
            except OSError:
                pass

        if rbfs == 0:
            print(f"::warning::{fork_name}: no jt*.rbf entries found under release/mister/ in bundle")
        print(f"{fork_name}: extracted {rbfs} RBF(s), {mras} MRA(s) into {arcade_dir}")


if __name__ == '__main__':
    main()
