#jsonnet=/cvmfs/larsoft.opensciencegrid.org/products/jsonnet/v0_12_1a/Linux64bit+3.10-2.17-e20-prof/bin/jsonnet
jsonnet=/cvmfs/larsoft.opensciencegrid.org/products/gojsonnet/v0_17_0/Linux64bit+3.10-2.17-e20/bin/jsonnet
#jsonnet=/home/yuhw/go/jsonnet/bin/jsonnet

cfg=/home/yuhw/wc/larsoft925/src/wct/cfg

name=$2
name=${name%.jsonnet}

if [[ $1 == "json" || $1 == "all" ]]; then
$jsonnet \
--ext-str input="depos-vd-1x8x14-genie/depos-4.tar.bz2" \
--ext-code channel_per_crm=900 \
-J $cfg ${name}.jsonnet \
-o ${name}.json
fi

if [[ $1 == "pdf" || $1 == "all" ]]; then
    #wirecell-pgraph dotify --jpath -1 --no-services --no-params ${name}.json ${name}.pdf
    wirecell-pgraph dotify --jpath -1 --no-params ${name}.json ${name}.pdf
fi
