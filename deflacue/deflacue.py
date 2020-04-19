"""
deflacue is a Cue Sheet parser and a wrapper for mighty SoX utility -
http://sox.sourceforge.net/.

SoX with appropriate plugins should be installed for deflacue to function.
Ubuntu users may install the following SoX packages: `sox`, `libsox-fmt-all`.


deflacue can function both as a Python module and in command line mode.
"""
import logging
import os
from collections import defaultdict
from subprocess import PIPE, Popen

from .cue import CueParser
from .exc import DeflacueError

__all__ = [
    'Deflacue',

    # It is export of ``CueParser`` and ``DeflacueError`` for backward
    # compatibility.
    'CueParser',
    'DeflacueError',
]

_COMMENTS_CUE_TO_VORBIS = {
    'TRACK_NUM': 'TRACKNUMBER',
    'TITLE': 'TITLE',
    'PERFORMER': 'ARTIST',
    'ALBUM': 'ALBUM',
    'GENRE': 'GENRE',
    'DATE': 'DATE',
}


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

    # Some lengthy shell command won't be executed on dry run.
    _dry_run = False

    def __init__(self,
                 source_path,
                 dest_path=None,
                 encoding=None,
                 use_logging=logging.INFO):
        """Prepares deflacue to for audio processing.

        `source_path` - Absolute or relative to the current directory path,
                        containing .cue file(s) or subdirectories with
                        .cue file(s) to process.

        `dest_path`   - Absolute or relative to the current directory path
                        to store output files in.
                        If None, output files are saved in `deflacue` directory
                        in the same directory as input file(s).

        `encoding`    -  Encoding used for .cue file(s).

        `use_logging` - Defines the verbosity level of deflacue. All messages
                        produced by the application are logged with `logging`
                        module.
                        Examples: logging.INFO, logging.DEBUG.

        """
        self.path_source = os.path.abspath(source_path)
        self.path_target = dest_path
        self.encoding = encoding

        if use_logging:
            self._configure_logging(use_logging)

        logging.info('Source path: %s', self.path_source)
        if not os.path.exists(self.path_source):
            raise DeflacueError('Path `%s` is not found.' % self.path_source)

        if dest_path is not None:
            self.path_target = os.path.abspath(dest_path)
            os.chdir(self.path_source)

    def _process_command(self, command, stdout=None, supress_dry_run=False):
        """Executes shell command with subprocess.Popen.
        Returns tuple, where first element is a process return code,
        and the second is a tuple of stdout and stderr output.
        """
        logging.debug('Executing shell command: %s', command)
        if (self._dry_run and supress_dry_run) or not self._dry_run:
            prc = Popen(command, shell=True, stdout=stdout)
            std = prc.communicate()
            return prc.returncode, std
        return 0, ('', '')

    def _configure_logging(self, verbosity_lvl=logging.INFO):
        """Switches on logging at given level."""
        logging.basicConfig(level=verbosity_lvl,
                            format='%(levelname)s: %(message)s')

    def _create_target_path(self, path):
        """Creates a directory for target files."""
        if not os.path.exists(path) and not self._dry_run:
            logging.debug('Creating target path: %s ...', path)
            try:
                os.makedirs(path)
            except OSError:
                raise DeflacueError('Unable to create target path: %s.' % path)

    def set_dry_run(self):
        """Sets deflacue into dry run mode, when all requested actions
        are only simulated, and no changes are written to filesystem.

        """
        self._dry_run = True

    def get_dir_files(self, recursive=False):
        """Creates and returns dictionary of files in source directory.
        `recursive` - if True search is also performed within subdirectories.

        """
        logging.info(
            'Enumerating files under the source path (recursive=%s) ...',
            recursive,
        )
        files = {}
        if not recursive:
            files[self.path_source] = [
                f for f in os.listdir(self.path_source)
                if os.path.isfile(os.path.join(self.path_source, f))
            ]
        else:
            for current_dir, _, dir_files in os.walk(self.path_source):
                files[
                    os.path.join(self.path_source, current_dir)
                ] = [f for f in dir_files]

        return files

    def filter_target_extensions(self, files_dict):
        """Takes file dictionary created with `get_dir_files` and returns
        dictionary of the same kind containing only audio files of supported
        types.

        """
        files_filtered = defaultdict(list)
        logging.info('Filtering .cue files ...')
        paths = files_dict.keys()

        for path in paths:
            if not path.endswith('deflacue'):
                files = sorted(files_dict[path])
                for f in files:
                    if os.path.splitext(f)[1] == '.cue':
                        files_filtered[path].append(f)
        return files_filtered

    def sox_check_is_available(self):
        """Checks whether SoX is available."""
        result = self._process_command('sox -h', PIPE, supress_dry_run=True)
        return result[0] == 0

    def sox_extract_audio(self,
                          source_file,
                          pos_start_samples,
                          pos_end_samples,
                          target_file,
                          metadata=None):
        """Using SoX extracts a chunk from source audio file into target."""
        logging.info('Extracting `%s` ...', os.path.basename(target_file))

        chunk_length_samples = ''
        if pos_end_samples is not None:
            chunk_length_samples = "%ss" % (pos_end_samples - pos_start_samples)

        add_comment = ''
        if metadata is not None:
            logging.debug('Metadata: %s\n', metadata)
            for key, val in _COMMENTS_CUE_TO_VORBIS.items():
                if key in metadata and metadata[key] is not None:
                    add_comment = '--add-comment="%s=%s" %s' % (
                        val, metadata[key], add_comment
                    )

        logging.debug('Extraction information:\n'
                      '      Source file: %(source)s\n'
                      '      Start position: %(pos_start)s samples\n'
                      '      End position: %(pos_end)s samples\n'
                      '      Length: %(length)s sample(s)',
                      source=source_file,
                      pos_start=pos_start_samples,
                      pos_end=pos_end_samples,
                      length=chunk_length_samples)

        command = (
            'sox -V1 "%(source)s" --comment="" %(add_comment)s '
            '"%(target)s" trim %(start_pos)ss %(length)s'
        ) % {
            'source': source_file,
            'target': target_file,
            'start_pos': pos_start_samples,
            'length': chunk_length_samples,
            'add_comment': add_comment
        }

        if not self._dry_run:
            self._process_command(command, PIPE)

    def process_cue(self, cue_file, target_path):
        """Parses .cue file, extracts separate tracks."""
        logging.info('Processing `%s`\n', os.path.basename(cue_file))
        parser = CueParser(cue_file, encoding=self.encoding)
        cd_info = parser.get_data_global()

        if not os.path.exists(cd_info['FILE']):
            logging.error(
                'Source file `%s` is not found. Cue Sheet is skipped.',
                cd_info['FILE'],
            )
            return

        tracks = parser.get_data_tracks()

        title = cd_info['ALBUM']
        if cd_info['DATE'] is not None:
            title = '%s - %s' % (cd_info['DATE'], title)

        try:  # Py2 support
            target_path = target_path.decode('utf-8')
        except AttributeError:
            pass

        bundle_path = os.path.join(target_path, cd_info['PERFORMER'], title)
        self._create_target_path(bundle_path)

        tracks_count = len(tracks)
        for track in tracks:
            track_num = str(track['TRACK_NUM']).rjust(
                len(str(tracks_count)), '0'
            )
            filename = '%s - %s.flac' % (
                track_num, track['TITLE'].replace('/', '')
            )
            self.sox_extract_audio(
                track['FILE'],
                track['POS_START_SAMPLES'],
                track['POS_END_SAMPLES'],
                os.path.join(bundle_path, filename),
                metadata=track
            )

    def do(self, recursive=False):
        """Main method processing .cue files in batch."""
        if self.path_target is not None and not os.path.exists(
                self.path_target
        ):
            self._create_target_path(self.path_target)

        files_dict = self.filter_target_extensions(
            self.get_dir_files(recursive)
        )

        dir_initial = os.getcwd()
        paths = sorted(files_dict.keys())
        for path in paths:
            os.chdir(path)
            logging.info('\n%s\n      Working on: %s\n', '====' * 10, path)

            if self.path_target is None:
                # When a target path is not specified, create `deflacue`
                # subdirectory in every directory we are working at.
                target_path = os.path.join(path, 'deflacue')
            else:
                # When a target path is specified, we create a subdirectory
                # there named after the directory we are working on.
                target_path = os.path.join(
                    self.path_target, os.path.split(path)[1]
                )

            self._create_target_path(target_path)
            logging.info('Target (output) path: %s', target_path)

            for cue in files_dict[path]:
                self.process_cue(os.path.join(path, cue), target_path)

        os.chdir(dir_initial)

        logging.info('We are done. Thank you.\n')
