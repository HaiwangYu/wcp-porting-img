#!/usr/bin/env python
import sys, os, glob

def main(fp1):
    if (os.path.exists('data/0')):
        print('found old data, removing ...')
        os.system('rm -rf data')
    if (os.path.exists('upload.zip')):
        os.system('rm -f upload.zip')
    os.system('mkdir -p data/0')
    density = 1
    cmd = 'wirecell-img bee-blobs -g protodunevd -s uniform -d %f --speed "-1.56*mm/us" --t0 "0*us" --x0 "-341.5*cm" -o data/0/0-apa0.json %s' % (density, fp1, )
    print(cmd)
    os.system(cmd)

    # cmd = 'wirecell-img bee-blobs -g protodunevd -s uniform -d %f --speed "-1.56*mm/us" --t0 "0*us" --x0 "-341.5*cm" -o data/0/0-apa1.json %s' % (density, fp2, )
    # print(cmd)
    # os.system(cmd)

    # cmd = 'wirecell-img bee-blobs -g protodunevd -s uniform -d %f --speed "-1.56*mm/us" --t0 "0*us" --x0 "-341.5*cm" -o data/0/0-apa2.json %s' % (density, fp3, )
    # print(cmd)
    # os.system(cmd)

    # cmd = 'wirecell-img bee-blobs -g protodunevd -s uniform -d %f --speed "-1.56*mm/us" --t0 "0*us" --x0 "-341.5*cm" -o data/0/0-apa3.json %s' % (density, fp4, )
    # print(cmd)
    # os.system(cmd)

    # cmd = 'wirecell-img bee-blobs -g protodunevd -s uniform -d %f --speed "1.56*mm/us" --t0 "0*us" --x0 "341.5*cm" -o data/0/0-apa4.json %s' % (density, fp5, )
    # print(cmd)
    # os.system(cmd)

    # cmd = 'wirecell-img bee-blobs -g protodunevd -s uniform -d %f --speed "1.56*mm/us" --t0 "0*us" --x0 "341.5*cm" -o data/0/0-apa5.json %s' % (density, fp6, )
    # print(cmd)
    # os.system(cmd)

    # cmd = 'wirecell-img bee-blobs -g protodunevd -s uniform -d %f --speed "1.56*mm/us" --t0 "0*us" --x0 "341.5*cm" -o data/0/0-apa6.json %s' % (density, fp7, )
    # print(cmd)
    # os.system(cmd)

    # cmd = 'wirecell-img bee-blobs -g protodunevd -s uniform -d %f --speed "1.56*mm/us" --t0 "0*us" --x0 "341.5*cm" -o data/0/0-apa7.json %s' % (density, fp8, )
    # print(cmd)
    # os.system(cmd)

    os.system('zip -r upload data')

if __name__ == "__main__":
    if (len(sys.argv)!=2):
        print("usage: python wct-img-2-bee.py 'fp1' 'fp2' 'fp3' 'fp4' 'fp5' 'fp6' 'fp7' 'fp8'")
    else:
        main(sys.argv[1])


