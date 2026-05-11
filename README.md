# MiSTer Distribution DB9

This repository contains all the files that you'll want in your MiSTer.

You may download all of them at once as a zip through the [following link](https://github.com/MiSTer-DB9/Distribution_MiSTer/archive/refs/heads/main.zip). Once you have them, place them as-is in your SD card, and everything should work out of the box.

### MiSTer Project

If you want to check more about the MiSTer project, please check [this wiki](https://github.com/MiSTer-devel/Main_MiSTer/wiki).

### Downloader script

For downloading all of these files in an automatic fashion, use [this tool](https://github.com/MiSTer-devel/Downloader_MiSTer).

#### List of Tags that you may use with the Downloader Filters:

ALL_TAGS_GO_HERE

### Unstable builds

Alongside the regular (stable) RBFs, the distribution can ship per-core **unstable** builds compiled from upstream MiSTer-devel HEAD with DB9 / SNAC / Saturn-key-gate patches applied on top. Unstable files land in a separate top-level folder, `_Unstable/`, and each is named `<Core>_unstable_<YYYYMMDD>_<HHMM>_<sha7>.rbf`. The last 7 builds per core are kept as GitHub Release assets on each fork repo (tag `unstable-builds`) for manual rollback if a fresh build regresses.

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

**Rolling back a bad unstable RBF.** Open the affected fork's repo on GitHub (e.g. `https://github.com/MiSTer-DB9/Saturn_MiSTer`), click *Releases* → the `unstable-builds` prerelease, and download an older asset (last 7 builds are kept). Drop it manually into your SD card's `_Unstable/` folder, then add `!unstable-<slug>` to `filter` to stop the downloader from upgrading it on the next run.
