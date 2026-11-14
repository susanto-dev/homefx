"""Deliberately installed Development video candidate; no startup authentication."""
import sys
import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
import xbmcvfs
from resources.lib.development_video import run


if __name__ == '__main__':
    run(sys.argv, xbmcaddon.Addon(), xbmcgui.Dialog(), xbmcgui.DialogProgress,
        xbmc.Monitor(), xbmcplugin, xbmcgui.ListItem, xbmcvfs.translatePath)
