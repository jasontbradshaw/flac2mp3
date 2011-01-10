#!/usr/bin/env python

import os
import subprocess as sp

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
    subdirectories.  if 'follow_links' is True, symbolic links will be followed.
    This option can lead to infinite looping since the function doesn't keep
    track of which directories have been visited.
    """

    # attempt to get the files in the given directory, returning an empty list
    # if it failed for any reason.
    contents = []
    try:
        contents = os.listdir(d)
    except OSError:
        return []

    # add original directory name to every listed file
    contents = map(lambda x: os.path.join(d, x), contents)

    # normalize all file names
    contents = map(os.path.abspath, contents)

    # add all file names to a list recursively
    new_files = []
    for f in contents:
        # skip links if specified
        if not follow_links and os.path.islink(f):
            continue

        # add all the files under a dir to the list
        if os.path.isdir(f):
            new_files.extend(walk_dir(f, follow_links=follow_links))
        # add files to the list
        else:
            new_files.append(f)

    return new_files

def get_filetype(fname):
    """
    Gets the file type of the given file as a MIME string and returns it.
    """

    # brief output, MIME version
    file_args = ["file", "-b", "-i", fname]
    p_file = sp.Popen(file_args, stdout=sp.PIPE)

    return p_file.communicate()[0]
