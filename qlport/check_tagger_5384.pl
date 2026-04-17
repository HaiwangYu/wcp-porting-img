#!/usr/bin/perl
use strict;
use warnings;
use Cwd 'abs_path';

# Run wire-cell-uboone-tagger-compare for every event that has both a toolkit
# output (track_com_5384_<ev>.root) and a prototype output
# (prototype/nue_5384_<subrun>_<ev>.root) in this directory.
#
# Logs are written to tagger_<ev>.log (verbose mode).
# Events run in parallel; every 8th job is waited on to cap concurrency.
#
# Usage:
#   perl check_tagger_5384.pl            # run all matched events
#   perl check_tagger_5384.pl <eventNo>  # run a single event

my $target_event = $ARGV[0] if @ARGV;

# ---- Locate the comparison binary ----
# 1. Check PATH (binary installed via wcb install or similar).
# 2. Search relative to this script's real on-disk location.
my $COMPARE = "wire-cell-uboone-tagger-compare";
my $compare_bin;

chomp(my $in_path = `which $COMPARE 2>/dev/null`);
if ($in_path && -x $in_path) {
    $compare_bin = $in_path;
} else {
    # Resolve the real directory of this script (following any symlinks).
    my $real_script = abs_path($0);
    (my $real_dir = $real_script) =~ s|/[^/]+$||;
    for my $cand (
        "$real_dir/../build/root/$COMPARE",          # qlport next to build/
        "$real_dir/../../toolkit/build/root/$COMPARE", # qlport in sibling project
    ) {
        if (-x $cand) { $compare_bin = abs_path($cand); last; }
    }
}
die "Cannot find $COMPARE in PATH or standard build locations.\n"
    unless defined $compare_bin && -x $compare_bin;
print "Using: $compare_bin\n";

# ---- Locate input files ----
# Use the logical working directory so glob() finds files correctly when
# qlport itself is a symlink.
my $qlport = $ENV{PWD} // do { use Cwd; Cwd::getcwd(); };

# Build a map: eventNo -> prototype file
my %proto_file;
for my $f (glob("$qlport/prototype/nue_5384_*.root")) {
    if ($f =~ /nue_5384_\d+_(\d+)\.root$/) {
        $proto_file{$1} = $f;
    }
}

# Walk toolkit files and pair with prototype counterparts.
my @jobs;
for my $toolkit (sort glob("$qlport/track_com_5384_*.root")) {
    my ($ev) = $toolkit =~ /track_com_5384_(\d+)\.root$/ or next;
    next if defined $target_event && $ev != $target_event;

    unless (exists $proto_file{$ev}) {
        print "[SKIP] no prototype file for event $ev\n";
        next;
    }
    push @jobs, { ev => $ev, proto => $proto_file{$ev}, toolkit => $toolkit };
}

if (@jobs == 0) {
    print "No matching events found.\n";
    exit 0;
}

print "Running " . scalar(@jobs) . " comparison(s)...\n";

my $n = 0;
for my $job (@jobs) {
    my $ev      = $job->{ev};
    my $proto   = $job->{proto};
    my $toolkit = $job->{toolkit};
    my $log     = "$qlport/tagger_$ev.log";

    my $cmd = "$compare_bin -p $proto -t $toolkit -v > $log 2>&1";
    print "$cmd\n";

    # Every 8th job: wait for the previous batch to limit concurrency.
    if ($n > 0 && $n % 8 == 0) {
        wait;
    }

    system("$cmd &");
    $n++;
}

# Wait for all remaining background jobs.
while (wait() != -1) {}

print "Done. Logs written to $qlport/tagger_<ev>.log\n";
