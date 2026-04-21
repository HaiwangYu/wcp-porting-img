#!/usr/bin/env python
import sys, os, glob

def main(run, subrun, event, fp1,fp2,fp3,fp4,fp5,fp6,fp7,fp8):
    if (os.path.exists('data/0')):
        print('found old data, removing ...')
        os.system('rm -rf data')
    if (os.path.exists('upload.zip')):
        os.system('rm -f upload.zip')
    os.system('mkdir -p data/0')
    density = 1
    rse = '--rse %s %s %s' % (run, subrun, event)
    cmd = 'wirecell-img bee-blobs -g protodunevd -s uniform -d %f %s --speed "-1.56*mm/us" --t0 "0*us" --x0 "-341.5*cm" -o data/0/0-apa0.json %s' % (density, rse, fp1, )
    print(cmd)
    os.system(cmd)

    cmd = 'wirecell-img bee-blobs -g protodunevd -s uniform -d %f %s --speed "-1.56*mm/us" --t0 "0*us" --x0 "-341.5*cm" -o data/0/0-apa1.json %s' % (density, rse, fp2, )
    print(cmd)
    os.system(cmd)

    cmd = 'wirecell-img bee-blobs -g protodunevd -s uniform -d %f %s --speed "-1.56*mm/us" --t0 "0*us" --x0 "-341.5*cm" -o data/0/0-apa2.json %s' % (density, rse, fp3, )
    print(cmd)
    os.system(cmd)

    cmd = 'wirecell-img bee-blobs -g protodunevd -s uniform -d %f %s --speed "-1.56*mm/us" --t0 "0*us" --x0 "-341.5*cm" -o data/0/0-apa3.json %s' % (density, rse, fp4, )
    print(cmd)
    os.system(cmd)

    cmd = 'wirecell-img bee-blobs -g protodunevd -s uniform -d %f %s --speed "1.56*mm/us" --t0 "0*us" --x0 "341.5*cm" -o data/0/0-apa4.json %s' % (density, rse, fp5, )
    print(cmd)
    os.system(cmd)

    cmd = 'wirecell-img bee-blobs -g protodunevd -s uniform -d %f %s --speed "1.56*mm/us" --t0 "0*us" --x0 "341.5*cm" -o data/0/0-apa5.json %s' % (density, rse, fp6, )
    print(cmd)
    os.system(cmd)

    cmd = 'wirecell-img bee-blobs -g protodunevd -s uniform -d %f %s --speed "1.56*mm/us" --t0 "0*us" --x0 "341.5*cm" -o data/0/0-apa6.json %s' % (density, rse, fp7, )
    print(cmd)
    os.system(cmd)

    cmd = 'wirecell-img bee-blobs -g protodunevd -s uniform -d %f %s --speed "1.56*mm/us" --t0 "0*us" --x0 "341.5*cm" -o data/0/0-apa7.json %s' % (density, rse, fp8, )
    print(cmd)
    os.system(cmd)

    os.system('zip -r upload data')

if __name__ == "__main__":
    if (len(sys.argv)!=12):
        print("usage: python wct-img-2-bee.py <run> <subrun> <event> 'fp1' 'fp2' 'fp3' 'fp4' 'fp5' 'fp6' 'fp7' 'fp8'")
    else:
        main(sys.argv[1],sys.argv[2],sys.argv[3],sys.argv[4],sys.argv[5],sys.argv[6],sys.argv[7],sys.argv[8],sys.argv[9],sys.argv[10],sys.argv[11])
