// some functions to help build pipelines for imaging.  These are
// mostly per-apa but tiling portions are per-face.

local g = import 'pgraph.jsonnet';
local f = import 'pgrapher/common/funcs.jsonnet';
local wc = import 'wirecell.jsonnet';

{
    // A functio that sets up slicing for an APA.
    slicing :: function(anode, aname, tag="", span=4, active_planes=[0,1,2], masked_planes=[], dummy_planes=[]) {
        ret: g.pnode({
            type: "MaskSlices",
            name: "slicing-"+aname,
            data: {
                tag: tag,
                tick_span: span,
                anode: wc.tn(anode),
                min_tbin: 0,
                max_tbin: 9592,
                active_planes: active_planes,
                masked_planes: masked_planes,
                dummy_planes: dummy_planes,
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
    multi_active_slicing_tiling :: function(anode, name, tag="gauss", span=4) {
        local active_planes = [[0,1,2],[0,1],[1,2],[0,2],],
        local masked_planes = [[],[2],[0],[1]],
        local iota = std.range(0,std.length(active_planes)-1),
        local slicings = [$.slicing(anode, name+"_%d"%n, tag, span, active_planes[n], masked_planes[n]) 
            for n in iota],
        local tilings = [$.tiling(anode, name+"_%d"%n)
            for n in iota],
        local multipass = [g.pipeline([slicings[n],tilings[n]]) for n in iota],
        ret: f.fanpipe("FrameFanout", multipass, "BlobSetMerge", "multi_active_slicing_tiling"),
    }.ret,

    //
    multi_masked_2view_slicing_tiling :: function(anode, name, tag="gauss", span=109) {
        local dummy_planes = [[2],[0],[1]],
        local masked_planes = [[0,1],[1,2],[0,2]],
        local iota = std.range(0,std.length(dummy_planes)-1),
        local slicings = [$.slicing(anode, name+"_%d"%n, tag, span,
            active_planes=[],masked_planes=masked_planes[n], dummy_planes=dummy_planes[n])
            for n in iota],
        local tilings = [$.tiling(anode, name+"_%d"%n)
            for n in iota],
        local multipass = [g.pipeline([slicings[n],tilings[n]]) for n in iota],
        ret: f.fanpipe("FrameFanout", multipass, "BlobSetMerge", "multi_masked_slicing_tiling"),
    }.ret,
    //
    multi_masked_slicing_tiling :: function(anode, name, tag="gauss", span=109) {
        local active_planes = [[2],[0],[1],[]],
        local masked_planes = [[0,1],[1,2],[0,2],[0,1,2]],
        local iota = std.range(0,std.length(active_planes)-1),
        local slicings = [$.slicing(anode, name+"_%d"%n, tag, span, active_planes[n], masked_planes[n]) 
            for n in iota],
        local tilings = [$.tiling(anode, name+"_%d"%n)
            for n in iota],
        local multipass = [g.pipeline([slicings[n],tilings[n]]) for n in iota],
        ret: f.fanpipe("FrameFanout", multipass, "BlobSetMerge", "multi_masked_slicing_tiling"),
    }.ret,

    // Just clustering
    clustering :: function(anode, aname, spans=1.0) {
        ret : g.pnode({
            type: "BlobClustering",
            name: "blobclustering-" + aname,
            data:  { spans : spans }
        }, nin=1, nout=1),
    }.ret, 

    // this bundles clustering, grouping and solving.  Other patterns
    // should be explored.  Note, anode isn't really needed, we just
    // use it for its ident and to keep similar calling pattern to
    // above..
    solving :: function(anode, aname, spans=1.0, threshold=0.0) {
        local bc = g.pnode({
            type: "BlobClustering",
            name: "blobclustering-" + aname,
            data:  { spans : spans }
        }, nin=1, nout=1),
        local bg = g.pnode({
            type: "BlobGrouping",
            name: "blobgrouping-" + aname,
            data:  {
            }
        }, nin=1, nout=1),
        local bs = g.pnode({
            type: "BlobSolving",
            name: "blobsolving-" + aname,
            data:  { threshold: threshold }
        }, nin=1, nout=1),
        local cs0 = g.pnode({
            type: "ChargeSolving",
            name: "chargesolving0-" + aname,
            data:  {
                weighting_strategies: ["uniform"], //"uniform", "simple"
            }
        }, nin=1, nout=1),
        local cs1 = g.pnode({
            type: "ChargeSolving",
            name: "chargesolving1-" + aname,
            data:  {
                weighting_strategies: ["uniform"], //"uniform", "simple"
            }
        }, nin=1, nout=1),
        local lcbr = g.pnode({
            type: "LCBlobRemoval",
            name: "lcblobremoval-" + aname,
            data:  {
                blob_value_threshold: 1e6,
                blob_error_threshold: 0,
            }
        }, nin=1, nout=1),
        local test_projection2d = g.pnode({
            type: "TestProjection2D",
            name: "TestProjection2D-" + aname,
            data:  {
                compare_brute_force: false,
                compare_rectangle: true,
                verbose: false,
            }
        }, nin=1, nout=1),
        local test_clustershadow = g.pnode({
            type: "TestClusterShadow",
            name: "TestClusterShadow-" + aname,
            data:  {
            }
        }, nin=1, nout=1),
        local test_pipe = g.pipeline([test_clustershadow, test_projection2d],"test_pipe"),
        local cs = g.intern(
            innodes=[cs0], outnodes=[cs1], centernodes=[],
            edges=[g.edge(cs0,cs1)],
            name="chargesolving-" + aname),
        local csp = g.intern(
            innodes=[cs0], outnodes=[cs1], centernodes=[test_pipe],
            edges=[g.edge(cs0,test_pipe), g.edge(test_pipe,cs1)],
            name="chargesolving-" + aname),
        local solver = csp,
        ret: g.intern(
            innodes=[bc], outnodes=[solver], centernodes=[bg],
            edges=[g.edge(bc,bg), g.edge(bg,solver)],
            name="solving-" + aname),
        // ret: bc,
    }.ret,

    dump_old :: function(anode, aname, drift_speed) {
        local js = g.pnode({
            type: "JsonClusterTap",
            name: "clustertap-" + aname,
            data: {
                filename: "clusters-pr165-"+aname+"-%04d.json",
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
                // outname: "clusters-apa-"+aname+".tar.gz",
                outname: "clusters-pr163-"+aname+".tar.gz",
                format: "json",
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
