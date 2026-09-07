#!/usr/bin/env bash
# doc 30 sec 1: reported peak_rss_gb vs the job's own MEM-ladder max, over every PR log.
root=$1
for d in "$root"/*/; do
  r=$(ls "$d"pr_resource_*.txt 2>/dev/null | head -1); [ -n "$r" ] || continue
  l=$(ls "$d"wct_pr_*.log 2>/dev/null | head -1); [ -n "$l" ] || continue
  rep=$(sed -nE 's/.*peak_rss_gb=([0-9.]+).*/\1/p' "$r" | head -1); [ -n "$rep" ] || continue
  lad=$(grep -o 'res=[0-9.e+]*K increment' "$l" | sed -E 's/res=([0-9.e+]*)K increment/\1/' | sort -g | tail -1)
  [ -n "$lad" ] || continue
  awk -v r="$rep" -v m="$lad" 'BEGIN{printf "%.4f %.4f\n", r, m/1048576}'
done
