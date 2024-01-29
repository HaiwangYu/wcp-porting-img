local wc = import "wirecell.jsonnet";
local g = import "pgraph.jsonnet";
local f = import 'pgrapher/common/funcs.jsonnet';
local params = import "pgrapher/experiment/uboone/simparams.jsonnet";
local tools_maker = import 'pgrapher/common/tools.jsonnet';
local tools = tools_maker(params);
local anodes = tools.anodes;

local img = {
    // IFrame -> IFrame
    pre_proc :: function(anode, aname = "") {
    local dumpframes = g.pnode({
        type: "DumpFrames",
        name: 'dumpframe',
    }, nin=1, nout=0),

    local magdecon = g.pnode({
        type: 'MagnifySink',
        name: 'magdecon',
        data: {
            output_filename: "mag.root",
            root_file_mode: 'UPDATE',
            frames: ['gauss', 'wiener', 'gauss_error'],
            cmmtree: [['bad','bad']],
            summaries: ['gauss', 'wiener', 'gauss_error'],
            trace_has_tag: true,
            anode: wc.tn(anode),
        },
    }, nin=1, nout=1, uses=[anode]),

    local waveform_map = {
        type: 'WaveformMap',
        name: 'wfm',
        data: {
            filename: "microboone-charge-error.json.bz2",
        }, uses: [],},

    local charge_err = g.pnode({
        type: 'ChargeErrorFrameEstimator',
        name: 'cefe',
        data: {
            intag: "gauss",
            outtag: 'gauss_error',
            anode: wc.tn(anode),
            rebin: 4,  // this number should be consistent with the waveform_map choice
            fudge_factors: [2.31, 2.31, 1.1],  // fudge factors for each plane [0,1,2]
            time_limits: [12, 800],  // the unit of this is in ticks
            errors: wc.tn(waveform_map),
        },
    }, nin=1, nout=1, uses=[waveform_map, anode]),

    local cmm_mod = g.pnode({
        type: 'CMMModifier',
        name: '',
        data: {
            cm_tag: "bad",
            trace_tag: "gauss",
            anode: wc.tn(anode),
            start: 0,   // start veto ...
            end: 9592, // end  of veto
            ncount_cont_ch: 2,
            cont_ch_llimit: [296, 2336+4800 ], // veto if continues bad channels
            cont_ch_hlimit: [671, 2463+4800 ],
            ncount_veto_ch: 1,
            veto_ch_llimit: [3684],  // direct veto these channels
            veto_ch_hlimit: [3699],
            dead_ch_ncount: 10,
            dead_ch_charge: 1000,
            ncount_dead_ch: 2,
            dead_ch_llimit: [2160, 2080], // veto according to the charge size for dead channels
            dead_ch_hlimit: [2176, 2096],
            ncount_org: 5,   // organize the dead channel ranges according to these boundaries 
            org_llimit: [0   , 1920, 3840, 5760, 7680], // must be ordered ...
            org_hlimit: [1919, 3839, 5759, 7679, 9592], // must be ordered ...
        },
    }, nin=1, nout=1, uses=[anode]),

    local frame_quality_tagging = g.pnode({
        type: 'FrameQualityTagging',
        name: '',
        data: {
            trace_tag: 'gauss',
            anode: wc.tn(anode),
            nrebin: 4, // rebin count ...
            length_cut: 3,
            time_cut: 3,
            ch_threshold: 100,
            n_cover_cut1: 12,
            n_fire_cut1: 14,
            n_cover_cut2: 6,
            n_fire_cut2: 6,
            fire_threshold: 0.22,
            n_cover_cut3: [1200, 1200, 1800 ],
            percent_threshold: [0.25, 0.25, 0.2 ],
            threshold1: [300, 300, 360 ],
            threshold2: [150, 150, 180 ],
            min_time: 3180,
            max_time: 7870,
            flag_corr: 1,
        },
    }, nin=1, nout=1, uses=[anode]),

    local frame_masking = g.pnode({
            type: 'FrameMasking',
            name: '',
            data: {
                cm_tag: "bad",
                trace_tags: ['gauss','wiener'],
                anode: wc.tn(anode),
            },
        }, nin=1, nout=1, uses=[anode]),

        ret: g.pipeline([cmm_mod, frame_masking, charge_err], "uboone-preproc"),
    }.ret,

    // A functio that sets up slicing for an APA.
    slicing :: function(anode, aname, span=4, active_planes=[0,1,2], masked_planes=[], dummy_planes=[]) {
        ret: g.pnode({
            type: "MaskSlices",
            name: "slicing-"+aname,
            data: {
                tick_span: span,
                wiener_tag: "wiener",
                charge_tag: "gauss",
                error_tag: "gauss_error",
                anode: wc.tn(anode),
                min_tbin: 0,
                max_tbin: 9592, // 9592,
                active_planes: active_planes,
                masked_planes: masked_planes,
                dummy_planes: dummy_planes,
                // nthreshold: [1e-6, 1e-6, 1e-6],
                nthreshold: [3.6, 3.6, 3.6],
            },
        }, nin=1, nout=1, uses=[anode]),
    }.ret,

    // A function sets up tiling for an APA incuding a per-face split.
    tiling :: function(anode, aname) {

        local slice_fanout = g.pnode({
            type: "SliceFanout",
            name: "slicefanout-" + aname,
            data: { multiplicity: 2 },
        }, nin=1, nout=2),

        local tilings = [g.pnode({
            type: "GridTiling",
            name: "tiling-%s-face%d"%[aname, face],
            data: {
                anode: wc.tn(anode),
                face: face,
                nudge: 1e-2,
            }
        }, nin=1, nout=1, uses=[anode]) for face in [0,1]],

        local blobsync = g.pnode({
            type: "BlobSetSync",
            name: "blobsetsync-" + aname,
            data: { multiplicity: 2 }
        }, nin=2, nout=1),

        // ret: g.intern(
        //     innodes=[slice_fanout],
        //     outnodes=[blobsync],
        //     centernodes=tilings,
        //     edges=
        //         [g.edge(slice_fanout, tilings[n], n, 0) for n in [0,1]] +
        //         [g.edge(tilings[n], blobsync, 0, n) for n in [0,1]],
        //     name='tiling-' + aname),
        ret : tilings[0],
    }.ret,

    //
    multi_active_slicing_tiling :: function(anode, name, span=4) {
        local active_planes = [[0,1,2],[0,1],[1,2],[0,2],],
        local masked_planes = [[],[2],[0],[1]],
        local iota = std.range(0,std.length(active_planes)-1),
        local slicings = [$.slicing(anode, name+"_%d"%n, span, active_planes[n], masked_planes[n]) 
            for n in iota],
        local tilings = [$.tiling(anode, name+"_%d"%n)
            for n in iota],
        local multipass = [g.pipeline([slicings[n],tilings[n]]) for n in iota],
        ret: f.fanpipe("FrameFanout", multipass, "BlobSetMerge", "multi_active_slicing_tiling"),
    }.ret,

    //
    multi_masked_2view_slicing_tiling :: function(anode, name, span=109) {
        local dummy_planes = [[2],[0],[1]],
        local masked_planes = [[0,1],[1,2],[0,2]],
        local iota = std.range(0,std.length(dummy_planes)-1),
        local slicings = [$.slicing(anode, name+"_%d"%n, span,
            active_planes=[],masked_planes=masked_planes[n], dummy_planes=dummy_planes[n])
            for n in iota],
        local tilings = [$.tiling(anode, name+"_%d"%n)
            for n in iota],
        local multipass = [g.pipeline([slicings[n],tilings[n]]) for n in iota],
        ret: f.fanpipe("FrameFanout", multipass, "BlobSetMerge", "multi_masked_slicing_tiling"),
    }.ret,

    local clustering_policy = "uboone", // uboone, simple

    // Just clustering
    clustering :: function(anode, aname, spans=1.0) {
        ret : g.pnode({
            type: "BlobClustering",
            name: "blobclustering-" + aname,
            data:  { spans : spans, policy: clustering_policy }
        }, nin=1, nout=1),
    }.ret,

    // in: IBlobSet out: ICluster
    solving :: function(anode, aname) {

        local bc = g.pnode({
            type: "BlobClustering",
            name: "blobclustering-" + aname,
            data:  { policy: "uboone" }
        }, nin=1, nout=1),

        local gc = g.pnode({
            type: "GlobalGeomClustering",
            name: "global-clustering-" + aname,
            data:  { policy: "uboone" }
        }, nin=1, nout=1),

        solving :: function(suffix = "1st") {
            local bg = g.pnode({
                type: "BlobGrouping",
                name: "blobgrouping-" + aname + suffix,
                data:  {
                }
            }, nin=1, nout=1),
            local cs1 = g.pnode({
                type: "ChargeSolving",
                name: "cs1-" + aname + suffix,
                data:  {
                    weighting_strategies: ["uniform"], //"uniform", "simple", "uboone"
                    solve_config: "uboone",
                    whiten: true,
                }
            }, nin=1, nout=1),
            local cs2 = g.pnode({
                type: "ChargeSolving",
                name: "cs2-" + aname + suffix,
                data:  {
                    weighting_strategies: ["uboone"], //"uniform", "simple", "uboone"
                    solve_config: "uboone",
                    whiten: true,
                }
            }, nin=1, nout=1),
            local local_clustering = g.pnode({
                type: "LocalGeomClustering",
                name: "local-clustering-" + aname + suffix,
                data:  {
                    dryrun: false,
                }
            }, nin=1, nout=1),
            // ret: g.pipeline([bg, cs1],"cs-pipe"+aname+suffix),
            ret: g.pipeline([bg, cs1, local_clustering, cs2],"cs-pipe"+aname+suffix),
        }.ret,

        global_deghosting :: function(suffix = "1st") {
            ret: g.pnode({
                type: "ProjectionDeghosting",
                name: "ProjectionDeghosting-" + aname + suffix,
                data:  {
                    dryrun: false,
                }
            }, nin=1, nout=1),
        }.ret,

        local_deghosting :: function(config_round = 1, suffix = "1st", good_blob_charge_th=300) {
            ret: g.pnode({
                type: "InSliceDeghosting",
                name: "inslice_deghosting-" + aname + suffix,
                data:  {
                    dryrun: false,
                    config_round: config_round,
                    good_blob_charge_th: good_blob_charge_th,
                }
            }, nin=1, nout=1),
        }.ret,

        local gd1 = self.global_deghosting("1st"),
        local cs1 = self.solving("1st"),
        local ld1 = self.local_deghosting(1,"1st"),

        local gd2 = self.global_deghosting("2nd"),
        local cs2 = self.solving("2nd"),
        local ld2 = self.local_deghosting(2,"2nd"),

        local cs3 = self.solving("3rd"),
        local ld3 = self.local_deghosting(3,"3rd"),

        ret: g.pipeline([bc, gd1, cs1, ld1, gd2, cs2, ld2, cs3, ld3, gc],"uboone-solving"),
        // ret: g.pipeline([bc, gd1, cs1, ld1],"uboone-pipe"),
    }.ret,

    // ICluster -> ITensorSet
    to_tensor :: function(anode, aname, nin=1) {

        // Note, the "sampler" must be unique to the "sampling".
        local bs_live = {
            type: "BlobSampler",
            name: "bs_live" + anode.data.ident, 
            data: {
                strategy: [
                    "center",
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
                extra: [".*"] // want all the extra
        }},
        local bs_dead = {
            type: "BlobSampler",
            name: "bs_dead" + anode.data.ident, 
            data: {
                strategy: [
                    "center",
                ],
                extra: [".*"] // want all the extra
        }},

        local tb = g.pnode({
            type: "PointTreeBuilding",
            name: "pct-buiding-" + aname,
            data:  {
                samplers: {
                    "3d": wc.tn(bs_live),
                    "dead": wc.tn(bs_dead),
                },
                multiplicity: nin,
                tags: ["live", "dead"],
            }
        }, nin=nin, nout=1, uses=[bs_live, bs_dead]),

        local mabc = g.pnode({
            type: "MultiAlgBlobClustering",
            name: "multi-alg-blob-clustering-" + aname,
            data:  {
                inpath: "pointtrees/%d",
                outpath: "pointtrees/%d",
            }
        }, nin=1, nout=1, uses=[]),

        ret: g.pipeline([tb, mabc],"clustering"),
    }.ret,

    dump :: function(anode, aname, drift_speed) {
        local cs = g.pnode({
            type: "ClusterFileSink",
            name: "clustersink-"+aname,
            data: {
                outname: "clusters-apa-"+aname+".tar.gz",
                format: "dummy", // json, numpy, dummy
            }
        }, nin=1, nout=0),
        ret: cs
    }.ret,

    tensor_dump :: function(anode, aname) {
        local cs = g.pnode({
            type: "TensorFileSink",
            name: "tensorsink-"+aname,
            data: {
                outname: "tensor-apa-"+aname+".tar.gz",
                prefix: "clustering_", // json, numpy, dummy
                dump_mode: true,
            }
        }, nin=1, nout=0),
        ret: cs
    }.ret,
};

// multi slicing includes 2-view tiling and dead tiling
local active_planes = [[0,1,2],[0,1],[1,2],[0,2],];
local masked_planes = [[],[2],[0],[1]];
// single, multi, active, masked
local multi_slicing = "multi";

local imgpipe (anode) =
if multi_slicing == "single"
then g.pipeline([
        img.slicing(anode, anode.name, 109, active_planes=[0,1,2], masked_planes=[],dummy_planes=[]), // 109*22*4
        // img.slicing(anode, anode.name, 1916, active_planes=[], masked_planes=[0,1],dummy_planes=[2]), // 109*22*4
        // img.slicing(anode, anode.name, 4, active_planes=[0,1,2], masked_planes=[],dummy_planes=[]), // 109*22*4
        img.tiling(anode, anode.name),
        img.solving(anode, anode.name),
        // img.clustering(anode, anode.name),
        // img.dump(anode, anode.name, params.lar.drift_speed),
        img.to_tensor(anode, anode.name),
        img.tensor_dump(anode, anode.name),
        ])
else if multi_slicing == "active"
then g.pipeline([
        img.multi_active_slicing_tiling(anode, anode.name+"-ms-active", 4),
        img.solving(anode, anode.name+"-ms-active"),
        // img.clustering(anode, anode.name+"-ms-active"),
        // img.dump(anode, anode.name+"-ms-active", params.lar.drift_speed)
        img.to_tensor(anode, anode.name),
        img.tensor_dump(anode, anode.name),
        ])
else if multi_slicing == "masked"
then g.pipeline([
        img.multi_masked_2view_slicing_tiling(anode, anode.name+"-ms-masked", 1744),
        img.clustering(anode, anode.name+"-ms-masked"),
        img.dump(anode, anode.name+"-ms-masked", params.lar.drift_speed)])
else {
    local single = g.pipeline([
        img.slicing(anode, anode.name, 109, active_planes=[0,1,2], masked_planes=[],dummy_planes=[]), // 109*22*4
        img.tiling(anode, anode.name),
        img.solving(anode, anode.name),
    ]),
    // local active_fork = single,
    local active_fork = g.pipeline([
        img.multi_active_slicing_tiling(anode, anode.name+"-ms-active", 109),
        img.solving(anode, anode.name+"-ms-active"),
        // img.dump(anode, anode.name+"-ms-active", params.lar.drift_speed),
    ]),
    local masked_fork = g.pipeline([
        img.multi_masked_2view_slicing_tiling(anode, anode.name+"-ms-masked", 1744), // 109, 1744 (total 9592)
        img.clustering(anode, anode.name+"-ms-masked"),
        // img.dump(anode, anode.name+"-ms-masked", params.lar.drift_speed),
    ]),
    // ret: g.fan.fanout("FrameFanout",[active_fork,masked_fork], "fan_active_masked"),
    local dead_live_fanout = g.pnode({
        type: "FrameFanout",
        name: "dead_live_fanout-"+anode.name,
        data: {
            multiplicity: 2,
        },
    }, nin=1, nout=2),
    // local dead_live_merging = g.pnode({
    //     type: "DeadLiveMerging",
    //     name: "dead_live_merging"+anode.name,
    //     data: {
    //         multiplicity: 2,
    //         tags: ["live", "dead"],
    //     },
    // }, nin=2, nout=1),
    local dead_live_merging = img.to_tensor(anode, anode.name, nin=2),
    local multipipe = g.intern(
        innodes=[dead_live_fanout],
        outnodes=[dead_live_merging],
        centernodes=[active_fork, masked_fork],
        edges=[
            g.edge(dead_live_fanout, active_fork, 0, 0),
            g.edge(dead_live_fanout, masked_fork, 1, 0),
            g.edge(active_fork, dead_live_merging, 0, 0),
            g.edge(masked_fork, dead_live_merging, 0, 1),
        ],
        name='img-multipipe'+anode.name),
    ret: g.pipeline([
        multipipe,
        // img.to_tensor(anode, anode.name),
        img.tensor_dump(anode, anode.name),
    ]),
}.ret;

local celltreesource = g.pnode({
    type: "CelltreeSource",
    name: "celltreesource",
    data: {
        filename: "celltreeOVERLAY.root",
        EventNo: 6501,
        // in_branch_base_names: raw [default], calibGaussian, calibWiener
        in_branch_base_names: ["calibWiener", "calibGaussian"],
        out_trace_tags: ["wiener", "gauss"], // orig, gauss, wiener
        in_branch_thresholds: ["channelThreshold", "channelThreshold"]
    },
 }, nin=0, nout=1);

local graph = g.pipeline([
    celltreesource,
    img.pre_proc(anodes[0]),
    imgpipe(anodes[0]),
    ], "main");

local app = {
    type: 'Pgrapher', //Pgrapher, TbbFlow
    data: {
    edges: g.edges(graph),
  },
};

local cmdline = {
    type: "wire-cell",
    data: {
        plugins: ["WireCellGen", "WireCellPgraph", /*"WireCellTbb",*/ "WireCellSio", "WireCellSigProc", "WireCellRoot", "WireCellImg"],
        apps: ["Pgrapher"]
    }
};

[cmdline] + g.uses(graph) + [app]
// graph
// img.to_tensor(anodes[0], anodes[0].name, nin=2)