"""Manually installed Development test entry point, separate from the preview."""
import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs


def main():
    try:
        from resources.lib.development_test import run
        run(xbmcaddon.Addon(), xbmcgui.Dialog(), xbmcgui.DialogProgress,
            xbmc.Monitor(), xbmcvfs.translatePath)
    except Exception:
        # Never expose configuration, private paths or callback exception text.
        try:
            xbmcgui.Dialog().textviewer("HomeFX Development Test", "Test unavailable. No success is established.")
        except Exception:
            pass


if __name__ == '__main__':
    main()
