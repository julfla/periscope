#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Plugin to enable periscope to donwload subtiles from OpenSubtitles. """

import os
import xmlrpclib
import logging
import socket  # For timeout purposes
import gzip
from periscope.helper import download_file
from periscope.plugins.SubtitleDatabase import SubtitleDB

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

    def __init__(self, config, cache_path):
        """ Overwrite the default constuctor. """
        super(OpenSubtitles, self).__init__(OS_LANGS)
        self.server = xmlrpclib.Server(self.server_url)
        response = self.server.LogIn("", "", "eng", "periscope")
        LOG.debug('LogIn : {}'.format(response))
        socket.setdefaulttimeout(10)
        self.token = response['token']

    def __del__(self):
        """ Logout from the service on destuction. """
        if self.token is not None:
            response = self.server.LogOut(self.token)
            LOG.debug('LogOut : {}'.format(response))
        socket.setdefaulttimeout(None)

    def process(self, file_path, langs):
        """ Get a list of subtitles in the wanted languages. """
        LOG.info("Processing {} for languages {}".format(file_path, langs))
        langs_id = ",".join([self.get_language(lang) for lang in langs])
        search_params = {'moviehash': self.hash_file(file_path),
                         'moviebytesize': os.path.getsize(file_path),
                         # 'file_basename': file_basename(file_path),
                         'sublanguageid': langs_id}
        try:
            LOG.debug("Querying with arguments : {}".format(search_params))
            response = self.server.SearchSubtitles(self.token, [search_params])
            LOG.debug("status: {}, {} subtitles".
                      format(response['status'], len(response['data'])))
        except Exception, err:
            LOG.error("Could not query the server OpenSubtitles")
            LOG.debug(err)
            return []
        return self.post_process_results(response['data'])

    def create_file(self, subtitle):
        """ Download the subtitle and unzip to to the .srt file. """
        suburl = subtitle["link"]
        videofilename = subtitle["filename"]
        srtbasefilename = videofilename.rsplit(".", 1)[0]
        download_file(suburl, srtbasefilename + ".srt.gz", LOG)
        srt_file = gzip.open(srtbasefilename + ".srt.gz")
        dump = open(srtbasefilename + ".srt", "wb")
        dump.write(srt_file.read())
        dump.close()
        srt_file.close()
        os.remove(srtbasefilename + ".srt.gz")
        return srtbasefilename + ".srt"

    def post_process_results(self, data):
        """ Postprocessing. See details in SubtitleDB class. """
        for sub in data:
            sub["release"] = sub.pop('SubFileName')
            sub["link"] = sub.pop('SubDownloadLink')
            sub["page"] = sub["link"]
            sub["lang"] = self.get_lang(sub.pop('SubLanguageID'))
        return data
