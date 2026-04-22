# ProtoDUNE-VD Utility Commands

## Geometry visualization

Wire geometry file:
```
/nfs/data/1/xqian/toolkit-dev/wire-cell-data/protodunevd-wires-larsoft-v3.json.bz2
```

```sh
GEOM=/nfs/data/1/xqian/toolkit-dev/wire-cell-data/protodunevd-wires-larsoft-v3.json.bz2
```

### Text summary (anode/face/plane/wire counts, pitch, coordinate ranges)

```sh
wirecell-util wires-info $GEOM
```

### Multi-page wire geometry plot (positions, segments, per-plane maps)

```sh
wirecell-util plot-wires $GEOM pdvd-wires.pdf
```

### Channel-to-coordinate scatter plots (X/Y/Z vs channel number)

```sh
wirecell-util wires-channels $GEOM pdvd-channels.pdf
```

### Plot selected channels by number

```sh
wirecell-util plot-select-channels $GEOM pdvd-selected.pdf 100 200 300
```
