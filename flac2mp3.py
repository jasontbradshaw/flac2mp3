#!/usr/bin/env python

import os
import re
import tempfile
import subprocess as sp
import multiprocessing as mp

def transcode(infile):
    """
    Transcodes a single flac file into a single mp3 file.  Preserves the file
    name but changes the extension.
    """

    # get the decoded flac data from the given file using 'flac', saving it to a
    # string
    args = ["flac", "-c", "-d", infile]
    p = sp.Popen(args, stdout=sp.PIPE)
    flac_data = p.communicate()[0]

    # write the decoded flac data to a temporary file, saving the file name for
    # use later with 'lame'
    flacdata_filename = None
    with tempfile.NamedTemporaryFile(prefix="flacdata_", delete=False) as f:
        flacdata_filename = f.name
        f.write(flac_data)

    print flacdata_filename

def copy_tag(infile, outfile):
    """
    Transfers tags from the first file to the second.
    """

    # get tag info text using 'metaflac'
    args = ["metaflac", "--list", "--block-type=VORBIS_COMMENT", infile]
    p = sp.Popen(args, stdout=sp.PIPE)
    metaflac_text = p.communicate()[0]

    # get the comment data from 'metaflac's returned text
    print metaflac_text

    # matches all lines like 'comment[0]: TITLE=Misery' and extracts them to
    # tuples like ('TITLE', 'Misery'), then stores them in a dict.
    pattern = "comment\[\d+\]:\s+([^=]+)=([^\n]+)\n"
    tag_dict = {}
    for t in re.findall(pattern, metaflac_text):
        tag_dict[t[0]] = t[1]
    
    print tag_dict

if __name__ == "__main__":
    copy_tag("song.flac", None)
    transcode("song.flac")
