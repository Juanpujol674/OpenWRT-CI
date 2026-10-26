#!/bin/bash
# SPDX-License-Identifier: MIT
# Run from the OpenWrt source directory; called after package/settings overrides.
set -euo pipefail

ROOT=${GITHUB_WORKSPACE:?GITHUB_WORKSPACE is required}
ONU_REV=3cb13560459f1d51136dac662baa1f399028b2b4

enabled() { [[ "${!1:-false}" == true ]]; }
onu_enabled() { [[ "${WRT_CONFIG:-}" == AIROHA && "${WRT_ONU_APP:-true}" != false ]]; }

clone_pinned() {
    local repo=$1 rev=$2 dest=$3
    # A fresh build tree is expected; never leave duplicate feed definitions.
    git clone --no-checkout "https://github.com/$repo.git" "$dest"
    git -C "$dest" checkout --detach "$rev"
}

packages() {
    # Remove only exact package directories/symlinks, not similarly named apps.
    local name
    if [[ "${WRT_CONFIG:-}" == AIROHA ]] && { onu_enabled || enabled WRT_ONU_DEBUG || enabled WRT_ONU_STATUS; }; then
        for name in luci-app-onu airoha-ponctl airoha-pond airoha-pon-daemons airoha-pon-debug luci-app-pon-status; do
            find ./feeds ./package/feeds -name "$name" -prune -exec rm -rf {} +
        done
        clone_pinned naoki66/OpenWrt_ONU_CONFIG "$ONU_REV" ./package/onu-config
    fi
}

set_config() {
    local symbol=$1 value=$2
    sed -i "/^${symbol}=/d; /^# ${symbol} is not set$/d" .config
    if [[ "$value" == n ]]; then
        printf '# %s is not set\n' "$symbol" >> .config
    else
        printf '%s=%s\n' "$symbol" "$value" >> .config
    fi
}

configure() {
    local line symbol value
    while IFS= read -r line; do
        [[ "$line" == CONFIG_*=* ]] || continue
        symbol=${line%%=*}; value=${line#*=}
        set_config "$symbol" "$value"
    done < "$ROOT/Config/COMMON.txt"

    if [[ "${WRT_CONFIG:-}" == AIROHA ]]; then
        if onu_enabled; then
            # ONU incorporates the old PON/IPTV UI and ships the same helpers.
            # Device defaults can reinstall those packages despite .config=n.
            "${PYTHON3:-python3}" "$ROOT/Scripts/prepare-onu.py"
            for symbol in luci-app-pon luci-app-iptv luci-i18n-pon-zh-cn luci-i18n-iptv-zh-cn; do
                set_config "CONFIG_PACKAGE_$symbol" n
            done
        fi
        # luci-app-onu requires both Rust backends; they are not optional extras.
        value=n; if onu_enabled; then value=y; fi
        set_config CONFIG_PACKAGE_luci-app-onu "$value"
        set_config CONFIG_PACKAGE_airoha-ponctl "$value"
        set_config CONFIG_PACKAGE_airoha-pond "$value"
        value=n; if enabled WRT_ONU_DEBUG; then value=y; fi
        set_config CONFIG_PACKAGE_airoha-pon-debug "$value"
        value=n; if enabled WRT_ONU_STATUS; then value=y; fi
        set_config CONFIG_PACKAGE_luci-app-pon-status "$value"
    fi
}

verify() {
    # defconfig silently drops unknown or unavailable packages. Fail visibly.
    local line symbol value failed=0
    while IFS= read -r line; do
        [[ "$line" == CONFIG_*=* ]] || continue
        symbol=${line%%=*}; value=${line#*=}
        if [[ "$value" == y ]]; then
            if ! grep -qxF "$line" .config; then
                echo "::error::Required option missing after defconfig: $line"
                failed=1
            fi
        elif grep -qxF "$symbol=y" .config || grep -qxF "$symbol=m" .config; then
            echo "::error::Disabled option still selected: $symbol"
            failed=1
        fi
    done < "$ROOT/Config/COMMON.txt"
    if [[ "${WRT_CONFIG:-}" == AIROHA ]]; then
        if onu_enabled; then
            for symbol in luci-app-pon luci-app-iptv luci-i18n-pon-zh-cn luci-i18n-iptv-zh-cn; do
                if grep -qxF "CONFIG_PACKAGE_$symbol=y" .config || grep -qxF "CONFIG_PACKAGE_$symbol=m" .config; then
                    echo "::error::Legacy package conflicts with luci-app-onu: $symbol"
                    failed=1
                fi
            done
        fi
        local entry
        for entry in "luci-app-onu:WRT_ONU_APP" "airoha-ponctl:WRT_ONU_APP" "airoha-pond:WRT_ONU_APP" "airoha-pon-debug:WRT_ONU_DEBUG" "luci-app-pon-status:WRT_ONU_STATUS"; do
            symbol=CONFIG_PACKAGE_${entry%%:*}
            value=n
            if [[ "${entry#*:}" == WRT_ONU_APP ]]; then
                if onu_enabled; then value=y; fi
            elif enabled "${entry#*:}"; then value=y; fi
            if [[ "$value" == y ]]; then
                if ! grep -qxF "$symbol=y" .config; then
                    echo "::error::ONU dependency unavailable: $symbol"; failed=1
                fi
            elif grep -qxF "$symbol=y" .config || grep -qxF "$symbol=m" .config; then
                echo "::error::ONU option disabled but selected: $symbol"; failed=1
            fi
        done
    fi
    return "$failed"
}

case "${1:-}" in
    packages) packages ;;
    config) configure ;;
    verify) verify ;;
    *) echo 'Usage: Extras.sh packages|config|verify' >&2; exit 2 ;;
esac
