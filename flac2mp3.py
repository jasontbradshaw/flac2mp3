#!/usr/bin/env python

from itertools import compress
import multiprocessing as mp
import os
import re
import shutil
import subprocess as sp
import sys
import tempfile

def get_missing_programs(required_programs):
    '''Gets a list of required programs that can't be found on the system.'''

    # try to launch the programs, and add them to a list if they're not found
    missing = []
    for program in required_programs:
        try:
            sp.call(program, stdout=sp.PIPE, stderr=sp.STDOUT)
        except OSError as e:
            # if the binary couldn't be found, put it in the list
            if e.errno == 2:
                missing.append(program)
            else:
                # propogate other errors
                raise

    return missing

def ensure_directory(d, ignore_errors=False):
    '''
    Given a directory, ensures that it exists by creating the directory tree if
    it's not already present. Returns True if the directory was created, False
    if it already exists.
    '''

    try:
        os.makedirs(d)
        return True
    except OSError as e:
        # propogate the error if it DOESN'T indicate that the directory already
        # exists.
        if e.errno != 17 and not ignore_errors:
            raise e
        return False

def change_file_ext(fname, ext):
    '''Transforms the given filename's extension to the given extension.'''
    return os.path.splitext(fname)[0] + ext

def walk_dir(d, follow_links=False):
    '''
    Yields all the file names in a given directory, including those in
    subdirectories.  If 'follow_links' is True, symbolic links will be followed.
    This option can lead to infinite looping since the function doesn't keep
    track of which directories have been visited.
    '''

    # walk the directory and collect the full path of every file therein
    for root, dirs, files in os.walk(d, followlinks=follow_links):
        for name in files:
            # append the normalized file name
            yield os.path.abspath(os.path.join(root, name))

def get_filetype(fname):
    '''Takes a file name and returns its MIME type.'''

    # brief output, MIME version
    file_args = ['file', '-b']
    if sys.platform == 'darwin':
        file_args.append('-I')
    else:
        file_args.append('-i')
    file_args.append(fname)

    # return one item per line
    p_file = sp.Popen(file_args, stdout=sp.PIPE)
    return p_file.communicate()[0].strip().decode('utf-8')

def transcode(infile, outfile=None, skip_existing=False, bad_chars=''):
    '''
    Transcodes a single flac file into a single mp3 file.  Preserves the file
    name but changes the extension.  Copies flac tag info from the original file
    to the transcoded file. If outfile is specified, the file is saved to that
    location, otherwise it's saved alongside the original file. If skip_existing
    is False (the default), overwrites existing files with the same name as
    outfile, otherwise skips the file completely. bad_chars is a collection of
    characters that should be removed from the output file name.  Returns the
    returncode of the lame process.
    '''

    # get a new file name for the mp3 if no output name was specified
    outfile = outfile or change_file_ext(infile, '.mp3')

    # replace incompatible filename characters in output file
    for c in bad_chars:
        outfile = outfile.replace(c, '')

    # skip transcoding existing files if specified
    if skip_existing and os.path.exists(outfile):
        return

    # NOTE: we use a temp file to store the incremental in-flight transcode, and
    # move it to the final output filename when transcode is complete. this
    # approach prevents partial or interrupted transcodes from getting in the
    # way of --skip-existing.

    # create the file in the same dir (and same filesystem) as the final target,
    # allowing us to use os.link rather than shutil.move later.
    dirname = os.path.dirname(outfile)
    with tempfile.NamedTemporaryFile(dir=dirname, suffix='.tmp') as temp_outfile:
        # get the tags from the input file
        flac_tags = get_tags(infile)

        # arguments for 'lame', including bitrate and tag values
        vbr_quality = 2 # ~190 kbps
        lame_args = ['lame', '-m', 's', '--vbr-new', '-V' + str(vbr_quality),
                '--add-id3v2', '--silent',
                '--tt', flac_tags['TITLE'],
                '--ta', flac_tags['ARTIST'],
                '--tl', flac_tags['ALBUM'],
                '--ty', flac_tags['DATE'],
                '--tc', flac_tags['COMMENT'],
                '--tn', flac_tags['TRACKNUMBER'] + '/' + flac_tags['TRACKTOTAL'],
                '--tg', flac_tags['GENRE'],
                '-', '-' ]

        # arguments for 'flac' decoding to be piped to 'lame'
        flac_args = ['flac', '--silent', '--stdout', '--decode', infile]

        # decode the 'flac' data and pass it to 'lame'
        # pass the lame encoding to our temp file
        p_flac = sp.Popen(flac_args, stdout=sp.PIPE)
        p_lame = sp.Popen(lame_args, stdin=p_flac.stdout, stdout=temp_outfile)

        # allow p_flac to receive a SIGPIPE if p_lame exits
        p_flac.stdout.close()

        # wait for the encoding to finish
        retval = p_lame.wait()

        # if the transcode worked, link the temp file to the final filename
        if retval == 0:
            os.link(temp_outfile.name, outfile)

    return retval

def get_tags(infile):
    '''
    Gets the flac tags from the given file and returns them as a dict.  Ensures
    a minimun set of id3v2 tags is available, giving them default values if
    these tags aren't found in the orininal file.
    '''

    # get tag info text using 'metaflac'
    metaflac_args = ['metaflac', '--list', '--block-type=VORBIS_COMMENT', infile]
    p_metaflac = sp.Popen(metaflac_args, stdout=sp.PIPE)
    metaflac_text = p_metaflac.communicate()[0].decode('utf-8')

    # ensure all possible id3v2 tags start off with a default value
    tag_dict = {
        'TITLE': 'NONE',
        'ARTIST': 'NONE',
        'ALBUM': 'NONE',
        'DATE': '1',
        'COMMENT': '',
        'TRACKNUMBER': '00',
        'TRACKTOTAL': '00',
        'GENRE': 'NONE'
    }

    # matches all lines like 'comment[0]: TITLE=Misery' and extracts them to
    # tuples like ('TITLE', 'Misery'), then stores them in a dict.
    pattern = r"\s+comment\[\d+\]:\s+([^=]+)=([^\n]+)\n"

    # get the comment data from the obtained text
    for name, value in re.findall(pattern, metaflac_text):
        tag_dict[name.upper()] = value

    return tag_dict

if __name__ == '__main__':
    import logging
    import time
    import argparse

    # parse arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('files', metavar='FILES', type=str, nargs='+',
            help='Files and/or directories to transcode')

    # options and flags
    parser.add_argument('-o', '--output-dir', type=os.path.abspath,
            help='Directory to output transcoded files to')
    parser.add_argument('-s', '--skip-existing', action='store_true',
            help='Skip transcoding files if the output file already exists')
    parser.add_argument('-l', '--logfile', type=os.path.normpath, default=None,
            help='log output to a file as well as to the console.')
    parser.add_argument('-q', '--quiet', action='store_true',
            help='Disable console output.')
    parser.add_argument('-c', '--copy-pattern', type=re.compile,
            help="Copy files who's names match the given pattern into the " +
            'output directory. Only works if an output directory is specified.')
    parser.add_argument('-n', '--num-threads', type=int, default=mp.cpu_count(),
            help='The number of threads to use for transcoding. Defaults ' +
            'to the number of CPUs on the machine.')
    args = parser.parse_args()

    # set log level and format
    log = logging.getLogger('flac2mp3')
    log.setLevel(logging.INFO)

    # prevent 'no loggers found' warning
    log.addHandler(logging.NullHandler())

    # custom log formatting
    formatter = logging.Formatter('[%(levelname)s] %(message)s')

    # log to stderr unless disabled
    if not args.quiet:
        sh = logging.StreamHandler()
        sh.setFormatter(formatter)
        log.addHandler(sh)

    # add a file handler if specified
    if args.logfile is not None:
        fh = logging.FileHandler(args.logfile)
        fh.setFormatter(formatter)
        log.addHandler(fh)

    # ensure we have all our required programs
    missing = get_missing_programs(['lame', 'file', 'flac', 'metaflac'])
    if len(missing) > 0:
        log.critical('The following programs are required: ' + ','.join(missing))
        sys.exit(1)

    # ensure the output directory exists
    if args.output_dir is not None:
        try:
            ensure_directory(args.output_dir)
        except OSError as e:
            log.error("Couldn't create directory '%s'" % args.output_dir)

    # add all the files/directories in the args recursively
    log.info('Enumerating files...')
    files = set()
    for f in args.files:
        if os.path.isdir(f):
            files.update(walk_dir(f))
        else:
            files.add(f)
    log.info('Found ' + str(len(files)) + ' files')

    # get the common prefix of all the files so we can preserve directory
    # structure when an output directory is specified.
    common_prefix = os.path.dirname(os.path.commonprefix(list(files)))

    def transcode_with_logging(f):
        '''Transcode the given file and print out progress statistics.'''

        short_fname = os.path.basename(f)

        # copy any non-FLAC files to the output dir if they match a pattern
        if 'audio/flac' not in get_filetype(f):
            if args.output_dir is not None and args.copy_pattern is not None:
                match = args.copy_pattern.search(f)
                if match is not None:
                    dest = os.path.join(args.output_dir,
                            f.replace(common_prefix, '').strip('/'))
                    try:
                        ensure_directory(os.path.dirname(dest))
                        shutil.copy(f, dest)
                        log.info("Copied '%s' ('%s' matched)", short_fname,
                                match.group(0))
                    except Exception as e:
                        log.error("Failed to copy '%s' (%s)", short_fname,
                                e.message)

                    # we're done once we've attempted a copy
                    return

            log.info("Skipped '%s'", short_fname)

            # never proceed further if the file wasn't a FLAC file
            return

        # a more compact file name representation
        log.info("Transcoding '%s'..." % short_fname)

        # time the transcode
        start_time = time.time()

        # assign the output directory
        outfile = None
        if args.output_dir is not None:
            mp3file = change_file_ext(f, '.mp3')
            outfile = os.path.join(args.output_dir,
                    mp3file.replace(common_prefix, '').strip('/'))

            # make the directory to ensure it exists. ignore errors since
            # lame takes care of other error messages.
            ensure_directory(os.path.dirname(outfile), ignore_errors=True)

        # store the return code of the process so we can see if it errored
        retcode = transcode(f, outfile, args.skip_existing, ':')
        total_time = time.time() - start_time

        # log success or error
        if retcode == 0:
            log.info("Transcoded '%s' in %.2f seconds" % (short_fname,
                total_time))
        elif retcode == None:
            log.info("Did not transcode '%s'", short_fname)
        else:
            log.error("Failed to transcode '%s' after %.2f seconds" %
                    (short_fname, total_time))

    # log transcode status
    log.info('Beginning transcode of %d files...' % len(files))
    overall_start_time = time.time()

    # build a thread pool for transcoding
    pool = mp.Pool(processes=args.num_threads)

    # transcode all the found files
    terminated = False
    succeeded = False
    try:
        result = pool.map_async(transcode_with_logging, files)
        while 1:
            try:
                # wait for the result to come in, and mark success once it does
                result.get(0.1)
                succeeded = True
                break
            except mp.TimeoutError:
                continue
    except KeyboardInterrupt:
        terminated = True
        pool.terminate()
        pool.join()
    except Exception as e:
        # catch and log all other exceptions gracefully
        log.exception(e)

    # log our exit status/condition
    overall_time = time.time() - overall_start_time
    if succeeded:
        log.info('Completed transcode in %.2f seconds' % overall_time)
        sys.exit(0)
    elif terminated:
        log.warning('User terminated transcode after %.2f seconds' %
                overall_time)
        sys.exit(3)
    else:
        log.error('Transcode failed after %.2f seconds' % overall_time)
        sys.exit(4)
