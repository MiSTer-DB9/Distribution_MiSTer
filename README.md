# MiSTer Distribution DB9

This repository contains all the files that you'll want in your MiSTer.

You may download all of them at once as a zip through the [following link](https://github.com/MiSTer-DB9/Distribution_MiSTer/archive/refs/heads/main.zip). Once you have them, place them as-is in your SD card, and everything should work out of the box.

### MiSTer Project

If you want to check more about the MiSTer project, please check [this wiki](https://github.com/MiSTer-devel/Main_MiSTer/wiki).

### Downloader script

For downloading all of these files in an automatic fashion, use [this tool](https://github.com/MiSTer-devel/Downloader_MiSTer).

#### List of Tags that you may use with the Downloader Filters:

ALL_TAGS_GO_HERE

### Stable builds

For each fork enrolled in the stable channel, the distribution overlays per-core stable RBFs straight from each fork repo's GitHub Releases page on top of whatever the upstream MiSTer-devel pass placed in the category dir. Stable releases use the canonical GitHub model: **one annotated tag per build commit, one Release per tag** — not a single rolling tag with a stack of historical assets crammed inside. Tag format is `stable/<MAIN_BRANCH>/<YYYYMMDD>-<sha7>` (e.g. `stable/master/20260512-abc1234`); per-variant prefix means multi-variant forks like GBA (master / GBA2P / accuracy) and X68000 (master / USERIO2) each get an independent latest pointer. The downloader pages through `/repos/<owner>/<repo>/releases?per_page=100`, filters by tag prefix for the section's `MAIN_BRANCH`, picks the newest by `created_at`, and downloads its single RBF asset (`<Core>_<YYYYMMDD>_<sha7>.<ext>`) into the same category dir upstream would have used. Stable files inherit upstream's tag set — `filter = console` keeps working as expected.

To browse the history of any stable build for a given core, open the fork repo's Releases page (e.g. `https://github.com/MiSTer-DB9/NES_MiSTer/releases`); stable builds are retained indefinitely unless a workflow explicitly opts back into a positive `RETENTION` cap.

### Unstable builds

Alongside the regular (stable) RBFs, the distribution can ship per-core **unstable** builds compiled from upstream MiSTer-devel HEAD with DB9 / SNAC / Saturn-key-gate patches applied on top. Unstable files land in a separate top-level folder, `_Unstable/`, with one subdir per core variant: `_Unstable/_<Core>/<Core>_unstable_<YYYYMMDD>_<HHMM>_<sha7>.rbf` (e.g. `_Unstable/_NES/NES_unstable_20260512_0211_14ed3d5.rbf`, `_Unstable/_GBA2P/GBA2P_unstable_...rbf`). Up to the last 7 builds per core are mirrored from each fork repo's `unstable-builds` GitHub Release straight onto the SD card, so rollback after a bad build is a one-step local file swap — no GitHub browsing required.

Unstable files carry **only** two tags: `unstable` (channel) and `unstable-<core_slug>` (per-fork). They deliberately do NOT inherit `console` / `computer` / `<core>` path tags, so a generic `filter = console` does not silently pull them in.

Filter recipes for `/media/fat/downloader.ini`:

```ini
[mister]
# default: stable + unstable for every supported core
filter =

# stable only (recommended unless you want to test in-development upstream changes)
filter = !unstable

# unstable only for specific cores (mix freely):
filter = !unstable unstable-saturn unstable-nes
filter = !unstable unstable-gba2p              # the GBA 2-player variant
filter = !unstable unstable-ataristuserio2     # the AtariST USERIO2 variant

# stable consoles only — unstable is NOT included because it carries no `console` tag
filter = console !unstable
```

**Rolling back a bad unstable RBF.** Up to the last 7 builds for each core are already on your SD card under `_Unstable/_<Core>/` once that core has accumulated multiple unstable builds — pick the one you want from the OSD, or delete the newest file in that subdir and load whichever older RBF you prefer. To keep the downloader from re-fetching what you removed on its next run, add `!unstable-<slug>` to your `filter`; the matching subdir will then stop being mirrored. As a deeper-history fallback, each fork's `unstable-builds` GitHub Release (e.g. `https://github.com/MiSTer-DB9/Saturn_MiSTer/releases/tag/unstable-builds`) holds the same retained asset set.
