local wc = import "wirecell.jsonnet";
local g = import "pgraph.jsonnet";
local params = import "pgrapher/experiment/uboone/simparams.jsonnet";
local hs = import "pgrapher/common/helpers.jsonnet";

local tools_maker = import 'pgrapher/common/tools.jsonnet';
local tools = tools_maker(params);

local wires = hs.aux.wires(params.files.wires);
local anodes = hs.aux.anodes(wires, params.det.volumes);

local img = import "img.jsonnet";

local celltreesource = g.pnode({
    type: "CelltreeSource",
    name: "celltreesource",
    data: {
        filename: "celltreeOVERLAY.root",
        EventNo: 6501,
        frames: ["gauss"],
        in_branch: "calibGaussian", // raw [default], calibGaussian, calibWiener
    },
 }, nin=0, nout=1);

local dumpframes = g.pnode({
        type: "DumpFrames",
        name: 'dumpframe',
    }, nin=1, nout=0);

local magdecon = g.pnode({
      type: 'MagnifySink',
      name: 'magdecon',
      data: {
        output_filename: "mag.root",
        root_file_mode: 'UPDATE',
        frames: ['gauss', 'wiener'],
        trace_has_tag: true,
        anode: wc.tn(anodes[0]),
      },
    }, nin=1, nout=1, uses=[anodes[0]]);

local anode = anodes[0];
local imgpipe = g.pipeline([
        img.slicing(anode, anode.name),
        img.tiling(anode, anode.name),
        img.solving(anode, anode.name),
        // img.clustering(anode, anode.name),
      ]
      + [
        img.dump(anode, anode.name, params.lar.drift_speed),
      ], 
      "img-" + anode.name);

local graph = g.pipeline([celltreesource, magdecon, /*dumpframes,*/ imgpipe], "main");

local app = {
  type: 'Pgrapher',
  data: {
    edges: g.edges(graph),
  },
};

local cmdline = {
    type: "wire-cell",
    data: {
        plugins: ["WireCellGen", "WireCellPgraph", "WireCellSio", "WireCellSigProc", "WireCellRoot", "WireCellImg"],
        apps: ["Pgrapher"]
    }
};

[cmdline] + g.uses(graph) + [app]