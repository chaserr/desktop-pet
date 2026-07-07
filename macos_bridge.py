"""macOS-only tweaks: hide dock icon, keep pet visible over full-screen apps."""
import platform


def is_macos() -> bool:
    return platform.system() == "Darwin"


def hide_dock_icon() -> bool:
    """Turn the Python process into a background 'accessory' app (no dock icon,
    no menu bar). Must be called after QApplication is instantiated so NSApp exists."""
    if not is_macos():
        return False
    try:
        from AppKit import NSApp, NSApplicationActivationPolicyAccessory
    except ImportError:
        return False
    app = NSApp() if callable(NSApp) else NSApp
    if app is None:
        return False
    app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)
    return True


def float_over_everything(widget) -> bool:
    """Boost the widget's NSWindow so it shows on every Space and over full-screen apps.
    Must be called after the widget is shown so winId() returns a valid NSView*."""
    if not is_macos():
        return False
    try:
        import objc
        from AppKit import (
            NSFloatingWindowLevel,
            NSWindowCollectionBehaviorCanJoinAllSpaces,
            NSWindowCollectionBehaviorFullScreenAuxiliary,
            NSWindowCollectionBehaviorStationary,
        )
    except ImportError:
        return False
    ptr = int(widget.winId())
    if not ptr:
        return False
    try:
        ns_view = objc.objc_object(c_void_p=ptr)
        ns_window = ns_view.window()
    except Exception:
        return False
    if ns_window is None:
        return False
    ns_window.setLevel_(NSFloatingWindowLevel)
    ns_window.setCollectionBehavior_(
        NSWindowCollectionBehaviorCanJoinAllSpaces
        | NSWindowCollectionBehaviorStationary
        | NSWindowCollectionBehaviorFullScreenAuxiliary
    )
    # Tool/accessory windows on macOS auto-hide when the owning app loses focus.
    # Force the NSWindow to stay visible regardless of activation state.
    ns_window.setHidesOnDeactivate_(False)
    return True
