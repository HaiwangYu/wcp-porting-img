#!/usr/bin/perl

# Get optional target event number
my $target_event = $ARGV[0] if @ARGV;

open(infile,"filelist") or die "Cannot open filelist: $!\n";
my $i = 0;
while(<infile>){
    my $filename = $_;
    chomp($filename);
    $filename =~ /nuselEval_(\d+)_(\d+)_(\d+)\.root/;
    my $runNo = $1;
    my $subRunNo = $2;
    my $eventNo = $3;

    #print("$filename $eventNo $target_event\n");

    # Skip if target event specified and doesn't match
    next if (defined $target_event && $eventNo != $target_event);

    if ($i%40 == 39){
        system("wire-cell -l stderr -A kind=both  -A beezip=mabc_$i\.zip -A initial_index=\"$i\" -A initial_runNo=\"$runNo\" -A initial_subRunNo=\"$subRunNo\" -A initial_eventNo=\"$eventNo\" -A infiles=$filename uboone-mabc.jsonnet > wct_$runNo\_$eventNo\.log");
    }else{
        system("wire-cell -l stderr -A kind=both  -A beezip=mabc_$i\.zip -A initial_index=\"$i\" -A initial_runNo=\"$runNo\" -A initial_subRunNo=\"$subRunNo\" -A initial_eventNo=\"$eventNo\" -A infiles=$filename uboone-mabc.jsonnet > wct_$runNo\_$eventNo\.log&");
    }


    $i++;
}

close(infile);