#!/bin/sh
set -e

echo "Generating fonts"
gftools builder ./sources/config.yaml
#echo "Compressing woffs"
#for FILE in ./fonts/variable/*.ttf; do python3 -m fontTools ttLib.woff2 compress $FILE; done
