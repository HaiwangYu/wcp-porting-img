// Per-anode MagnifySink pipelines for SBND SP-frame → Magnify ROOT conversion.
// tools:             object with .anodes array (filtered subset to process)
// outputfile_prefix: base path; each anode writes to <prefix>-anode<N>.root
// runinfo:           optional {runNo, subRunNo, eventNo, total_time_bin}
//
// Each anode's MagnifySink writes to its own ROOT file (RECREATE mode) so all
// anodes can be processed in a single wire-cell invocation from a shared frame.
// Upstream Retagger must duplicate 'dnnsp<N>' → ['dnnsp<N>', 'threshold<N>'] so
// the summary is written as h[uvw]_threshold<N> as Magnify expects.

local g = import 'pgraph.jsonnet';
local wc = import 'wirecell.jsonnet';

function(tools, outputfile_prefix, runinfo=null) {
  local nanodes = std.length(tools.anodes),

  local mksink(anode) = g.pnode({
    type: 'MagnifySink',
    name: 'magdecon%d' % anode.data.ident,
    data: {
      output_filename: '%s-anode%d.root' % [outputfile_prefix, anode.data.ident],
      root_file_mode: 'RECREATE',
      frames: ['dnnsp%d' % anode.data.ident],
      summaries: ['threshold%d' % anode.data.ident],
      summary_operator: { ['threshold%d' % anode.data.ident]: 'set' },
      cmmtree: [['bad', 'T_bad%d' % anode.data.ident]],
      trace_has_tag: true,
      anode: wc.tn(anode),
    } + (if runinfo != null
         then { runinfo: runinfo { anodeNo: anode.data.ident },
                geo_tree: 'T_geo%d' % anode.data.ident }
         else {}),
  }, nin=1, nout=1, uses=[anode]),

  return: {
    decon_pipe: [
      g.pipeline([mksink(tools.anodes[n])], name='magpipe%d' % n)
      for n in std.range(0, nanodes - 1)
    ],
  },
}.return
