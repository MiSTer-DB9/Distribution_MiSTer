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
import subprocess
try:
    import httpimport
except ImportError as _:
    subprocess.run(['python3', '-m', 'pip', 'install', 'requests', 'httpimport==1.3.1'])
    import httpimport

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

    download_distribution.process_all(extra_content_categories, cores, download_distribution.read_target_dir())

    print()
    print("Time:")
    end = time.time()
    print(end - start)
    print()

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
        upstream_repo = str(Path(forks[fork]['upstream_repo']).with_suffix("")).replace('https:/g', 'https://g')
        fork_repo = str(Path(forks[fork]['fork_repo']).with_suffix("")).replace('https:/g', 'https://g')
        replacements[upstream_repo.lower()] = fork_repo

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
