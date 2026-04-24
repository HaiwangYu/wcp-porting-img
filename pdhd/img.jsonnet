// Local wrapper for wcp-porting-img/pdhd/wct-img-all.jsonnet.
// Instantiates the toolkit img.jsonnet with the output_dir parameter
// so that cluster output files are written to the specified directory.

local toolkit_img = import 'pgrapher/experiment/pdhd/img.jsonnet';

function(output_dir='')
    local img_obj = toolkit_img({});
    {
        per_anode(anode, pipe_type='multi') ::
            img_obj.per_anode(anode, pipe_type, output_dir),
    }
