local g = import 'pgraph.jsonnet';
local f = import 'pgrapher/common/funcs.jsonnet';
local wc = import 'wirecell.jsonnet';

{
    // IFrame -> IFrame
    pre_proc :: function(anode, aname) {
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

    // in: IBlobSet out: ICluster
    solving_pipe :: function(anode, aname) {

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
}