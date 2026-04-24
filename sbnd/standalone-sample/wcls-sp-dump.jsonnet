local g = import "pgraph.jsonnet";
local wc = import "wirecell.jsonnet";

local params = import 'pgrapher/experiment/sbnd/simparams.jsonnet';

local wcls_input = g.pnode({
    type: 'wclsCookedFrameSource',
    name: 'sigs',
    data: {
        nticks: params.daq.nticks,
        frame_scale: 50,
        summary_scale: 50,
        frame_tags: ["orig"],
        recobwire_tags:   std.extVar('recobwire_tags'),
        trace_tags:       std.extVar('trace_tags'),
        summary_tags:     std.extVar('summary_tags'),
        input_mask_tags:  std.extVar('input_mask_tags'),
        output_mask_tags: std.extVar('output_mask_tags'),
    },
}, nin=0, nout=1);

local sink = g.pnode({
    type: "FrameFileSink",
    data: {
        outname: std.extVar('outname'),
        tags: std.extVar('trace_tags'),
        digitize: false, // float32 output
        masks: true,     // include chanmask_<name>_<ident>.npy arrays
    },
}, nin=1, nout=0);

local graph = g.pipeline([wcls_input, sink], "main");

local app = {
    type: 'Pgrapher',
    data: { edges: g.edges(graph) },
};

local cmdline = {
    type: "wire-cell",
    data: {
        plugins: ["WireCellGen", "WireCellPgraph", "WireCellSio", "WireCellRoot", "WireCellLarsoft"],
        apps: ["Pgrapher"],
    }
};

[cmdline] + g.uses(graph) + [app]
