if __name__ == '__main__':
    try:
        from mobile_desk.app import main
    except Exception:
        # Catch import/DLL failures before Qt's application logger can initialize.
        import os
        from pathlib import Path
        import sys
        import traceback
        folder=Path(os.environ.get('LOCALAPPDATA',str(Path.home())))/'MobileDesk'/'logs'
        folder.mkdir(parents=True,exist_ok=True)
        log=folder/'startup.log'
        log.write_text(traceback.format_exc(),encoding='utf-8')
        if sys.platform=='win32' and getattr(sys,'frozen',False):
            import ctypes
            ctypes.windll.user32.MessageBoxW(0,'Mobile Desk could not load its program files. Reinstall the complete application. Your shop records have not been changed.\n\nDiagnostic log: '+str(log),'Mobile Desk could not start',0x10)
        else:
            raise
        raise SystemExit(1)
    raise SystemExit(main())
