
run UbooneBlobSource
```bash
wire-cell -A iname="result_5384_130_6501.root" -A oname="active-clusters-anode0.npz" -A kind="live" uboone-val.jsonnet
wire-cell -A iname="result_5384_130_6501.root" -A oname="masked-clusters-anode0.npz" -A kind="dead" uboone-val.jsonnet
```

run clustering
```bash
wire-cell -l stdout -L debug -c ../wct-uboone-clustering.jsonnet -A bee_zip=live-dead.zip
```

upload to BEE
```bash
./upload-to-bee.sh live-dead.zip
```

Note: an older version used to write to a directory named with now obsolete `bee_dir` config var.
The `bee_zip` is used as of:

https://github.com/WireCell/wire-cell-toolkit/commit/324b3b83261b8ec52b4f881cefd47fb118ace3dc

---

Origin cfg for `UbooneBlobSource` -> BEE
```bash
wire-cell -A iname="result_5384_130_6501.root" -A oname="live.zip" -A kind="live" uboone-blobs.jsonnet
../upload-to-bee.sh live.zip
```

example bee:
https://www.phy.bnl.gov/twister/bee/set/fc4e52b6-a8d3-4c64-9d0d-0749bedc83e2/event/0/
