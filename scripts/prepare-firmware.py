#!/usr/bin/env python3
"""Validate ath10k containers; generate automatic board catalogs and chip firmware profiles.

Formats: Linux v6.12 ath10k/hw.h and core.c. No network or device access.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path
import struct
import sys

BOARD_MAGIC = b"QCA-ATH10K-BOARD\0"
FW_MAGIC = b"QCA-ATH10K\0"
BOARD_SIZE = 8124

class BoardNotFound(ValueError):
    """Only a well-formed API2 container without a match allows API1 fallback."""



def ies(data, magic=None):
    pos = 0
    if magic is not None:
        if not data.startswith(magic):
            raise ValueError("incorrect container magic")
        pos = (len(magic) + 3) & ~3
        if len(data) < pos:
            raise ValueError("truncated magic padding")
    while pos < len(data):
        if len(data) - pos < 8:
            raise ValueError("truncated IE header")
        tag, size = struct.unpack_from("<II", data, pos)
        pos += 8
        padded = (size + 3) & ~3
        if padded > len(data) - pos:
            raise ValueError("IE length exceeds container")
        yield tag, data[pos:pos + size]
        pos += padded


def parse_board_catalog(data):
    """Validate the complete API2 container, including aliases and unused keys."""
    if len(data) > 16 * 1024 * 1024:
        raise ValueError("board catalog exceeds size limit")
    catalog = {}
    for tag, block in ies(data, BOARD_MAGIC):
        if tag != 0:
            continue
        names = []
        for subtag, value in ies(block):
            if subtag == 0:
                name = value.decode("ascii")
                if not name or len(name) > 512 or any(ord(c) < 32 or ord(c) > 126 for c in name):
                    raise ValueError("invalid board name")
                names.append(name)
            elif subtag == 1:
                if not names or len(value) != BOARD_SIZE:
                    raise ValueError("board data requires names and exactly 8124 bytes")
                for name in names:
                    if len(catalog) >= 4096:
                        raise ValueError("too many board catalog entries")
                    if name in catalog:
                        raise ValueError(f"duplicate board name: {name}")
                    catalog[name] = value
                names = []
        if names:
            raise ValueError("board names without board data")
    return catalog


def select_board(data, key):
    catalog = parse_board_catalog(data)
    if key not in catalog:
        raise BoardNotFound("no exact board match")
    return catalog[key]


def parse_firmware(data):
    parts = {}
    for tag, value in ies(data, FW_MAGIC):
        if tag in parts:
            raise ValueError(f"duplicate firmware IE {tag}")
        parts[tag] = value
    for tag in (0, 3, 4, 5, 6):
        if not parts.get(tag):
            raise ValueError(f"missing/empty firmware IE {tag}")
    for tag in (5, 6):
        if len(parts[tag]) != 4:
            raise ValueError(f"bad operation-version size for IE {tag}")
    wmi, htt = (struct.unpack("<I", parts[tag])[0] for tag in (5, 6))
    if (wmi, htt) != (4, 3):
        raise ValueError("expected TLV WMI=4 / HTT=3")
    if 7 in parts:
        raise ValueError("code-swap firmware is not supported in this milestone")
    version = parts[0].rstrip(b"\0").decode("ascii")
    if not version or any(ord(c) < 32 or ord(c) > 126 for c in version):
        raise ValueError("invalid firmware version string")
    return parts, version


def sha(data):
    return hashlib.sha256(data).hexdigest()


def ignore_otp_result(parts):
    # Linux v6.12 core.h: ATH10K_FW_FEATURE_IGNORE_OTP_RESULT = 7.
    features = parts.get(2, b"")
    return bool(features and (features[0] & 0x80))


def supports_skip_clock_init(parts):
    # Linux v6.12 core.h: ATH10K_FW_FEATURE_SUPPORTS_SKIP_CLOCK_INIT = 9.
    features = parts.get(2, b"")
    return len(features) > 1 and bool(features[1] & 0x02)


def parse_segments(image):
    """Uncompressed SGMT image, with data + one BEGINADDR + terminal DONE.

    Linux bmi.h/hw.c define this envelope. EXEC/BDDATA are deliberately
    rejected: this milestone downloads code without executing WLAN firmware.
    Offsets refer to the original image (metadata is not sent as raw RAM).
    """
    if len(image) < 8 or len(image) > 2 * 1024 * 1024:
        raise ValueError("unsupported SGMT image size")
    if struct.unpack_from("<II", image) != (0x544d4753, 0):
        raise ValueError("expected uncompressed SGMT firmware image")
    pos, entry, segments = 8, None, []
    while pos < len(image):
        if len(image) - pos < 8:
            raise ValueError("truncated SGMT metadata")
        address, size = struct.unpack_from("<II", image, pos)
        pos += 8
        if size == 0xffffffff:
            if pos != len(image) or entry is None or not segments:
                raise ValueError("invalid SGMT end / missing entry point")
            if not any(s['address'] <= entry < s['address'] + s['length'] for s in segments):
                raise ValueError("SGMT entry point is outside data segments")
            return segments, entry
        if size == 0xfffffffd:
            if entry is not None or (address & 3):
                raise ValueError("duplicate/unaligned SGMT entry point")
            entry = address
            continue
        if size & 0x80000000:
            raise ValueError("unsupported SGMT EXEC/BDDATA/metadata")
        if entry is not None or size == 0 or size > len(image) - pos:
            raise ValueError("invalid SGMT data length/order")
        # Rounded-up tail reads must also fit the target's 32-bit address space.
        if address & 3 or address + ((size + 3) & ~3) > 0x100000000:
            raise ValueError("invalid SGMT target address range")
        if len(segments) >= 64:
            raise ValueError("too many SGMT segments")
        if any(address < s['address'] + s['length'] and s['address'] < address + size for s in segments):
            raise ValueError("overlapping SGMT segments cannot be verified independently")
        # Protect the boot configuration and board area used by this milestone.
        if address < 0x404000 and address + size > 0x400800:
            raise ValueError("SGMT data overlaps Host Interest / board RAM")
        segments.append({'address': address, 'offset': pos, 'length': size})
        pos += size
    raise ValueError("SGMT DONE marker missing")


# These describe supported chip/ROM ABIs, never PCI subsystem allowlists.
FAMILIES = (
    {"folder": "firmware", "namespace": "Ath10kPayload", "output": "firmware/prepared",
     "name": "QCA6174/hw3.2", "device": 0x003e, "chip": 10, "target": 0x05030000},
    {"folder": "firmware/QCA9377/hw1.0", "namespace": "Ath10kPayload9377",
     "output": "firmware/prepared/QCA9377", "name": "QCA9377/hw1.1",
     "device": 0x0042, "chip": 1, "target": 0x05020001},
)
PCI_BOARD_NAME = re.compile(
    r"bus=pci,vendor=([0-9a-fA-F]{4}),device=([0-9a-fA-F]{4}),"
    r"subsystem-vendor=([0-9a-fA-F]{4}),subsystem-device=([0-9a-fA-F]{4})"
    r"(?:,variant=([^,]{1,128}))?")


def byte_array(name, data):
    lines = [f"static constexpr UInt8 {name}[] = {{"]
    for pos in range(0, len(data), 16):
        lines.append("    " + ", ".join(f"0x{x:02x}" for x in data[pos:pos + 16]) + ",")
    return lines + ["};"]


def prepare_family(root, family):
    folder = root / family["folder"]
    board_path = folder / "board-2.bin"
    # Absence permits the API1 fallback; malformed API2 data fails the build.
    board_container = board_path.read_bytes() if board_path.exists() else None
    catalog = parse_board_catalog(board_container) if board_container is not None else {}
    fallback_path = folder / "board.bin"
    fallback = fallback_path.read_bytes() if fallback_path.exists() else None
    if fallback is not None and len(fallback) != BOARD_SIZE:
        raise ValueError("invalid API1 fallback board size")
    fw_container = (folder / "firmware-6.bin").read_bytes()
    parts, version = parse_firmware(fw_container)
    if family["device"] == 0x0042:
        if sha(fw_container) != "8f8b002fccfe81d42238f27dd1f56d189604f180bd4772c7c8e75ae1fef16f01":
            raise ValueError("QCA9377 firmware does not match the reviewed ABI")
        if fallback is not None and sha(fallback) != "127d35d82edb46278f30c448cbca664d755ff0d5fed57b649959cdbc4208c768":
            raise ValueError("QCA9377 fallback board does not match the reviewed profile")
    segments, entry = parse_segments(parts[3])
    selected, excluded, identities = [], [], set()
    for key, data in sorted(catalog.items()):
        match = PCI_BOARD_NAME.fullmatch(key)
        if not match:
            excluded.append(key)
            continue
        vendor, device, subvendor, subdevice = (int(n, 16) for n in match.groups()[:4])
        if vendor != 0x168c or device != family["device"]:
            excluded.append(key)
            continue
        identity = (subvendor, subdevice, match.group(5) or "")
        if identity in identities:
            raise ValueError(f"ambiguous PCI board identity: {key}")
        identities.add(identity)
        selected.append({"key": key, "subvendor": subvendor, "subdevice": subdevice,
                         "variant": match.group(5) or "", "data": data})
    if not selected and fallback is None:
        raise ValueError(f"no usable board data for {family['name']}")
    namespace = family["namespace"]
    header = [f"namespace {namespace} {{",
              f"static constexpr char kFirmwareVersion[] = {json.dumps(version)};",
              f"static constexpr UInt32 kFirmwareSize = {len(parts[3])};",
              f"static constexpr char kFirmwareSHA256[] = {json.dumps(sha(parts[3]))};",
              f"static constexpr UInt32 kOTPSize = {len(parts[4])};",
              f"static constexpr char kOTPSHA256[] = {json.dumps(sha(parts[4]))};",
              f"static constexpr bool kOTPIgnoreResult = {str(ignore_otp_result(parts)).lower()};",
              f"static constexpr bool kSupportsSkipClockInit = {str(supports_skip_clock_init(parts)).lower()};"]
    # Board aliases share storage. Firmware and OTP are emitted once per chip.
    boards = {sha(b["data"]): b["data"] for b in selected}
    if fallback is not None:
        boards[sha(fallback)] = fallback
    board_names = {digest: f"kBoard{index}" for index, digest in enumerate(sorted(boards))}
    for digest, name in board_names.items():
        header += byte_array(name, boards[digest])
    header += byte_array("kOTP", parts[4])
    header += byte_array("kFirmware", parts[3])
    header += ["static constexpr Ath10kPayload::FirmwareSegment kFirmwareSegments[] = {"]
    header += [f"    {{0x{s['address']:08x}u, {s['offset']}u, {s['length']}u}}," for s in segments]
    header += ["};", f"static constexpr UInt32 kFirmwareSegmentCount = {len(segments)};",
               f"static constexpr UInt32 kFirmwareSegmentDataBytes = {sum(s['length'] for s in segments)};",
               f"static constexpr UInt32 kFirmwareEntryAddress = 0x{entry:08x}u;", "}"]

    def profile_line(board=None, selection="board-profile-not-found"):
        data = board["data"] if board else None
        digest = sha(data) if data is not None else "unavailable"
        data_ref = f"{namespace}::{board_names[digest]}" if data is not None else "nullptr"
        key = board["key"] if board else "unavailable"
        subvendor, subdevice = (board["subvendor"], board["subdevice"]) if board else (0, 0)
        variant = board["variant"] if board else ""
        return (f"    {{0x{family['device']:04x}, 0x{subvendor:04x}, 0x{subdevice:04x}, "
                f"{family['chip']}, 0x{family['target']:08x}u, {str(data is not None).lower()}, "
                f"{json.dumps(key)}, {json.dumps(selection)}, {json.dumps(digest)}, {data_ref}, "
                f"{len(data) if data is not None else 0}, {namespace}::kFirmwareVersion, "
                f"{namespace}::kFirmwareSize, {namespace}::kFirmwareSHA256, {namespace}::kFirmware, "
                f"{namespace}::kOTPSize, {namespace}::kOTPSHA256, {namespace}::kOTP, "
                f"{namespace}::kOTPIgnoreResult, {namespace}::kSupportsSkipClockInit, "
                f"{namespace}::kFirmwareSegments, {namespace}::kFirmwareSegmentCount, "
                f"{namespace}::kFirmwareSegmentDataBytes, {namespace}::kFirmwareEntryAddress, "
                f"{json.dumps(variant)}, {len(selected)}}},")

    entries = [profile_line(b, "board-api2-variant" if b["variant"] else "board-api2-exact") for b in selected]
    fallback_board = {"key": "board.bin", "data": fallback, "subvendor": 0, "subdevice": 0, "variant": ""} if fallback is not None else None
    fallback_entry = profile_line(fallback_board, "board-api1-fallback") if fallback_board else None
    missing_entry = profile_line()
    manifest = {
        "profile": family["name"], "device": f"168c:{family['device']:04x}",
        "chip_revision": family["chip"], "target_version": f"0x{family['target']:08x}",
        "selection_policy": "exact PCI+variant, exact PCI, chip API1 fallback, explicit missing-board error",
        "board_catalog_entries": len(selected), "unique_board_payloads": len(boards),
        "boards": [{"key": b["key"], "variant": b["variant"], "board_bytes": len(b["data"]),
                    "board_sha256": sha(b["data"])} for b in selected],
        "excluded_board_keys": excluded,
        "board_container_sha256": sha(board_container) if board_container is not None else None,
        "fallback_board_sha256": sha(fallback) if fallback is not None else None,
        "firmware_container_sha256": sha(fw_container), "firmware_version": version,
        "firmware_bytes": len(parts[3]), "firmware_sha256": sha(parts[3]),
        "otp_bytes": len(parts[4]), "otp_sha256": sha(parts[4]), "wmi_op": 4, "htt_op": 3,
        "otp_ignore_result_feature": ignore_otp_result(parts),
        "supports_skip_clock_init_feature": supports_skip_clock_init(parts),
        "firmware_segments": segments, "firmware_entry_address": entry,
        "firmware_segment_data_bytes": sum(s['length'] for s in segments),
    }
    outdir = root / family["output"]
    outputs = {outdir / "otp.bin": parts[4], outdir / "firmware-image.bin": parts[3],
               outdir / "manifest.json": (json.dumps(manifest, indent=2) + "\n").encode()}
    # Only an actual API1 source is exported as board.bin, never an arbitrary API2 entry.
    if fallback is not None:
        outputs[outdir / "board.bin"] = fallback
    print(f"Prepared {family['name']}: {len(selected)} board keys, {len(boards)} unique boards, "
          f"API1 fallback={'yes' if fallback is not None else 'no'}; firmware {version}")
    return outputs, header, entries, fallback_entry, missing_entry


def prepare(root):
    outputs, entries, fallbacks, missing = {}, [], [], []
    header = ["// Generated by scripts/prepare-firmware.py. Do not edit.",
              "#pragma once", '#include "Ath10kPayloadProfile.hpp"']
    for family in FAMILIES:
        files, lines, rows, fallback, unavailable = prepare_family(root, family)
        outputs.update(files)
        header.extend(lines)
        entries.extend(rows)
        if fallback:
            fallbacks.append(fallback)
        missing.append(unavailable)
    header += ["namespace Ath10kPayload {", "static constexpr Profile kProfiles[] = {", *(entries or ["    {},"]), "};",
               "static constexpr Profile kFallbackProfiles[] = {", *(fallbacks or ["    {},"]), "};",
               "static constexpr Profile kMissingBoardProfiles[] = {", *missing, "};",
               "static constexpr Profile kUnavailable = {};",
               "const Profile &selectProfile(UInt16 vendor, UInt16 device, UInt16 subvendor, UInt16 subdevice, UInt8 chip, const char *variant) {",
               "    if (vendor != 0x168c) return kUnavailable;",
               "    if (variant && variant[0]) for (const auto &p : kProfiles)",
               "        if (p.device == device && p.chip == chip && p.subvendor == subvendor && p.subdevice == subdevice && boardVariantEqual(p.kBoardVariant, variant)) return p;",
               "    for (const auto &p : kProfiles)",
               "        if (p.device == device && p.chip == chip && p.subvendor == subvendor && p.subdevice == subdevice && !p.kBoardVariant[0]) return p;",
               "    for (const auto &p : kFallbackProfiles)",
               "        if (p.hasFirmware() && p.device == device && p.chip == chip) return p;",
               "    for (const auto &p : kMissingBoardProfiles)",
               "        if (p.device == device && p.chip == chip) return p;",
               "    return kUnavailable;", "}", "}"]
    outputs[root / "src/kext/Ath10kPayload.hpp"] = ("\n".join(header) + "\n").encode()
    # Parse and validate every input before replacing any generated output.
    for path, content in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.read_bytes() == content:
            continue
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_bytes(content)
        tmp.replace(path)
    # Remove the old single-API2-board exports so they cannot be confused with API1 fallback data.
    for family in FAMILIES:
        stale = root / family["output"] / "board.bin"
        if not (root / family["folder"] / "board.bin").exists() and stale.exists():
            stale.unlink()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    try:
        prepare(args.root)
    except (OSError, ValueError) as error:
        print(f"Payload preparation FAILED: {error}", file=sys.stderr)
        sys.exit(1)
