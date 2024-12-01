#!/usr/bin/env python
import sys, os, glob

def main(filepattern):
    if (os.path.exists('data/0')):
        print('found old data, removing ...')
        os.system('rm -rf data')
    if (os.path.exists('upload.zip')):
        os.system('rm -f upload.zip')
    os.system('mkdir -p data/0')
    # cmd = 'wirecell-img bee-blobs -g uboone -s center -d 900 -o data/0/0-test.json %s' % (
    # cmd = 'wirecell-img bee-blobs -g uboone -s uniform -d 1 -o data/0/0-test.json %s' % (
    # cmd = 'wirecell-img bee-blobs -g uboone -s center --x0=0*cm -o data/0/0-test.json %s' % (
    # cmd = 'wirecell-img bee-blobs -g protodunevd-test -s center --x0=0*cm --t0=1600*us --speed=-1.101*mm/us -o data/0/0-test.json %s' % (
    cmd = 'wirecell-img bee-blobs -g sbnd -s center --x0=0*cm --t0=-200*us --speed=-1.6*mm/us -o data/0/0-apa0.json clusters-apa-apa0.tar.gz'
    print(cmd)
    os.system(cmd)
    cmd = 'wirecell-img bee-blobs -g sbnd -s center --x0=0*cm --t0=-200*us --speed=1.6*mm/us -o data/0/0-apa1.json clusters-apa-apa1.tar.gz'
    print(cmd)
    os.system(cmd)
    os.system('zip -r upload data')

if __name__ == "__main__":
    if (len(sys.argv)!=2):
        print("usage: python wct-img-2-bee.py 'filepattern'")
    else:
        main(sys.argv[1])
