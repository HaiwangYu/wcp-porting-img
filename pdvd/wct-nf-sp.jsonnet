// Pure WireCell (no LArSoft) NF+SP pipeline.
//
// Part 2 of a two-part split of wcls-nf-sp-out.jsonnet:
//   Part 1: wcls-nf-sp-out.jsonnet  (runs in art/LArSoft)
//     - reads RawDigits, runs ChannelSelector, saves per-anode orig frames:
//         protodune-orig-frames-anode{N}.tar.bz2
//   Part 2: this file  (runs standalone with wire-cell CLI)
//     - reads per-anode orig frames, runs [Resampler ->] NF -> SP
//     - saves NF frames: protodune-nf-frames-anode{N}.tar.bz2
//     - saves SP frames: protodune-sp-frames-anode{N}.tar.bz2
//
// Run example (all anodes):
//   wire-cell -l stdout -L debug \
//     --tla-str orig_prefix="protodune-orig-frames" \
//     --tla-str sp_prefix="protodune-sp-frames" \
//     --tla-str use_resampler="true" \
//     -c pgrapher/experiment/protodunevd/wct-nf-sp.jsonnet
//
// To process a subset of anodes:
//   wire-cell ... --tla-code anode_indices='[4,5]' -c wct-nf-sp.jsonnet

local g = import 'pgraph.jsonnet';
local wc = import 'wirecell.jsonnet';

local params = import 'pgrapher/experiment/protodunevd/params.jsonnet';

local tools_maker = import 'pgrapher/common/tools.jsonnet';
local tools_all = tools_maker(params);

function(
  orig_prefix   = 'protodune-orig-frames',  // input prefix; reads {prefix}-anode{N}.tar.bz2
  raw_prefix    = 'protodune-sp-frames-raw',   // output prefix for NF (raw) frames
  sp_prefix     = 'protodune-sp-frames',    // output prefix for SP frames
  use_resampler = 'true',                   // 'true' to resample bottom anodes (n<4)
  sigoutform    = 'dense',                 // 'sparse' or 'dense'
  anode_indices = std.range(0, std.length(tools_all.anodes) - 1)
)

  local tools = tools_all;

  local base = import 'pgrapher/experiment/protodunevd/chndb-base.jsonnet';
  local chndb = [{
    type: 'OmniChannelNoiseDB',
    name: 'ocndbperfect%d' % n,
    data: base(params, tools.anodes[n], tools.field, tools.anodes[n].data.ident) { dft: wc.tn(tools.dft) },
    uses: [tools.anodes[n], tools.field, tools.dft],
  } for n in std.range(0, std.length(tools.anodes) - 1)];

  local nf_maker = import 'pgrapher/experiment/protodunevd/nf.jsonnet';
  local nf_pipes = [nf_maker(params, tools.anodes[n], chndb[n], tools.anodes[n].data.ident, name='nf%d' % tools.anodes[n].data.ident) for n in std.range(0, std.length(tools.anodes) - 1)];

  local sp_maker = import 'pgrapher/experiment/protodunevd/sp.jsonnet';
  local sp = sp_maker(params, tools, { sparse: sigoutform == 'sparse' });
  local sp_pipes = [sp.make_sigproc(a) for a in tools.anodes];

  local resamplers_config = import 'pgrapher/common/resamplers.jsonnet';
  local load_resamplers = resamplers_config(g, wc, tools);
  local resamplers = load_resamplers.resamplers;

  // Tap: save NF output (raw) frame per anode
  local raw_frame_tap = function(anode_ident)
    g.fan.tap('FrameFanout',
      g.pnode({
        type: 'FrameFileSink',
        name: 'rawframesink%d' % anode_ident,
        data: {
          outname: '%s-anode%d.tar.bz2' % [raw_prefix, anode_ident],
          tags: ['raw%d' % anode_ident],
          digitize: false,
          masks: false,
        },
      }, nin=1, nout=0),
      'rawframetap%d' % anode_ident);

  // Tap: save SP output (gauss+wiener) frame per anode
  local frame_tap = function(anode_ident)
    g.fan.tap('FrameFanout',
      g.pnode({
        type: 'FrameFileSink',
        name: 'spframesink%d' % anode_ident,
        data: {
          outname: '%s-anode%d.tar.bz2' % [sp_prefix, anode_ident],
          tags: [
            'gauss%d'  % anode_ident,
            'wiener%d' % anode_ident,
          ],
          digitize: false,
          masks: true,
        },
      }, nin=1, nout=0),
      'spframetap%d' % anode_ident);

  // Build one source -> [resampler ->] NF -> SP pipeline per anode
  local per_anode_graph(n) =
    local anode = tools.anodes[n];
    local aid = anode.data.ident;

    local src = g.pnode({
      type: 'FrameFileSource',
      name: 'origframesrc%d' % aid,
      data: {
        inname: '%s-anode%d.tar.bz2' % [orig_prefix, aid],
        tags: ['orig'],
      },
    }, nin=0, nout=1);

    local sink = g.pnode({ type: 'DumpFrames', name: 'dump%d' % aid }, nin=1, nout=0);

    g.pipeline(
      [src]
      + (if use_resampler == 'true' && n < 4 then [resamplers[n]] else [])
      + [nf_pipes[n]]
      + [raw_frame_tap(aid)]
      + [sp_pipes[n]]
      + [frame_tap(aid)]
      + [sink],
      'nfsp_pipe_%d' % n);

  local graphs = [per_anode_graph(n) for n in anode_indices];

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
        'WireCellAux',
      ],
      apps: ['Pgrapher'],
    },
  };

  [cmdline] + all_uses + [app]
