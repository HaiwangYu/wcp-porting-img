#!/usr/bin/perl

# Get optional target event number
my $target_event = $ARGV[0] if @ARGV;

open(infile,"filelist") or die "Cannot open filelist: $!\n";
my $i = 0;
while(<infile>){
    my $filename = $_;
    chomp($filename);
    $filename =~ /result_(\d+)_(\d+)_(\d+)\.root/;
    my $runNo = $1;
    my $subRunNo = $2;
    my $eventNo = $3;

    # Skip if target event specified and doesn't match
    next if (defined $target_event && $eventNo != $target_event);

    #if ($i%40 == 39){
    #     system("wire-cell -A iname=\"$filename\" -A oname=\"active-clusters-anode_$runNo\_$eventNo\.npz\" -A kind=\"live\" uboone-val.jsonnet");
    #     system("wire-cell -A iname=\"$filename\" -A oname=\"masked-clusters-anode_$runNo\_$eventNo\.npz\" -A kind=\"dead\" uboone-val.jsonnet");
    # }else{
    #     system("wire-cell -A iname=\"$filename\" -A oname=\"active-clusters-anode_$runNo\_$eventNo\.npz\" -A kind=\"live\" uboone-val.jsonnet &");
    #     system("wire-cell -A iname=\"$filename\" -A oname=\"masked-clusters-anode_$runNo\_$eventNo\.npz\" -A kind=\"dead\" uboone-val.jsonnet &");
    #}

    if ($i%40 == 39){
        system("wire-cell -l stdout -L debug -A active_clusters=\"active-clusters-anode_$runNo\_$eventNo\.npz\" -A masked_clusters=\"masked-clusters-anode_$runNo\_$eventNo\.npz\" -A bee_zip=$i\.zip -A initial_index=\"$i\" -A initial_runNo=\"$runNo\" -A initial_subRunNo=\"$subRunNo\" -A initial_eventNo=\"$eventNo\" -c ../wct-uboone-clustering.jsonnet > wct_$runNo\_$eventNo\.log");
    }else{
        system("wire-cell -l stdout -L debug -A active_clusters=\"active-clusters-anode_$runNo\_$eventNo\.npz\" -A masked_clusters=\"masked-clusters-anode_$runNo\_$eventNo\.npz\" -A bee_zip=$i\.zip -A initial_index=\"$i\" -A initial_runNo=\"$runNo\" -A initial_subRunNo=\"$subRunNo\" -A initial_eventNo=\"$eventNo\" -c ../wct-uboone-clustering.jsonnet > wct_$runNo\_$eventNo\.log&");
    }


    $i++;
}

close(infile);