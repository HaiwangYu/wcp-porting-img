source /cvmfs/sbnd.opensciencegrid.org/products/sbnd/setup_sbnd.sh

# setup sbndcode v10_06_03 -q e26:prof
# source /exp/sbnd/app/users/yuhw/larsoft/v10_06_03/localProducts_larsoft_v10_06_00_02_e26_prof/setup

setup sbndcode v10_14_02_01 -q e26:prof

unsetup larwirecell
unsetup wirecell
unsetup larevt
unsetup lardata
unsetup larsim
unsetup lardataalg
unsetup larg4
unsetup lardataobj
setup larwirecell v10_02_00 -q e26:prof

setup gdb
setup cetmodules v3_24_00

# for compiling larwirecell
# path-prepend /exp/sbnd/app/users/yuhw/opt CMAKE_PREFIX_PATH


path-remove ()
{
    local IFS=':';
    local NEWPATH;
    local DIR;
    local PATHVARIABLE=${2:-PATH};
    for DIR in ${!PATHVARIABLE};
    do
        if [ "$DIR" != "$1" ]; then
            NEWPATH=${NEWPATH:+$NEWPATH:}$DIR;
        fi;
    done;
    export $PATHVARIABLE="$NEWPATH"
}

path-prepend ()
{
    path-remove "$1" "$2";
    local PATHVARIABLE="${2:-PATH}";
    export $PATHVARIABLE="$1${!PATHVARIABLE:+:${!PATHVARIABLE}}"
}

path-append ()
{
    path-remove "$1" "$2";
    local PATHVARIABLE="${2:-PATH}";
    export $PATHVARIABLE="${!PATHVARIABLE:+${!PATHVARIABLE}:}$1"
}

# path-prepend /exp/sbnd/app/users/yuhw/opt/lib/ LD_LIBRARY_PATH
# path-prepend /exp/sbnd/app/users/yuhw/opt/bin/ PATH

path-prepend /exp/sbnd/app/users/yuhw/wire-cell-toolkit/cfg WIRECELL_PATH
path-prepend /exp/sbnd/app/users/yuhw/wire-cell-data WIRECELL_PATH

path-prepend /exp/sbnd/app/users/yuhw/wct-porting/cfg WIRECELL_PATH
rs
export PS1=(app)$PS1

source /exp/sbnd/app/users/yuhw/wire-cell-python/venv/bin/activate

