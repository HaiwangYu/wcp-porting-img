```bash
# in SL7 container

# setup 
source setup.sh

# run img and clus
time lar --nskip 0 -n 4 -c wcls-img-clus.fcl -s input-moon.root --no-output >& log
time lar --nskip 0 -n 4 -c wcls-img-dump.fcl -s input-moon.root --no-output >& log
time wire-cell -l stdout -L debug -c wct-clus.jsonnet -V input="1event" >& log


# merge two APAs
python merge-zip.py merged.zip "mabc-*.zip"

# upload to BEE
../upload-to-bee.sh merged.zip
```


Sim/prabhjot
```bash
time lar --nskip 0 -n 4 -c wcls-img-clus.fcl -s input-prabhjot.root --no-output >& log
```


add matching
```bash
time lar --nskip 1 -n 1 -c wcls-img-clus.fcl -s lynn-sim.root --no-output >& log
time lar --nskip 1 -n 1 -c wcls-img-clus-matching.fcl -s lynn-sim.root --no-output >& lynn-sim.log
time lar --nskip 0 -n 1 -c wcls-img-clus-matching.fcl -s lynn-iso.root --no-output >& lynn-iso.log
time lar --nskip 0 -n 1 -c wcls-img-clus-matching.fcl -s lynn-30.root --no-output >& lynn-30.log

python merge-zip.py merged.zip "mabc-*.zip"
python merge-apa.py --inpath=data-sep --outpath=data --eventNo=0
./merge-upload.sh
```

debug stuff
```bash
python filter_cluster.py -o data-sep/2/2-img-apa0-cluster-2.json data-sep/2/2-img-apa0.json 2
python filter_cluster.py -o ref-lynn-filter.json ref-lynn.json 2
```