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
time lar --nskip 2 -n 2 -c wcls-img-clus.fcl -s lynn-sim.root --no-output >& log
time lar --nskip 2 -n 2 -c wcls-img-clus-matching.fcl -s lynn-sim.root --no-output >& log

python merge-zip.py merged.zip "mabc-*.zip"
./merge-upload.sh 2 # outside container
```