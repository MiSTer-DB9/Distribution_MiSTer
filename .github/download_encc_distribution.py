#!/usr/bin/env python3
# Copyright (c) 2022 José Manuel Barroso Galindo <theypsilon@gmail.com>

import json
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
