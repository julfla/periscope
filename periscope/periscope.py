#!/usr/bin/python
# -*- coding: utf-8 -*-

""" This module is the access point to the plugins to download subtitles."""

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

        self.plugins = self.prefered_plugins
        self._prefered_languages = None

    def _set_config_value(self, config, value, is_list=False):
        """ Update config and save to config file. """
        if is_list:
            value = ",".join(value)
        self.config.set("DEFAULT", config, value)
        with open(self.config_file, "w") as config_file:
            LOG.info("Set config {} : {}".format(config, value))
            self.config.write(config_file)
            LOG.info("Config saved into {}".format(self.config_file))

    def _get_config_value(self, config, is_list=False):
        """ Get value from config. """
        value = self.config.get("DEFAULT", config)
        if is_list:
            if value:
                value = [x.strip() for x in value.split(",")]
            else:
                value = []
        LOG.info(" Read config {} : {}".format(config, value))
        return value

    @property
    def prefered_languages(self):
        """ Get prefered_languages value from config. """
        value = self._get_config_value("lang", True)
        if not value:
            try:
                value = [getdefaultlocale()[0][:2]]
            except (IndexError, ValueError):
                value = DEFAULT_LANG
                LOG.info(" Default value lang : {}".format(value))
        return value

    @prefered_languages.setter
    def prefered_languages(self, value):
        """ Set prefered_languages value in config. """
        self._set_config_value("lang", value, True)

    @property
    def prefered_plugins(self):
        """ Get prefered_plugins value from config. """
        value = self.config.get("DEFAULT", "plugins")
        if not value:
            value = self.list_existing_plugins()
        return value

    @prefered_plugins.setter
    def prefered_plugins(self, value):
        """ Set prefered_plugins value in config. """
        self._set_config_value("plugins", value, True)

    @property
    def prefered_naming(self):
        """ Get prefered_naming value from config. """
        try:
            return bool(self._get_config_value("lang-in-name"))
        except ValueError:
            return False

    @prefered_naming.setter
    def prefered_naming(self, value):
        """ Set prefered_naming value in config. """
        value = "yes" if value else "no"
        self._set_config_value("lang_in_name", value)

    def deactivate_plugin(self, plugin):
        """ Remove a plugin from the list. """
        self.plugins -= plugin
        self.prefered_plugins = self.plugins

    def activate_plugin(self, plugin):
        """ Activate a plugin. """
        if plugin not in self.list_existing_plugins():
            raise ImportError("No plugin with the name {} exists".
                              format(plugin))
        self.plugins += plugin
        self.prefered_plugins = self.plugins

    def list_active_plugins(self):
        """ Return all active plugins. """
        return self.plugins

    @classmethod
    def list_existing_plugins(cls):
        """ List all possible plugins from the plugin folder. """
        return plugins.EXISTING_PLUGINS

    def list_subtitles(self, filename, langs=None):
        """ Return all matching subtitles using the active plugins. """
        LOG.info(" Searching subtitles for {} with langs {}".
                 format(filename, langs))
        subtitles = []
        queue = Queue()
        for plugin_class in self.plugins:
            try:
                plugin = plugin_class(self.config, self.cache_path)
                LOG.info(" Searching on {}".format(plugin_class.__name__))
                thread = threading.Thread(
                    target=plugin.search_in_thread,
                    args=(queue, filename, langs))
                thread.start()
            except ImportError:
                LOG.error("Plugin {} is not a valid plugin name. Skipping it.".
                    format(plugin_class.__name__))

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
