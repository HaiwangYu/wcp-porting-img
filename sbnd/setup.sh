source /cvmfs/sbnd.opensciencegrid.org/products/sbnd/setup_sbnd.sh
setup sbndcode v09_91_02 -q e26:prof
source /exp/sbnd/app/users/yuhw/larsoft/v09_91_02/localProducts_larsoft_v09_91_02_e26_prof/setup
mrbsetenv
mrbslp

path-prepend /exp/sbnd/app/users/yuhw/opt/lib/ LD_LIBRARY_PATH

path-prepend /exp/sbnd/app/users/yuhw/wct-cfg/cfg WIRECELL_PATH
path-prepend /exp/sbnd/app/users/yuhw/wire-cell-data WIRECELL_PATH
