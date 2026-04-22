# standalone-sample

```bash
# Part A: dump image clusters
lar -n 1 -c wcls-img-dump.fcl 2025f-mc.root

# Part B: dump opflash data
lar -n 1 -c wcls-flash-dump.fcl 2025f-mc.root

# Part C: clustering + QL matching + all-APA clustering (needs LArSoft env)
lar -n 1 -c wct-clus-matching.fcl
```