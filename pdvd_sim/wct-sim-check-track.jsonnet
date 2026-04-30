// wct-sim-check-track.jsonnet
//
// Simulate the longest track from a woodpecker extract-tracks JSON file,
// run noise filtering, and save the resulting raw (NF output) frames.
//
// Usage:
//   wire-cell \
//     --tla-code "tracks_json=$(cat woodpecker_data/tracks-upload.json)" \
//     --tla-str  output_prefix=woodpecker_data/protodune-sp-frames-sim \
//     --tla-code anode_indices='[2]' \
//     -c wcp-porting-img/pdvd/wct-sim-check-track.jsonnet
//
// Parameters
// ----------
//   tracks_json    : content of tracks-*.json from 'woodpecker extract-tracks'
//                    passed via --tla-code so the shell expands it as a value:
//                    --tla-code "tracks_json=$(cat file.json)"
//   anode_indices  : jsonnet array of anode indices to simulate (default: all)
//   output_prefix  : prefix for output tar.bz2 files
//                    output: <output_prefix>-anode<N>.tar.bz2
//                    (default: 'woodpecker_data/protodune-sp-frames-sim')

local g = import 'pgraph.jsonnet';
local f = import 'pgrapher/common/funcs.jsonnet';
local wc = import 'wirecell.jsonnet';

local tools_maker = import 'pgrapher/common/tools.jsonnet';
local params = import 'pgrapher/experiment/protodunevd/simparams.jsonnet';

local tools_all = tools_maker(params);

local sim_maker = import 'pgrapher/experiment/protodunevd/sim.jsonnet';
local sim = sim_maker(params, tools_all);

function(
    tracks_json    = '[]',
    anode_indices  = std.range(0, std.length(tools_all.anodes) - 1),
    output_prefix  = 'woodpecker_data/protodune-sp-frames-sim',
)

// ── Pick the longest track ─────────────────────────────────────────────────
// tracks_json arrives as a jsonnet array (passed via --tla-code)
local sorted_tracks = std.sort(tracks_json, keyF=function(t) -t.length_cm);
local best_track = sorted_tracks[0];

local s = best_track.start;  // [x, y, z] in cm
local e = best_track.end;

local tracklist = [{
    time:   0 * wc.us,
    charge: -500,   // ~2000 e/mm
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
local perfect = import 'pgrapher/experiment/protodunevd/chndb-base.jsonnet';
local chndb = [{
    type: 'OmniChannelNoiseDB',
    name: 'ocndbperfect%d' % anodes[n].data.ident,
    data: perfect(params, anodes[n], tools_all.field, anodes[n].data.ident) { dft: wc.tn(tools_all.dft) },
    uses: [anodes[n], tools_all.field, tools_all.dft],
} for n in anode_iota];

local nf_maker = import 'pgrapher/experiment/protodunevd/nf.jsonnet';
// nf.jsonnet hardcodes intraces:'orig' (frame tag).
// Digitizer outputs frame tag 'orig<ident>', so add a frame-level retagger first.
local frame_retagger(anode_ident) = g.pnode({
    type: 'Retagger',
    name: 'simretag%d' % anode_ident,
    data: {
        tag_rules: [{
            frame: { ['orig%d' % anode_ident]: 'orig' },
        }],
    },
}, nin=1, nout=1);

local nf_pipes = [
    nf_maker(params, anodes[n], chndb[n], anodes[n].data.ident,
             name='nf%d' % anodes[n].data.ident)
    for n in anode_iota
];

// ── FrameFileSink — saves NF output frames (tag: raw<ident>) ──────────────
// Placed at end of per-anode pipeline; saves NF output tag 'raw<ident>'.
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

// ── Per-anode pipeline: sim+noise → retag → NF → tap(file) ───────────────
// sim.splusn_pipelines is indexed over ALL anodes (0..7); use anode_indices[n].
// Digitizer outputs frame tag 'orig<ident>' but nf.jsonnet reads frame tag 'orig',
// so insert a frame Retagger to rename orig<ident> → orig before NF.
local sn_pipes = sim.splusn_pipelines;

local raw_pipes = [
    g.pipeline([
        sn_pipes[anode_indices[n]],
        frame_retagger(anodes[n].data.ident),
        nf_pipes[n],
        frame_sink(anodes[n].data.ident),
    ], 'sim_raw_pipe_%d' % n)
    for n in anode_iota
];

// DepoSetFanout → [sim+retag+NF+sink per anode]
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
