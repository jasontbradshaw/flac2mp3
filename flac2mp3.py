#!/usr/bin/env python

import os
import re
import subprocess as sp
import sys
import multiprocessing as mp

def get_changed_file_ext(fname, ext):
    """
    Transforms the given filename's extension to the given extension.  'ext' is
    the new extension, 'fname' is the file name transformation is to be done on.
    """

    # determine the new file name (old file name minus the extension if it had
    # one, otherwise just the old file name with new extension added).
    new_fname = fname

    # if we have a file extension, strip the final one and get the base name
    if len(fname.rsplit(".", 1)) == 2:
        new_fname = fname.rsplit(".", 1)[0]

    # add the new extension
    new_fname += ext

    return new_fname

def walk_dir(d, follow_links=False):
    """
    Returns all the file names in a given directory, including those in
    subdirectories.  If 'follow_links' is True, symbolic links will be followed.
    This option can lead to infinite looping since the function doesn't keep
    track of which directories have been visited.
    """

    # walk the directory and collect the full path of every file therein
    contents = []
    for root, dirs, files in os.walk(d, followlinks=follow_links):
        for name in files:
            contents.append(os.path.join(root, name))

    # normalize all file names
    contents = map(os.path.abspath, contents)

    return contents

def get_filetype(fname):
    """
    Gets the file type of the given file as a MIME string and returns it.
    """

    # brief output, MIME version
    file_args = ["file", "-b"]
    if sys.platform == "darwin":
        file_args.append("-I")
    else:
        file_args.append("-i")
    file_args.append(fname)

    p_file = sp.Popen(file_args, stdout=sp.PIPE)

    return p_file.communicate()[0]

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

    # get a new file name for the mp3 based on the input file's name
    mp3_filename = get_changed_file_ext(infile, ".mp3")

    # get the tags from the input file
    flac_tags = get_tags(infile)

    # arguments for 'lame', including bitrate and tag values
    bitrate = 320
    lame_args = ["lame", "-h", "-m", "s", "--cbr", "-b", str(bitrate),
            "--add-id3v2", "--silent",
            "--tt", flac_tags["TITLE"],
            "--ta", flac_tags["ARTIST"],
            "--tl", flac_tags["ALBUM"],
            "--ty", flac_tags["DATE"],
            "--tc", flac_tags["COMMENT"],
            "--tn", flac_tags["TRACKNUMBER"] + "/" + flac_tags["TRACKTOTAL"],
            "--tg", flac_tags["GENRE"],
            "-", mp3_filename]

    # encode the file using 'lame' and wait for it to finish
    p_lame = sp.Popen(lame_args, stdin=sp.PIPE)

    # pass 'lame' the decoded sound data via stdin
    p_lame.communicate(flac_data)

def get_tags(infile):
    """
    Gets the flac tags from the given file and returns them as a dict.  Ensures
    a minimun set of id3v2 tags is available, giving them default values if
    these tags aren't found in the orininal file.
    """

    # get tag info text using 'metaflac'
    metaflac_args = ["metaflac", "--list", "--block-type=VORBIS_COMMENT", infile]
    p_metaflac = sp.Popen(metaflac_args, stdout=sp.PIPE)
    metaflac_text = p_metaflac.communicate()[0]

    # ensure all possible id3v2 tags start off with a default value
    tag_dict = {
        "TITLE": "NONE",
        "ARTIST": "NONE",
        "ALBUM": "NONE",
        "DATE": "1",
        "COMMENT": "",
        "TRACKNUMBER": "00",
        "TRACKTOTAL": "00",
        "GENRE": "NONE"
    }

    # matches all lines like 'comment[0]: TITLE=Misery' and extracts them to
    # tuples like ('TITLE', 'Misery'), then stores them in a dict.
    pattern = "\s+comment\[\d+\]:\s+([^=]+)=([^\n]+)\n"

    # get the comment data from the obtained text
    for t in re.findall(pattern, metaflac_text):
        tag_dict[t[0]] = t[1]

    return tag_dict

if __name__ == "__main__":
    import sys
    import time

    print "Enumerating files..."

    # add all the files/directories in the args recursively
    flacfiles = []
    for f in sys.argv[1:]:
        if os.path.isdir(f):
            flacfiles.extend(walk_dir(f))
        else:
            flacfiles.append(f)

    # remove all non-flac files from the list
    is_flac_file = lambda x: get_filetype(x).count("audio/x-flac") > 0
    flacfiles = filter(is_flac_file, flacfiles)

    # remove duplicates and sort resulting list
    flacfiles = list(set(flacfiles))
    flacfiles.sort()

    # get the number of threads we should use while transcoding (usually twice
    # the number of processors, or 2 if that number can't be determined).
    thread_count = 2
    try:
        thread_count = 2 * mp.cpu_count()
    except NotImplementedError:
        pass

    def transcode_with_printout(f):
        """
        Transcode the given file and print out progress statistics.
        """

        # a more compact file name relative to the current directory
        short_fname = os.path.relpath(f)
        print "Transcoding '%s'..." % short_fname

        # time the transcode
        start_time = time.time()
        transcode(f)
        total_time = time.time() - start_time

        print "Transcoded '%s' in %.2f seconds" % (short_fname, total_time)

    number_word = "files" if len(flacfiles) != 1 else "file"
    print "Beginning transcode of %d %s..." % (len(flacfiles), number_word)
    overall_start_time = time.time()

    # transcode all the found files
    # TODO: handle Ctrl+C while mapping, currently becomes a broken zombie
    pool = mp.Pool(processes=thread_count)
    result = pool.map_async(transcode_with_printout, flacfiles)
    result.get()

    overall_time = time.time() - overall_start_time
    print "Completed transcode in %.2f seconds" % overall_time
