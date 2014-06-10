#!/usr/bin/python
# -*- coding: utf-8 -*-

#   This file is part of periscope.
#   Copyright (c) 2008-2011 Patrick Dessalle <patrick@dessalle.be>
#
#    periscope is free software; you can redistribute it and/or modify
#    it under the terms of the GNU Lesser General Public License
#    as published by the Free Software Foundation;
#    either version 2 of the License, or (at your option) any later version.
#
#    periscope is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Lesser General Public License for more details.
#
#    You should have received a copy of the GNU Lesser General Public License
#    along with periscope; if not, write to the Free Software
#    Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
from __future__ import absolute_import

import os
import threading
import logging
from locale import getdefaultlocale
from Queue import Queue

import ConfigParser

import periscope.plugins as plugins


LOG = logging.getLogger(__name__)
SUPPORTED_FORMATS = (
    'video/x-msvideo',
    'video/quicktime',
    'video/x-matroska',
    'video/mp4'
)
DEFAULT_LANG = ["en"]


def select_subtitle_auto(subtitles, langs=None):
    """ Return the first subtile in the wanted language. """
    if not langs:
        langs = DEFAULT_LANG
    for lang in langs:
        for subtitle in subtitles:
            if subtitle['lang'] == lang:
                return subtitle
    return None


def select_subtitle_interactive(subtitles):
    """ Ask the user to select a subtitle and return it. """
    if not subtitles:
        return None
    for i, sub in enumerate(subtitles):
        print "[%d]: %s" % (i, sub["release"])

    while True:
        try:
            selected_idx = int(raw_input(
                "Please select a subtitle: "))
            return subtitles[selected_idx]
        except (IndexError, ValueError):
            print ("Please enter a valid subtitle number. "
                   "Press ctrl+c to exit.")
        except KeyboardInterrupt:
            return None


class Periscope(object):

    """ Main Periscope class. """

    def __init__(self, cache_folder=None):
        """ Initalization method. """
        self.config = ConfigParser.SafeConfigParser({
            "lang": "",
            "plugins": "",
            "lang-in-name": "no",
        })
        LOG.info("Log level : {}".format(LOG.getEffectiveLevel()))
        self.config_file = os.path.join(cache_folder, "config")
        self.cache_path = cache_folder

        if not os.path.exists(self.config_file):
            folder = os.path.dirname(self.config_file)
            if not os.path.exists(folder):
                LOG.info("Creating folder {}".format(folder))
                os.mkdir(folder)
                LOG.info("Creating config file")
                config_file = open(self.config_file, "w")
                self.config.write(config_file)
                config_file.close()
        else:
            self.config.read(self.config_file)

        self.plugins = self.get_prefered_plugins()
        self._prefered_languages = None

    def get_prefered_languages(self):
        """ Get the prefered language from the config file. """
        config_lang = self.config.get("DEFAULT", "lang")
        LOG.info("lang read from config: " + config_lang)
        if config_lang == "":
            try:
                return [getdefaultlocale()[0][:2]]
            except IndexError:
                return DEFAULT_LANG
        else:
            return [x.strip() for x in config_lang.split(",")]

    def set_prefered_languages(self, langs):
        """ Update the config file to set the prefered language. """
        self.config.set("DEFAULT", "lang", ",".join(langs))
        config_file = open(self.config_file, "w")
        self.config.write(config_file)
        config_file.close()

    def get_prefered_plugins(self):
        """ Get the prefered plugins from the config file. """
        config_plugins = self.config.get("DEFAULT", "plugins")
        if not config_plugins or config_plugins.strip() == "":
            return self.list_existing_plugins()
        else:
            LOG.info("plugins read from config : " + config_plugins)
            return [x.strip() for x in config_plugins.split(",")]

    def set_prefered_plugins(self, new_plugins):
        """ Update the config file to set the prefered plugins. """
        self.config.set("DEFAULT", "plugins", ",".join(new_plugins))
        config_file = open(self.config_file, "w")
        self.config.write(config_file)
        config_file.close()

    def get_prefered_naming(self):
        """ Get the prefered naming convention from the config file. """
        try:
            lang_in_name = self.config.getboolean("DEFAULT", "lang-in-name")
            LOG.info("lang-in-name read from config: " + str(lang_in_name))
        except ValueError:
            lang_in_name = False
        return lang_in_name

    def set_prefered_naming(self, lang_in_name):
        """ Update the config file to set the prefered naming convention. """
        self.config.set(
            'DEFAULT',
            'lang-in-name',
            'yes' if lang_in_name else 'no')
        config_file = open(self.config_file, "w")
        self.config.write(config_file)
        config_file.close()

    # Getter/setter for the property prefered_languages
    prefered_languages = property(get_prefered_languages,
                                  set_prefered_languages)
    prefered_plugins = property(get_prefered_plugins, set_prefered_plugins)
    prefered_naming = property(get_prefered_naming, set_prefered_naming)

    def deactivate_plugin(self, plugin):
        """ Remove a plugin from the list. """
        self.plugins -= plugin
        self.set_prefered_plugins(self.plugins)

    def activate_plugin(self, plugin):
        """ Activate a plugin. """
        if plugin not in self.list_existing_plugins():
            raise ImportError("No plugin with the name {} exists".
                format(plugin))
        self.plugins += plugin
        self.set_prefered_plugins(self.plugins)

    def list_active_plugins(self):
        """ Return all active plugins. """
        return self.plugins

    @classmethod
    def list_existing_plugins(cls):
        """ List all possible plugins from the plugin folder. """
        return plugins.EXISTING_PLUGINS

    def list_subtitles(self, filename, langs=None):
        """ Return all matching subtitles using the active plugins. """
        LOG.info("Searching subtitles for {} with langs {}".
                 format(filename, langs))
        subtitles = []
        queue = Queue()
        for plugin_name in self.plugins:
            try:
                plugin_class = getattr(plugins, plugin_name)
                plugin = plugin_class(self.config, self.cache_path)
                LOG.info("Searching on {}".format(plugin.__class__.__name__))
                thread = threading.Thread(
                    target=plugin.search_in_thread,
                    args=(queue, filename, langs))
                thread.start()
            except ImportError:
                LOG.error("Plugin %s is not a valid plugin name. Skipping it.")

        # Get data from the queue and wait till we have a result
        for _ in self.plugins:
            subs = queue.get(True)
            if subs and len(subs) > 0:
                if not langs:
                    subtitles += subs
                else:
                    for sub in subs:
                        if sub["lang"] in langs:
                            subtitles.append(sub)
        LOG.debug("{} subtitles has been returned." .format(len(subtitles)))
        return subtitles

    def download_subtitle(self, filename, langs=None):
        """ Dowload only the best subtitle for the file. """
        subtitles = self.list_subtitles(filename, langs)
        return self.attempt_download_subtitle(subtitles, langs)

    def attempt_download_subtitle(self, subtitles, langs):
        """ Attempt to download the best available subtitle in the list. """
        subtitle = select_subtitle_auto(subtitles, langs)
        if not subtitle:
            LOG.error("No subtitles could be chosen.")
            return None
        LOG.info("Trying to download subtitle: {}".format(subtitle['link']))
        subpath = subtitle["plugin"].create_file(subtitle)
        if subpath:
            subtitle["subtitlepath"] = subpath
            return subtitle
        LOG.warn(("Subtitle {} could not be downloaded, "
                  "trying the next on the list.").format(subtitle['link']))
        subtitles.remove(subtitle)
        return self.attempt_download_subtitle(subtitles, langs)
