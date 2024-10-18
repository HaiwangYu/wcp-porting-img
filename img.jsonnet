// some functions to help build pipelines for imaging.  These are
// mostly per-apa but tiling portions are per-face.

local g = import 'pgraph.jsonnet';
local f = import 'pgrapher/common/funcs.jsonnet';
local wc = import 'wirecell.jsonnet';

{
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
    //
    multi_masked_slicing_tiling :: function(anode, name, span=109) {
        local active_planes = [[2],[0],[1],[]],
        local masked_planes = [[0,1],[1,2],[0,2],[0,1,2]],
        local iota = std.range(0,std.length(active_planes)-1),
        local slicings = [$.slicing(anode, name+"_%d"%n, span, active_planes[n], masked_planes[n]) 
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

    // solving now configured in uboone_pipe
    solving :: function(anode, aname) {
        local uboone_pipe = import "uboone-img.jsonnet",
        ret: uboone_pipe.solving_pipe(anode, aname),
    }.ret,

    dump_old :: function(anode, aname, drift_speed) {
        local js = g.pnode({
            type: "JsonClusterTap",
            name: "clustertap-" + aname,
            data: {
                filename: "clusters-apa-"+aname+"-%04d.json",
                drift_speed: drift_speed
            },
        }, nin=1, nout=1),

        local cs = g.pnode({
            type: "ClusterSink",
            name: "clustersink-"+aname,
            data: {
                filename: "clusters-apa-"+aname+"-%d.dot",
            }
        }, nin=1, nout=0),
        ret: g.intern(innodes=[js], outnodes=[cs], edges=[g.edge(js,cs)],
                      name="clusterdump-"+aname)
    }.ret,

    dump :: function(anode, aname, drift_speed) {

        local cs = g.pnode({
            type: "ClusterFileSink",
            name: "clustersink-"+aname,
            data: {
                outname: "clusters-apa-"+aname+".tar.gz",
                format: "json", // json, numpy, dummy
            }
        }, nin=1, nout=0),
        ret: cs
    }.ret,

    // A function that reverts blobs to frames
    reframing :: function(anode, aname) {
        ret : g.pnode({
            type: "BlobReframer",
            name: "blobreframing-" + aname,
            data: {
                frame_tag: "reframe%d" %anode.data.ident,
            }
        }, nin=1, nout=1),
    }.ret,

    // fill ROOT histograms with frames
    magnify :: function(anode, aname, frame_tag="orig") {
        ret: g.pnode({
          type: 'MagnifySink',
          name: 'magnify-'+aname,
          data: {
            output_filename: "magnify-img.root",
            root_file_mode: 'UPDATE',
            frames: [frame_tag + anode.data.ident],
            trace_has_tag: true,
            anode: wc.tn(anode),
          },
        }, nin=1, nout=1),
    }.ret,

    // the end
    dumpframes :: function(anode, aname) {
        ret: g.pnode({
            type: "DumpFrames",
            name: "dumpframes-"+aname,
        }, nin=1, nout=0),
    }.ret,

}
