import json
import re
import os
from optparse import OptionParser

def str2apa(str):
    return re.search(r"apa(\d+)", str).group(1)

def merge_charge(file_list, cluster_id_offset_per_file=1000):
    '''
    cluster_id increases by cluster_id_offset_per_file for each file
    '''
    merged_data = {
        "eventNo": [],
        "subRunNo": [],
        "runNo": [],
        "type": [],
        "geom": "sbnd",
        "cluster_id": [],
        "apa": [],
        "x": [],
        "y": [],
        "z": [],
        "q": [],
    }

    cluster_id_offset = 0
    for file in file_list:
        with open(file, 'r') as f:
            data = json.load(f)
        
        merged_data["eventNo"] = data["eventNo"]
        merged_data["subRunNo"] = data["subRunNo"]
        merged_data["runNo"] = data["runNo"]
        merged_data["type"] = data["type"]
        merged_data["geom"] = "sbnd"
        merged_data["cluster_id"].extend([id + cluster_id_offset for id in data["cluster_id"]])
        merged_data["apa"].extend([str2apa(file)] * len(data["cluster_id"]))
        merged_data["x"].extend(data["x"])
        merged_data["y"].extend(data["y"])
        merged_data["z"].extend(data["z"])
        merged_data["q"].extend(data["q"])

        # print(f"{file}: {max(merged_data['cluster_id'])}")
        cluster_id_offset = cluster_id_offset + cluster_id_offset_per_file

    return merged_data


def merge_light(file_list, charge_data, cluster_id_offset_per_file=1000):
    merged_data = {
        "eventNo": [],
        "subRunNo": [],
        "runNo": [],
        "geom": [],
        "cluster_id": [],
        "apa": [],
        "op_peTotal": [],
        "op_pes": [],
        "op_pes_pred": [],
        "op_t": [],
    }

    all_cluster_id = sorted(set(charge_data["cluster_id"]))

    cluster_id_offset = 0
    for file in file_list:
        with open(file, 'r') as f:
            data = json.load(f)

        merged_data["eventNo"] = data["eventNo"]
        merged_data["subRunNo"] = data["subRunNo"]
        merged_data["runNo"] = data["runNo"]
        merged_data["geom"] = "sbnd"
        cluster_ids_all_apa = [[x + cluster_id_offset for x in sublist] for sublist in data["cluster_id"]]
        
        merged_data["cluster_id"].extend(cluster_ids_all_apa)
        merged_data["apa"].extend([str2apa(file)] * len(data["cluster_id"]))
        merged_data["op_peTotal"].extend(data["op_peTotal"])
        merged_data["op_pes"].extend(data["op_pes"])
        merged_data["op_pes_pred"].extend(data["op_pes_pred"])
        merged_data["op_t"].extend(data["op_t"])

        # print(f"{file}: {merged_data['cluster_id']}")
        cluster_id_offset = cluster_id_offset + cluster_id_offset_per_file

    sorted_indices = sorted(range(len(merged_data["op_t"])), key=lambda k: merged_data["op_t"][k])
    sorted_data = {
        "eventNo": merged_data["eventNo"],
        "subRunNo": merged_data["subRunNo"],
        "runNo": merged_data["runNo"],
        "geom": merged_data["geom"],
        "op_cluster_ids": [merged_data["cluster_id"][i] for i in sorted_indices],
        "apa": [merged_data["apa"][i] for i in sorted_indices],
        "op_peTotal": [merged_data["op_peTotal"][i] for i in sorted_indices],
        "op_pes": [merged_data["op_pes"][i] for i in sorted_indices],
        "op_pes_pred": [merged_data["op_pes_pred"][i] for i in sorted_indices],
        "op_t": [merged_data["op_t"][i] for i in sorted_indices],
    }
    # print(sorted_data["op_cluster_ids"][0])
    return sorted_data

if __name__ == "__main__":
    parser = OptionParser()
    parser.add_option('--inpath', dest='inpath',
                      help='path to the input files')
    parser.add_option('--outpath', dest='outpath',
                      help='path to the output files')
    parser.add_option('--eventNo', dest='eventNo',
                      help='event number')
    parser.add_option('--cleanup', dest='cleanup', default=False,
                      help='remove original files after merging')
    (options, args) = parser.parse_args()


    inpath_event = f"{options.inpath}/{options.eventNo}"
    qfiles = [inpath_event+"/"+f for f in sorted(os.listdir(inpath_event)) if re.search(r"img", f)]
    lfiles = [inpath_event+"/"+f for f in sorted(os.listdir(inpath_event)) if re.search(r"op", f)]

    qdata = merge_charge(qfiles)
    qfile = f"{options.outpath}/{options.eventNo}/{options.eventNo}-img.json"
    qfile_dir = os.path.dirname(qfile)
    os.makedirs(qfile_dir, exist_ok=True)
    with open(qfile, 'w') as f:
        json.dump(qdata, f)

    ldata = merge_light(lfiles, qdata)
    lfile = f"{options.outpath}/{options.eventNo}/{options.eventNo}-op.json"
    lfile_dir = os.path.dirname(lfile)
    os.makedirs(lfile_dir, exist_ok=True)
    with open(lfile, 'w') as f:
        json.dump(ldata, f)
    
    if options.cleanup:
        for f in qfiles + lfiles:
            os.remove(f)