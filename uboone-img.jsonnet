local g = import 'pgraph.jsonnet';
local f = import 'pgrapher/common/funcs.jsonnet';
local wc = import 'wirecell.jsonnet';

// in: IBlobSet out: ICluster

function(anode, aname) {

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

    local_deghosting :: function(config_round = 1, suffix = "1st") {
        ret: g.pnode({
            type: "InSliceDeghosting",
            name: "inslice_deghosting-" + aname + suffix,
            data:  {
                dryrun: false,
                config_round: config_round,
            }
        }, nin=1, nout=1),
    }.ret,

    local gd1 = $.global_deghosting("1st"),
    local cs1 = $.solving("1st"),
    local ld1 = $.local_deghosting(1,"1st"),

    local gd2 = $.global_deghosting("2nd"),
    local cs2 = $.solving("2nd"),
    local ld2 = $.local_deghosting(2,"2nd"),

    local cs3 = $.solving("3rd"),
    local ld3 = $.local_deghosting(3,"3rd"),

    ret: g.pipeline([bc, gd1, cs1, ld1, gd2, cs2, ld2, cs3, ld3, gc],"uboone-pipe"),
    // ret: g.pipeline([bc, gd1, cs1, ld1],"uboone-pipe"),
}.ret