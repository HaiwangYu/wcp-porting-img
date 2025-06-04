#!/usr/bin/perl

# First identify all zip files in the current directory
my @zip_files = glob("mabc*.zip");

# Sort the zip files by numeric value (assuming the filenames are numbers)
@zip_files = sort { ($a =~ /(\d+)\.zip/)[0] <=> ($b =~ /(\d+)\.zip/)[0] } @zip_files;

# Create data directory if it doesn't exist
system("mkdir -p ./data");
system("rm -rf ./data/*");

# Process each zip file
foreach my $zip_file (@zip_files) {
    print "Extracting $zip_file\n";
    system("unzip $zip_file; rm -f $zip_file");
}
