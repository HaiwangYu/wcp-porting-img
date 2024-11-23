#!/usr/bin/perl

open(infile,"filelist");
my $i = 0;
system("rm -rf ./data/*");
while(<infile>){
    system("unzip $i\.zip; rm -f $i\.zip");


    $i++;
}
