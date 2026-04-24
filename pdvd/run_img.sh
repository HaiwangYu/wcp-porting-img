#!/bin/sh

WCT_BASE=/nfs/data/1/xning/wirecell-working
export WIRECELL_PATH=${WCT_BASE}/toolkit/cfg:${WCT_BASE}/dunereco/dunereco/DUNEWireCell/protodunevd:${WIRECELL_PATH}
PDVD_DIR=$(cd "$(dirname "$0")" && pwd)

# Single anode (original, one file):
#wire-cell -l stdout -L debug -c wct-img.jsonnet

# All anodes:
#wire-cell -l stdout -L debug -c wct-img-all.jsonnet

# Selected anodes by index into tools_all.anodes (e.g. indices 4 and 5):
# wire-cell -l stdout -L debug --tla-code anode_indices='[4,5]' -c wct-img-all.jsonnet

# Selected anodes with a custom file prefix:
wire-cell -l stdout -L debug \
 --tla-str input_prefix='protodune-sp-frames-part' \
 --tla-code anode_indices='[1]' \
 -c wct-img-all.jsonnet

# python wct-img-2-bee-only.py clusters-apa-anode0-ms-active.tar.gz 
# python wct-img-2-bee.py clusters-apa-anode0-ms-active.tar.gz clusters-apa-anode1-ms-active.tar.gz clusters-apa-anode2-ms-active.tar.gz clusters-apa-anode3-ms-active.tar.gz clusters-apa-anode4-ms-active.tar.gz clusters-apa-anode5-ms-active.tar.gz clusters-apa-anode6-ms-active.tar.gz clusters-apa-anode7-ms-active.tar.gz
#  zip -r upload data
#  ../upload-to-bee.sh upload.zip

wire-cell -l stdout -L debug \
  --tla-str input="." \
  --tla-code anode_indices='[1]' \
  -c wct-clustering.jsonnet

./unzip.pl 
./zip-upload.sh 


#wire-cell -l stdout -L debug \
#  --tla-str input="$PDVD_DIR" \
#  -c wct-clustering.jsonnet

