import argparse
from logging import DEBUG, INFO, basicConfig, exception, warning
from os.path import abspath

from .deflacue import Deflacue
from .exc import DeflacueError

__all__ = [
    'run_deflacue',
]


def _configure_logging(log_level: int) -> None:
    """Switches on logging at given level."""
    basicConfig(level=log_level, format='%(levelname)s: %(message)s')


def run_deflacue() -> None:

    argparser = argparse.ArgumentParser('deflacue')

    argparser.add_argument(
        'source_path',
        help='Absolute or relative source path with .cue file(s).',
    )
    argparser.add_argument(
        '-r',
        '--recursive',
        help='Recursion flag to search directories under the source_path.',
        action='store_true',
        default=False,
    )
    argparser.add_argument(
        '-i',
        '--in-place',
        help='In-place flag to convert files in their folders.',
        action='store_true',
        default=False,
    )
    argparser.add_argument(
        '-d',
        '--dest-path',
        help='Absolute or relative destination path for output audio file(s).',
    )
    argparser.add_argument(
        '-e',
        '--encoding',
        help='Cue Sheet file(s) encoding.',
    )
    argparser.add_argument(
        '--dry',
        '--dry-run',
        dest='dry_run',
        help='Perform the dry run with no changes done to filesystem.',
        action='store_true',
        default=False,
    )
    argparser.add_argument(
        '--debug',
        help='Show debug messages while processing.',
        action='store_true',
        default=False,
    )
    argparser.add_argument(
        '--skip-errors',
        help='Skip files, which processing occures any errors.',
        action='store_true',
        default=False,
    )

    args = argparser.parse_args()

    _configure_logging(DEBUG if args.debug else INFO)

    dest_path = args.dest_path
    in_place = args.in_place

    if in_place and dest_path:
        warning('Option --dest-path is not used if favor of --in-place option.')
        dest_path = None

    elif dest_path is not None:
        dest_path = abspath(dest_path)

    try:
        deflacue = Deflacue(
            args.source_path,
            encoding=args.encoding,
            dry_run=args.dry_run,
        )

        if not deflacue.sox_check_is_available():
            raise DeflacueError(
                'SoX seems not available. Please install it (e.g. '
                '`sudo apt-get install sox libsox-fmt-all`).'
            )

        deflacue.do(recursive=args.recursive,
                    in_place=in_place,
                    dest_path=dest_path,
                    skip_errors=args.skip_errors)
    except DeflacueError as e:
        exception(e)


if __name__ == '__main__':
    run_deflacue()
