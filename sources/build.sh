#!/bin/sh
set -e


echo "Generating Static fonts"
mkdir -p ../fonts
fontmake -g Podkova.glyphs -i -o ttf --output-dir ../fonts/

echo "Generating VFs"
fontmake -g Podkova.glyphs -o variable --output-path ../fonts/Podkova-VF.ttf

rm -rf master_ufo/ instance_ufo/


echo "Post processing"
ttfs=$(ls ../fonts/*.ttf)
for ttf in $ttfs
do
	gftools fix-dsig -f $ttf;
	./ttfautohint-vf $ttf "$ttf.fix";
	mv "$ttf.fix" $ttf;
done

echo "Post processing VFs"
vfs=$(ls ../fonts/*-VF.ttf)
for vf in $vfs
do
	gftools fix-dsig -f $vf;
	./ttfautohint-vf --stem-width-mode nnn $vf "$vf.fix";
	mv "$vf.fix" $vf;
done


echo "Fixing VF Meta"
gftools fix-vf-meta $vfs;
for vf in $vfs
do
	mv "$vf.fix" $vf;
	ttx -f -x "MVAR" $vf; # Drop MVAR. Table has issue in DW
	rtrip=$(basename -s .ttf $vf)
	new_file=../fonts/$rtrip.ttx;
	rm $vf;
	ttx $new_file
	rm $new_file
done

