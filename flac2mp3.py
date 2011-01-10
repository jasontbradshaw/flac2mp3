#!/usr/bin/env python

import os
import re
import subprocess as sp
import multiprocessing as mp

def enc(f):
    """
    Encodes a single flac file as a single mp3 file.
    """

def copy_tag(infile, outfile):
    """
    Transfers tags from the first file to the second.
    """

    # get tag info text using metaflac
    p = sp.Popen(["metaflac", "--list", "--block-type=VORBIS_COMMENT", infile],
            stdout=sp.PIPE)
    text = p.communicate()[0]

    print text

if __name__ == "__main__":
    copy_tag("song.flac", None)
