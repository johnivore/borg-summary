# Changelog

## [unrealed]

### Removed

* Removed color from error output

## [0.3]

### Added

* Fix checking for borg repos being locked / unable to be read.
* Don't do a `borg info` every time we just want to get the repo ID.
* Add `--short-names` option which makes repo names in reports more succinct.
* Add optional config file and configurable warn-if-older-than-X-hours per-repo settings.

### Changed

* Changed "warn_days" to "warn_hours"
* `--check` warns if no backups for over 30 hours (instead of 24) to give the backups a little time to finish, assuming the check is running once per day.

## [0.2]

### Changed

* Use borg's JSON "API" (`--json`).
* Instead of storing backup info in CSV files, store in a SQLite database using SQLAlchemy.
* Require `tabulate` and `sqlalchemy`.

### Removed

* Remove `borgsummary-all.py` - its functionality is incorporated into `borgsummary.py`

## [0.1]

### Added

* Read & write CSV data files containing backup info for each host.
* Better error checking from borg output.
* Add `borgsummary-all` which prints a very succinct summary of all backup repos, and optionally details about every repo.

### Changed

* Split into two scripts; `borgsummary` reports on just one borg backup; `borgsummary-all` is a wrapper script which handles multiple borg repos.
* Created BorgBackupRepo class to better encapsulate the data in a borg backup repo.

### Removed

* Because it's no longer applicable, removed `--first` option.

## [Initial version]

* Prints a simple summary of multiple borg backup repositories.
