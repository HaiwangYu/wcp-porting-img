#!/bin/bash
# doc 102: the arm completion + cost table, straight off the arms.
set -u
SX=/nfs/data/1/xqian/toolkit-dev/wcp-porting-img/sbnd/sbnd_xin
cd "$SX"
printf '%-9s %6s %6s %6s %8s %8s %9s %9s %8s %8s\n' sample nA_ql nB_pr rcbad ql_pctree prA_GiB prB_GiB imgW_s qlW_s prCore_s
for s in nuecc48 ncpi0 mcp1k mcp2k; do
  A=work-$s-d102m; B=work-$s-d102mpr
  nA=$(ls -d $A/ql_evt* 2>/dev/null | wc -l)
  nP=$(ls $A/ql_evt*/pctree-evt*.tar.gz 2>/dev/null | wc -l)
  nB=$(ls -d $B/pr_evt* 2>/dev/null | wc -l)
  bad=$(grep -L 'rc=0' $B/pr_evt*/rc.txt 2>/dev/null | wc -l)
  szA=$(du -sm $A 2>/dev/null | cut -f1); szB=$(du -sm $B 2>/dev/null | cut -f1)
  imgw=$(cat $A/g*/.img.time.meta 2>/dev/null | sed -n 's/^wall_s=//p' | sort -n | awk '{a[NR]=$1} END{if(NR)print a[int(NR/2)+1]; else print "-"}')
  qlw=$(cat $A/g*/.ql.time.meta 2>/dev/null | sed -n 's/^wall_s=//p' | sort -n | awk '{a[NR]=$1} END{if(NR)print a[int(NR/2)+1]; else print "-"}')
  prc=$(grep -ho 'Timer: Total [0-9.]* wall-sec, [0-9.]*' $B/pr_evt*/wct_pr_evt*.log 2>/dev/null | awk '{print $5}' | sort -n | awk '{a[NR]=$1} END{if(NR)print a[int(NR/2)+1]; else print "-"}')
  printf '%-9s %6s %6s %6s %8s %8.2f %9.2f %9s %8s %8s\n' "$s" "$nA" "$nB" "$bad" "$nP" "$(echo "scale=2;$szA/1024"|bc)" "$(echo "scale=2;${szB:-0}/1024"|bc)" "$imgw" "$qlw" "$prc"
done
echo
for s in nuecc48 ncpi0 mcp1k mcp2k; do
  f=work-$s-d102mpr/nusel-events.tsv
  [ -f "$f" ] && echo "$s nusel-events rows=$(wc -l < $f)  nusel-table rows=$(wc -l < work-$s-d102mpr/nusel-table.tsv)"
done
