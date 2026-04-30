// wct-sim-check-track.jsonnet  (ProtoDUNE-HD variant)
//
// Simulate the longest track from a woodpecker extract-tracks JSON file,
// run noise filtering, and save the resulting raw (NF output) frames.
//
// Mirrors wcp-porting-img/pdvd/wct-sim-check-track.jsonnet but uses HD
// imports (pgrapher/experiment/pdhd/...) and the HD-specific lar overrides
// from toolkit/cfg/pgrapher/experiment/pdhd/wct-sim-check.jsonnet.
//
// Usage:
//   wire-cell \
//     --tla-code "tracks_json=$(cat woodpecker_data/tracks-upload.json)" \
//     --tla-str  output_prefix=woodpecker_data/protodunehd-sp-frames-sim \
//     --tla-code anode_indices='[0]' \
//     -c wcp-porting-img/pdhd/wct-sim-check-track.jsonnet
//
// Parameters
// ----------
//   tracks_json    : content of tracks-*.json from 'woodpecker extract-tracks'
//                    passed via --tla-code so the shell expands it as a value.
//   anode_indices  : jsonnet array of anode indices to simulate (default: all 0..3)
//   output_prefix  : prefix for output tar.bz2 files
//                    output: <output_prefix>-anode<N>.tar.bz2

local g = import 'pgraph.jsonnet';
local f = import 'pgrapher/common/funcs.jsonnet';
local wc = import 'wirecell.jsonnet';

local tools_maker = import 'pgrapher/common/tools.jsonnet';
local base = import 'pgrapher/experiment/pdhd/simparams.jsonnet';

// HD lar overrides — keep consistent with
// toolkit/cfg/pgrapher/experiment/pdhd/wct-sim-check.jsonnet
local params = base {
    lar: super.lar {
        DL: 6.2 * wc.cm2 / wc.s,
        DT: 16.3 * wc.cm2 / wc.s,
        lifetime: 50 * wc.ms,
        drift_speed: 1.565 * wc.mm / wc.us,
    },
};

local tools_all = tools_maker(params);

local sim_maker = import 'pgrapher/experiment/pdhd/sim.jsonnet';
local sim = sim_maker(params, tools_all);

function(
    tracks_json    = '[]',
    anode_indices  = std.range(0, std.length(tools_all.anodes) - 1),
    output_prefix  = 'woodpecker_data/protodunehd-sp-frames-sim',
)

// ── Pick the longest track ─────────────────────────────────────────────────
local sorted_tracks = std.sort(tracks_json, keyF=function(t) -t.length_cm);
local best_track = sorted_tracks[0];

local s = best_track.start;  // [x, y, z] in cm
local e = best_track.end;

local tracklist = [{
    time:   0 * wc.us,
    charge: -500,   // MIP, ~5000 e/mm at step=0.1 mm
    ray: {
        tail: wc.point(s[0], s[1], s[2], wc.cm),
        head: wc.point(e[0], e[1], e[2], wc.cm),
    },
}];

local depos = sim.tracks(tracklist, step=0.1 * wc.mm);

// ── Select anodes ──────────────────────────────────────────────────────────
local anodes = [tools_all.anodes[i] for i in anode_indices];
local nanodes = std.length(anodes);
local anode_iota = std.range(0, nanodes - 1);

// ── NF ─────────────────────────────────────────────────────────────────────
local perfect = import 'pgrapher/experiment/pdhd/chndb-base.jsonnet';
local chndb = [{
    type: 'OmniChannelNoiseDB',
    name: 'ocndbperfect%d' % anodes[n].data.ident,
    data: perfect(params, anodes[n], tools_all.field, anodes[n].data.ident) { dft: wc.tn(tools_all.dft) },
    uses: [anodes[n], tools_all.field, tools_all.dft],
} for n in anode_iota];

local nf_maker = import 'pgrapher/experiment/pdhd/nf.jsonnet';
// HD nf.jsonnet uses intraces:'' (wildcard), so no frame retagger needed.
local nf_pipes = [
    nf_maker(params, anodes[n], chndb[n], anodes[n].data.ident,
             name='nf%d' % anodes[n].data.ident)
    for n in anode_iota
];

// ── FrameFileSink — saves NF output frames (tag: raw<ident>) ──────────────
local frame_sink(anode_ident) =
    g.pnode({
        type: 'FrameFileSink',
        name: 'simframesink%d' % anode_ident,
        data: {
            outname: '%s-anode%d.tar.bz2' % [output_prefix, anode_ident],
            tags: ['raw%d' % anode_ident],
            digitize: false,
            masks: false,
        },
    }, nin=1, nout=0);

// ── Per-anode pipeline: sim+noise → NF → tap(file) ─────────────────────────
// sim.splusn_pipelines is indexed over ALL anodes (0..nanodes_total-1).
local sn_pipes = sim.splusn_pipelines;

local raw_pipes = [
    g.pipeline([
        sn_pipes[anode_indices[n]],
        nf_pipes[n],
        frame_sink(anodes[n].data.ident),
    ], 'sim_raw_pipe_%d' % n)
    for n in anode_iota
];

// DepoSetFanout → [sim+NF+sink per anode]
// Each pipe ends in a sink (nout=0), so use f.fan.sink instead of fanpipe.
local parallel_graph = g.fan.sink('DepoSetFanout', raw_pipes, 'sim_raw');

local drifter = sim.drifter;
local bagger  = sim.make_bagger();

local graph = g.pipeline([depos, drifter, bagger, parallel_graph]);

local app = {
    type: 'Pgrapher',
    data: { edges: g.edges(graph) },
};

local cmdline = {
    type: 'wire-cell',
    data: {
        plugins: ['WireCellGen', 'WireCellPgraph', 'WireCellSio',
                  'WireCellSigProc', 'WireCellRoot', 'WireCellTbb'],
        apps: ['Pgrapher'],
    },
};

[cmdline] + g.uses(graph) + [app]
