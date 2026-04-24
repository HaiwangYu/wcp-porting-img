# standalone-sample

```bash
lar -n 10 -c wcls-sp-dump.fcl -s 2025f-mc.root --no-output
wirecell-plot frame -t gauss -o sp-frames.pdf sp-frames.tar.bz2
```

```bash
# Part A: dump image clusters
lar -n 1 -c wcls-img-dump.fcl 2025f-mc.root

# Part B: dump opflash data
lar -n 1 -c wcls-flash-dump.fcl 2025f-mc.root

# Part C: clustering + QL matching + all-APA clustering (needs LArSoft env)
lar -n 1 -c wct-clus-matching.fcl
```