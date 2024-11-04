local wc = import "wirecell.jsonnet";
local g = import "pgraph.jsonnet";
local f = import 'pgrapher/common/funcs.jsonnet';
local params = import "pgrapher/experiment/uboone/simparams.jsonnet";
local tools_maker = import 'pgrapher/common/tools.jsonnet';
local tools = tools_maker(params);
local anodes = tools.anodes;

local cluster_source(fname) = g.pnode({
    type: "ClusterFileSource",
    name: fname,
    data: {
        inname: fname,
        anodes: [wc.tn(a) for a in anodes],
    }
}, nin=0, nout=1, uses=anodes);

function (
    active_clusters = "active-clusters-anode0.npz",
    masked_clusters = "masked-clusters-anode0.npz",
    output = "tensor-apa-uboone.tar.gz",
    bee_dir = "data")

    local active = cluster_source(active_clusters);
    local masked = cluster_source(masked_clusters);

    // Note, the "sampler" must be unique to the "sampling".
    local bs_live = {
        type: "BlobSampler",
        name: "bs_live",
        data: {
            drift_speed: 1.101 * wc.mm / wc.us,
            time_offset: -1600 * wc.us + 6 * wc.mm/self.drift_speed,
            strategy: [
                // "center",
                // "corner",
                // "edge",
                // "bounds",
                "stepped",
                // {name:"grid", step:1, planes:[0,1]},
                // {name:"grid", step:1, planes:[1,2]},
                // {name:"grid", step:1, planes:[2,0]},
                // {name:"grid", step:2, planes:[0,1]},
                // {name:"grid", step:2, planes:[1,2]},
                // {name:"grid", step:2, planes:[2,0]},
            ],
            // extra: [".*"] // want all the extra
            extra: [".*wire_index"] //
            // extra: [] //
        }};
    local bs_dead = {
        type: "BlobSampler",
        name: "bs_dead",
        data: {
            strategy: [
                "center",
            ],
            extra: [".*"] // want all the extra
        }};

    local ptb = g.pnode({
        type: "PointTreeBuilding",
        name: "",
        data:  {
            samplers: {
                "3d": wc.tn(bs_live),
                "dead": wc.tn(bs_dead),
            },
            multiplicity: 2,
            tags: ["live", "dead"],
            anode: wc.tn(anodes[0]),
        }
    }, nin=2, nout=1, uses=[bs_live, bs_dead]);

    local front_end = g.intern(
        innodes = [active, masked],
        outnodes = [ptb],
        edges = [
            g.edge(active, ptb, 0, 0),
            g.edge(masked, ptb, 0, 1),
        ],
        name = "front-end");

    local mabc = g.pnode({
        type: "MultiAlgBlobClustering",
        name: "",
        data:  {
            inpath: "pointtrees/%d",
            outpath: "pointtrees/%d",
            perf: true,
            bee_dir: bee_dir, // "data/0/0",
            save_deadarea: true, 
            // bee_dir: "", // "data/0/0",
            anode: wc.tn(anodes[0]),
            func_cfgs: [
                {name: "clustering_live_dead", dead_live_overlap_offset: 2},
                {name: "clustering_extend", flag: 4, length_cut: 60 * wc.cm, num_try: 0, length_2_cut: 15 * wc.cm, num_dead_try: 1},
                {name: "clustering_regular", length_cut: 60*wc.cm, flag_enable_extend: false},
                {name: "clustering_regular", length_cut: 30*wc.cm, flag_enable_extend: true},
                {name: "clustering_parallel_prolong", length_cut: 35*wc.cm},
                {name: "clustering_close", length_cut: 1.2*wc.cm},
                {name: "clustering_extend_loop", num_try: 3},
                {name: "clustering_separate", use_ctpc: true},
                {name: "clustering_connect1"},
                {name: "clustering_deghost"},
                {name: "clustering_examine_x_boundary"},
                {name: "clustering_protect_overclustering"},
                {name: "clustering_neutrino"},
                // {name: "clustering_isolated"},
            ],
        }
    }, nin=1, nout=1, uses=[]);

    local sink = g.pnode({
        type: "TensorFileSink",
        name: output,
        data: {
            outname: output,
            prefix: "clustering_", // json, numpy, dummy
            dump_mode: true,
        }
    }, nin=1, nout=0);

    local graph = g.pipeline([front_end, mabc, sink]);

    local app = {
        type: 'Pgrapher', //Pgrapher, TbbFlow
        data: {
            edges: g.edges(graph),
        },
    };
    local cmdline = {
        type: "wire-cell",
        data: {
            plugins: ["WireCellGen", "WireCellPgraph", /*"WireCellTbb",*/
                      "WireCellSio", "WireCellSigProc", "WireCellRoot", "WireCellImg", "WireCellClus"],
        apps: [wc.tn(app)]
        },
    };

    [cmdline] + g.uses(graph) + [app]
