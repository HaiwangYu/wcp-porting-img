// Append raw-signal histograms to an existing per-anode Magnify ROOT file.
//
// Reads protodune-sp-frames-raw-anode<N>.tar.bz2 (tag raw<N>) and writes
// h{u,v,w}_raw<N> TH2F histograms into the already-created ROOT file via
// MagnifySink UPDATE mode.  No Trun / T_bad / threshold output.
//
// Typical usage (called from run_sp_to_magnify_evt.sh after the decon pass):
//   wire-cell \
//     --tla-str  input_prefix=/path/to/protodune-sp-frames-raw \
//     --tla-code anode_indices='[0]' \
//     --tla-str  output_file=magnify-run040475-evt1-anode0.root \
//     -c wct-raw-to-magnify.jsonnet

local g = import 'pgraph.jsonnet';
local wc = import 'wirecell.jsonnet';

local params = import 'pgrapher/experiment/protodunevd/simparams.jsonnet';
local tools_maker = import 'pgrapher/common/tools.jsonnet';
local tools_all = tools_maker(params);

function(
  input_prefix  = 'protodune-sp-frames-raw',
  anode_indices = std.range(0, std.length(tools_all.anodes) - 1),
  output_file   = 'magnify.root'
)
  local anodes  = [tools_all.anodes[i] for i in anode_indices];
  local nanodes = std.length(anodes);

  local per_anode_graph(anode) =
    local aid = anode.data.ident;
    local src = g.pnode({
      type: 'FrameFileSource',
      name: 'raw_source_anode%d' % aid,
      data: {
        inname: '%s-anode%d.tar.bz2' % [input_prefix, aid],
        tags: ['raw%d' % aid],
      },
    }, nin=0, nout=1);
    local sink = g.pnode({
      type: 'MagnifySink',
      name: 'magraw%d' % aid,
      data: {
        output_filename: output_file,
        root_file_mode: 'UPDATE',
        frames: ['raw%d' % aid],
        trace_has_tag: true,
        anode: wc.tn(anode),
      },
    }, nin=1, nout=1, uses=[anode]);
    local dump = g.pnode({
      type: 'DumpFrames',
      name: 'rawdump_anode%d' % aid,
    }, nin=1, nout=0);
    g.pipeline([src, sink, dump], 'raw_graph_anode%d' % aid);

  local graphs = [per_anode_graph(anodes[n])
                  for n in std.range(0, nanodes - 1)];

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
        'WireCellRoot',
      ],
      apps: ['Pgrapher'],
    },
  };

  [cmdline] + all_uses + [app]
