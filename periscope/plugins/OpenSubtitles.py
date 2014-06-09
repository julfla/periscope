# -*- coding: utf-8 -*-

#   This file is part of periscope.
#   Copyright (c) 2008-2011 Patrick Dessalle <patrick@dessalle.be>
#
#    periscope is free software; you can redistribute it and/or modify
#    it under the terms of the GNU Lesser General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
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
import xmlrpclib
import logging
import socket  # For timeout purposes
import gzip
from periscope.helper import download_file
# import struct
# import commands
# import traceback

from SubtitleDatabase import SubtitleDB

LOG = logging.getLogger(__name__)

# TODO : get this hash from OpenSubtitle itself and cache it.
OS_LANGS = {"en": "eng",
            "fr": "fre",
            "hu": "hun",
            "cs": "cze",
            "pl": "pol",
            "sk": "slo",
            "pt": "por",
            "pt-br": "pob",
            "es": "spa",
            "el": "ell",
            "ar": "ara",
            "sq": "alb",
            "hy": "arm",
            "ay": "ass",
            "bs": "bos",
            "bg": "bul",
            "ca": "cat",
            "zh": "chi",
            "hr": "hrv",
            "da": "dan",
            "nl": "dut",
            "eo": "epo",
            "et": "est",
            "fi": "fin",
            "gl": "glg",
            "ka": "geo",
            "de": "ger",
            "he": "heb",
            "hi": "hin",
            "is": "ice",
            "id": "ind",
            "it": "ita",
            "ja": "jpn",
            "kk": "kaz",
            "ko": "kor",
            "lv": "lav",
            "lt": "lit",
            "lb": "ltz",
            "mk": "mac",
            "ms": "may",
            "no": "nor",
            "oc": "oci",
            "fa": "per",
            "ro": "rum",
            "ru": "rus",
            "sr": "scc",
            "sl": "slv",
            "sv": "swe",
            "th": "tha",
            "tr": "tur",
            "uk": "ukr",
            "vi": "vie"}


class OpenSubtitles(SubtitleDB):

    """ Module to download subtitles from OpenSubtitles. """

    url = "http://www.opensubtitles.org/"
    site_name = "OpenSubtitles"
    server_url = 'http://api.opensubtitles.org/xml-rpc'
    server = xmlrpclib.Server('http://api.opensubtitles.org/xml-rpc')
    token = None  # token used in the api

    def __init__(self, arg, arg2):
        """ Overwrite the default constuctor. """
        super(OpenSubtitles, self).__init__(OS_LANGS)
        response = self.server.LogIn("", "", "eng", "periscope")
        LOG.debug('LogIn : %s' % response)
        socket.setdefaulttimeout(10)
        self.token = response['token']

    def __del__(self):
        """ Logout from the service on destuction. """
        if self.token is not None:
            response = self.server.LogOut(self.token)
            LOG.debug('LogOut : %s' % response)
        socket.setdefaulttimeout(None)

    def process(self, file_path, langs):
        """ Get a list of subtitles for the file in the wanted languages. """
        LOG.info("Processing {} for languages {}".format(file_path, langs))
        langs_id = ",".join([self.getLanguage(lang) for lang in langs])
        search_params = {'moviehash': self.hashFile(file_path),
                         'moviebytesize': os.path.getsize(file_path),
                         # 'file_basename': file_basename(file_path),
                         'sublanguageid': langs_id}
        try:
            LOG.debug("Querying with arguments : {}".format(search_params))
            response = self.server.SearchSubtitles(self.token, [search_params])
            LOG.debug("status: {}, {} subtitles".
                      format(response['status'], len(response['data'])))
        except Exception, e:
            LOG.error("Could not query the server OpenSubtitles")
            LOG.debug(e)
            return []
        return self.post_process_results(response['data'])

    def createFile(self, subtitle):
        """ Download the subtitle and unzip to to the .srt file. """
        suburl = subtitle["link"]
        videofilename = subtitle["filename"]
        srtbasefilename = videofilename.rsplit(".", 1)[0]
        download_file(suburl, srtbasefilename + ".srt.gz", LOG)
        f = gzip.open(srtbasefilename+".srt.gz")
        dump = open(srtbasefilename+".srt", "wb")
        dump.write(f.read())
        dump.close()
        f.close()
        os.remove(srtbasefilename+".srt.gz")
        return srtbasefilename+".srt"

    def post_process_results(self, data):
        """ Postprocessing. See details in SubtitleDB class. """
        for sub in data:
            sub["release"] = sub.pop('SubFileName')
            sub["link"] = sub.pop('SubDownloadLink')
            sub["page"] = sub["link"]
            sub["lang"] = self.getLG(sub.pop('SubLanguageID'))
        return data

    # def sort_by_moviereleasename(self, x, y):
    #     ''' sorts based on the movierelease name tag. More matching, returns 1'''
    #     #TODO add also support for subtitles release
    #     xmatch = x['MovieReleaseName'] and (x['MovieReleaseName'].find(self.filename)>-1 or self.filename.find(x['MovieReleaseName'])>-1)
    #     ymatch = y['MovieReleaseName'] and (y['MovieReleaseName'].find(self.filename)>-1 or self.filename.find(y['MovieReleaseName'])>-1)
    #     #print "analyzing %s and %s = %s and %s" %(x['MovieReleaseName'], y['MovieReleaseName'], xmatch, ymatch)
    #     if xmatch and ymatch:
    #         if x['MovieReleaseName'] == self.filename or x['MovieReleaseName'].startswith(self.filename) :
    #             return -1
    #         return 0
    #     if not xmatch and not ymatch:
    #         return 0
    #     if xmatch and not ymatch:
    #         return -1
    #     if not xmatch and ymatch:
    #         return 1
    #     return 0
