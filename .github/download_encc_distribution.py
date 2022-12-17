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
from download_distribution import process_all, classify_extra_content, fetch_extra_content_urls, fetch_cores, fetch_text, validate_cores, validate_extra_content_urls

def main():

    start = time.time()

    cores = fetch_cores()
    extra_content_urls = fetch_extra_content_urls()
    extra_content_categories = classify_extra_content(extra_content_urls)
    forks = fetch_forks()

    print(f'Cores {len(cores)}:')
    print(json.dumps(cores))
    print()

    validate_cores(cores)

    print(f'Extra Content URLs {len(extra_content_urls)}:')
    print(json.dumps(extra_content_urls))
    print()

    validate_extra_content_urls(extra_content_urls)

    print('Extra Content Categories:')
    print(json.dumps(extra_content_categories))
    print()

    print('Forks:')
    print(json.dumps(forks))
    print()

    replace_urls(cores, extra_content_categories, forks)

    target = 'delme'
    if len(sys.argv) > 1:
        target = sys.argv[1].strip()

    if 'delme' in target.lower():
        shutil.rmtree(target, ignore_errors=True)
        Path(target).mkdir(parents=True, exist_ok=True)

    process_all(extra_content_categories, cores, target)

    print()
    print("Time:")
    end = time.time()
    print(end - start)
    print()

def fetch_forks():
    with io.StringIO(fetch_text('https://raw.githubusercontent.com/MiSTer-DB9/Forks_MiSTer/master/Forks.ini')) as buf:
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
        lower = ore['url'].lower()
        if lower in replacements:
            print(f'Replaced core: {core["url"]} = {replacements[lower]}')
            core['url'] = replacements[lower]

    for key in replacements:
        if key in extra_content_categories:
            print(f'Replaced extra content: {replacements[key]} = {key}')
            extra_content_categories[replacements[key]] = extra_content_categories[key]
            del extra_content_categories[key]

if __name__ == '__main__':
    main()
