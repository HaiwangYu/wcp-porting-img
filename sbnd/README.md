```bash
# in SL7 container

# setup 
source setup.sh

# run img and clus
time lar --nskip 0 -n 1 -c wcls-img-clus.fcl -s input-moon.root --no-output >& log

# merge two APAs
python merge-zip.py

# upload to BEE
../upload-to-bee.sh mabc.zip
```