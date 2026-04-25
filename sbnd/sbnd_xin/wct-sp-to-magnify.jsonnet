// Convert SBND SP frame archive (sp-frames.tar.bz2) to per-anode Magnify ROOT files
// and per-anode woodpecker-ready frame archives.
//
// Input:  sp-frames.tar.bz2 — single-event archive containing:
//           frame_dnnsp_<EVT>.npy, channels_dnnsp_<EVT>.npy, tickinfo_dnnsp_<EVT>.npy,
//           summary_dnnsp_<EVT>.npy, chanmask_bad_<EVT>.npy
// Output: <output_file_prefix>-anode0.root, <output_file_prefix>-anode1.root
//         <sp_frame_prefix>-anode0.tar.bz2,  <sp_frame_prefix>-anode1.tar.bz2
//           (per-anode, gauss<N>-tagged — consumed by woodpecker / run_select_evt.sh)
//
// Pipeline:
//   FrameFileSource(dnnsp)
//   → FrameFanout: for each anode N rename dnnsp→dnnsp<N>, bad→bad (pass-through)
//   → per-anode ChannelSelector
//   → tap: Retagger(dnnsp<N>→gauss<N>) → FrameFileSink(<sp_frame_prefix>-anode<N>.tar.bz2)
//   → Retagger: dnnsp<N>→[dnnsp<N>,threshold<N>] (duplicate for MagnifySink summary)
//   → MagnifySink (RECREATE, writes <prefix>-anode<N>.root)
//   → DumpFrames
//
// Usage (called from run_sp_to_magnify_evt.sh):
//   wire-cell \
//     --tla-str  input=work/evt2/sp-frames.tar.bz2 \
//     --tla-code anode_indices='[0,1]' \
//     --tla-str  output_file_prefix=work/evt2/magnify-evt2 \
//     --tla-str  sp_frame_prefix=work/evt2/sbnd-sp-frames \
//     --tla-code run=0 --tla-code subrun=0 --tla-code event=2 \
//     -c wct-sp-to-magnify.jsonnet

local g = import 'pgraph.jsonnet';
local f = import 'pgrapher/common/funcs.jsonnet';
local wc = import 'wirecell.jsonnet';

local params = import 'pgrapher/experiment/sbnd/simparams.jsonnet';
local tools_maker = import 'pgrapher/common/tools.jsonnet';
local tools_all = tools_maker(params);

function(
  input              = 'sp-frames.tar.bz2',
  anode_indices      = [0, 1],
  output_file_prefix = 'magnify',
  sp_frame_prefix    = 'sbnd-sp-frames',
  run                = 0,
  subrun             = 0,
  event              = 0,
  nticks             = 3427,
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
    { anodes: anodes }, output_file_prefix, runinfo=runinfo);

  // Single FrameFileSource reads the shared per-event tarball.
  local src = g.pnode({
    type: 'FrameFileSource',
    name: 'frame_source',
    data: {
      inname: input,
      tags: ['dnnsp'],
    },
  }, nin=0, nout=1);

  // FrameFanout splits one frame into N per-anode copies, renaming dnnsp→dnnsp<N>.
  // The 'bad' channel mask flows through unchanged (accessed by name in MagnifySink).
  local fanout_rules = [
    {
      frame: { '.*': '' },
      trace: { dnnsp: 'dnnsp%d' % anodes[n].data.ident },
    }
    for n in std.range(0, nanodes - 1)
  ];

  // Tap: per-anode FrameFileSink for woodpecker (retags dnnsp<N>→gauss<N>).
  // Mirrors pdhd/wct-nf-sp.jsonnet's frame_tap pattern.
  local sp_frame_tap(n) =
    local aid = anodes[n].data.ident;
    local retag_for_sink = g.pnode({
      type: 'Retagger',
      name: 'retagger_spframe_anode%d' % aid,
      data: {
        tag_rules: [{
          frame: { '.*': '' },
          trace: { ['dnnsp%d' % aid]: 'gauss%d' % aid },
        }],
      },
    }, nin=1, nout=1);
    local sink = g.pnode({
      type: 'FrameFileSink',
      name: 'spframesink_anode%d' % aid,
      data: {
        outname: '%s-anode%d.tar.bz2' % [sp_frame_prefix, aid],
        tags: ['gauss%d' % aid],
        digitize: false,
        masks: true,
      },
    }, nin=1, nout=0);
    g.fan.tap('FrameFanout',
              g.pipeline([retag_for_sink, sink],
                         'spframetap_pipe_anode%d' % aid),
              'spframetap_anode%d' % aid);

  // Per-anode subgraph: ChannelSelector → [tap: gauss FrameFileSink] → Retagger(dnnsp<N>→[dnnsp<N>,threshold<N>]) → MagnifySink → DumpFrames
  local per_anode_pipe(n) =
    local aid = anodes[n].data.ident;
    // Filter to only this anode's channels before MagnifySink (which throws on foreign channels).
    // SBND has 5638 channels per anode: anode0 → 0..5637, anode1 → 5638..11275.
    local chsel = g.pnode({
      type: 'ChannelSelector',
      name: 'chsel%d' % aid,
      data: {
        channels: std.range(5638 * aid, 5638 * (aid + 1) - 1),
        tags: ['dnnsp%d' % aid],
      },
    }, nin=1, nout=1, uses=[anodes[n]]);
    local retag = g.pnode({
      type: 'Retagger',
      name: 'retagger_anode%d' % aid,
      data: {
        tag_rules: [{
          frame: { '.*': '' },
          trace: {
            ['dnnsp%d' % aid]: ['dnnsp%d' % aid, 'threshold%d' % aid],
          },
        }],
      },
    }, nin=1, nout=1);
    local dump = g.pnode({
      type: 'DumpFrames',
      name: 'dump_anode%d' % aid,
    }, nin=1, nout=0);
    g.pipeline([chsel, sp_frame_tap(n), retag, mag.decon_pipe[n], dump],
               'magnify_branch_anode%d' % aid);

  local per_anode_pipes = [per_anode_pipe(n) for n in std.range(0, nanodes - 1)];

  local fanout_graph = f.fanout('FrameFanout', per_anode_pipes, 'magnify_fanout', fanout_rules);
  local graph = g.pipeline([src, fanout_graph], 'main');

  local all_edges = g.edges(graph);
  local all_uses  = g.uses(graph);

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
