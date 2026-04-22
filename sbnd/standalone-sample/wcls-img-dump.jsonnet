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

local wcls_input = g.pnode({
    type: 'wclsCookedFrameSource',
    name: 'sigs',
    data: {
        nticks: params.daq.nticks,
        frame_scale: 50,
        summary_scale: 50,
        frame_tags: ["orig"],
        recobwire_tags: std.extVar('recobwire_tags'),
        trace_tags: std.extVar('trace_tags'),
        summary_tags: std.extVar('summary_tags'),
        input_mask_tags: std.extVar('input_mask_tags'),
        output_mask_tags: std.extVar('output_mask_tags'),
    },
}, nin=0, nout=1);

local img = import 'pgrapher/experiment/sbnd/img.jsonnet';
local img_maker = img();
local img_pipes = [img_maker.per_anode(a, "multi-3view", add_dump = false) for a in tools.anodes];

local ClusterFileSink(fname) = g.pnode({
    type: 'ClusterFileSink',
    name: fname,
    data: {
        format: "numpy",
        outname: fname,
    },
}, nin=1, nout=0);

// port 0: active (live) clusters, port 1: masked (dead) clusters
local cfsinks_active = [ClusterFileSink("icluster-apa%d-active.npz" % n) for n in std.range(0, std.length(tools.anodes) - 1)];
local cfsinks_masked = [ClusterFileSink("icluster-apa%d-masked.npz" % n) for n in std.range(0, std.length(tools.anodes) - 1)];

local img_dump_pipe = [g.intern(
    innodes = [img_pipes[n]],
    centernodes = [],
    outnodes = [cfsinks_active[n], cfsinks_masked[n]],
    edges = [
        g.edge(img_pipes[n], cfsinks_active[n], 0, 0),
        g.edge(img_pipes[n], cfsinks_masked[n], 1, 0)
    ]
)
for n in std.range(0, std.length(tools.anodes) - 1)];

local fanout_apa_rules =
[
    {
        frame: {
            '.*': 'orig%d' % n,
        },
        trace: {
            gauss: 'gauss%d' % n,
            wiener: 'wiener%d' % n,
        },
    }
    for n in std.range(0, std.length(tools.anodes) - 1)
];
local parallel_graph = f.fanout("FrameFanout", img_dump_pipe, "parallel_graph", fanout_apa_rules);

local graph = g.pipeline([wcls_input, parallel_graph], "main");

local app = {
  type: 'Pgrapher',
  data: {
    edges: g.edges(graph),
  },
};

local cmdline = {
    type: "wire-cell",
    data: {
        plugins: ["WireCellGen", "WireCellPgraph", "WireCellSio", "WireCellSigProc", "WireCellRoot", "WireCellTbb", "WireCellImg"],
        apps: ["Pgrapher"]
    }
};

[cmdline] + g.uses(graph) + [app]
