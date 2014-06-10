# -*- coding: utf-8 -*-

#   This file is part of periscope.
#   Copyright (c) 2008-2011 Patrick Dessalle <patrick@dessalle.be>
#
#    periscope is free software; you can redistribute it and/or modify
#    it under the terms of the GNU Lesser General Public License as published
#    by the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#
#    periscope is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Lesser General Public License for more details.
#
#    You should have received a copy of the GNU Lesser General Public License
#    along with periscope; if not, write to the Free Software
#    Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

import os
import logging
import zipfile
import struct
import re
# from abc import ABCMeta, abstractmethod, abstractproperty

LOG = logging.getLogger(__name__)


# TODO : make the class abstract
class SubtitleDB(object):

    """ Abstract class that represent a SubtitleDB, usually a website. """

    # __metaclass__ = ABCMeta

    site_name = "Overwrite to name the module"

    def __init__(self, langs, revertlangs=None):
        """ Init method with a list of language as argument. """
        if langs:
            self.langs = langs
            self.revertlangs = dict(map(lambda item: (item[1], item[0]),
                                        self.langs.items()))
        if revertlangs:
            self.revertlangs = revertlangs
            self.langs = dict(map(lambda item: (item[1], item[0]),
                                  self.revertlangs.items()))
        self.tvshowRegex = re.compile(('(?P<show>.*)S(?P<season>[0-9]{2})'
                                       'E(?P<episode>[0-9]{2}).(?P<teams>.*)'),
                                      re.IGNORECASE)
        self.tvshowRegex2 = re.compile(('(?P<show>.*).(?P<season>[0-9]{1,2})x('
                                        '?P<episode>[0-9]{1,2})'
                                        '(?P<teams>.*)'), re.IGNORECASE)
        self.movieRegex = re.compile(('(?P<movie>.*)[\.|\[|\(| ]{1}'
                                      '(?P<year>(?:(?:19|20)[0-9]{2}))'
                                      '(?P<teams>.*)'), re.IGNORECASE)

    def search_in_thread(self, queue, filename, langs):
        """ Append subtitles to the queue. """
        try:
            subs = self.process(filename, langs)
            for sub in subs:
                sub.setdefault("plugin", self)
                sub.setdefault("filename", filename)
            LOG.info("{} writing {} items to queue".format(self, len(subs)))
        except:
            LOG.exception("Error occured")
            subs = []
        # Each plugin must write something
        # The caller periscope.py waits for a result on the queue
        queue.put(subs, True)

    def create_file(self, subtitle):
        """ Download subtile, unzip and create the subtitle file. """
        suburl = subtitle["link"]
        videofilename = subtitle["filename"]
        srtbasefilename = videofilename.rsplit(".", 1)[0]
        zipfilename = srtbasefilename + ".zip"
        self.downloadFile(suburl, zipfilename)

        if zipfile.is_zipfile(zipfilename):
            LOG.debug("Unzipping file " + zipfilename)
            unzipped_file = zipfile.ZipFile(zipfilename, "r")

            for elem in unzipped_file.infolist():
                extension = elem.orig_filename.rsplit(".", 1)[1]
                if extension in ("srt", "sub", "txt"):
                    outfile = open(srtbasefilename + "." +
                                   extension, "wb")
                    outfile.write(unzipped_file.read(elem.orig_filename))
                    outfile.flush()
                    outfile.close()
                else:
                    LOG.info("File {} does not seem to be valid ".
                             format(elem.orig_filename))
            # Deleting the zip file
            unzipped_file.close()
            os.remove(zipfilename)
            return srtbasefilename + ".srt"
        else:
            LOG.info("Unexpected file type (not zip)")
            os.remove(zipfilename)
            return None

    def get_lang(self, language):
        """ Return a language two character code from its long naming. """
        try:
            return self.revertlangs[language]
        except KeyError:
            LOG.warn(("Ooops, you found a missing language in the config file"
                      " of {}: {}. Send a bug report to have it added.".
                      format(self.__class__.__name__, language)))

    def get_language(self, lang):
        """ Return a language long naming from its two character code. """
        try:
            return self.langs[lang]
        except KeyError:
            LOG.warn(("Ooops, you found a missing language in the config file"
                      " of {}: {}. Send a bug report to have it added.".
                      format(self.__class__.__name__, lang)))

    # @abstractmethod
    def process(self, filepath, langs):
        """ Dowload the subtiles for a file in the wanted languages. """
        pass

    # @abstractmethod
    def query(self, token):
        """ Behaviour not understood. """
        pass

    # @abstractmethod
    def get_available_subtitles(self, file_path):
        """ Return a list of available subtitles. """
        pass

    # @abstractmethod
    def post_process_results(self, subtitles):
        """ Postprocess the raw result to fit to a common pattern. """
        pass

    def guess_file_data(self, filename):
        """ Return the more relevent information for the file name. """
        filename = unicode(self.getFileName(filename).lower())
        matches_tvshow = self.tvshowRegex.match(filename)
        if not matches_tvshow:  # we try the second regex
            matches_tvshow = self.tvshowRegex2(filename)
        if matches_tvshow:  # It looks like a tv show
            (tvshow, season, episode, teams) = matches_tvshow.groups()
            tvshow = tvshow.replace(".", " ").strip()
            teams = teams.split('.')
            return {'type': 'tvshow',
                    'name': tvshow.strip(),
                    'season': int(season),
                    'episode': int(episode),
                    'teams': teams}

        matches_movie = self.movieRegex.match(filename)
        if matches_movie:  # It looks like a movie
            (movie, year, teams) = matches_movie.groups()
            teams = teams.split('.')
            part = None
            if "cd1" in teams:
                teams.remove('cd1')
                part = 1
            if "cd2" in teams:
                teams.remove('cd2')
                part = 2
                return {'type': 'movie',
                        'name': movie.strip(),
                        'year': year,
                        'teams': teams,
                        'part': part}
        # No relevant information were found from the file name
        return {'type': 'unknown', 'name': filename, 'teams': []}

    def hash_file(self, file_path):
        """ Return the hash of the file as used by OpenSubtitles.

        The method is defined on OpenSubtitles API (link below)
        http://trac.opensubtitles.org/projects/opensubtitles/
        wiki/HashSourceCodes#Python
        """
        try:
            longlongformat = 'q'  # long long
            bytesize = struct.calcsize(longlongformat)

            input_file = open(file_path, "rb")
            file_size = os.path.getsize(file_path)
            file_hash = file_size

            if file_size < 65536 * 2:
                return "SizeError"

            for _ in range(65536 / bytesize):
                file_buffer = input_file.read(bytesize)
                (l_value,) = struct.unpack(longlongformat, file_buffer)
                file_hash += l_value
                file_hash = file_hash & 0xFFFFFFFFFFFFFFFF

            input_file.seek(max(0, file_size - 65536), 0)
            for _ in range(65536 / bytesize):
                file_buffer = input_file.read(bytesize)
                (l_value,) = struct.unpack(longlongformat, file_buffer)
                file_hash += l_value
                file_hash = file_hash & 0xFFFFFFFFFFFFFFFF

            input_file.close()
            return "%016x" % file_hash

        except(IOError):
            return "IOError"

    def __str__(self):
        """ Overwrite, return the name of the service. """
        return self.site_name.__str__()


class InvalidFileException(Exception):

    """ Exception object to be raised when the file is invalid. """

    def __init__(self, filename, reason):
        """ Init function with a filename and a reason as parameters. """
        self.filename = filename
        self.reason = reason

    def __str__(self):
        """ Overwrite of the __str__ method. """
        return (repr(self.filename), repr(self.reason))
