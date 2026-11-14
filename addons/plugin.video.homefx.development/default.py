"""Deliberately installed Development video candidate; no startup authentication."""
import sys
import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
import xbmcvfs
from resources.lib.development_video import run


def local_info():
    from pathlib import Path
    from resources.lib.development_info import report
    addon = xbmcaddon.Addon()
    return report(Path(addon.getAddonInfo('path')) / 'resources' / 'build.json',
        lambda: xbmc.getInfoLabel('System.BuildVersion'),
        lambda: xbmc.getSkinDir(),
        lambda: xbmcaddon.Addon(xbmc.getSkinDir()).getAddonInfo('version'))


if __name__ == '__main__':
    run(sys.argv, xbmcaddon.Addon(), xbmcgui.Dialog(), xbmcgui.DialogProgress,
        xbmc.Monitor(), xbmcplugin, xbmcgui.ListItem, xbmcvfs.translatePath, local_info=local_info)
