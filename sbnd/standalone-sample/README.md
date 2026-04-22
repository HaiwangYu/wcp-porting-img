# standalone-sample

```bash
# Part A: dump image clusters
lar -n 1 -c wcls-img-dump.fcl 2025f-mc.root

# Part B: dump opflash data
lar -n 1 -c wcls-flash-dump.fcl 2025f-mc.root

# Part C: standalone clustering + matching
wire-cell \
  -V reality=sim \
  -V DL=6.2 -V DT=9.8 -V lifetime=6 -V driftSpeed=1.565 \
  -V input=. \
  -c wct-clus-matching.jsonnet
```