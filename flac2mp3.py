#!/usr/bin/env python

import os
import re
import tempfile
import subprocess as sp
import multiprocessing as mp

def transcode(infile):
    """
    Transcodes a single flac file into a single mp3 file.  Preserves the file
    name but changes the extension.  Copies flac tag info from the transcoded
    file to the new file.
    """

    # get the decoded flac data from the given file using 'flac', saving it to a
    # string.
    flac_args = ["flac", "--silent", "-c", "-d", infile]
    p_flac = sp.Popen(flac_args, stdout=sp.PIPE)
    flac_data = p_flac.communicate()[0]

    # write the decoded flac data to a temporary file, saving the file name for
    # use later with 'lame'
    flacdata_filename = None
    with tempfile.NamedTemporaryFile(prefix="flacdata_", delete=False) as f:
        flacdata_filename = f.name
        f.write(flac_data)

    # get a new file name for the mp3 based on the input file's name
    mp3_filename = get_changed_file_ext(infile, ".mp3")

    # get the tags from the input file and ensure required fields are present
    flac_tags = get_tags(infile)

    if "TITLE" not in flac_tags:
        flac_tags["TITLE"] = "<na>"
    if "ARTIST" not in flac_tags:
        flac_tags["ARTIST"] = "<na>"
    if "ALBUM" not in flac_tags:
        flac_tags["ALBUM"] = "<na>"
    if "YEAR" not in flac_tags:
        flac_tags["YEAR"] = "1"
    if "COMMENT" not in flac_tags:
        flac_tags["COMMENT"] = ""
    if "TRACKNUMBER" not in flac_tags:
        flac_tags["TRACKNUMBER"] = "0"
    if "TRACKTOTAL" not in flac_tags:
        flac_tags["TRACKTOTAL"] = "0"

    # arguments for lame, including bitrate and tag creation
    bitrate = 320
    lame_args = ["lame", "-h", "-m", "s", "--cbr", "-b", str(bitrate),
            "--add-id3v2",
            "--tt", flac_tags["TITLE"],
            "--ta", flac_tags["ARTIST"],
            "--tl", flac_tags["ALBUM"],
            "--ty", flac_tags["YEAR"],
            "--tc", flac_tags["COMMENT"],
            "--tn", flac_tags["TRACKNUMBER"] + "\\" + flac_tags["TRACKTOTAL"],
            "--tg", flac_tags["GENRE"],
            flacdata_filename, mp3_filename]

    # encode the file using 'lame'

def get_changed_file_ext(fname, ext):
    """
    Transforms the given filename's extension to the given extension.  'ext' is
    the new extension, 'fname' is the file name transformation is to be done on.
    """

    # determine the new file name (old file name minus the extension if it had
    # one, otherwise just the old file name with new extension added).
    new_fname = fname

    # if we have a file extension, strip the final one and get the base name
    if len(fname.split(".")) >= 2:
        new_fname = fname.rsplit(".", 1)[0]

    # add the new extension
    new_fname += ext

    return new_fname

def get_tags(infile):
    """
    Gets the flac tags from the given file and returns them as a dict.
    """

    # get tag info text using 'metaflac'
    metaflac_args = ["metaflac", "--list", "--block-type=VORBIS_COMMENT", infile]
    p_metaflac = sp.Popen(metaflac_args, stdout=sp.PIPE)
    metaflac_text = p_metaflac.communicate()[0]

    # matches all lines like 'comment[0]: TITLE=Misery' and extracts them to
    # tuples like ('TITLE', 'Misery'), then stores them in a dict.
    pattern = "\s+comment\[\d+\]:\s+([^=]+)=([^\n]+)\n"

    # get the comment data from the obtained text
    tag_dict = {}
    for t in re.findall(pattern, metaflac_text):
        tag_dict[t[0]] = t[1]

    return tag_dict

if __name__ == "__main__":
    get_tags("song.flac")
    transcode("song.flac")
