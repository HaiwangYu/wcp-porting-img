import uproot
import numpy as np
root_file = uproot.open("result_5384_130_6501.root")
root_file.allkeys()
TDC = root_file['TDC']
print(TDC.allkeys())

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

def _signature(tree, entry=0):
    time_slice_mm = _minmax_from_branch(tree, 'time_slice',entry)
    time_slice_mm = time_slice_mm*4
    wire_index_u_mm = _minmax_from_branch(tree, 'wire_index_u',entry,0)
    wire_index_v_mm = _minmax_from_branch(tree, 'wire_index_v',entry,2400)
    wire_index_w_mm = _minmax_from_branch(tree, 'wire_index_w',entry,4800)
    flag_u = np.array(tree['flag_u'].array()[entry])
    flag_u = np.expand_dims(flag_u, axis=1)
    flag_v = np.array(tree['flag_v'].array()[entry])
    flag_v = np.expand_dims(flag_v, axis=1)
    flag_w = np.array(tree['flag_w'].array()[entry])
    flag_w = np.expand_dims(flag_w, axis=1)
    return np.concatenate((time_slice_mm,wire_index_u_mm,wire_index_v_mm,wire_index_w_mm,flag_u,flag_v,flag_w), axis=1)

def _sort(arr):
    ind = np.lexsort((arr[:,7],arr[:,6],arr[:,5],arr[:,4],arr[:,3],arr[:,2]))
    arr = np.array([arr[i] for i in ind])
    return arr

sigs = _signature(TDC, 0)
sigs = sigs[sigs[:,0]==0,:] # select tick == 0
sigs = sigs[sigs[:,10]==1,:] # dusigsy = w
sigs = _sort(sigs)
print(sigs.shape)
# for i in range(min([sigs.shape[0], 20])):
for i in range(sigs.shape[0]):
    # print(i, sigs[i,:])
    print(sigs[i,0:2],
        sigs[i,2], ':', sigs[i,3]+1, ',',
        sigs[i,4], ':', sigs[i,5]+1, ','
        #,sigs[i,6], ':', sigs[i,7]+1
        #,sigs[i,8:]
        )
