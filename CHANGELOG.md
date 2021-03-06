# Changelog

## [0.10] 2019-08-11

* add `-H` option to print human-readable dates in `--all` summary
* bump SQLAlchemy version

## [0.9] 2019-07-01

* bump SQLAlchemy version
* `--summary` replaces `--detail`; using both `--summary` and `--detail` replicates previous behavior

## [0.8] 2019-02-18

* Add `--dry-run` option (for --tar-latest)
* `--update` deletes backups from SQL that are not present in the borg repo

## [0.7] 2019-02-11

* `--start-times` only shows HH:MM and now follows `--detail` output
* Bugfix

## [0.6] 2019-02-09

* Add `--tar-latest` argument

## [0.5] 2019-02-08

* Add `--overlap-days` option
* `--start-times` option has its own option; `--check-overlap` no longer prints start times
* Fix bug where "size (GB)" always ended in `.0`
* Other bugfixes

## [0.4] 2019-01-23

* Add `--check-overlap` which prints a warning if any backups overlap in time (i.e., running simultaneously).
* `--check-overlap` prints a table of all start times if any backups overlap
* Removed color from error output

## [0.3] 2019-01-12

* Fix checking for borg repos being locked / unable to be read.
* Don't do a `borg info` every time we just want to get the repo ID.
* Add `--short-names` option which makes repo names in reports more succinct.
* Add optional config file and configurable warn-if-older-than-X-hours per-repo settings.
* Changed "warn_days" to "warn_hours"
* `--check` warns if no backups for over 30 hours (instead of 24) to give the backups a little time to finish, assuming the check is running once per day.

## [0.2] 2019-01-11

* Use borg's JSON "API" (`--json`).
* Instead of storing backup info in CSV files, store in a SQLite database using SQLAlchemy.
* Require `tabulate` and `sqlalchemy`.
* Remove `borgsummary-all.py` - its functionality is incorporated into `borgsummary.py`

## [0.1] 2019-01-06

* Read & write CSV data files containing backup info for each host.
* Better error checking from borg output.
* Add `borgsummary-all` which prints a very succinct summary of all backup repos, and optionally details about every repo.
* Split into two scripts; `borgsummary` reports on just one borg backup; `borgsummary-all` is a wrapper script which handles multiple borg repos.
* Created BorgBackupRepo class to better encapsulate the data in a borg backup repo.
* Because it's no longer applicable, removed `--first` option.

## [Initial version]

* Prints a simple summary of multiple borg backup repositories.
