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
import urllib2
import urllib
import logging
import hashlib

from periscope.plugins.SubtitleDatabase import SubtitleDB

LOG = logging.getLogger(__name__)

SS_LANGUAGES = {"en": "en",
                "nl": "nl",
                "pt": "pt",
                "pt-br": "pt",
                "no": "Norwegian",
                "fr": "French",
                "es": "Spanish",
                "is": "Icelandic"}


class TheSubDB(SubtitleDB):

    url = "http://thesubdb.com/"
    site_name = "SubDB"
    user_agent = "SubDB/1.0 (periscope/0.1; http://code.google.com/p/periscope)"

    def __init__(self, config, cache_folder_path):
        super(TheSubDB, self).__init__(SS_LANGUAGES)
        self.base_url = 'http://api.thesubdb.com/?{0}'

    def process(self, filepath, langs):
        ''' main method to call on the plugin, pass the filename and the wished
        languages and it will query the subtitles source '''
        # Get the hash
        filehash = self.get_hash(filepath)
        LOG.debug('File hash : {}'.format(filehash))
        # Make the search
        params = {'action': 'search', 'hash': filehash}
        search_url = self.base_url.format(urllib.urlencode(params))
        LOG.debug('Query URL : {}'.format(search_url))
        req = urllib2.Request(search_url)
        req.add_header('User-Agent', self.user_agent)
        subs = []
        try:
            page = urllib2.urlopen(req, timeout=5)
            content = page.readlines()
            plugin_langs = content[0].split(',')
            for lang in plugin_langs:
                if not langs or lang in langs:
                    result = {}
                    result['release'] = filepath
                    result['lang'] = lang
                    result['link'] = self.base_url.format(urllib.urlencode({
                        'action': 'download',
                        'hash': filehash,
                        'language': lang}))
                    result['page'] = result['link']
                    subs.append(result)
            return subs
        except urllib2.HTTPError, err:
            if err.code == 404:  # No result found
                return subs
            else:
                LOG.exception('Error occured : {}'.format(err))

    def get_hash(self, name):
        '''this hash function receives the name of the file and
        returns the hash code'''
        readsize = 64 * 1024
        with open(name, 'rb') as input_file:
            data = input_file.read(readsize)
            input_file.seek(-readsize, os.SEEK_END)
            data += input_file.read(readsize)
        return hashlib.md5(data).hexdigest()

    def create_file(self, subtitle):
        '''pass the URL of the sub and the file it matches, will unzip it
        and return the path to the created file'''
        suburl = subtitle["link"]
        videofilename = subtitle["filename"]
        srtfilename = videofilename.rsplit(".", 1)[0] + '.srt'
        self.download_file(suburl, srtfilename)
        return srtfilename

    def download_file(self, url, srtfilename):
        ''' Downloads the given url to the given filename '''
        req = urllib2.Request(url)
        req.add_header('User-Agent', self.user_agent)

        down_file = urllib2.urlopen(req)
        dump = open(srtfilename, "wb")
        dump.write(down_file.read())
        dump.close()
        down_file.close()
        LOG.debug("Download finished to file {}. Size : {}".
            format(srtfilename, os.path.getsize(srtfilename)))

    def upload_file(self, filepath, subpath):
        # Get the hash
        filehash = self.get_hash(filepath)
        LOG.debug('File hash : {}'.format(filehash))

        # Upload the subtitle
        params = {'action': 'upload', 'hash': filehash}
        upload_url = self.base_url.format(urllib.urlencode(params))
        LOG.debug('Query URL : {}'.format(upload_url))
        sub = open(subpath, "r")
        '''content = sub.read()
        sub.close()
        fd = StringIO.StringIO()
        fd.name = '%s.srt' % filehash
        fd.write(content)'''

        data = urllib.urlencode({'hash': filehash, 'file': sub})
        req = urllib2.Request(upload_url, data)
        req.add_header('User-Agent', self.user_agent)
        try:
            page = urllib2.urlopen(req, data, timeout=5)
            LOG.debug(page.readlines())
        except urllib2.HTTPError, err:
            LOG.exception('Error occured while uploading : {}'.format(err))
        finally:
            pass
            #fd.close()

    def post_process_results(self, subtitles):
        """ Postprocess the raw result to fit to a common pattern. """
        pass
