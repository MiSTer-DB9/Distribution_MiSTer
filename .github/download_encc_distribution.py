#!/usr/bin/env python3
# Copyright (c) 2022 José Manuel Barroso Galindo <theypsilon@gmail.com>

import json
import time
import sys
import shutil
import io
import sys
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

    replace_urls(cores, extra_content_categories, forks)

    cores = filter_dead_cores(cores)

    download_distribution.process_all(extra_content_categories, cores, download_distribution.read_target_dir())

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

def replace_urls(cores, extra_content_categories, forks):
    replacements = {}
    for fork in forks['Forks']['syncing_forks'].split(' '):
        main_branch = forks[fork]['main_branch']
        upstream_repo = str(Path(forks[fork]['upstream_repo']).with_suffix("")).replace('https:/g', 'https://g')
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

if __name__ == '__main__':
    main()
