flac2mp3
----

`flac2mp3` is a Python wrapper around several tools used for encoding FLAC and
MP3 files, namely `flac`, `metaflac`, and `lame` (all of which it assumes are
installed). It uses multiple cores to simultaneously re-encode FLAC files as MP3
files while preserving any id3 tags found.

Process
----
The utility walks the given files and/or directories and collects all the FLAC
files it finds, them passes them through `flac` to decode them, piping the
output through `lame` to re-encode them, and stores them in the output directory
intelligently using the nearest comment ancestor directory as a template to
ensure they don't end up lumped illogically in the output directory.

Simple Usage
----
`python flac2mp3.py [-o OUTPUT_DIR] FILES [FILES ...]`

If no output directory is specified, the new MP3 files are stored in the same
directories as their FLAC parents.

Further options can be discovered through the `-h` or `--help` commands,
including specifying the number of cores to use, a file to log console output
to, and whether to overwrite existing files.

