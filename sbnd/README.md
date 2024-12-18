```bash
# in SL7 container

# setup 
source setup.sh

# run img and clus
time lar -n 1 -c wcls-sig-to-img_v4.fcl -s input-moon.root -o tmp.root >& log

# merge two APAs
python merge-zip.py

# upload to BEE
../upload-to-bee.sh mabc.zip
```