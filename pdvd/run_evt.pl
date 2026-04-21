#!/usr/bin/perl
# Per-event dispatcher for imaging, clustering, and Bee upload.
# Usage: perl run_evt.pl <run> <evt> [subrun] [img|clus|chain|bee]
# Default stage: chain (= img -> clus -> bee)

use strict;
use warnings;
use File::Basename qw(dirname);
use Cwd qw(abs_path);

my $pdvd_dir = abs_path(dirname($0));
chdir($pdvd_dir) or die "Cannot chdir to $pdvd_dir: $!\n";

my ($run, $evt, $subrun_or_stage, $stage_arg) = @ARGV;
unless (defined $run && defined $evt) {
    die "Usage: perl $0 <run> <evt> [subrun] [img|clus|chain|bee]\n";
}

# Third arg is optional subrun (integer) or stage keyword.
my ($subrun, $stage);
if (defined $subrun_or_stage && $subrun_or_stage =~ /^\d+$/) {
    $subrun = $subrun_or_stage;
    $stage  = $stage_arg // 'chain';
} else {
    $subrun = 0;
    $stage  = $subrun_or_stage // 'chain';
}
unless ($stage =~ /^(img|clus|chain|bee)$/) {
    die "Unknown stage '$stage'. Valid: img, clus, chain, bee\n";
}

sub run_stage {
    my ($script, @args) = @_;
    my $cmd = "bash $script " . join(' ', @args);
    print "==> $cmd\n";
    my $ret = system($cmd);
    die "$script failed (exit " . ($ret >> 8) . ")\n" if $ret != 0;
}

run_stage('./run_img_evt.sh',     $run, $evt)          if $stage eq 'img'   || $stage eq 'chain';
run_stage('./run_clus_evt.sh',    $run, $evt)          if $stage eq 'clus'  || $stage eq 'chain';
run_stage('./run_bee_img_evt.sh', $run, $evt, $subrun) if $stage eq 'bee'   || $stage eq 'chain';
