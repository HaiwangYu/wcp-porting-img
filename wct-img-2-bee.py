#!/usr/bin/env python
import sys, os, glob

def main(filepattern):
    if (os.path.exists('data/0')):
        print('found old data, removing ...')
        os.system('rm -rf data')
    if (os.path.exists('upload.zip')):
        os.system('rm -f upload.zip')
    os.system('mkdir -p data/0')
    cmd = 'wirecell-img bee-blobs -g uboone -s center -o data/0/0-test.json %s' % (
        filepattern, )
    print(cmd)
    os.system(cmd)
    os.system('zip -r upload data')

if __name__ == "__main__":
    if (len(sys.argv)!=2):
        print("usage: python wct-img-2-bee.py 'filepattern'")
    else:
        main(sys.argv[1])
