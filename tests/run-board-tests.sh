#!/bin/sh
# Portable host tests for the catalog and the actual BMI/PLL/board methods.
set -eu
cd "$(dirname "$0")/.."
python3 scripts/prepare-firmware.py
python3 -m unittest discover -s tests -p 'test_payload.py' -v
board_test_tmp=$(mktemp -d)
trap 'rm -rf "$board_test_tmp"' EXIT HUP INT TERM
mkdir -p "$board_test_tmp/IOKit"
cp tests/mock_iolib.h "$board_test_tmp/IOKit/IOLib.h"
cat > "$board_test_tmp/IOKit/IOTypes.h" <<'EOF'
#pragma once
#include <cstdint>
using UInt8=uint8_t;
using UInt16=uint16_t;
using UInt32=uint32_t;
using UInt64=uint64_t;
EOF
python3 tests/extract-production.py "$board_test_tmp/driver_methods.inc"
for target in board_catalog pll pll_memory board_flow bmi_identity qca9377_flow; do
    "${CXX:-c++}" -std=c++17 -O1 -pthread -Wall -Wextra -Werror \
        -fsanitize=address,undefined -I"$board_test_tmp" -Isrc/kext \
        "tests/test_${target}.cpp" -o "$board_test_tmp/$target"
    ASAN_OPTIONS=detect_leaks=0 "$board_test_tmp/$target"
    echo "Board regression passed: $target"
done
echo 'Automatic board-selection host tests passed; physical hardware was not exercised.'
