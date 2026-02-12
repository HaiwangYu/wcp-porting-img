

### setup script:
```bash
/exp/sbnd/app/users/yuhw/setup.sh
```
this is `sbndcode v10_14_02_03` based.

### cfg repo & running cmd:
```bash
lar --nskip 0 -n 1 -c wcls-img-clus-matching.fcl -s lynn-iso.root --no-output
```
in here:
https://github.com/HaiwangYu/wcp-porting-img/blob/main/sbnd/README.md

### For wire-cell-toolkit, lib and path, maybe use the setup in `/exp/sbnd/app/users/yuhw/setup.sh`
The lib part should be the same as wirecell 0.33.0
There are some changes related to the img.jsonnet (`nthreshold: [1e-6, 1e-6, 1e-6]`) and the params.jsonnet (using `wires: "sbnd-wires-geometry-v0200.json.bz2"`)

### my larwirecell branch:
https://github.com/HaiwangYu/larwirecell/tree/dev-v10_14_02_02