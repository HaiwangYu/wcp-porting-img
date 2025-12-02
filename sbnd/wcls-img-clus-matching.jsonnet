local g = import "pgraph.jsonnet";
local f = import "pgrapher/common/funcs.jsonnet";
local wc = import "wirecell.jsonnet";

local tools_maker = import 'pgrapher/common/tools.jsonnet';

// added Ewerton 2023-09-06 
local reality = std.extVar('reality');
local params_maker =
if reality == 'data' then import 'params.jsonnet'
else import 'simparams.jsonnet';

local base = import 'pgrapher/experiment/sbnd/simparams.jsonnet';
local params = base {
  lar: super.lar { // <- super.lar overrides default values
    // Longitudinal diffusion constant
    DL: std.extVar('DL') * wc.cm2 / wc.s,
    // Transverse diffusion constant
    DT: std.extVar('DT') * wc.cm2 / wc.s,
    // Electron lifetime
    lifetime: std.extVar('lifetime') * wc.ms,
    // Electron drift speed, assumes a certain applied E-field
    drift_speed: std.extVar('driftSpeed') * wc.mm / wc.us,
  },
};


local tools_all = tools_maker(params);
local tools = tools_all {anodes: [tools_all.anodes[n] for n in [0,1]]}; //added Ewerton 2023-09-08

// must match name used in fcl
local wcls_input = {
    sigs: g.pnode({
        type: 'wclsCookedFrameSource', //added wcls Ewerton 2023-07-27
        name: 'sigs',
        data: {
            nticks: params.daq.nticks,
            frame_scale: 50,                             // scale up input recob::Wire by this factor
            summary_scale: 50,                             // scale up input summary by this factor
            frame_tags: ["orig"],                 // frame tags (only one frame in this module)
            recobwire_tags: std.extVar('recobwire_tags'), // ["sptpc2d:gauss", "sptpc2d:wiener"],
            trace_tags: std.extVar('trace_tags'), // ["gauss", "wiener"],
            summary_tags: std.extVar('summary_tags'), // ["", "sptpc2d:wienersummary"],
            input_mask_tags: std.extVar('input_mask_tags'), // ["sptpc2d:badmasks"],
            output_mask_tags: std.extVar('output_mask_tags'), // ["bad"],
        },
    }, nin=0, nout=1),
  opflashes0: g.pnode({
    type: 'wclsOpFlashSource',
    name: 'tpc0',
    data: {
      art_tag: std.extVar('opflash0_input_label'),
    },
  }, nin=0, nout=1),
  opflashes1: g.pnode({
    type: 'wclsOpFlashSource',
    name: 'tpc1',
    data: {
      art_tag: std.extVar('opflash1_input_label'),
    },
  }, nin=0, nout=1),
  opflashes: [wcls_input.opflashes0, wcls_input.opflashes1],
};

local img = import 'pgrapher/experiment/sbnd/img.jsonnet';
local img_maker = img();
local img_pipes = [img_maker.per_anode(a, "multi-3view", add_dump = false) for a in tools.anodes];

local clus = import 'clus.jsonnet';
local clus_maker = clus();
local clus_pipes = [clus_maker.per_apa(anode, dump=false) for anode in tools.anodes];

local img_clus_pipe = [g.intern(
    innodes = [img_pipes[n]],
    centernodes = [],
    outnodes = [clus_pipes[n]],
    edges = [
        g.edge(img_pipes[n], clus_pipes[n], p, p)
        for p in std.range(0, 1)
    ]
)
for n in std.range(0, std.length(tools.anodes) - 1)];

local matching_pipe = [
    g.pnode({
        type: 'QLMatching',
        name: 'matching%d' % n,
        local dv = clus_maker.detector_volumes([tools.anodes[n]]), // face should be 0 for sbnd
        data: {
            anode: wc.tn(tools.anodes[n]),
            detector_volumes: wc.tn(dv),
            bee_dir: "data-sep"
        },
    }, nin=2, nout=1)
    for n in std.range(0, std.length(tools.anodes) - 1)
];

// prefix:
// opflash: "opflash_"
// clbundle: "clbundle_"
local ts_sink = function(name, prefix) {
    // https://github.com/WireCell/wire-cell-toolkit/blob/master/aux/docs/tensor-data-model.org#tensor-archive-files
    local cs = g.pnode({
        type: "TensorFileSink",
        name: "ts_sink-"+name,
        data: {
            outname: "ts-"+name+".tar.gz",
            prefix: prefix,
            dump_mode: true,
        }
    }, nin=1, nout=0),
    ret: cs
}.ret;

local cl_sinks = [
    ts_sink('clbundle%d' % n, 'clbundle_')
    for n in std.range(0, std.length(tools.anodes) - 1)
];

local matching_maker = function(light_pipe, charge_pipe, matching_pipe, outnode=null) {
    ret: if outnode != null then
        g.intern(
            innodes=[charge_pipe],
            outnodes=[outnode],
            centernodes=[
                light_pipe,
                matching_pipe
            ],
            edges=[
                g.edge(charge_pipe, matching_pipe, 0, 0),
                g.edge(light_pipe, matching_pipe, 0, 1),
                g.edge(matching_pipe, outnode, 0, 0),
            ])
        else
        g.intern(
            innodes=[charge_pipe],
            outnodes=[matching_pipe],
            centernodes=[
                light_pipe
            ],
            edges=[
                g.edge(charge_pipe, matching_pipe, 0, 0),
                g.edge(light_pipe, matching_pipe, 0, 1),
            ],
    )
}.ret;

local matching_pipes = [
    matching_maker(
        wcls_input.opflashes[n],
        img_clus_pipe[n],
        matching_pipe[n],
        null /*cl_sinks[n]*/
        )
    for n in std.range(0, std.length(tools.anodes) - 1)
];

local fanout_apa_rules =
[
    {
        frame: {
            //'.*': 'number%d' % n,
            //'.*': 'gauss%d' % n,
            //'.*': 'framefanout%d ' % n,
            '.*': 'orig%d' % n,
        },
        trace: {
            // fake doing Nmult SP pipelines
            //orig: ['wiener', 'gauss'],
            gauss: 'gauss%d' % n, //uncommented Ewerton 2023-09-27
            wiener: 'wiener%d' % n, //created Ewerton 2023-09-27
            //'.*': 'orig',
        },
    }
    for n in std.range(0, std.length(tools.anodes) - 1)
];
local img_clus_per_apa = f.fanout("FrameFanout", matching_pipes, "img_clus_per_apa", fanout_apa_rules);
// local img_clus_per_apa = f.fanout("FrameFanout", img_clus_pipe, "img_clus_per_apa", fanout_apa_rules);

local clus_all_apa = clus_maker.all_apa(tools.anodes);

// local graph = g.pipeline([wcls_input.sigs, img_clus_per_apa], "main");
local graph = g.intern(
    innodes=[wcls_input.sigs],
    centernodes = [img_clus_per_apa],
    outnodes=[clus_all_apa],
    edges=
    [g.edge(wcls_input.sigs, img_clus_per_apa, 0, 0)] +
    [g.edge(img_clus_per_apa, clus_all_apa, i, i) for i in std.range(0, std.length(tools.anodes) - 1)]
);

local app = {
  type: 'Pgrapher', //Pgrapher, TbbFlow
  data: {
    edges: g.edges(graph),
  },
};

local cmdline = {
    type: "wire-cell",
    data: {
        plugins: ["WireCellGen", "WireCellPgraph", "WireCellSio", "WireCellSigProc", "WireCellRoot", "WireCellTbb", "WireCellImg"],
        apps: ["Pgrapher"] //TbbFlow
    }
};

[cmdline] + g.uses(graph) + [app]
// clus_all_apa
