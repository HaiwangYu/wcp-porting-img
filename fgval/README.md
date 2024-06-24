```bash
wire-cell -A iname="result_5384_130_6501.root" -A oname="active-clusters-anode0.npz" -A kind="live" uboone-val.jsonnet
wire-cell -A iname="result_5384_130_6501.root" -A oname="masked-clusters-anode0.npz" -A kind="dead" uboone-val.jsonnet
../upload-to-bee.sh live.zip
```

example bee:
https://www.phy.bnl.gov/twister/bee/set/fc4e52b6-a8d3-4c64-9d0d-0749bedc83e2/event/0/


```bash
wire-cell -l stdout -L debug -c ../wct-uboone-clustering.jsonnet
```