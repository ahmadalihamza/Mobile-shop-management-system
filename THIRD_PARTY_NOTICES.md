# Third-party notices and source information

Mobile Desk 1.0.0 is GPL-3.0-or-later. `LICENSE` contains the full licence. The installer and portable distribution include `MobileDesk-1.0.0-Source.zip`, containing the application source, resources, tests and reproducible build scripts. Shop financial records, source workbooks and private migration plans are not included. The application icon was retained from the supplied GPL prototype.

## Catalogue

Historical names: [ilyasozkurt/mobilephone-brands-and-models](https://github.com/ilyasozkurt/mobilephone-brands-and-models), GPL-3.0. Android mappings: [bsthen/device-models](https://github.com/bsthen/device-models), Apache-2.0 (see preserved upstream licence). Modifications: normalized brand/model names, combined aliases, deterministic IDs and filtering. Apple names are factual references from the supplied catalogue, attributed to [Apple model identification](https://support.apple.com/en-us/108044). No affiliation with phone manufacturers is implied. Details/checksums are in CATALOGUE.md.

## Runtime and build components

| Component | Version used | Licence / upstream |
|---|---|---|
| CPython | 3.12.14 | Python Software Foundation licence and bundled third-party notices; [source releases](https://www.python.org/downloads/source/) |
| Qt / PySide6 Essentials / Shiboken6 | 6.10.2 | LGPL-3.0 (alternative upstream GPL/commercial terms also exist); [Qt source archives](https://download.qt.io/archive/qt/6.10/6.10.2/), [PySide source](https://download.qt.io/official_releases/QtForPython/pyside6/PySide6-6.10.2-src/) |
| SQLite | Version recorded in release metadata | Public domain; [SQLite copyright](https://www.sqlite.org/copyright.html) |
| PyInstaller bootloader | 6.16.0 | GPL with distribution exception; [licence](https://github.com/pyinstaller/pyinstaller/blob/v6.16.0/COPYING.txt) |
| Inno Setup | 6.7.3 | Jordan Russell / Martijn Laan, preserved [licence](https://github.com/jrsoftware/issrc/blob/is-6_7_3/license.txt) |

Full available licence texts are copied into `licences/` in the application distribution. CPython's licence includes notices for its bundled dependencies. Qt libraries remain separate DLLs in the onedir build; a compatible modified LGPL library can replace them. The source/build recipe is supplied so the program can be rebuilt against compatible modified libraries. No restriction is imposed on modification or reverse engineering for debugging such modifications. Obtain the exact upstream component source/version and its complete third-party licence files from the source links above when redistributing modified components.

Development-only packages (pytest, openpyxl and PyInstaller build dependencies) are pinned in requirements-dev.txt and are not needed by the client application. Their metadata/licences are preserved in the build environment; runtime dependency metadata and notices are copied by the release tooling.

The Inno compiler used for this release was downloaded from the [official download page](https://jrsoftware.org/isdl.php) in portable mode. Its Authenticode signature validated as Pyrsys B.V.; installer SHA-256: `9c73c3bae7ed48d44112a0f48e66742c00090bdb5bef71d9d3c056c66e97b732`. It is a build tool, not a client prerequisite.
