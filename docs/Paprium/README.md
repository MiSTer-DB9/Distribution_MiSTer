Paprium for MiSTer Mega Drive

A MiSTer Mega Drive core fork bringing Everdrive Pro Style Paprium support to Mister FPGA, with working MCU/cart behaviour, streamed graphics, CDDA/MD+ music, 

This project builds on years of community reverse-engineering, preservation, emulator work, and flash-cart development.

## V.07 — with huge thanks to thekoalakoa

Most of the fixes in V.07 come from **[thekoalakoa](https://github.com/thekoalakoa)**,
who ported this core to the Analogue Pocket and, in doing so, found the real root
causes of bugs that had been open here since the beginning — the Intercom elevator
above all. Their firmware work is a genuinely extraordinary piece of reverse
engineering: every fix argued from hardware captures, measured against the game's
own data, with the wrong turns written down so nobody repeats them.

**Go and look at the Pocket core — it is superb:**
### 👉 https://github.com/thekoalakoa/paprium-pocket

They are also decoding the cartridge's *native* 26-voice music synthesiser, which
nobody has ever emulated. If that lands, Paprium gets its real soundtrack back.

The V.07 firmware is built from their `patches/mega-ppm-pocket.patch` (0.2.5)
against krikzz's `mega-ppm`; the patch is included in `patches/` here.

Based on prior work by:
thekoalakoa / paprium-pocket - the Analogue Pocket core, and the firmware fixes in V.07 (https://github.com/thekoalakoa/paprium-pocket)
Krikzz / mega-ppm (including the first-level door fix, shared ahead of release)
adroxe / Paprium-Arcade - the Arcade Mode unlock IPS (https://github.com/adroxe/Paprium-Arcade)
Project Little Man
TheHpman / MAME Paprium research
MAVProxyUser / Genesis Plus GX Paprium PR
Paprium preservation community

Special thanks:
MiSTer Mega Drive core developers
Genesis Plus GX / MAME contributors
Everyone who helped test, document, and preserve Paprium


ROM and WAV assets are not included.
Bring your own Paprium dump and audio files.

If only there were some kind of archive on the internet...

## Required Files

Create this folder on your MiSTer SD card:

`/media/fat/games/MegaDrive/Paprium/`

Place the ROM and WAV files there:

```text
├── Paprium.md
├── paprium.cue
├── 01 Theme of Paprium.wav
├── 02 90's Acid Dub Character Select.wav
├── 03 Bone Crusher.wav
├── 04 Drumbass Boss.wav
├── 05 Asian Chill.wav
├── ...
└── 52 Waterfront Beat.wav
```
Load Paprium.md from the Mega Drive Paprium core.

**You need to boot the game once and select "Save back up ram" in the OSD the first time you play - Then hit reset in the OSD to get the REAL version of paprium to boot** 

## A note on AI use ("vibe coding")

Let's get this out of the way: it's a **Paprium** project *and* it's **AI
vibe-coded** — two of the internet's favourite things to argue about, bundled
into one repo. I'm fully expecting some hate for it, and honestly, that's fair.

I'm not an FPGA engineer. Most of the Verilog in here was generated and debugged
by AI (Claude and Codex) through a lot of back-and-forth — I'm not going to
pretend I hand-wrote it, because I didn't.

What I actually did was the boring half: running every build on a real MiSTer,
photographing the garbled graphics, listening to the broken audio, feeding it
all back, correcting the AI when it was confidently wrong, and deciding what was
good enough to call done. The Paprium / EverDrive Pro / firmware / MD+ knowledge
came from me and the wider preservation community — the AI couldn't see the
screen or hear the speakers, so that bit was on me.

It's a hack, not a "proper" core, and I've no doubt someone could do it far
better. If it annoys anyone enough to go and build the real thing from scratch,
without AI — genuinely, brilliant, please do, everyone wins. Until then, I made
this so a few people could mess about with Paprium on MiSTer. If that's you,
enjoy.
