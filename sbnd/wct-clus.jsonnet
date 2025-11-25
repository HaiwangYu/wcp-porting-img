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
local tools = tools_all {anodes: [tools_all.anodes[n] for n in [0,1]]};

local cluster_source(fname) = g.pnode({
    type: "ClusterFileSource",
    name: fname,
    data: {
        inname: fname,
        anodes: [wc.tn(a) for a in tools.anodes],
    }
}, nin=0, nout=1, uses=tools.anodes);
local input = std.extVar('input');
local active_files = [ "%s/sbnd_live_clus_apa%d.npz"%[input, a.data.ident] for a in tools.anodes];
local masked_files = [ "%s/sbnd_dead_clus_apa%d.npz"%[input, a.data.ident] for a in tools.anodes];
local active_clusters = [cluster_source(f) for f in active_files];
local masked_clusters = [cluster_source(f) for f in masked_files];

local clus = import 'clus.jsonnet';
local clus_maker = clus();
local clus_pipes = [clus_maker.per_apa(anode, dump=false) for anode in tools.anodes];

local img_clus_pipe = [g.intern(
    innodes = [active_clusters[n], masked_clusters[n]],
    centernodes = [],
    outnodes = [clus_pipes[n]],
    edges = [
        g.edge(active_clusters[n], clus_pipes[n], 0, 0),
        g.edge(masked_clusters[n], clus_pipes[n], 0, 1),
    ]
)
for n in std.range(0, std.length(tools.anodes) - 1)];

// Bundle per-APA subgraphs into a single graph node so g.edges/g.uses
// operate on a Pnode instead of a raw array.
local graph = g.components(img_clus_pipe, "main");

local clus_all_apa = clus_maker.all_apa(tools.anodes);

local parallel_graph = 
 {
    local begin = img_clus_pipe,
    local end = clus_all_apa,
    ret :: g.intern(
        innodes=[begin],
        outnodes=[end],
        edges=[g.edge(begin, end, i, i) for i in std.range(0, std.length(tools.anodes) - 1)]
    ),
}.ret;

local graph = g.intern(
    innodes=img_clus_pipe,
    outnodes=[clus_all_apa],
    edges=[g.edge(img_clus_pipe[i], clus_all_apa, 0, i) for i in std.range(0, std.length(tools.anodes) - 1)]
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
        plugins: ["WireCellGen", "WireCellPgraph", "WireCellSio", "WireCellSigProc", "WireCellImg", "WireCellRoot", "WireCellTbb", "WireCellClus"],
        apps: ["Pgrapher"] //TbbFlow
    }
};

[cmdline] + g.uses(graph) + [app]
// clus_pipes
