rm -f upload.zip
zip -r upload data
./upload-to-bee.sh upload.zip
