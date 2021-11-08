#!/usr/bin/env bash

# Switchboard-1 training data preparation customized for Edinburgh
# Author:  Arnab Ghoshal (Jan 2013)

# To be run from one directory above this script.

## The input is some directory containing the switchboard-1 release 2
## corpus (LDC97S62).  Note: we don't make many assumptions about how
## you unpacked this.  We are just doing a "find" command to locate
## the .sph files.

## The second input is optional, which should point to a directory containing
## Switchboard transcriptions/documentations (specifically, the conv.tab file).
## If specified, the script will try to use the actual speaker PINs provided 
## with the corpus instead of the conversation side ID (Kaldi default). We 
## will be using "find" to locate this file so we don't make any assumptions
## on the directory structure. (Peng Qi, Aug 2014)

#. ./path.sh

#check existing directories
if [ $# != 1 -a $# != 2 ]; then
  echo "Usage: swbd1_data_prep.sh /path/to/SWBD [/path/to/SWBD_DOC]"
  exit 1; 
fi 

SWBD_DIR=$1

dir=data/local/train
mkdir -p $dir


# Audio data directory check
if [ ! -d $SWBD_DIR ]; then
  echo "Error: run.sh requires a directory argument"
  exit 1; 
fi  



# (1a) Transcriptions preparation
# make basic transcription file (add segments info)
# **NOTE: In the default Kaldi recipe, everything is made uppercase, while we 
# make everything lowercase here. This is because we will be using SRILM which
# can optionally make everything lowercase (but not uppercase) when mapping 
# LM vocabs.
awk '{ 
       name=substr($1,1,6); gsub("^sw","sw0",name); side=substr($1,7,1); 
       stime=$2; etime=$3;
       printf("%s-%s_%06.0f-%06.0f", 
              name, side, int(100*stime+0.5), int(100*etime+0.5));
       for(i=4;i<=NF;i++) printf(" %s", $i); printf "\n"
}' download/swb_ms98_transcriptions/*/*/*-trans.text  > $dir/transcripts1.txt

# test if trans. file is sorted
export LC_ALL=C;
sort -c $dir/transcripts1.txt || exit 1; # check it's sorted.

# Remove SILENCE, <B_ASIDE> and <E_ASIDE>.

# Note: we have [NOISE], [VOCALIZED-NOISE], [LAUGHTER], [SILENCE].
# removing [SILENCE], and the <B_ASIDE> and <E_ASIDE> markers that mark
# speech to somone; we will give phones to the other three (NSN, SPN, LAU). 
# There will also be a silence phone, SIL.
# **NOTE: modified the pattern matches to make them case insensitive
cat $dir/transcripts1.txt \
  | perl -ane 's:\s\[SILENCE\](\s|$):$1:gi; 
               s/<B_ASIDE>//gi; 
               s/<E_ASIDE>//gi; 
               print;' \
  | awk '{if(NF > 1) { print; } } ' > $dir/transcripts2.txt


# **NOTE: swbd1_map_words.pl has been modified to make the pattern matches 
# case insensitive
local/swbd1_map_words.pl -f 2- $dir/transcripts2.txt  > $dir/text

