#!/bin/sh
set -e


echo "Generating Static fonts"
##mkdir -p ../fonts
#fontmake -g Lora.glyphs -i -o ttf --output-dir ../fonts/TTF/
fontmake -g Lora-Italic.glyphs -i -o ttf --output-dir ../fonts/TTF/
#fontmake -g Lora.glyphs -i -a -o otf --output-dir ../fonts/OTF/
#fontmake -g Lora-Italic.glyphs -i -a -o otf --output-dir ../fonts/OTF/

