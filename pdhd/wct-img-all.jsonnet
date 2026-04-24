// Standalone imaging pipeline for ProtoDUNE-HD.
//
// Reads per-anode SP frames and runs the imaging pipeline per anode.
// Cluster output files are named: clusters-apa-apa{N}-ms-active.tar.gz
//                                 clusters-apa-apa{N}-ms-masked.tar.gz
//
// Run standalone (all anodes):
//   wire-cell -l stdout -L debug -c wct-img-all.jsonnet
//
// With a custom file prefix:
//   wire-cell -l stdout -L debug \
//     --tla-str input_prefix="protodunehd-sp-frames" \
//     -c wct-img-all.jsonnet
//
// To select a subset of anodes:
//   wire-cell -l stdout -L debug \
//     --tla-code anode_indices='[0,1]' \
//     -c wct-img-all.jsonnet
//
// To write cluster output files to a specific directory:
//   wire-cell -l stdout -L debug \
//     --tla-str output_dir="woodpecker_data" \
//     -c wct-img-all.jsonnet

local g = import 'pgraph.jsonnet';
local wc = import 'wirecell.jsonnet';

local params = import 'pgrapher/experiment/pdhd/simparams.jsonnet';

local tools_maker = import 'pgrapher/common/tools.jsonnet';
local tools_all = tools_maker(params);

// Top-level function: parameters overridable via --tla-str / --tla-code
function(
  // Prefix for per-anode input files: "{input_prefix}-anode{N}.tar.bz2"
  input_prefix = 'protodunehd-sp-frames',
  // Indices into tools_all.anodes to process; default = all
  anode_indices = std.range(0, std.length(tools_all.anodes) - 1),
  // Directory for output cluster files ('' means current directory)
  output_dir = ''
)

  local anodes = [tools_all.anodes[i] for i in anode_indices];

  local img_maker = import 'img.jsonnet';
  local img = img_maker(output_dir=output_dir);

  // Build one FrameFileSource + imaging pipeline per anode
  local per_anode_graph(anode) =
    local aid = anode.data.ident;
    local src = g.pnode({
      type: 'FrameFileSource',
      name: 'frame_source_anode%d' % aid,
      data: {
        inname: '%s-anode%d.tar.bz2' % [input_prefix, aid],
        tags: ['gauss%d' % aid, 'wiener%d' % aid],
      },
    }, nin=0, nout=1);
    g.pipeline([src, img.per_anode(anode)],
               'img_graph_anode%d' % aid);

  local graphs = [per_anode_graph(a) for a in anodes];

  local all_edges = std.foldl(function(acc, gr) acc + g.edges(gr), graphs, []);
  local all_uses  = std.foldl(function(acc, gr) acc + g.uses(gr),  graphs, []);

  local app = {
    type: 'Pgrapher',
    data: { edges: all_edges },
  };

  local cmdline = {
    type: 'wire-cell',
    data: {
      plugins: [
        'WireCellGen',
        'WireCellPgraph',
        'WireCellSio',
        'WireCellSigProc',
        'WireCellImg',
        'WireCellClus',
      ],
      apps: ['Pgrapher'],
    },
  };

  [cmdline] + all_uses + [app]
