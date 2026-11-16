# Ath10kMac 0.0.93 — automatic board selection

Based on the supplied Ath10kMac-main archive (version 0.0.92).

## Changes / Alterações

- Board/firmware preparation reads the complete API2 catalog instead of two subsystem allowlists. Runtime selection uses exact PCI + optional OEM variant, then exact PCI, then the same family's API1 board.bin. No arbitrary manufacturer board is used as a fallback.
- 77 QCA6174 PCI keys (65 base entries and 12 optional variants) and 37 QCA9377 PCI keys are embedded. Identical board blobs share storage; firmware and OTP are emitted once per chip family.
- Killer 1a56:143a and Lenovo 17aa:0901 use their exact API2 board data. QCA9377's previous 1235:0901 case keeps its reviewed API1 fallback.
- Chip/ROM firmware compatibility is independent of subsystem matching. Missing board data is reported as board-profile-not-found before PLL registers are changed.
- Info.plist uses one primary PCI match per chip. The redundant Killer personality is removed. IORegistry exposes the requested/selected board and selection status.
- Version identifiers are 0.0.93, including the driver control API. README and diagnostic collection are updated; GitHub Actions runs the board tests before the native kext build.

## Validation / Validação

Passed in the Linux host environment:

- sh tests/run-tests.sh: complete existing regression suite, including the new catalog test, with ASan/UBSan. Exit status 0.
- sh tests/run-board-tests.sh: parser/catalog and actual extracted BMI/PLL/board methods, with ASan/UBSan. Exit status 0.
- Additional OTP/firmware tests pass with subsystem IDs set BEFORE board upload, checking the actual uploaded board bytes for Lenovo and Killer, followed by OTP and WLAN download/readback. These strengthened fixtures are included.
- All Python syntax, plist structure, workflow YAML and workflow shell blocks validated. Source firmware and board container bytes are unchanged from the supplied archive.

The logs in validation/ are host-test results. Native Xcode/Mach-O compilation, real ROM/firmware execution, Wi-Fi connectivity and sleep recovery of this update have not been exercised here. The workflow includes native compilation for the user's next GitHub run.

## Coverage / Cobertura

Supported firmware/ROM profiles remain QCA6174 hw3.2 (chip revision 10, ROM 0x05030000) and QCA9377 hw1.1 (revision 1, ROM 0x05020001). A catalog entry is not a hardware-test certification.

QCA9377 includes its own source board.bin fallback. QCA6174 currently has no generic source board.bin; an unknown PCI board without an API2 entry fails explicitly. The old firmware/prepared/board.bin was a single Dell API2 extraction and is removed to avoid treating it as a generic API1 file.

OEM variants are selected only when Ath10kBoardVariant is explicitly supplied; the exact base PCI entry is used otherwise. BMI/OTP-only board keys are retained as excluded_board_keys in the manifests, not guessed from PCI IDs. Adding supported PCI boards requires updating source board data and rebuilding, without editing subsystem IDs in C++ or Info.plist.

## Build and test on macOS / Compilar e testar no macOS

```sh
make clean
make kext
```

Install build/out/Ath10kMac.kext using the existing loading method, reboot, then collect:

```sh
sudo sh scripts/test-qca9377.sh > ~/Desktop/ath10k-board-0.0.93.txt 2>&1
```

Check Ath10kDriverVersion, Ath10kBoardLookupStatus, Ath10kRequestedBoardKey, Ath10kPreparedBoardKey, Ath10kPLLComplete, Ath10kFirmwareBootStatus and Ath10kWMIRuntimeActive. Use Ath10k Connectivity to connect once the interface is available.

## Modified and added files / Arquivos modificados e adicionados

- `.github/workflows/ath10kmac-release.yml`
- `Ath10kMac.kext/Contents/Info.plist`
- `README.md`
- `firmware/prepared/QCA9377/manifest.json`
- `firmware/prepared/manifest.json`
- `scripts/prepare-firmware.py`
- `scripts/test-qca9377.sh`
- `src/kext/Ath10kPCIDevice.cpp`
- `src/kext/Ath10kPCIDevice.hpp`
- `src/kext/Ath10kPayload.hpp`
- `src/kext/Ath10kPayloadProfile.hpp`
- `src/kext/Ath10kUserClient.cpp`
- `src/kext/kmod_info.c`
- `tests/run-board-tests.sh`
- `tests/run-tests.sh`
- `tests/test_board_catalog.cpp`
- `tests/test_firmware_flow.cpp`
- `tests/test_otp_flow.cpp`
- `tests/test_payload.py`
- `tests/test_pll.cpp`
- `tests/test_pll_memory.cpp`
- `tests/test_qca9377_flow.cpp`
- `tests/test_recovery.cpp`
- `validation/board-tests-0.0.93.log`
- `validation/host-tests-0.0.93.log`
- `CHANGES-0.0.93.md`
- `SOURCE-HASHES-current.json`

Removed / Removido:
- `firmware/prepared/board.bin`
