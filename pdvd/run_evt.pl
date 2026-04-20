#!/usr/bin/perl
# Per-event dispatcher for imaging, clustering, and Bee upload.
# Usage: perl run_evt.pl <run> <evt> [img|clus|chain|bee]
# Default stage: chain (= img -> clus -> bee)

use strict;
use warnings;
use File::Basename qw(dirname);
use Cwd qw(abs_path);

my $pdvd_dir = abs_path(dirname($0));
chdir($pdvd_dir) or die "Cannot chdir to $pdvd_dir: $!\n";

my ($run, $evt, $stage) = @ARGV;
unless (defined $run && defined $evt) {
    die "Usage: perl $0 <run> <evt> [img|clus|chain|bee]\n";
}
$stage //= 'chain';
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

run_stage('./run_img_evt.sh',  $run, $evt) if $stage eq 'img'   || $stage eq 'chain';
run_stage('./run_clus_evt.sh', $run, $evt) if $stage eq 'clus'  || $stage eq 'chain';
run_stage('./run_bee_evt.sh',  $run, $evt) if $stage eq 'bee'   || $stage eq 'chain';
