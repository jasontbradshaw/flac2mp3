#!/usr/bin/env python

import os
import re
import subprocess as sp
import sys
import multiprocessing as mp

def get_missing_programs(required_programs):
    """Gets a list of required programs that can't be found on the system."""

    # try to launch the programs, and add them to a list if they're not found
    missing = []
    for program in required_programs:
        try:
            sp.call(program, stdout=sp.PIPE, stderr=sp.STDOUT)
        except OSError, e:
            # if the binary couldn't be found, put it in the list
            if e.errno == 2:
                missing.append(program)
            else:
                # propogate other errors
                raise

    return missing

def change_file_ext(fname, ext):
    """Transforms the given filename's extension to the given extension."""
    return os.path.splitext(fname)[0] + ext

def walk_dir(d, follow_links=False):
    """
    Yields all the file names in a given directory, including those in
    subdirectories.  If 'follow_links' is True, symbolic links will be followed.
    This option can lead to infinite looping since the function doesn't keep
    track of which directories have been visited.
    """

    # walk the directory and collect the full path of every file therein
    for root, dirs, files in os.walk(d, followlinks=follow_links):
        for name in files:
            # append the normalized file name
            yield os.path.abspath(os.path.join(root, name))

def get_filetype(fname):
    """Gets the file type of the given file as a MIME string and returns it."""

    # brief output, MIME version
    file_args = ["file", "-b"]
    if sys.platform == "darwin":
        file_args.append("-I")
    else:
        file_args.append("-i")
    file_args.append(fname)

    p_file = sp.Popen(file_args, stdout=sp.PIPE)
    return p_file.communicate()[0]

def transcode(infile, outfile=None):
    """
    Transcodes a single flac file into a single mp3 file.  Preserves the file
    name but changes the extension.  Copies flac tag info from the original file
    to the transcoded file. If outfile is specified, the file is saved to that
    location, otherwise it's saved alongside the original file.
    """

    # get a new file name for the mp3 if no output name was specified
    outfile = outfile or change_file_ext(infile, ".mp3")

    # get the tags from the input file
    flac_tags = get_tags(infile)

    # arguments for 'lame', including bitrate and tag values
    vbr_quality = 2 # ~190 kbps
    lame_args = ["lame", "-m", "s", "--vbr-new", "-V" + str(vbr_quality),
            "--add-id3v2", "--silent",
            "--tt", flac_tags["TITLE"],
            "--ta", flac_tags["ARTIST"],
            "--tl", flac_tags["ALBUM"],
            "--ty", flac_tags["DATE"],
            "--tc", flac_tags["COMMENT"],
            "--tn", flac_tags["TRACKNUMBER"] + "/" + flac_tags["TRACKTOTAL"],
            "--tg", flac_tags["GENRE"],
            "-", outfile]

    # arguments for 'flac' decoding to be piped to 'lame'
    flac_args = ["flac", "--silent", "--stdout", "--decode", infile]

    # decode the 'flac' data and pass it to 'lame'
    p_flac = sp.Popen(flac_args, stdout=sp.PIPE)
    p_lame = sp.Popen(lame_args, stdin=p_flac.stdout)

    # allow p_flac to receive a SIGPIPE if p_lame exits
    p_flac.stdout.close()

    # wait for the encoding to finish
    p_lame.wait()

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
    import time
    import argparse

    # parse arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("files", metavar="FILES", type=str, nargs="+",
            help="Files and/or directories to transcode")
    parser.add_argument("-o", "--output-dir", type=os.path.abspath,
            help="Directory to output transcoded files to")
    args = parser.parse_args()

    # ensure we have all our required programs
    missing_progs = get_missing_programs(["lame", "file", "flac", "metaflac"])
    if len(missing_progs) > 0:
        print "The following programs are required: " + ", ".join(missing_progs)
        sys.exit(1)

    # ensure the output directory exists
    if args.output_dir is not None:
        try:
            os.makedirs(args.output_dir)
        except OSError, e:
            # give up if the error DOESN'T indicate that the dir exists
            if e.errno != 17:
                print "Couldn't create directory '" + args.output_dir + "'"
                sys.exit(2)

    # add all the files/directories in the args recursively
    print "Enumerating files..."
    flacfiles = set()
    for f in args.files:
        if os.path.isdir(f):
            flacfiles.update(walk_dir(f))
        else:
            flacfiles.add(f)

    # remove all non-flac files from the list
    is_flac_file = lambda x: get_filetype(x).count("audio/x-flac") > 0
    flacfiles = filter(is_flac_file, flacfiles)

    # get the common prefix of all the files so we can preserve directory
    # structure when an output directory is specified.
    common_prefix = os.path.dirname(os.path.commonprefix(flacfiles))

    # get the number of threads we should use while transcoding (usually the
    # number of processors, or 1 if that number can't be determined).
    thread_count = 1
    try:
        thread_count = mp.cpu_count()
    except NotImplementedError:
        pass

    def transcode_with_printout(f):
        """Transcode the given file and print out progress statistics."""

        # a more compact file name representation
        short_fname = os.path.basename(f)
        print "Transcoding '%s'..." % short_fname

        # time the transcode
        start_time = time.time()

        # assign the output directory
        outfile = None
        if args.output_dir is not None:
            mp3file = change_file_ext(f, ".mp3")
            outfile = os.path.join(args.output_dir,
                    mp3file.replace(common_prefix, "").strip("/"))

            # make the directory to ensure it exists
            try:
                os.makedirs(os.path.dirname(outfile))
            except OSError, o:
                # lame takes care of other error messages
                pass

        transcode(f, outfile)

        total_time = time.time() - start_time

        print "Transcoded '%s' in %.2f seconds" % (short_fname, total_time)

    # print transcode status
    number_word = "files" if len(flacfiles) != 1 else "file"
    print "Beginning transcode of %d %s..." % (len(flacfiles), number_word)
    overall_start_time = time.time()

    # transcode all the found files
    pool = mp.Pool(processes=thread_count)
    terminated = False
    succeeded = False
    try:
        result = pool.map_async(transcode_with_printout, flacfiles)
        while 1:
            try:
                result.get(0.1)
                succeeded = True
                break
            except mp.TimeoutError:
                continue
    except KeyboardInterrupt:
        terminated = True
        pool.terminate()
        pool.join()
    except Exception, e:
        # catch all other exceptions gracefully
        print e

    # print our exit status/condition
    overall_time = time.time() - overall_start_time
    if terminated:
        print "User terminated transcode after %.2f seconds" % overall_time
    elif succeeded:
        print "Completed transcode in %.2f seconds" % overall_time
    else:
        print "Transcode failed after %.2f seconds" % overall_time
