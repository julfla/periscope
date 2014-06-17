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

import zipfile
import os
import urllib2
import urllib
import logging
import traceback
import httplib

from BeautifulSoup import BeautifulSoup

from periscope.helper import USER_AGENT, get_file_name
from periscope.plugins.SubtitleDatabase import SubtitleDB

LOG = logging.getLogger(__name__)

SS_LANGUAGES = {"en": "English",
        "se": "Swedish",
        "da": "Danish",
        "fi": "Finnish",
        "no": "Norwegian",
        "fr": "French",
        "es": "Spanish",
        "is": "Icelandic",
        "cs": "Czech",
        "bg": "Bulgarian",
        "de": "German",
        "ar": "Arabic",
        "el": "Greek",
        "fa": "Farsi/Persian",
        "nl": "Dutch",
        "he": "Hebrew",
        "id": "Indonesian",
        "ja": "Japanese",
        "vi": "Vietnamese",
        "pt": "Portuguese",
        "ro": "Romanian",
        "tr": "Turkish",
        "sr": "Serbian",
        "pt-br": "Brazillian Portuguese",
        "ru": "Russian",
        "hr": "Croatian",
        "sl": "Slovenian",
        "zh": "Chinese BG code",
        "it": "Italian",
        "pl": "Polish",
        "ko": "Korean",
        "hu": "Hungarian",
        "ku": "Kurdish",
        "et": "Estonian"}


class SubScene(SubtitleDB):

    """ Class to download subtitles from SubScene """

    url = "http://subscene.com/"
    site_name = "SubScene"

    def __init__(self, config, cache_path):
        super(SubScene, self).__init__(SS_LANGUAGES)
        self.host = "http://subscene.com/s.aspx?subtitle="

    def process(self, filepath, langs):
        """ Calls the plugin, passes the filename and the wished
        languages the  query the subtitles source """
        fname = get_file_name(filepath)
        try:
            subs = self.query(fname, langs)
            if not subs and fname.rfind(".[") > 0:
                # Try to remove the [VTV] or [EZTV] at the end of the file
                teamless_filename = fname[0: fname.rfind(".[")]
                subs = self.query(teamless_filename, langs)
            return subs
        except Exception, err:
            logging.error("Error raised by plugin {}: {}".
                format(self.__class__.__name__, err))
            traceback.print_exc()
            return []

    def create_file(self, subtitle):
        """ Pass the URL of the sub and the file it matches, will unzip it
        and return the path to the created file. """

        page = BeautifulSoup(urllib2.urlopen(subtitle["page"]))
        dlhref = page.find("div", {"class": "download"}).find("a")["href"]
        subtitle["link"] = "http://subscene.com" + dlhref.split('"')[7]
        srt_base_filename = subtitle["filename"].rsplit(".", 1)[0]
        archive_filename = srt_base_filename + '.zip'
        self.download_file(subtitle["link"], archive_filename)
        subtitle_filename = None

        if zipfile.is_zipfile(archive_filename):
            LOG.debug("Unzipping file {}".format(archive_filename))
            zip_file = zipfile.ZipFile(archive_filename, "r")
            for elem in zip_file.infolist():
                extension = elem.orig_filename.rsplit(".", 1)[1]
                if extension in ("srt", "sub", "txt"):
                    subtitle_filename = srt_base_filename + "." + extension
                    outfile = open(subtitle_filename, "wb")
                    outfile.write(zip_file.read(elem.orig_filename))
                    outfile.flush()
                    outfile.close()
                else:
                    LOG.info("File {} does not seem to be valid ".
                        format(elem.orig_filename))

            zip_file.close()
            os.remove(archive_filename)
            return subtitle_filename

        elif archive_filename.endswith('.rar'):
            LOG.warn(" Rar is not really supported yet. Trying to call unrar")
            import subprocess
            try:
                output = subprocess.Popen('unrar', 'lb', archive_filename,
                    stdout=subprocess.PIPE).communicate()[0]
                for elem in output.splitlines():
                    extension = elem.rsplit(".", 1)[1]
                    if extension in ("srt", "sub"):
                        subprocess.Popen('unrar', 'e', archive_filename, elem,
                            os.path.dirname(archive_filename))
                        tmp_subtitle_filename = os.path.join(
                            os.path.dirname(archive_filename), elem)
                        srt_base_filename += "." + extension
                        subtitle_filename = os.path.join(os.path.dirname(
                            archive_filename), srt_base_filename)
                        if os.path.exists(tmp_subtitle_filename):
                            # rename it to match the file
                            os.rename(tmp_subtitle_filename, subtitle_filename)
                        return subtitle_filename

            except OSError, err:
                LOG.error("Execution failed: {}".format(err))
                return None

        else:
            LOG.info("Unexpected file type (not zip) for {}".
                format(archive_filename))
            return None

    def download_file(self, url, filename):
        """ Downloads the given url to the given filename """
        LOG.info("Downloading file {}".format(url))
        req = urllib2.Request(url, headers={'Referer': url,
            'User-Agent': USER_AGENT})

        subtitle_file = urllib2.urlopen(req, data=urllib.urlencode({
            '__EVENTTARGET': 's$lc$bcr$downloadLink',
            '__EVENTARGUMENT': '',
            '__VIEWSTATE': '/wEPDwUHNzUxOTkwNWRk4wau5efPqhlBJJlOkKKHN8FIS04='
        }))
        dump = open(filename, "wb")
        try:
            subtitle_file.read(1000000)
        except httplib.IncompleteRead, err:
            dump.write(err.partial)
            LOG.warn('Incomplete read for {} ... Trying anyway to decompress.'.
                format(url))
        dump.close()
        subtitle_file.close()

        #SubtitleDatabase.SubtitleDB.downloadFile(self, req, filename)

    def query(self, token, langs=None):
        """ Makes a query on subscene and returns info (link, lang)
        about found subtitles. """
        sublinks = []

        searchurl = "{}{}".format(self.host, urllib.quote(token))
        LOG.debug(" downloading {}".format(searchurl))
        page = BeautifulSoup(urllib2.urlopen(searchurl))

        for subs in page("a", {"class": "a1"}):
            lang_span = subs.find("span")
            lang = self.get_lang(lang_span.contents[0].strip())
            release_span = lang_span.findNext("span")
            release = release_span.contents[0].strip().split(" (")[0]
            sub_page = subs["href"]
            if release.startswith(token) and (not langs or lang in langs):
                result = {}
                result["release"] = release
                result["lang"] = lang
                result["link"] = None
                result["page"] = "http://subscene.com" + sub_page
                sublinks.append(result)
        return sublinks

    def post_process_results(self, subtitles):
        """ Postprocess the raw result to fit to a common pattern. """
        pass
