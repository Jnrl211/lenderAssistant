import ctypes
import tkinter as tk
from tkinter import ttk  # New themed widgets, though less controllable


class PauseWindow(tk.Tk):
    """Creates a Tkinter window to pause the scrapper at the log-in page so the user can enter their credentials manually.
    
    This class extends a root window (tk.Tk), no implicit master window is required, unlike in classes that extend tk.Frame. 
    The motive for defining an explicit root window class is that this enables autocomplete suggestions for tk methods and properties,
    unlike code examples where the master window is implicitly created from a tk.Frame.
    
    This pause window should be started from a subprocess started by the main script in order to provide thread isolation from other packages,
    and to ensure the window can be terminated cleanly and without delay with a termination or interruption signal propagated by the main script.

    From experience, Tkinter runs into conflicts and unpredictable behaviour with Selenium web drivers when running on the same script, 
    hence the need for subprocess isolation.
    """

    class PauseWindowFrame(ttk.Frame):

        outerFrame: ttk.Frame  # Draws an inner contour along the border of the window
        innerFrame: ttk.Frame  # Groups widgets and adds vertical padding around and between them
        messageLabel: ttk.Label
        spacer: ttk.Frame
        continueButton: ttk.Button

        def __init__(self, master: tk.Tk):
            super().__init__(master=master)

        def addWidgets(self, labelText: str, buttonText: str):
            self.outerFrame = ttk.Frame(master=self, borderwidth=2, relief="groove")
            self.outerFrame.pack(padx=8, pady=8)
            self.innerFrame = ttk.Frame(master=self.outerFrame)
            self.innerFrame.pack(side="top", padx=96, pady=48)
            self.messageLabel = ttk.Label(master=self.innerFrame, text=labelText)
            self.messageLabel.pack(side="top")
            self.spacer = ttk.Frame(master=self.innerFrame, height=8)
            self.spacer.pack(side="top")
            self.continueButton = ttk.Button(master=self.innerFrame, text=buttonText, command=self.master.destroy)  # To close the Tk window, not just the Frame
            self.continueButton.pack(side="top", ipadx=16, ipady=4)

    frame: PauseWindowFrame | None = None

    def __init__(
        self,
        title: str = "Pause",
        labelText: str = "An action is required to continue.",
        buttonText: str = "Continue",
        **kwargs
    ):
        super().__init__(**kwargs)  # **kwargs is an unpacked dictionary containing the default keyword arguments of the tk.Tk parent class
        self.attributes("-topmost", True)  # Called using property alias instead of platform specific method to maintain multiplatform compatibility
        # self.protocol(name="", func=self.myCustomFunction)  # TODO: to be defined, or removed
        self.resizable(width=False, height=False)    # Required because "pack" layouts do not resize or reposition widgets
        self.title(string=title)
        self.addWidgets(labelText=labelText, buttonText=buttonText)

    def addWidgets(self, labelText: str, buttonText: str):
        self.frame = self.PauseWindowFrame(master=self)
        self.frame.pack()
        self.frame.addWidgets(labelText=labelText, buttonText=buttonText)


def makeProcessDPIAware():
    """Makes the process DPI aware to remove Tkinter window blurriness on Windows display configurations with scale factors different to 100%.
    
    Even though type and autocomplete hints for runtime dynamic loaders (like ctypes.windll) are unavailable, this works as intended.
    """

    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)  # On Windows 8.1+
    except Exception as e:
        try:
            ctypes.windll.user32.SetProcessDPIAware()  # Fallback, on Windows Vista+
        except Exception:
            pass  # Last resource fallback, ignore on older Windows


def main():
    """Main function to run the pause window as a subprocess from other scripts."""
    window: tk.Tk
    makeProcessDPIAware()
    window = PauseWindow()
    window.mainloop()
    return window


if __name__ == "__main__":
    main()