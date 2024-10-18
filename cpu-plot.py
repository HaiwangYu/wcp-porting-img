#!/usr/bin/env python

import matplotlib.pyplot as plt
import pandas as pd
import numpy as np

import matplotlib
print("Backend used by matplotlib is: ", matplotlib.get_backend())

inputs = [
"top.log",
]
labels = inputs
linestyles = [
"-",
"-",
"-",
"-",
"-",
"-",
"-",
"-",
]


dfs = [pd.read_csv(tag, sep=' ', header=None) for tag in inputs]
xscale = 9./24
xscale = 204./740
cpu_lim = [0, 900]
ram_size = 31.3 # 31.3, 10
ram_lim = [0, ram_size]

fontsize = 18

for i in range(len(inputs)) :
    x = np.linspace(0,dfs[i][0].shape[0]*xscale,dfs[i][0].shape[0])
    plt.plot(x,dfs[i][0],label=labels[i]
        , linestyle=linestyles[i]
    )
plt.legend(loc='best',fontsize=fontsize)
plt.grid()
plt.ylim(cpu_lim)
plt.xlabel("time [sec]", fontsize=fontsize)
plt.ylabel("cpu [%]", fontsize=fontsize)
plt.yticks(fontsize=fontsize)
plt.xticks(fontsize=fontsize)
plt.tight_layout()
plt.show()

for i in range(len(inputs)) :
    x = np.linspace(0,dfs[i][0].shape[0]*xscale,dfs[i][0].shape[0])
    plt.plot(x,dfs[i][1]*ram_size/100,label=labels[i]
             , linestyle=linestyles[i]
    )
# plt.plot((dfs[1][1]-dfs[0][1])*31.3/100,label="TBB-single - Pgrapher")
plt.legend(loc='best',fontsize=fontsize)
plt.grid()
plt.ylim(ram_lim)
plt.xlabel("time [sec]", fontsize=fontsize)
plt.ylabel("memory [GB]", fontsize=fontsize)
plt.yticks(fontsize=fontsize)
plt.xticks(fontsize=fontsize)
plt.tight_layout()
plt.show()


# plt.plot((dfs[1][1]-dfs[0][1])*31.3/100,label="TBB-single - Pgrapher")
# plt.legend(loc='best',fontsize=fontsize)
# plt.grid()
# plt.ylim(-1,1)
# plt.xlabel("time [sec]", fontsize=fontsize)
# plt.ylabel("memory [GB]", fontsize=fontsize)
# plt.show()

# for i in range(len(inputs)) :
#     plt.plot(dfs[i][1]*31.3/dfs[i][0],label=labels[i])
# plt.legend(loc='best',fontsize=fontsize)
# plt.grid()
# plt.ylim(0,2)
# plt.xlabel("time [sec]", fontsize=fontsize)
# plt.ylabel("memory/CPU load [GB]", fontsize=fontsize)
# plt.show()

#%%
