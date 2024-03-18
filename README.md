# wcp-porting-img

Example input CellTree
https://www.phy.bnl.gov/~hyu/wcp-porting-img/celltreeOVERLAY.root

CellTree -> Img
```
wire-cell -l stdout -L debug -c wct-celltree-img.jsonnet
```

To paraview format
```bash
wirecell-img paraview-blobs clusters-apa-uboone.tar.gz clusters-apa-uboone.vtu

```

To bee format
```
python wct-img-2-bee.py 'clusters*.tar.gz'
```

Upload to bee
https://www.phy.bnl.gov/twister/bee


validation examples:
```
wirecell-img dump-blobs clusters-apa-uboone.tar.gz >& b.log
wirecell-img dump-bb-clusters clusters-apa-uboone-ms-active.tar.gz >& c.log
```

## clustering

testing:
```
wire-cell -l stdout -L debug -c wct-uboone-full.jsonnet

wire-cell -l stdout -L debug -c wct-uboone-full.jsonnet \
--tla-str input="celltreeOVERLAY.root" \
--tla-code entry=0 \
--tla-str bee_dir="data"
```

or the above, split up in two stages:
```
wire-cell -l stdout -L debug -c wct-uboone-img.jsonnet
$ ls -l active-clusters-anode0.npz masked-clusters-anode0.npz
SPDLOG_LEVEL=debug wire-cell -l stdout -L debug -c wct-uboone-clustering.jsonnet
```
