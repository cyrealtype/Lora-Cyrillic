#!/bin/sh
set -e

# Go the sources directory to run commands
SOURCE="${BASH_SOURCE[0]}"
DIR=$( cd -P "$( dirname "$SOURCE" )" >/dev/null 2>&1 && pwd )
cd $DIR
echo $(pwd)

echo "Generating Static fonts"
mkdir -p ../fonts/ttf
mkdir -p ../fonts/otf
fontmake -m Lora.designspace -i -o ttf --output-dir ../fonts/ttf/
fontmake -m Lora-Italic.designspace -i -o ttf --output-dir ../fonts/ttf/
fontmake -m Lora.designspace -i -a -o otf --output-dir ../fonts/otf/
fontmake -m Lora-Italic.designspace -i -a -o otf --output-dir ../fonts/otf/


echo "Generating VFs"
mkdir -p ../fonts/vf
fontmake -m Lora.designspace -o variable --output-path ../fonts/vf/Lora[wght].ttf
fontmake -m Lora-Italic.designspace -o variable --output-path ../fonts/vf/Lora-Italic[wght].ttf

rm -rf master_ufo/ instance_ufo/ instance_ufos/

echo "Post processing"
ttfs=$(ls ../fonts/ttf/*.ttf)
for ttf in $ttfs
do
	gftools fix-dsig -f $ttf;
	python3 -m ttfautohint $ttf "$ttf.fix";
	mv "$ttf.fix" $ttf;
done


echo "Post processing VFs"
vfs=$(ls ../fonts/vf/*.ttf)
for vf in $vfs
do
	gftools fix-dsig -f $vf;
	mv "$vf.fix" $vf;
done

echo "Fixing VF Meta"
gftools fix-vf-meta $vfs;
echo "Dropping MVAR"
for vf in $vfs
do
	mv "$vf.fix" $vf;
	ttx -f -x "MVAR" $vf; # Drop MVAR. Table has issue in DW
	rtrip=$(basename -s .ttf $vf)
	new_file=../fonts/vf/$rtrip.ttx;
	rm $vf;
	ttx $new_file
	rm $new_file
done

echo "Fixing Non-Hinting"
for vf in $vfs
do
	gftools fix-nonhinting $vf $vf.fix;
	mv "$vf.fix" $vf;
done
for ttf in $ttfs
do
	gftools fix-hinting $ttf;
	mv "$ttf.fix" $ttf;
done

