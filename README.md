# wcp-porting-img

Example input CellTree
https://www.phy.bnl.gov/~hyu/wcp-porting-img/celltreeOVERLAY.root

CellTree -> Img
```
wire-cell -l stdout -L debug -c wct-celltree-img.jsonnet
```


To bee format
```
python wct-img-2-bee.py 'clusters-*.json'
```

Upload to bee
https://www.phy.bnl.gov/twister/bee


validation examples:
```
wirecell-img dump-blobs clusters-apa-uboone.tar.gz >& wct-b-111.log
wirecell-img dump-bb-clusters clusters-apa-uboone-ms-active.tar.gz >& wct-c.log
```
