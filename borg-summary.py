#!/usr/bin/env python3

"""
borg-summary.py

Copyright 2019  John Begenisich

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

import os
from pathlib import Path
import glob
import subprocess
import argparse
import csv
import datetime


BORG_ENV = os.environ.copy()
# TODO: possibly want these configureable
BORG_ENV['BORG_RELOCATED_REPO_ACCESS_IS_OK'] = 'yes'
BORG_ENV['BORG_UNKNOWN_UNENCRYPTED_REPO_ACCESS_IS_OK'] = 'yes'

BACKUP_FIELDS = ['backup_name', 'start_time', 'end_time', 'num_files', 'original_size',
                 'dedup_size', 'all_original_size', 'all_dedup_size', 'command_line']


def get_xdg():
    """
    Return a Path to the XDG_DATA_HOME for borg-summary.
    """
    if 'XDG_DATA_HOME' in os.environ:
        return os.environ['XDG_DATA_HOME'] / '.local' / 'share' / 'borg-summary'
    return Path.home() / '.local' / 'share' / 'borg-summary'


def print_error(message, stdout=None, stderr=None):
    """
    Print an error, optionally include stdout and/or stderr strings, using red for error.
    """
    # TODO: color should be optional
    print(f'\033[0;31m{message}\033[0m')
    if stdout or stderr:
        print('output from borg follows:')
        if stdout:
            print(stdout.decode().strip())
        if stderr:
            print('\033[0;31m{}\033[0m'.format(stderr.decode().strip()))


def get_backup_list(path):
    """
    Return a list of backups in <path> that get be queried with "borg info".
    Returns None if the directory is locked by borgbackup.
    Exits with 1 on error from borg.
    """
    # check for lock file
    if (Path(path) / 'lock.exclusive').exists():
        return None
    result = subprocess.run(['borg', 'list', '--short', str(path)],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            env=BORG_ENV)
    if result.returncode != 0:
        print_error('Error running: {}'.format(' '.join(result.args)), result.stdout, result.stderr)
        exit(1)
    backup_list = []
    for line in result.stdout.decode().split('\n'):
        # there is a blank newline at the end
        if line:
            backup_list.append(line)
    return backup_list


def get_backup_info(path, backup_name):
    """
    Returns a dictionary describing borg backup <backup_name> in <path>.
    Exits with 1 on error from borg.
    {
        'start_time': datetime,
        'end_time': datetime,
        'num_files': int,
        'original_size': str,
        'dedup_size': str,
        'all_original_size': str,
        'all_dedup_size': str,
        'command_line': str,
    }
    """
    result = subprocess.run(['borg', 'info', f'{path}::{backup_name}'],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            env=BORG_ENV)
    if result.returncode != 0:
        print_error('Error running "{}"'.format(' '.join(result.args)), result.stdout, result.stderr)
        exit(1)
    borg_info = {'backup_name': backup_name}
    lines = result.stdout.decode().split('\n')
    for line in lines:
        s = line.split()
        if line.startswith('Time (start):'):
            borg_info['start_time'] = datetime.datetime.strptime('{} {}'.format(s[3], s[4]), '%Y-%m-%d %H:%M:%S')
        elif line.startswith('Time (end):'):
            borg_info['end_time'] = datetime.datetime.strptime('{} {}'.format(s[3], s[4]), '%Y-%m-%d %H:%M:%S')
        elif line.startswith('Number of files:'):
            borg_info['num_files'] = int(s[3])
        elif line.startswith('This archive:'):
            borg_info['original_size'] = '{} {}'.format(s[2], s[3])
            borg_info['dedup_size'] = '{} {}'.format(s[6], s[7])
        elif line.startswith('All archives:'):
            borg_info['all_original_size'] = '{} {}'.format(s[2], s[3])
            borg_info['all_dedup_size'] = '{} {}'.format(s[6], s[7])
        elif line.startswith('Command line:'):
            borg_info['command_line'] = line[14:]
    return borg_info


def write_backup_data_file(borg_path, data_filename):
    """
    Create a CSV file containing a list of backups for a borg repository,
    overwriting if it already exists.  Skip if borg has locked the repo
    (i.e., a backup is running).
    borg_path: the path to a borg backup pool
    data_filename: the Path to a CSV file describing the backup sets
    """
    backup_names = get_backup_list(borg_path)
    if not backup_names:  # either None - locked by borg; or [] - no backups
        return
    with open(data_filename, 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, BACKUP_FIELDS)
        writer.writeheader()
        for backup_name in backup_names:
            writer.writerow(get_backup_info(borg_path, backup_name))


def read_backup_data_file(data_filename):
    """
    Return a list of dicts representing the backups in a borg repository.
    See get_backup_info() for the dict format.
    data_filename: the Path to a CSV file describing the backup sets
    """
    backup_list = []
    with open(data_filename) as csvfile:
        reader = csv.DictReader(csvfile, BACKUP_FIELDS)
        next(reader, None)  # skip header
        for row in reader:
            row['start_time'] = datetime.datetime.strptime(row['start_time'], '%Y-%m-%d %H:%M:%S')
            row['end_time'] = datetime.datetime.strptime(row['end_time'], '%Y-%m-%d %H:%M:%S')
            backup_list.append(row)
    return backup_list


def get_data_file_age(data_filename):
    """
    Returns an int representing the age of data_filename in number of minutes.
    """
    mtime = datetime.datetime.fromtimestamp(data_filename.stat().st_mtime)
    deltat = datetime.datetime.now() - mtime
    return int(deltat.days * 1440 + deltat.seconds / 60)


def check_data_file_age(data_filename):
    """
    Print a warning if Path data_filename is older than 24 hours.
    """
    print(get_data_file_age(data_filename))



# -----

def main():
    """
    main
    """
    parser = argparse.ArgumentParser(description='Print a summary of a borgbackup repository',
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('path', help='The path to a borgbackup repository')
    parser.add_argument('--csv', type=str, default=None,
                        help='The path to a CSV file holding backup info; generated automatically if not specified.')
    parser.add_argument('--data-path', type=str, default=Path.home() / 'borg-summary',
                        help='The path to CSV data files holding backup info; default: {}'.format(Path.home() / 'borg-summary'))
    parser.add_argument('--update', action='store_true', default=False, help='Create CSV data file')
    parser.add_argument('--autoupdate', action='store_true', default=False,
                        help='Create CSV data file if currente data file is older than 24 hours.')
    parser.add_argument('--check', action='store_true', default=False,
                        help='Print a warning if the CSV data file is older than 24 hours.')
    args = parser.parse_args()

    borg_path = Path(args.path)
    if not borg_path.is_dir():
        print(f'{borg_path} not found!')
        exit(1)

    if args.csv:
        data_path = Path(args.csv)
        backup_name = args.csv
    else:
        data_path = get_xdg() / borg_path.parent.name / (borg_path.name + '.csv')
        backup_name = f'{borg_path.parent.name} - {borg_path.name}'

    if not data_path.parent.is_dir():
        os.makedirs(data_path.parent)

    if args.update:
        write_backup_data_file(borg_path, data_path)

    if args.autoupdate:
        if not data_path.is_file() or get_data_file_age(data_path) > 1440:
            write_backup_data_file(borg_path, data_path)

    backups = read_backup_data_file(data_path)

    print(backup_name)
    print('-' * len(backup_name))

    print('\nCommand line: {}\n'.format(backups[-1]['command_line']))

    print('Size of all backups:              {:>10s}'.format(backups[-1]['all_original_size']))
    print('Deduplicated size of all backups: {:>10s}'.format(backups[-1]['all_dedup_size']))
    result = subprocess.check_output('du -sh {}'.format(borg_path), shell=True)
    print('Actual size on disk:              {:>10s}'.format(result.decode().split()[0]))
    print()
    print('{:<16s}  {:<16s}  {:>10s}  {:>10s}  {:>10s}'.format('Start time', 'End time', '# files', 'Orig size', 'Dedup size'))
    print('{:<16s}  {:<16s}  {:>10s}  {:>10s}  {:>10s}'.format('----------', '--------', '-------', '---------', '----------'))
    for d in backups:
        print('{:%Y-%m-%d %H:%M}  {:%Y-%m-%d %H:%M}  {:>10s}  {:>10s}  {:>10s}'.format(d['start_time'], d['end_time'], d['num_files'], d['original_size'], d['dedup_size']))
    print()


if __name__ == '__main__':
    main()
