"""Manually installed Development test entry point, separate from the preview."""
import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs


def main():
    """Return whether UI delivery was available, without leaking callback errors."""
    try:
        from resources.lib.development_test import run
        return run(xbmcaddon.Addon(), xbmcgui.Dialog(), xbmcgui.DialogProgress,
            xbmc.Monitor(), xbmcvfs.translatePath)
    except Exception:
        # Never expose configuration, private paths or callback exception text.
        try:
            xbmcgui.Dialog().textviewer("HomeFX Development Test", "Test unavailable. No success is established.")
        except Exception:
            return False
        return True


if __name__ == '__main__':
    main()
