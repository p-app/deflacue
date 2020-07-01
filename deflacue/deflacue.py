"""
deflacue is a Cue Sheet parser and a wrapper for mighty SoX utility -
http://sox.sourceforge.net/.

SoX with appropriate plugins should be installed for deflacue to function.
Ubuntu users may install the following SoX packages: `sox`, `libsox-fmt-all`.


deflacue can function both as a Python module and in command line mode.
"""
from collections import defaultdict
from logging import debug, error, info, warning
from os import chdir, getcwd, listdir, makedirs, remove, walk
from os.path import abspath, basename, exists, isfile, join, split, splitext
from subprocess import PIPE, Popen
from typing import Any, DefaultDict, Dict, IO, List, Optional, Tuple, \
    Union

from .cue import CueParser
from .exc import DeflacueError

__all__ = [
    'Deflacue',

    # It is export of ``CueParser`` and ``DeflacueError`` for backward
    # compatibility.
    'CueParser',
    'DeflacueError',
]

_FilesDictType = Dict[str, List[str]]
_ProcessResultType = Tuple[int, Union[Tuple[str, str], Tuple[bytes, bytes]]]

_COMMENTS_CUE_TO_VORBIS = {
    'TRACK_NUM': 'TRACKNUMBER',
    'TITLE': 'TITLE',
    'PERFORMER': 'ARTIST',
    'ALBUM': 'ALBUM',
    'GENRE': 'GENRE',
    'DATE': 'DATE',
}  # type: Dict[str, str]

_DEFLACUE_SUBFOLDER_NAME = 'deflacue'


def _filter_target_extensions(
    files_dict: _FilesDictType
) -> DefaultDict[str, List[str]]:
    """Takes file dictionary created with `get_dir_files` and returns
    dictionary of the same kind containing only audio files of supported
    types.

    """
    files_filtered = defaultdict(list)
    info('Filtering .cue files ...')
    paths = files_dict.keys()

    for path in paths:
        if path.endswith(_DEFLACUE_SUBFOLDER_NAME):
            continue
            
        files = sorted(files_dict[path])
        for f in files:
            if splitext(f)[1] == '.cue':
                files_filtered[path].append(f)
                
    return files_filtered


class Deflacue(object):
    """deflacue functionality is encapsulated in this class.

    Usage example:
        deflacue = Deflacue('/home/idle/cues_to_process/')
        deflacue.do()

    This will search `/home/idle/cues_to_process/` and subdirectories
    for .cue files, parse them and extract separate tracks.
    Extracted tracks are stored in Artist - Album hierarchy within
    `deflacue` directory under each source directory.

    """
    def __init__(self,
                 source_path: str,
                 encoding: Optional[str] = None,
                 dry_run: bool = False) -> None:
        """Prepares deflacue to for audio processing.

        `source_path` - Absolute or relative to the current directory path,
                        containing .cue file(s) or subdirectories with
                        .cue file(s) to process.

        `encoding`    -  Encoding used for .cue file(s).

        `dry_run`     -  Sets deflacue into dry run mode, when all requested
                         actions are only simulated, and no changes are
                         written to filesystem.
        """
        self._source_path = abspath(source_path)
        self._encoding = encoding
        self._dry_run = dry_run

        info('Source path: %s', self._source_path)
        if not exists(self._source_path):
            raise DeflacueError('Path `%s` is not found.' % self._source_path)

    def _process_command(
        self,
        command: str,
        stdout: Optional[Union[int, IO[Any]]] = None,
        supress_dry_run: bool = False,
    ) -> _ProcessResultType:
        """Executes shell command with subprocess.Popen.
        Returns tuple, where first element is a process return code,
        and the second is a tuple of stdout and stderr output.
        """
        debug('Executing shell command: %s', command)
        if (self._dry_run and supress_dry_run) or not self._dry_run:
            prc = Popen(command, shell=True, stdout=stdout)
            std = prc.communicate()
            return prc.returncode, std
        return 0, ('', '')

    def _create_target_path(self, path: str) -> None:
        """Creates a directory for target files."""
        if exists(path) or self._dry_run:
            return

        debug('Creating target path: %s ...', path)
        try:
            makedirs(path)
        except OSError:
            raise DeflacueError('Unable to create target path: %s.' % path)

    def _get_dir_files(self, recursive: bool = False) -> _FilesDictType:
        """Creates and returns dictionary of files in source directory.
        `recursive` - if True search is also performed within subdirectories.

        """
        info(
            'Enumerating files under the source path (recursive=%s) ...',
            recursive,
        )
        if not recursive:
            return {
                self._source_path: [
                    f for f in listdir(self._source_path)
                    if isfile(join(self._source_path, f))
                ]
            }

        files = {}  # type: Dict[str, List[str]]
        for current_dir, _, dir_files in walk(self._source_path):
            files[join(self._source_path, current_dir)] = dir_files

        return files

    def sox_check_is_available(self) -> bool:
        """Checks whether SoX is available."""
        result = self._process_command('sox -h', PIPE, supress_dry_run=True)
        return result[0] == 0

    def _sox_extract_audio(
        self,
        source_file: str,
        pos_start_samples: int,
        pos_end_samples: int,
        target_file: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[_ProcessResultType]:
        """Using SoX extracts a chunk from source audio file into target."""
        info('Extracting `%s` ...', basename(target_file))

        chunk_length_samples = ''
        if pos_end_samples is not None:
            chunk_length_samples = "%ss" % (pos_end_samples - pos_start_samples)

        add_comment = []
        if metadata is not None:
            debug('Metadata: %s\n', metadata)
            for key, val in _COMMENTS_CUE_TO_VORBIS.items():
                if key in metadata and metadata[key] is not None:
                    add_comment.append(
                        '--add-comment="%s=%s"' % (val, metadata[key])
                    )

        debug('Extraction information:\n'
              '      Source file: %(source)s\n'
              '      Start position: %(pos_start)s samples\n'
              '      End position: %(pos_end)s samples\n'
              '      Length: %(length)s sample(s)',
              dict(
                  source=source_file,
                  pos_start=pos_start_samples,
                  pos_end=pos_end_samples,
                  length=chunk_length_samples,
              ))

        command = (
            'sox -V1 "%(source)s" --comment="" %(add_comment)s '
            '"%(target)s" trim %(start_pos)ss %(length)s'
        ) % {
            'source': source_file,
            'target': target_file,
            'start_pos': pos_start_samples,
            'length': chunk_length_samples,
            'add_comment': ' '.join(add_comment),
        }

        if not self._dry_run:
            return self._process_command(command, PIPE)

    def _process_cue(self,
                     cue_filepath: str,
                     target_path: str,
                     in_place: bool) -> None:
        """Parses .cue file, extracts separate tracks."""
        info('Processing `%s`\n', basename(cue_filepath))
        parser = CueParser(cue_filepath, encoding=self._encoding)
        cd_info = parser.get_data_global()

        if not exists(cd_info['FILE']):
            error(
                'Source file `%s` is not found. Cue Sheet is skipped.',
                cd_info['FILE'],
            )
            return

        tracks = parser.get_data_tracks()

        title = cd_info['ALBUM']
        if cd_info['DATE'] is not None:
            title = '%s - %s' % (cd_info['DATE'], title)

        if in_place:
            bundle_path = target_path

        else:
            bundle_path = join(target_path, cd_info['PERFORMER'], title)
            self._create_target_path(bundle_path)

        tracks_count = len(tracks)
        for track in tracks:
            track_num = str(track['TRACK_NUM']).rjust(
                len(str(tracks_count)), '0'
            )
            filename = '%s - %s.flac' % (
                track_num, track['TITLE'].replace('/', '')
            )

            process_result = self._sox_extract_audio(
                track['FILE'],
                track['POS_START_SAMPLES'],
                track['POS_END_SAMPLES'],
                join(bundle_path, filename),
                metadata=track,
            )

            if process_result is not None and process_result[0] != 0:
                raise DeflacueError(
                    'Error occured during processing file %r.' %
                    join(target_path, filename)
                )

        if in_place:
            info('Removing %r file because of --in-place option.',
                 cd_info['FILE'])
            remove(cd_info['FILE'])

    def do(self,
           dest_path: Optional[str] = None,
           recursive: bool = False,
           in_place: bool = False) -> None:
        """Main method processing .cue files in batch."""
        if not in_place and dest_path is not None and not exists(dest_path):
            self._create_target_path(dest_path)

        files_dict = _filter_target_extensions(
            self._get_dir_files(recursive)
        )

        dir_initial = getcwd()  # type: str
        paths = sorted(files_dict.keys())  # type: List[str]
        for path in paths:
            chdir(path)
            info('\n%s\n      Working on: %s\n', '====' * 10, path)

            if in_place:
                target_path = path

            elif dest_path is None:
                # When a target path is not specified, create `deflacue`
                # subdirectory in every directory we are working at.
                target_path = join(path, _DEFLACUE_SUBFOLDER_NAME)
            else:
                # When a target path is specified, we create a subdirectory
                # there named after the directory we are working on.
                target_path = join(dest_path, split(path)[1])

            if not in_place:
                self._create_target_path(target_path)

            info('Target (output) path: %s', target_path)

            for cue in files_dict[path]:
                cue_filepath = join(path, cue)

                try:
                    self._process_cue(cue_filepath, target_path, in_place)

                except DeflacueError as err:
                    if in_place:
                        warning('Error occured during processing %r cue '
                                'file.' % cue_filepath, exc_info=err)

                    else:
                        raise

        chdir(dir_initial)

        info('We are done. Thank you.\n')
