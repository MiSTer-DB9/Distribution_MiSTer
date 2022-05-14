#!/usr/bin/env bash
# Copyright (c) 2021 José Manuel Barroso Galindo <theypsilon@gmail.com>

set -euo pipefail

export ZIPS_CONFIG=/tmp/zips_config.json
curl -o "${ZIPS_CONFIG}" "https://raw.githubusercontent.com/MiSTer-devel/Distribution_MiSTer/develop/.github/zips_config.json"

curl -o /tmp/update_distribution.source "https://raw.githubusercontent.com/MiSTer-devel/Distribution_MiSTer/main/.github/update_distribution.sh"
source /tmp/update_distribution.source
rm /tmp/update_distribution.source

update_distribution() {
    local OUTPUT_FOLDER="${1}"
    local PUSH_COMMAND="${2:-}"

    local CURL_RETRY="--connect-timeout 15 --max-time 120 --retry 3 --retry-delay 5"
    local SSL_SECURITY_OPTION=""
    local MISTER_DEVEL_REPOS_URL="https://api.github.com/users/mister-db9/repos"
    local FORKS_INI_URL="https://raw.githubusercontent.com/MiSTer-DB9/Forks_MiSTer/master/Forks.ini"

    source <(curl ${CURL_RETRY} ${SSL_SECURITY_OPTION} "${FORKS_INI_URL}" 2> /dev/null | python3 -c "
import sys
import configparser
config = configparser.ConfigParser(inline_comment_prefixes=(';','#'))
config.read_file(sys.stdin)
for sec in config.sections():
    print(\"declare -A %s\" % (sec))
    for key, val in config.items(sec):
        print('%s[%s]=\"%s\"' % (sec, key, val))
")

    declare -A ENCC_CORES
    for i in ${Forks[syncing_forks]}
    do
        declare -n fork="${i}"
        local UPSTREAM_REPO="${fork[upstream_repo]}"
        local FORK_REPO="${fork[fork_repo]}"
        ENCC_CORES["${UPSTREAM_REPO%.git}"]="${FORK_REPO%.git}"
    done

    fetch_core_urls
    classify_core_categories

    for url in ${!CORE_CATEGORIES[@]} ; do
        for category in ${CORE_CATEGORIES[${url}]} ; do
            if [[ "${ENCC_CORES[${url}]:-false}" != "false" ]] ; then
                process_url "${ENCC_CORES[${url}]}" "${category}" "${OUTPUT_FOLDER}"
            else
                process_url "${url}" "${category}" "${OUTPUT_FOLDER}"
            fi
        done
    done

    if [[ "${PUSH_COMMAND}" != "--push" ]] ; then
        return
    fi

    git fetch --unshallow origin
    git checkout -f develop -b main
    echo "Running detox"
    detox -v -s utf_8-only -r *
    echo "Detox done"
    git add "${OUTPUT_FOLDER}"
    git commit -m "-"
    git fetch origin main || true
    curl -o /tmp/calculate_db.py "https://raw.githubusercontent.com/MiSTer-devel/Distribution_MiSTer/main/.github/calculate_db.py"
    chmod +x /tmp/calculate_db.py
    /tmp/calculate_db.py
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]] ; then
    update_distribution "${1}" "${2:-}"
fi
