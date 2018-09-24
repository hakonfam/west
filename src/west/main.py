#!/usr/bin/env python3

# Copyright 2018 Open Source Foundries Limited.
#
# SPDX-License-Identifier: Apache-2.0

'''Zephyr RTOS meta-tool (west) main module
'''


import argparse
import colorama
from functools import partial
import os
import sys
from subprocess import CalledProcessError, check_output, DEVNULL

# HACK: the version is stored in the bootstrap package for now;
# pull it out of there.
from west._bootstrap import version

import log
from commands import CommandContextError
from commands.build import Build
from commands.flash import Flash
from commands.debug import Debug, DebugServer, Attach
from commands.project import ListProjects, Fetch, Pull, Rebase, Branch, \
                             Checkout, Diff, Status, Update, ForAll, \
                             WestUpdated
from util import quote_sh_list


COMMANDS = (
    Build(),
    Flash(),
    Debug(),
    DebugServer(),
    Attach(),

    # Project-related commands
    ListProjects(),
    Fetch(),
    Pull(),
    Rebase(),
    Branch(),
    Checkout(),
    Diff(),
    Status(),
    Update(),
    ForAll(),
)
'''Built-in West commands.'''


class InvalidWestContext(RuntimeError):
    pass


def command_handler(command, known_args, unknown_args):
    command.run(known_args, unknown_args)


def validate_context(args, unknown):
    '''Validate the run-time context expected by west.'''
    if args.zephyr_base:
        os.environ['ZEPHYR_BASE'] = args.zephyr_base
    else:
        if 'ZEPHYR_BASE' not in os.environ:
            log.wrn('--zephyr-base missing and no ZEPHYR_BASE',
                    'in the environment')
        else:
            args.zephyr_base = os.environ['ZEPHYR_BASE']


def parse_args(argv):
    # The prog='west' override avoids the absolute path of the main.py script
    # showing up when West is run via the wrapper
    west_parser = argparse.ArgumentParser(
        prog='west', description='The Zephyr RTOS meta-tool.',
        epilog='Run "west <command> -h" for help on each command.')
    west_parser.add_argument('-z', '--zephyr-base', default=None,
                             help='''Path to the Zephyr base directory. If not
                             given, ZEPHYR_BASE must be defined in the
                             environment, and will be used instead.''')
    west_parser.add_argument('-v', '--verbose', default=0, action='count',
                             help='''Display verbose output. May be given
                             multiple times to increase verbosity.''')
    west_parser.add_argument('-V', '--version', action='store_true')
    subparser_gen = west_parser.add_subparsers(title='commands',
                                               dest='command')

    for command in COMMANDS:
        parser = command.add_parser(subparser_gen)
        parser.set_defaults(handler=partial(command_handler, command))

    args, unknown = west_parser.parse_known_args(args=argv)

    if args.version:
        log.inf('West bootstrapper version: v{} ({})'.format(version.__version__,
                                           os.path.dirname(version.___file__)))
        log.inf('West bootstrapper version:', version.__version__)
        try:
            git_describe = check_output(['git', 'describe', '--tags'],
                                        stderr=DEVNULL,
                                        cwd=os.path.dirname(__file__)).decode(
                                            sys.getdefaultencoding()).strip()
            print('West repository version:{} ({})'.format(git_describe,
                                                    os.path.dirname(__file__)))
        except CalledProcessError as e:
            print('West repository version: unknown, no tags found')
        sys.exit(0)

    # Set up logging verbosity before doing anything else, so
    # e.g. verbose messages related to argument handling errors
    # work properly.
    log.set_verbosity(args.verbose)

    try:
        validate_context(args, unknown)
    except InvalidWestContext as iwc:
        log.err(*iwc.args, fatal=True)
        west_parser.print_usage(file=sys.stderr)
        sys.exit(1)

    if 'handler' not in args:
        log.err('you must specify a command', fatal=True)
        west_parser.print_usage(file=sys.stderr)
        sys.exit(1)

    return args, unknown


def main(argv=None):
    # Makes ANSI color escapes work on Windows, and strips them when
    # stdout/stderr isn't a terminal
    colorama.init()

    if argv is None:
        argv = sys.argv[1:]
    args, unknown = parse_args(argv)

    for_stack_trace = 'run as "west -v ... {} ..." for a stack trace'.format(
        args.command)
    try:
        args.handler(args, unknown)
    except WestUpdated:
        # West has been automatically updated. Restart ourselves to run the
        # latest version, with the same arguments that we were given.
        os.execv(sys.executable, [sys.executable] + sys.argv)
    except KeyboardInterrupt:
        sys.exit(0)
    except CalledProcessError as cpe:
        log.err('command exited with status {}: {}'.format(
            cpe.args[0], quote_sh_list(cpe.args[1])))
        if args.verbose:
            raise
        else:
            log.inf(for_stack_trace)
    except CommandContextError as cce:
        log.die('command', args.command, 'cannot be run in this context:',
                *cce.args)
    except Exception as exc:
        log.err(*exc.args, fatal=True)
        if args.verbose:
            raise
        else:
            log.inf(for_stack_trace)

if __name__ == "__main__":
    main()
