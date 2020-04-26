from copy import deepcopy
from logging import debug, warning
from typing import Dict, List, Optional, Union

from .exc import DeflacueError

__all__ = [
    'CueParser',
]


_ContextType = Dict[str, Optional[Union[str, int]]]

_DEFAULT_SAMPLE_RATE = 44100


def _unquote(in_str: str) -> str:
    return in_str.strip(' "')


def _timestr_to_sec(timestr: str) -> int:
    """Converts `mm:ss:` time string into seconds integer."""
    splitted = timestr.split(':')[:-1]
    splitted.reverse()
    seconds = 0
    for i, chunk in enumerate(splitted, 0):
        factor = pow(60, i)
        if i == 0:
            factor = 1
        seconds += int(chunk) * factor
    return seconds


def _timestr_to_samples(timestr: str) -> int:
    """Converts `mm:ss:ff` time string into samples integer, assuming the
    CD sampling rate of 44100Hz."""
    # 75 frames per second of audio
    frames_factor = _DEFAULT_SAMPLE_RATE // 75
    full_seconds = _timestr_to_sec(timestr)
    frames = int(timestr.split(':')[-1])
    return full_seconds * _DEFAULT_SAMPLE_RATE + frames * frames_factor


class CueParser(object):
    """Simple Cue Sheet file parser."""

    def __init__(self,
                 cue_filepath: str,
                 encoding: Optional[str] = None) -> None:
        self._context_global = {
            'PERFORMER': 'Unknown',
            'SONGWRITER': None,
            'ALBUM': 'Unknown',
            'GENRE': 'Unknown',
            'DATE': None,
            'FILE': None,
            'COMMENT': None,
        }  # type: _ContextType
        self._context_tracks = []  # type: List[_ContextType]

        self._current_context = self._context_global  # type: _ContextType
        try:
            with open(cue_filepath, encoding=encoding) as f:
                lines = f.readlines()
        except UnicodeDecodeError:
            raise DeflacueError(
                'Unable to read data from .cue file. '
                'Please use -encoding command line argument to set correct '
                'encoding.'
            )

        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            command, args = line.split(' ', 1)
            debug('Command `%s`. Args: %s', command, args)
            method = getattr(self, 'cmd_%s' % command.lower(), None)
            if method is not None:
                method(args)
            else:
                warning('Unknown command `%s`. Skipping ...', command)

        for idx, track_data in enumerate(self._context_tracks):
            track_end_pos = None
            try:
                track_end_pos = self._context_tracks[idx + 1][
                    'POS_START_SAMPLES'
                ]
            except IndexError:
                pass
            track_data['POS_END_SAMPLES'] = track_end_pos

    def get_data_global(self) -> _ContextType:
        """Returns a dictionary with global CD data."""
        return self._context_global

    def get_data_tracks(self) -> List[_ContextType]:
        """Returns a list of dictionaries with individual
        tracks data. Note that some of the data is borrowed from global data.

        """
        return self._context_tracks

    def _in_global_context(self) -> bool:
        return self._current_context == self._context_global

    def cmd_rem(self, args: str) -> None:
        subcommand, subargs = args.split(' ', 1)
        if subargs.startswith('"'):
            subargs = _unquote(subargs)
        self._current_context[subcommand.upper()] = subargs

    def cmd_performer(self, args: str) -> None:
        unquoted = _unquote(args)
        self._current_context['PERFORMER'] = unquoted

    def cmd_title(self, args: str) -> None:
        unquoted = _unquote(args)
        if self._in_global_context():
            self._current_context['ALBUM'] = unquoted
        else:
            self._current_context['TITLE'] = unquoted

    def cmd_file(self, args: str) -> None:
        filename = _unquote(args.rsplit(' ', 1)[0])
        self._current_context['FILE'] = filename

    def cmd_index(self, args: str) -> None:
        timestr = args.split()[1]
        self._current_context['INDEX'] = timestr
        self._current_context['POS_START_SAMPLES'] = _timestr_to_samples(
            timestr
        )

    def cmd_track(self, args: str) -> None:
        num, _ = args.split()
        new_track_context = deepcopy(self._context_global)
        self._context_tracks.append(new_track_context)
        self._current_context = new_track_context
        self._current_context['TRACK_NUM'] = int(num)

    def cmd_flags(self, args: str) -> None: ...
