// Standalone WCT config: read image clusters + opflash files produced by
// wcls-img-dump and wcls-flash-dump, run per-APA clustering + QL matching +
// all-APA clustering.
//
// Run with:
//   wire-cell -V reality=sim \
//             -V DL=6.2 -V DT=9.8 -V lifetime=6 -V driftSpeed=1.565 \
//             -V input=. \
//             -c wct-clus-matching.jsonnet

local g = import "pgraph.jsonnet";
local f = import "pgrapher/common/funcs.jsonnet";
local wc = import "wirecell.jsonnet";

local tools_maker = import 'pgrapher/common/tools.jsonnet';

local reality = std.extVar('reality');

local base = import 'pgrapher/experiment/sbnd/simparams.jsonnet';
local params = base {
  lar: super.lar {
    DL: std.extVar('DL') * wc.cm2 / wc.s,
    DT: std.extVar('DT') * wc.cm2 / wc.s,
    lifetime: std.extVar('lifetime') * wc.ms,
    drift_speed: std.extVar('driftSpeed') * wc.mm / wc.us,
  },
};

local tools_all = tools_maker(params);
local tools = tools_all {anodes: [tools_all.anodes[n] for n in [0,1]]};

// Directory containing icluster-apa{n}-active/masked.npz files
local input = std.extVar('input');

// --- Sources ---

local ClusterFileSource(fname) = g.pnode({
    type: "ClusterFileSource",
    name: fname,
    data: {
        inname: fname,
        anodes: [wc.tn(a) for a in tools.anodes],
    }
}, nin=0, nout=1, uses=tools.anodes);

local active_clusters = [
    ClusterFileSource("%s/icluster-apa%d-active.npz" % [input, tools.anodes[n].data.ident])
    for n in std.range(0, std.length(tools.anodes) - 1)
];
local masked_clusters = [
    ClusterFileSource("%s/icluster-apa%d-masked.npz" % [input, tools.anodes[n].data.ident])
    for n in std.range(0, std.length(tools.anodes) - 1)
];

local opflash_sources = [
    g.pnode({
        type: "TensorFileSource",
        name: "opflash_src_apa%d" % n,
        data: {
            inname: "opflash_apa%d.tar.gz" % n,
            prefix: "opflash_",
        }
    }, nin=0, nout=1)
    for n in std.range(0, std.length(tools.anodes) - 1)
];

// --- Per-APA clustering ---

local clus = import '../clus.jsonnet';
local clus_maker = clus();
local clus_pipes = [clus_maker.per_apa(tools.anodes[n], dump=false) for n in std.range(0, std.length(tools.anodes) - 1)];

// --- QL Matching ---

local matching_pipes = [
    g.pnode({
        type: 'QLMatching',
        name: 'matching%d' % n,
        local dv = clus_maker.detector_volumes([tools.anodes[n]]),
        data: {
            anode: wc.tn(tools.anodes[n]),
            detector_volumes: wc.tn(dv),
            bee_dir: "data-sep",
            beamonly: false,
            data: if reality == 'data' then true else false,
            QtoL: 1.0,
            ch_mask: [39, 64, 66, 71, 85, 86, 87, 115, 138, 141, 197, 217, 221, 222, 223, 226, 245, 249, 302],
            flash_minPE: 50,
        },
    }, nin=2, nout=1)
    for n in std.range(0, std.length(tools.anodes) - 1)
];

// --- Per-APA subgraphs ---
// Each combines: ClusterFileSource(active) + ClusterFileSource(masked) →
//                clus_per_apa → ql_matching ← TensorFileSource(opflash)

local per_apa = [g.intern(
    innodes=[active_clusters[n], masked_clusters[n], opflash_sources[n]],
    centernodes=[clus_pipes[n]],
    outnodes=[matching_pipes[n]],
    edges=[
        g.edge(active_clusters[n], clus_pipes[n], 0, 0),
        g.edge(masked_clusters[n], clus_pipes[n], 0, 1),
        g.edge(clus_pipes[n], matching_pipes[n], 0, 0),
        g.edge(opflash_sources[n], matching_pipes[n], 0, 1),
    ]
) for n in std.range(0, std.length(tools.anodes) - 1)];

// --- All-APA clustering ---

local clus_all_apa = clus_maker.all_apa(tools.anodes, dump=true);

// --- Top-level graph ---
// Connect both per-APA matching outputs into all-APA clustering.

local graph = g.intern(
    innodes=per_apa,
    outnodes=[clus_all_apa],
    edges=[g.edge(per_apa[i], clus_all_apa, 0, i) for i in std.range(0, std.length(tools.anodes) - 1)]
);

local app = {
  type: 'Pgrapher',
  data: {
    edges: g.edges(graph),
  },
};

local cmdline = {
    type: "wire-cell",
    data: {
        plugins: ["WireCellGen", "WireCellPgraph", "WireCellSio", "WireCellSigProc",
                  "WireCellImg", "WireCellRoot", "WireCellTbb", "WireCellClus", "WireCellQLMatch"],
        apps: ["Pgrapher"]
    }
};

[cmdline] + g.uses(graph) + [app]
