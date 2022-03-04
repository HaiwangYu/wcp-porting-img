# wcp-porting-img

Example input CellTree
https://www.phy.bnl.gov/~hyu/wcp-porting-img/celltreeOVERLAY.root

CellTree -> Img
```
wire-cell -l stdout -L debug -c wct-celltree-sink.jsonnet
```


To bee format
```
python wct-img-2-bee.py 'clusters-*.json'
```

Upload to bee
https://www.phy.bnl.gov/twister/bee
