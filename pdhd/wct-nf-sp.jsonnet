// Pure WireCell (no LArSoft) NF+SP pipeline for ProtoDUNE-HD.
//
// Part 2 of a two-part split of wcls-nf-sp-out.jsonnet:
//   Part 1: wcls-nf-sp-out.jsonnet  (runs in art/LArSoft)
//     - reads RawDigits, runs ChannelSelector, saves per-anode orig frames:
//         protodunehd-orig-frames-anode{N}.tar.bz2
//   Part 2: this file  (runs standalone with wire-cell CLI)
//     - reads per-anode orig frames, runs NF -> SP
//     - saves NF frames: protodunehd-sp-frames-raw-anode{N}.tar.bz2
//     - saves SP frames: protodunehd-sp-frames-anode{N}.tar.bz2
//
// Run example (all anodes):
//   wire-cell -l stdout -L debug \
//     --tla-str orig_prefix="protodunehd-orig-frames" \
//     --tla-str sp_prefix="protodunehd-sp-frames" \
//     -c pgrapher/experiment/pdhd/wct-nf-sp.jsonnet
//
// To process a subset of anodes:
//   wire-cell ... --tla-code anode_indices='[0,1]' -c pgrapher/experiment/pdhd/wct-nf-sp.jsonnet
//
// Data vs simulation:
//   reality='data' (default) inserts a Resampler (512 ns -> 500 ns) on every
//   anode before NF, mirroring the LArSoft pdhd config. Pass reality='sim' to
//   skip resampling for simulated input that is already at 500 ns.

local g = import 'pgraph.jsonnet';
local wc = import 'wirecell.jsonnet';

local params = import 'pgrapher/experiment/pdhd/params.jsonnet';

local tools_maker = import 'pgrapher/common/tools.jsonnet';
local tools_all = tools_maker(params);

function(
  orig_prefix   = 'protodunehd-orig-frames',    // input prefix; reads {prefix}-anode{N}.tar.bz2
  raw_prefix    = 'protodunehd-sp-frames-raw',  // output prefix for NF (raw) frames
  sp_prefix     = 'protodunehd-sp-frames',      // output prefix for SP frames
  reality       = 'data',                       // 'data' enables the 512->500 ns Resampler; 'sim' disables it
  anode_indices = std.range(0, std.length(tools_all.anodes) - 1),
  use_freqmask  = true,                         // apply per-channel frequency mask in NF; override with --tla-code use_freqmask=false
  debug_dump_path = '',                         // when non-empty, PDHDCoherentNoiseSub dumps per-group .npz under this dir (default OFF)
  debug_dump_groups = [],                       // optional whitelist of group ids (= first-channel idents). [] = all groups
  l1sp_pd_mode = 'process',                     // 'process' (default, ON) / 'dump' (calib bypass) / '' (OFF)
  l1sp_pd_dump_path = '',                       // scalar dump directory (used when l1sp_pd_mode='dump'); pass via -c flag
  l1sp_pd_wf_dump_path = '',                    // waveform dump directory (used when l1sp_pd_mode='process'); pass via -w flag
  l1sp_pd_adj_enable = true,                    // cross-channel adjacency expansion; default ON (see sigproc/docs/l1sp/L1SPFilterPD.md). Pass false to recover pre-2026-05-02 behaviour.
  // l1sp_pd_planes is not exposed here: sp.jsonnet defaults to APA0→[0], APA1-3→[0,1].
)

  local tools = tools_all;
  local use_resampler = (reality == 'data');

  local base = import 'pgrapher/experiment/pdhd/chndb-base.jsonnet';
  local chndb = [{
    type: 'OmniChannelNoiseDB',
    name: 'ocndbperfect%d' % n,
    data: base(params, tools.anodes[n], tools.field, n, use_freqmask=use_freqmask) { dft: wc.tn(tools.dft) },
    uses: [tools.anodes[n], tools.field, tools.dft],
  } for n in std.range(0, std.length(tools.anodes) - 1)];

  local nf_maker = import 'pgrapher/experiment/pdhd/nf.jsonnet';
  local nf_pipes = [nf_maker(params, tools.anodes[n], chndb[n], n, name='nf%d' % n,
                             debug_dump_path=debug_dump_path, debug_dump_groups=debug_dump_groups)
                    for n in std.range(0, std.length(tools.anodes) - 1)];

  local sp_maker = import 'pgrapher/experiment/pdhd/sp.jsonnet';
  local sp = sp_maker(params, tools, { sparse: false });
  local sp_pipes = [sp.make_sigproc(a,
                                    l1sp_pd_mode=l1sp_pd_mode,
                                    l1sp_pd_dump_path=l1sp_pd_dump_path,
                                    l1sp_pd_wf_dump_path=l1sp_pd_wf_dump_path,
                                    l1sp_pd_adj_enable=l1sp_pd_adj_enable)
                    for a in tools.anodes];

  local resamplers_config = import 'pgrapher/common/resamplers.jsonnet';
  local load_resamplers = resamplers_config(g, wc, tools);
  local resamplers = load_resamplers.resamplers;

  // Tap: save NF output (raw) frame per anode
  local raw_frame_tap = function(n)
    g.fan.tap('FrameFanout',
      g.pnode({
        type: 'FrameFileSink',
        name: 'rawframesink%d' % n,
        data: {
          outname: '%s-anode%d.tar.bz2' % [raw_prefix, n],
          tags: ['raw%d' % n],
          digitize: false,
          masks: true,
        },
      }, nin=1, nout=0),
      'rawframetap%d' % n);

  // Tap: save SP output (gauss+wiener) frame per anode
  local frame_tap = function(n)
    g.fan.tap('FrameFanout',
      g.pnode({
        type: 'FrameFileSink',
        name: 'spframesink%d' % n,
        data: {
          outname: '%s-anode%d.tar.bz2' % [sp_prefix, n],
          tags: [
            'gauss%d'  % n,
            'wiener%d' % n,
          ],
          digitize: false,
          masks: true,
        },
      }, nin=1, nout=0),
      'spframetap%d' % n);

  // Build one source -> NF -> SP pipeline per anode
  local per_anode_graph(n) =
    local src = g.pnode({
      type: 'FrameFileSource',
      name: 'origframesrc%d' % n,
      data: {
        inname: '%s-anode%d.tar.bz2' % [orig_prefix, n],
        tags: [],  // load all traces regardless of tag
      },
    }, nin=0, nout=1);

    local sink = g.pnode({ type: 'DumpFrames', name: 'dump%d' % n }, nin=1, nout=0);

    g.pipeline(
      [src]
      + (if use_resampler then [resamplers[n]] else [])
      + [nf_pipes[n]]
      + [raw_frame_tap(n)]
      + [sp_pipes[n]]
      + [frame_tap(n)]
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
