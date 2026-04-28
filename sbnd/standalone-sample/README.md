# standalone-sample

## check SP results
```bash
lar -n 10 -c wcls-sp-dump.fcl -s 2025f-mc.root --no-output
wirecell-plot frame -t dnnsp -o sp-frames.pdf sp-frames.tar.bz2

python plot_simchannels.py --input 2025f-mc.root --channel-min 0 --channel-max 1983 --vmax-percentile 80 --entry 0 --out-prefix simchannels_entry0
```

## standalone files
```bash
# Part A: dump image clusters
lar -n 1 -c wcls-img-dump.fcl 2025f-mc.root

# Part B: dump opflash data
lar -n 1 -c wcls-flash-dump.fcl 2025f-mc.root

# Part C: clustering + QL matching + all-APA clustering (needs LArSoft env)
lar -n 1 -c wct-clus-matching.fcl
```