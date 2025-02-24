#jsonnet=/cvmfs/larsoft.opensciencegrid.org/products/jsonnet/v0_12_1a/Linux64bit+3.10-2.17-e20-prof/bin/jsonnet
#jsonnet=/cvmfs/larsoft.opensciencegrid.org/products/gojsonnet/v0_17_0/Linux64bit+3.10-2.17-e20/bin/jsonnet
#jsonnet=/home/yuhw/go/jsonnet/bin/jsonnet

cfg=/home/yuhw/wc/larsoft925/src/wct/cfg

name=$2

if [[ $1 == "json" || $1 == "all" ]]; then
jsonnet \
--ext-code DL=4.0 \
--ext-code DT=8.8 \
--ext-code lifetime=10.4 \
--ext-code driftSpeed=1.60563 \
--ext-str detector="uboone" \
--ext-str input="orig-bl.root" \
--ext-code evt=0 \
--ext-str output="orig-bl-nf-sp.root" \
-A kind="both" \
-J $cfg/obsolete \
-J $cfg \
${name}.jsonnet \
-o ${name}.json
fi

if [[ $1 == "pdf" || $1 == "all" ]]; then
    wirecell-pgraph dotify --jpath -1 --no-services --no-params ${name}.json ${name}.pdf
    #wirecell-pgraph dotify --no-services --jpath -1 ${name}.json ${name}.pdf
fi
