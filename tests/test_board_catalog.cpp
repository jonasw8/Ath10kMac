#include <cassert>
#include <cstdio>
#include <cstring>
#include <initializer_list>
#include "Ath10kPayload.hpp"

int main() {
    using namespace Ath10kPayload;
    const auto &dell=selectProfile(0x168c,0x003e,0x1028,0x0310,10);
    const auto &killer=selectProfile(0x168c,0x003e,0x1a56,0x143a,10);
    const auto &lenovo=selectProfile(0x168c,0x0042,0x17aa,0x0901,1);
    assert(dell.available && killer.available && lenovo.available);
    assert(!strcmp(dell.kBoardSHA256,"7b01edabe0fc9071abe4d20c7f336fc5e4dc6e2ed4803df54487eef155b16862"));
    assert(!strcmp(killer.kBoardSHA256,"968e3a8fe226d691f4e5c526e05700ee3519e86237eceedd6f2fd2e85c201ce7"));
    assert(!strcmp(lenovo.kBoardSHA256,"34a25b4120d7c1a9bf9c4136ccf9ce0abe95fd8ab367fe0f1707b1674a8ef673"));
    assert(dell.kFirmware==killer.kFirmware && dell.kOTP==killer.kOTP);
    assert(dell.kBoard!=killer.kBoard && lenovo.kFirmware!=dell.kFirmware);
    unsigned entries=0,variants=0;
    for(const auto &p:kProfiles) {
        const auto &selected=selectProfile(0x168c,p.device,p.subvendor,p.subdevice,p.chip,p.kBoardVariant);
        assert(&selected==&p && p.matchesTarget(p.targetVersion,8,12));
        assert(!p.matchesTarget(0,8,12) && !p.matchesTarget(p.targetVersion,7,12));
        assert(!p.matchesTarget(p.targetVersion,8,8));
        assert(!strcmp(p.kBoardSelection,p.kBoardVariant[0]?"board-api2-variant":"board-api2-exact"));
        ++entries;
        if(p.kBoardVariant[0]) ++variants;
        for(const auto &other:kProfiles)
            if(p.device==other.device && !strcmp(p.kBoardSHA256,other.kBoardSHA256)) assert(p.kBoard==other.kBoard);
    }
    assert(entries>=114 && variants>=12);
    // An unknown variant falls back to the exact, unqualified PCI key.
    assert(&selectProfile(0x168c,0x003e,0x1028,0x0310,10,"unknown")==&dell);
    const auto &fallback=selectProfile(0x168c,0x0042,0xbeef,0xcafe,1);
    assert(fallback.available && !strcmp(fallback.kBoardSelection,"board-api1-fallback"));
    assert(!strcmp(fallback.kBoardSHA256,"127d35d82edb46278f30c448cbca664d755ff0d5fed57b649959cdbc4208c768"));
    assert(fallback.kBoard!=lenovo.kBoard && fallback.kFirmware==lenovo.kFirmware);
    // A missing board retains firmware identity, never another manufacturer's board.
    const auto &missing=selectProfile(0x168c,0x003e,0xbeef,0xcafe,10);
    assert(!missing.available && !missing.kBoard && missing.kBoardSize==0);
    assert(missing.matchesFirmwareTarget(0x05030000,8,12) && !missing.matchesTarget(0x05030000,8,12));
    for(const auto *p:{&selectProfile(0x1234,0x0042,0x17aa,0x0901,1),
                       &selectProfile(0x168c,0x0042,0x17aa,0x0901,0),
                       &selectProfile(0x168c,0x003e,0x1028,0x0310,8)})
        assert(!p->hasFirmware() && !p->available);
    printf("Board catalog passed: %u exact keys (%u variants), Dell/Killer/Lenovo hashes, shared firmware, deduplicated boards, chip fallback and missing-board/ROM guards.\n",entries,variants);
}
