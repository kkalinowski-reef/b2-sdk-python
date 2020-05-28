######################################################################
#
# File: b2sdk/sync/scan_policies.py
#
# Copyright 2019 Backblaze Inc. All Rights Reserved.
#
# License https://www.backblaze.com/using_b2_code.html
#
######################################################################

import logging
import re

logger = logging.getLogger(__name__)


class RegexSet(object):
    """
    Hold a (possibly empty) set of regular expressions and know how to check
    whether a string matches any of them.
    """

    def __init__(self, regex_iterable):
        """
        :param regex_iterable: an interable which yields regexes
        """
        self._compiled_list = [re.compile(r) for r in regex_iterable]

    def matches(self, s):
        """
        Check whether a string matches any of regular expressions.

        :param s: a string to check
        :type s: str
        :rtype: bool
        """
        return any(c.match(s) is not None for c in self._compiled_list)


def convert_dir_regex_to_dir_prefix_regex(dir_regex):
    """
    The patterns used to match directory names (and file names) are allowed
    to match a prefix of the name.  This 'feature' was unintentional, but is
    being retained for compatibility.

    This means that a regex that matches a directory name can't be used directly
    to match against a file name and test whether the file should be excluded
    because it matches the directory.

    The pattern 'photos' will match directory names 'photos' and 'photos2',
    and should exclude files 'photos/kitten.jpg', and 'photos2/puppy.jpg'.
    It should not exclude 'photos.txt', because there is no directory name
    that matches.

    On the other hand, the pattern 'photos$' should match 'photos/kitten.jpg',
    but not 'photos2/puppy.jpg', nor 'photos.txt'

    If the original regex is valid, there are only two cases to consider:
    either the regex ends in '$' or does not.

    :param dir_regex: a regular expression string or literal
    :type dir_regex: str
    """
    if dir_regex.endswith('$'):
        return dir_regex[:-1] + r'/'
    else:
        return dir_regex + r'.*?/'


class IntegerRange(object):
    """
    Hold a range of two integers. If the range value is None, it indicates that
    the value should be treated as -Inf (for begin) or +Inf (for end).
    """

    def __init__(self, begin, end):
        """
        :param begin: begin position of the range (included)
        :type begin: int
        :param end: end position of the range (included)
        :type end: int
        """
        self._begin = begin
        self._end = end

    def __contains__(self, item):
        ge_begin, le_end = True, True

        if self._begin is not None:
            ge_begin = item >= self._begin
        if self._end is not None:
            le_end = item <= self._end

        return ge_begin and le_end


class ScanPoliciesManager(object):
    """
    Policy object used when scanning folders for syncing, used to decide
    which files to include in the list of files to be synced.

    Code that scans through files should at least use should_exclude_file()
    to decide whether each file should be included; it will check include/exclude
    patterns for file names, as well as patterns for excluding directories.

    Code that scans may optionally use should_exclude_directory() to test whether
    it can skip a directory completely and not bother listing the files and
    sub-directories in it.
    """

    def __init__(
        self,
        exclude_dir_regexes=tuple(),
        exclude_file_regexes=tuple(),
        include_file_regexes=tuple(),
        exclude_all_symlinks=False,
        exclude_modified_before=None,
        exclude_modified_after=None,
    ):
        """
        :param exclude_dir_regexes: a tuple of regexes to exclude directories
        :type exclude_dir_regexes: tuple
        :param exclude_file_regexes: a tuple of regexes to exclude files
        :type exclude_file_regexes: tuple
        :param include_file_regexes: a tuple of regexes to include files
        :type include_file_regexes: tuple
        :param exclude_all_symlinks: if True, exclude all symlinks
        :type exclude_all_symlinks: bool
        :param exclude_modified_before: optionally exclude file versions modified before (in millis)
        :type exclude_modified_before: int, optional
        :param exclude_modified_after: optionally exclude file versions modified after (in millis)
        :type exclude_modified_after: int, optional
        """
        self._exclude_dir_set = RegexSet(exclude_dir_regexes)
        self._exclude_file_because_of_dir_set = RegexSet(
            map(convert_dir_regex_to_dir_prefix_regex, exclude_dir_regexes)
        )
        self._exclude_file_set = RegexSet(exclude_file_regexes)
        self._include_file_set = RegexSet(include_file_regexes)
        self.exclude_all_symlinks = exclude_all_symlinks
        self._include_mod_time_range = IntegerRange(exclude_modified_before, exclude_modified_after)

    def should_exclude_file(self, file_path):
        """
        Given the full path of a file, decide if it should be excluded from the scan.

        :param file_path: the path of the file, relative to the root directory
                          being scanned.
        :type: str
        :return: True if excluded.
        :rtype: bool
        """
        exclude_because_of_dir = self._exclude_file_because_of_dir_set.matches(file_path)
        exclude_because_of_file = (
            self._exclude_file_set.matches(file_path) and
            not self._include_file_set.matches(file_path)
        )
        return exclude_because_of_dir or exclude_because_of_file

    def should_exclude_file_version(self, mod_time_millis):
        """
        Given the modification time of a file or file version,
        decide if it should be excluded from the scan.

        :param mod_time_millis: the modification time of the file.
        :type: int
        :return: True if excluded.
        :rtype: bool
        """
        return mod_time_millis not in self._include_mod_time_range

    def should_exclude_directory(self, dir_path):
        """
        Given the full path of a directory, decide if all of the files in it should be
        excluded from the scan.

        :param dir_path: the path of the directory, relative to the root directory
                         being scanned.  The path will never end in '/'.
        :type dir_path: str
        :return: True if excluded.
        """
        return self._exclude_dir_set.matches(dir_path)


DEFAULT_SCAN_MANAGER = ScanPoliciesManager()
