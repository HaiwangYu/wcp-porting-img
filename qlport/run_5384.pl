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

    # -L clus.NeutrinoPattern:debug
    if ($i%40 == 39){
        system("rm -f wct_$runNo\_$eventNo\.log");
        system("wire-cell -l stderr -l wct_$runNo\_$eventNo\.log:debug -L clus:debug -A kind=both  -A beezip=mabc_$i\.zip -A initial_index=\"$i\" -A initial_runNo=\"$runNo\" -A initial_subRunNo=\"$subRunNo\" -A initial_eventNo=\"$eventNo\" -A infiles=$filename uboone-mabc.jsonnet > /dev/null 2>&1");
        print("wire-cell -l stderr -l wct_$runNo\_$eventNo\.log:debug  -L clus:debug -A kind=both  -A beezip=mabc_$i\.zip -A initial_index=\"$i\" -A initial_runNo=\"$runNo\" -A initial_subRunNo=\"$subRunNo\" -A initial_eventNo=\"$eventNo\" -A infiles=$filename uboone-mabc.jsonnet\n");
    }else{
        system("rm -f wct_$runNo\_$eventNo\.log");
        system("wire-cell -l stderr -l wct_$runNo\_$eventNo\.log:debug -L clus:debug -A kind=both  -A beezip=mabc_$i\.zip -A initial_index=\"$i\" -A initial_runNo=\"$runNo\" -A initial_subRunNo=\"$subRunNo\" -A initial_eventNo=\"$eventNo\" -A infiles=$filename uboone-mabc.jsonnet > /dev/null 2>&1 &");
        print("wire-cell -l stderr -l wct_$runNo\_$eventNo\.log:debug  -L clus:debug -A kind=both  -A beezip=mabc_$i\.zip -A initial_index=\"$i\" -A initial_runNo=\"$runNo\" -A initial_subRunNo=\"$subRunNo\" -A initial_eventNo=\"$eventNo\" -A infiles=$filename uboone-mabc.jsonnet\n");
    }


    $i++;
}

close(infile);