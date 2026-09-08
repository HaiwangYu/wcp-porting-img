// doc pdhd/16 sec 9 -- re-run the MCS engine over an arm's own muon clouds at
// several cathode-band half-widths, WITHOUT re-running the arm.
//
// This exists to produce the negative control the doc never had: every MCS
// number in doc pdhd/16 sec 6.4 was measured with mcs_cathode_xcut already at
// 5 cm, so nothing on record says what the excision does on a ProtoDUNE.
// xcut = 0 is that control (mcs/inc/WireCellMcs/MuonMCS.h:79, "0 = off,
// bit-for-bit upstream").
//
// The engine is used verbatim, exactly as CheckSTM_Michel::fill_mcs uses it
// (CheckSTM_Michel.cxx:855-858): default McsOptions -- the five upstream-bug
// fixes stay ON -- with only cathode_x/cathode_xcut set.  What is
// reimplemented here is the INPUT ASSEMBLY, which is why the caller must gate
// the xcut = 5 column against the arm's own persisted values before believing
// any other column.
//
// Input: the text stream written by d16_mcs_cathode_export.py.
// Output: one TSV row per (muon, xcut) on stdout.
//
// Build: ./d16_mcs_cathode_build.sh

#include "WireCellMcs/MuonMCS.h"

#include <cmath>
#include <cstdio>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

using WireCell::Mcs::McsOptions;
using WireCell::Mcs::McsResult;
using WireCell::Mcs::MuonMCS;

namespace {

struct Muon {
    std::string det, tag;
    int cid{0}, is_stm{0}, nsegs_ref{0}, bad_ref{0};
    double len{0}, ke_range{0}, ke_mcs_ref{0}, amb_ref{0}, tracklen_ref{0};
    std::vector<double> start, stop;
    std::vector<std::vector<double>> pts;
};

bool read_muon(std::istream& in, Muon& m)
{
    std::string line, kw;
    while (std::getline(in, line)) {
        if (line.compare(0, 5, "MUON ") != 0) continue;
        std::istringstream s(line);
        s >> kw >> m.det >> m.tag >> m.cid >> m.is_stm >> m.len >> m.ke_range
          >> m.ke_mcs_ref >> m.amb_ref >> m.nsegs_ref >> m.bad_ref >> m.tracklen_ref;

        std::getline(in, line);
        std::istringstream v(line);
        m.start.assign(3, 0.0);
        m.stop.assign(3, 0.0);
        v >> kw >> m.start[0] >> m.start[1] >> m.start[2]
          >> m.stop[0] >> m.stop[1] >> m.stop[2];

        std::getline(in, line);
        std::istringstream n(line);
        int npts = 0;
        n >> kw >> npts;
        m.pts.assign(npts, std::vector<double>(3, 0.0));
        for (int i = 0; i < npts; ++i) {
            std::getline(in, line);
            std::istringstream p(line);
            p >> m.pts[i][0] >> m.pts[i][1] >> m.pts[i][2];
        }
        return true;
    }
    return false;
}

}  // namespace

int main(int argc, char** argv)
{
    std::vector<double> xcuts;
    for (int i = 1; i < argc; ++i) xcuts.push_back(std::atof(argv[i]));
    if (xcuts.empty()) xcuts = {0.0, 5.0, 8.0, 10.0, 15.0};

    // Both ProtoDUNEs and SBND are cathode-centred at x = 0, and every
    // inter-TPC seam on all three is in y or z -- never x.  So one plane is
    // the complete description, not a simplification.
    const double cathode_x = 0.0;

    std::printf("det\ttag\tcid\tis_stm\tlen\tke_range\tke_mcs_ref\tnsegs_ref"
                "\txcut\tke_mcs\tamb\tnsegs\tbad_path\tcath_segs\tcath_angles"
                "\ttracklen\tminabsx\tcrosses\n");

    Muon m;
    long nmuon = 0;
    while (read_muon(std::cin, m)) {
        ++nmuon;
        // Cloud-level geometry, so the analysis can stratify without the tree.
        double minabsx = 1e30, xlo = 1e30, xhi = -1e30;
        for (const auto& p : m.pts) {
            minabsx = std::min(minabsx, std::fabs(p[0]));
            xlo = std::min(xlo, p[0]);
            xhi = std::max(xhi, p[0]);
        }
        const int crosses = (xlo < cathode_x && xhi > cathode_x) ? 1 : 0;

        for (double xc : xcuts) {
            McsOptions opt;             // the five upstream-bug fixes stay ON
            opt.cathode_x = cathode_x;
            opt.cathode_xcut = xc;
            const McsResult r = MuonMCS(opt).run(m.start, m.stop, m.pts);
            // %.17g throughout: the xcut = 5 column is gated for BIT
            // equality against the arm's own persisted values, so the text
            // must not be the thing that loses the last bits.
            std::printf("%s\t%s\t%d\t%d\t%.17g\t%.17g\t%.17g\t%d"
                        "\t%.2f\t%.17g\t%.17g\t%d\t%d\t%d\t%d\t%.17g\t%.17g\t%d\n",
                        m.det.c_str(), m.tag.c_str(), m.cid, m.is_stm, m.len,
                        m.ke_range, m.ke_mcs_ref, m.nsegs_ref,
                        xc, r.ke_MCS, r.ambiguity_MCS, r.nsegs,
                        r.bad_path ? 1 : 0, r.counters.cathode_seg_dropped,
                        r.counters.cathode_angle_masked, r.mu_tracklen,
                        minabsx, crosses);
        }
    }
    std::fprintf(stderr, "swept %ld muons x %zu xcut values\n", nmuon, xcuts.size());
    return 0;
}
