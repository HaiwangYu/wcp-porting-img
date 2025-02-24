```
valgrind --tool=massif wire-cell -t 1 -l stdout -L debug -c wct-depo-sim-img-fans.jsonnet -V input=depos-vd-1x8x14-genie/depos-1.tar.bz2 | tee log
valgrind --tool=massif wire-cell -t 1 -l stdout -L debug -c wct-sim-fans.jsonnet | tee log
wire-cell -t 1 -l stdout -L debug -c wct-depo-sim-img-fans.jsonnet -V input=depos-vd-1x8x14-genie/depos-1.tar.bz2
wirecell-plot frame -t gauss -n wave --interactive frame-gauss5.tar.bz2 tmp.pdf
```
python wct-img-2-bee.py 'clusters*.tar.gz'
