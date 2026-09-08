#!/bin/bash
# Linear member-content comparison of two WCT archives (tarfile+bz2 random
# access is O(n^2); extract-then-sha256 is O(n)).  M2: never cmp the tarball.
set -u
SCR=${TMPDIR:-/home/xqian/tmp}/d102m-cmp   # never scratch inside the repo
mkdir -p "$SCR"
N=$1; A=$2; B=$3
rm -rf "$SCR/x/$N"; mkdir -p "$SCR/x/$N/a" "$SCR/x/$N/b"
untar() { case "$1" in *.bz2) tar xjf "$1" -C "$2";; *) tar xzf "$1" -C "$2";; esac; }
untar "$A" "$SCR/x/$N/a" || exit 2
untar "$B" "$SCR/x/$N/b" || exit 2
( cd "$SCR/x/$N/a" && find . -type f | sort | xargs sha256sum ) > "$SCR/x/$N.a.sha"
( cd "$SCR/x/$N/b" && find . -type f | sort | xargs sha256sum ) > "$SCR/x/$N.b.sha"
na=$(wc -l < "$SCR/x/$N.a.sha"); nb=$(wc -l < "$SCR/x/$N.b.sha")
nd=$(diff "$SCR/x/$N.a.sha" "$SCR/x/$N.b.sha" | grep -c '^[<>]')
echo "$N : members mine=$na recorded=$nb differing=$nd"
rm -rf "$SCR/x/$N"
[ "$nd" -eq 0 ] && [ "$na" -eq "$nb" ] && [ "$na" -gt 0 ]
