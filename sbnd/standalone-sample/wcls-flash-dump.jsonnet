local wc = import 'wirecell.jsonnet';
local g = import 'pgraph.jsonnet';

local data_params = import 'pgrapher/experiment/sbnd/params.jsonnet';
local simu_params = import 'pgrapher/experiment/sbnd/simparams.jsonnet';

local reality = std.extVar('reality');
local params = if reality == 'data' then data_params else simu_params;

local tools_maker = import 'pgrapher/common/tools.jsonnet';
local tools_all = tools_maker(params);
local tools = tools_all {anodes: [tools_all.anodes[n] for n in [0,1]]};

local opflash_srcs = [
    g.pnode({
        type: 'wclsOpFlashSource',
        name: 'tpc%d' % n,
        data: {
            art_tag: std.extVar('opflash%d_input_label' % n),
        },
    }, nin=0, nout=1)
    for n in std.range(0, std.length(tools.anodes) - 1)
];

local opflash_sinks = [
    g.pnode({
        type: "TensorFileSink",
        name: "opflash_sink_apa%d" % n,
        data: {
            outname: "opflash_apa%d.tar.gz" % n,
            prefix: "opflash_",
            dump_mode: true,
        }
    }, nin=1, nout=0)
    for n in std.range(0, std.length(tools.anodes) - 1)
];

local pipes = [g.pipeline([opflash_srcs[n], opflash_sinks[n]]) for n in std.range(0, std.length(tools.anodes) - 1)];

local app = {
    type: 'Pgrapher',
    data: {
        edges: std.foldl(function(acc, p) acc + g.edges(p), pipes, []),
    },
};

std.foldl(function(acc, p) acc + g.uses(p), pipes, []) + [app]
