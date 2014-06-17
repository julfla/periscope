""" Module with helper functions used in various plugins. """

import os
import urllib2
import socket  # For timeout purposes
import zipfile

USER_AGENT = 'Mozilla/5.0 (X11; U; Linux x86_64; en-US; rv:1.9.1.3)'


def download_file(url, file_path, logger):
    """ Download the given url to the given filename. """
    content = download_content(url, logger)
    dump = open(file_path, "wb")
    dump.write(content)
    dump.close()
    logger.debug("Download finished to file {}. Size : {}".
                 format(file_path, os.path.getsize(file_path)))


def download_content(url, logger, timeout=None):
    """ Download the given url and returns its contents."""
    try:
        logger.debug("Downloading %s" % url)
        req = urllib2.Request(url, headers={'Referer': url,
                                            'User-Agent': USER_AGENT})
        if timeout:
            socket.setdefaulttimeout(timeout)
        f = urllib2.urlopen(req)
        content = f.read()
        f.close()
        return content
    except urllib2.HTTPError, e:
        logger.warning("HTTP Error: %s - %s" % (e.code, url))
    except urllib2.URLError, e:
        logger.warning("URL Error: %s - %s" % (e.reason, url))


def file_extension(file_path):
    """ Return the file extension. """
    return os.path.splitext(file_path)[1][1:].lower()


def file_basename(file_path):
    """ Return the basename of a file with its extension. """
    # TODO
    pass


def get_file_name(filepath):
    """ Returns the filename corresponding to a filepath. """
    if os.path.isfile(filepath):
        filename = os.path.basename(filepath)
    else:
        filename = filepath
    if filename.endswith(('.avi', '.wmv', '.mov', '.mp4',
            '.mpeg', '.mpg', '.mkv')):
        fname = filename.rsplit('.', 1)[0]
    else:
        fname = filename
    return fname


def is_file_zipped(file_path):
    """ Return true if the file is a ZIP archive false otherwise. """
    zip_file = zipfile.ZipFile(file_path, 'r')
    return zip_file.is_zipfile()


def extract_subtitle_from_zip_file(file_path, logger):
    """ Return get the content of the subtitle file in the archive. """
    logger.info("Unzipping file {}".format(file_path))
    zip_file = zipfile.ZipFile(file_path, 'r')
    for file_info in zip_file.infolist():
        if file_extension(file_info.orig_filename) in ('srt', 'sub'):
            return zip_file.read(file_info.orig_filename)
    logger.warn("No content found in {}".format(file_path))
