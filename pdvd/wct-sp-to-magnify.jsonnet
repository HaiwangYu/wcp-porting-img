// Convert per-anode SP frame archives (protodune-sp-frames-anode{N}.tar.bz2)
// into a single Magnify ROOT file containing all anodes.
//
// Each anode produces: hu/hv/hw_gauss<N>, hu/hv/hw_wiener<N> (TH2F),
//   hu/hv/hw_threshold<N> (TH1F per-channel threshold), T_bad<N> (cmmtree).
// One Trun tree is written by the first anode's sink.
//
// Typical usage (called from run_sp_to_magnify_evt.sh):
//   wire-cell \
//     --tla-str  input_prefix=/path/to/protodune-sp-frames \
//     --tla-code anode_indices='[0,1,2,3,4,5,6,7]' \
//     --tla-str  output_file=magnify-run039324-evt1.root \
//     --tla-code run=39324 --tla-code subrun=0 --tla-code event=339870 \
//     -c wct-sp-to-magnify.jsonnet

local g = import 'pgraph.jsonnet';
local wc = import 'wirecell.jsonnet';

local params = import 'pgrapher/experiment/protodunevd/simparams.jsonnet';
local tools_maker = import 'pgrapher/common/tools.jsonnet';
local tools_all = tools_maker(params);

function(
  input_prefix  = 'protodune-sp-frames',
  anode_indices = std.range(0, std.length(tools_all.anodes) - 1),
  output_file   = 'magnify.root',
  run           = 0,
  subrun        = 0,
  event         = 0,
  nticks        = 6000  // pdvd SP frame length (3 ms at 500 ns/tick)
)
  local anodes  = [tools_all.anodes[i] for i in anode_indices];
  local nanodes = std.length(anodes);

  local runinfo = {
    runNo:          run,
    subRunNo:       subrun,
    eventNo:        event,
    total_time_bin: nticks,
  };

  local mag = (import 'magnify-sinks.jsonnet')(
    { anodes: anodes }, output_file, runinfo=runinfo);

  local per_anode_graph(n, anode) =
    local aid = anode.data.ident;
    local src = g.pnode({
      type: 'FrameFileSource',
      name: 'frame_source_anode%d' % aid,
      data: {
        inname: '%s-anode%d.tar.bz2' % [input_prefix, aid],
        tags: ['gauss%d' % aid, 'wiener%d' % aid],
      },
    }, nin=0, nout=1);
    // Retagger duplicates wiener<N> → [wiener<N>, threshold<N>] so
    // MagnifySink can write h[uvw]_threshold<N> TH1F (Magnify expects that name).
    local retag = g.pnode({
      type: 'Retagger',
      name: 'retagger_anode%d' % aid,
      data: {
        tag_rules: [{
          frame: { '.*': '' },
          trace: {
            ['gauss%d' % aid]: 'gauss%d' % aid,
            ['wiener%d' % aid]: ['wiener%d' % aid, 'threshold%d' % aid],
          },
        }],
      },
    }, nin=1, nout=1);
    local dump = g.pnode({
      type: 'DumpFrames',
      name: 'dump_anode%d' % aid,
    }, nin=1, nout=0);
    g.pipeline([src, retag, mag.decon_pipe[n], dump],
               'magnify_graph_anode%d' % aid);

  local graphs = [per_anode_graph(n, anodes[n])
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
