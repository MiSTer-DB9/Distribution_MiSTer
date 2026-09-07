# RCA Studio II for MiSTer

MiSTer FPGA core for the RCA Studio II, Studio III/MPT-02 family, and Toshiba Visicom COM-100.

Supported hardware includes:
* RCA Studio II
* RCA Studio III (unreleased)
* Academy Apollo 80
* Conic M-1200
* Hanimex MPT-02
* Mustang 9016
* Sheen M-1200
* Soundic Victory (MPT-02)
* Toshiba Visicom COM-100
* Trevi M-1200

## Install

Copy the release `.rbf` to e.g. `/media/fat/_Console/` on MiSTer.

Put the four native firmware files below in `/media/fat/games/Studio-II/`. For CHIP-8 support, put `chip8.bin` in the same directory as your CHIP-8 games, or load it manually. Firmware images are available in the Emma 02 GitHub repository, e.g. [Studio II](https://github.com/etxmato/emma_02/blob/master/data/StudioII/studio2.rom).

**Load Firmware** temporarily replaces the active machine's native firmware; **Load CHIP-8 Interpreter** loads `chip8.bin` separately, where it is only used when a `.ch8` program is loaded.

`Machine` selects `Studio II`, `Studio III (PAL)`, `Studio III (NTSC)`, or `Visicom`. Changes take effect after **Apply and reset**.

| Machine | Autoload filename | Tested firmware | Size | MD5 |
|---|---|---|---:|---|
| Studio II | `boot0.rom` | `studio2.rom` | 2 KB | `B37205BF19B197682F00619D05DA194B` |
| Studio III PAL | `boot1.rom` | `studio3_pal.bin` | 4 KB | `A6B94E449BC9EC58A30E1F75D590C558` |
| Studio III NTSC | `boot2.rom` | `studio3_ntsc.bin` | 4 KB | `849A484AA4B2784ECE5C35C39D9D51A8` |
| Visicom | `boot3.rom` | `visicom.rom` | 2 KB | `AEEC6FE3934481E20EB7DB6D5FF56A54` |
| CHIP-8 interpreter | `chip8.bin` | `chip8.bin` | 768 bytes | `9F037435B6721BE9EE91DC93293E52CE` |

Other firmware images may work; those listed above were used during development and testing.

The native firmware includes resident games. Using a resident game's start key causes the core to attempt to load an appropriate controller profile. Games often start on a black screen. Selection keys and play instructions are listed in [docs/how-to-play.md](docs/how-to-play.md).

## Keypad and CLEAR

Keypad A and B are called "Keyboards" in RCA documentation. Keypad is used instead to avoid confusion. 

The keypads are mapped to the MiSTer keyboard like this:

```text
   Keypad A (left)        Keypad B (right)
    1  2  3                7  8  9
    Q  W  E                U  I  O
    A  S  D                J  K  L
       X                      ,
```

| Key | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 0 |
|---|---|---|---|---|---|---|---|---|---|---|
| Keypad A | `1` | `2` | `3` | `Q` | `W` | `E` | `A` | `S` | `D` | `X` |
| Keypad B | `7` | `8` | `9` | `U` | `I` | `O` | `J` | `K` | `L` | `,` |

## CHIP-8

Marcel van Tongeren's [Studio II CHIP-8 interpreter](https://github.com/etxmato/emma_02/blob/master/data/StudioII/chip8.bin) is required for CHIP-8 support.

CHIP-8 uses the COSMAC VIP's 16-key hexadecimal keypad:

```text
    1  2  3  C
    4  5  6  D
    7  8  9  E
    A  0  B  F
```

This layout doesn't cleanly map to the Studio II inputs. In Marcel's interpreter, `0`–`9` map directly to the Studio II's keypad A and `A`–`F` to keypad B `1`–`6` (keyboard `7`, `8`, `9`, `U`, `I`, `O`).

The **CHIP-8** gamepad profile maps D-pad Up/Left/Down/Right to `5/7/8/9`, Start to `1`, Fire to `F`, and Extra to `0`. There is probably a better mapping for Start, Fire, and Extra. Please create an issue if you have a suggestion for the default CHIP-8 profile.

The Studio-family interpreter has some limitations on which CHIP-8 games are compatible. See Marcel van Tongeren's [informational page](https://emma02.hobby-site.com/studio_chip8.html) for more details.

    When unloading a running CHIP-8 program without resetting, the interpreter may produce garbage video or sound because execution continues after the program is unmapped. Use Unload Cartridge and Reset for a clean exit.

CHIP-8 is not supported on Visicom because there is no available interpreter for the platform.

## Options

**NE555 pitch** adjusts the Studio II and Visicom beeper tuning.

**CDP1863 pitch** only applies to Studio III NTSC. The PAL option applies the CDP1864 divide-by-four stage for PAL-equivalent pitch on NTSC.

**Load Palette** allows setting a 2-color (Studio II, CHIP-8) or 4-color (Visicom) color palette. MiSTer Game Boy `.gbp` palettes are supported. Example palettes are in [`palettes`](palettes/).

**Clear** initializes (resets) the game or firmware you have running. It's a physical button on the hardware.

**Unload Cartridge** ejects without resetting; video remains active and the previous firmware or resident-game mapping becomes visible again.

**Unload Cartridge and Reset** ejects the active cartridge and resets the machine. 

## Controller profiles

**Mapping: Auto** selects a controller profile from the cartridge CRC, falling back to 8-way for unknown games. Resident games can also select their profiles automatically. **Manual** allows direct profile selection.

**Mapping: Manual** overrides automatic mappings and enables the Profile field.

## Numstick (on-screen keypad)

**Numstick** assigns the overlay to keypad A or B. The right stick selects 1–9 and the left stick selects 0. Hold a direction for about half a second to register it; nudge and release the right stick for 5.

## Studio IV

Studio IV is not supported.

## Project information

Original core by Jason Coombes, with MiSTer integration and early Pixie work by Flandango and later contributions by Alan Steremberg and Elle Ball. See [CREDITS.md](CREDITS.md) for detailed acknowledgements.

GPL-2.0-or-later; see file headers and [LICENSE](LICENSE).
