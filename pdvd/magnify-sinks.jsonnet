// Per-anode MagnifySink pipelines for pdvd SP-frame → Magnify ROOT conversion.
// tools:      object with .anodes array (filtered subset to process)
// outputfile: output ROOT file path
// runinfo:    optional {runNo, subRunNo, eventNo, total_time_bin} injected into
//             the first sink's Trun tree; null skips Trun writing.
//             anodeNo is added automatically from the anode's ident.

local g = import 'pgraph.jsonnet';
local wc = import 'wirecell.jsonnet';

function(tools, outputfile, runinfo=null) {
  local nanodes = std.length(tools.anodes),

  // First sink RECREATEs the file; subsequent sinks UPDATE it.
  // Only the first sink carries runinfo to avoid duplicate Trun cycles.
  local mksink(n, anode) = g.pnode({
    type: 'MagnifySink',
    name: 'magdecon%d' % anode.data.ident,
    data: {
      output_filename: outputfile,
      root_file_mode: if n == 0 then 'RECREATE' else 'UPDATE',
      frames: ['gauss%d' % anode.data.ident, 'wiener%d' % anode.data.ident],
      // Retagger (inserted upstream) copies wiener<N> → threshold<N>, so
      // summaries get written as h[uvw]_threshold<N> as Magnify expects.
      summaries: ['threshold%d' % anode.data.ident],
      summary_operator: { ['threshold%d' % anode.data.ident]: 'set' },
      cmmtree: [['bad', 'T_bad%d' % anode.data.ident]],
      trace_has_tag: true,
      anode: wc.tn(anode),
    } + (if n == 0 && runinfo != null then { runinfo: runinfo { anodeNo: anode.data.ident } } else {}),
  }, nin=1, nout=1, uses=[anode]),

  return: {
    decon_pipe: [
      g.pipeline([mksink(n, tools.anodes[n])], name='magpipe%d' % n)
      for n in std.range(0, nanodes - 1)
    ],
  },
}.return
