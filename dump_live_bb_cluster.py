import uproot
import numpy as np
root_file = uproot.open("result_5384_130_6501.root")
# root_file.allkeys()
TC = root_file['TC']
def _minmax_from_branch(tree, bname, entry=0, offset=0):
    '''
    Awkward Array
    TDC['wire_index_u'].array()[event#][blob#]
    '''
    akarray = tree[bname].array()[entry]
    min = np.array([np.min(l)+offset for l in akarray])
    min = np.expand_dims(min, axis=1)
    max = np.array([np.max(l)+offset for l in akarray])
    max = np.expand_dims(max, axis=1)
    return np.concatenate((min,max), axis=1)

def _wire_charge_sum(tree, bname, entry=0):
    wire_charge = tree[bname].array()[entry]
    wire_charge = np.array([int(sum(l)) for l in wire_charge])
    wire_charge = np.expand_dims(wire_charge, axis=1)
    return wire_charge

def _nparray(tree, bname, entry=0):
    a = tree[bname].array()[entry]
    a = np.array(a)
    a = np.expand_dims(a, axis=1)
    return a

def _bsignature(tree, entry=0):
    cluster_id = _nparray(tree, 'cluster_id')
    time_slice_mm = _minmax_from_branch(tree, 'time_slice',entry)
    time_slice_mm = time_slice_mm*4
    time_slice_mm[:,1] = time_slice_mm[:,1]+4
    wire_index_u_mm = _minmax_from_branch(tree, 'wire_index_u',entry,0)
    wire_index_v_mm = _minmax_from_branch(tree, 'wire_index_v',entry,2400)
    wire_index_w_mm = _minmax_from_branch(tree, 'wire_index_w',entry,4800)
    # 0
    # 1, 2 time bound
    # 3, 4, 5, 6, 7, 8 wire bound
    sig = np.concatenate((cluster_id,time_slice_mm,wire_index_u_mm,wire_index_v_mm,wire_index_w_mm), axis=1)
    wire_charge_u = _wire_charge_sum(tree,'wire_charge_u',entry)
    wire_charge_v = _wire_charge_sum(tree,'wire_charge_v',entry)
    wire_charge_w = _wire_charge_sum(tree,'wire_charge_w',entry)
    # 9, 10, 11 wire charge
    sig = np.concatenate((sig,wire_charge_u,wire_charge_v,wire_charge_w), axis=1)
    uc_cluster_id = _nparray(tree, 'uc_cluster_id')
    vc_cluster_id = _nparray(tree, 'vc_cluster_id')
    wc_cluster_id = _nparray(tree, 'wc_cluster_id')
    # 12, 13, 14 covered by cluster_id
    sig = np.concatenate((sig,uc_cluster_id,vc_cluster_id,wc_cluster_id), axis=1)
    return sig

def _csignature(tree, entry=0):
    bsigs = _bsignature(tree, entry)
    # print(f'#b: {bsigs.shape[0]}')
    clusters = [bsigs[bsigs[:,0] == cluster_id, :] for cluster_id in np.unique(bsigs[:,0])]
    def sig(cluster):
        cluster_id = cluster[0,0]
        min_start = min(cluster[:,1])
        max_start = max(cluster[:,1])
        nblob = cluster.shape[0]
        min_u = min(cluster[:,3])
        max_u = max(cluster[:,4])
        min_v = min(cluster[:,5])
        max_v = max(cluster[:,6])
        min_w = min(cluster[:,7])
        max_w = max(cluster[:,8])
        charge_u = sum(cluster[:,9])
        charge_v = sum(cluster[:,10])
        charge_w = sum(cluster[:,11])
        uc_cluster_id = cluster[0,12]
        vc_cluster_id = cluster[0,13]
        wc_cluster_id = cluster[0,14]
        return np.array([min_start, max_start, nblob,
                         min_u, max_u, min_v, max_v, min_w, max_w,
                         charge_u, charge_v, charge_w,
                         cluster_id, uc_cluster_id, vc_cluster_id, wc_cluster_id
                         ])
    csigs = [sig(cluster) for cluster in clusters]
    csigs = np.array(csigs)
    return csigs

def _sort(arr):
    ind = np.lexsort((arr[:,8],arr[:,7],arr[:,6],arr[:,5],arr[:,4],arr[:,3],arr[:,2],arr[:,1],arr[:,0]))
    arr = np.array([arr[i] for i in ind])
    return arr


csigs = _csignature(TC, 0)
print(csigs.shape)
# csigs = csigs[csigs[:,13]!=-1,:]
# csigs = csigs[csigs[:,14]==-1,:]
# csigs = csigs[csigs[:,15]==-1,:]
csigs = _sort(csigs)
print('WCP')
print(csigs.shape)
for i in range(csigs.shape[0]):
    print(csigs[i,0:2], csigs[i,2],          # time, nblobs
        csigs[i,3], ',', csigs[i,4]+1, ',',  # U
        csigs[i,5], ',', csigs[i,6]+1, ',',  # V
        csigs[i,7], ',', csigs[i,8]+1,       # W
        csigs[i,9:12]                        # charge
        , ',',csigs[i,12]                    # cluster_id
        , ',',csigs[i,13:16]                 # covered by ...
        )