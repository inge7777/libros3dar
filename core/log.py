from datetime import datetime
from tkinter import NORMAL, DISABLED, END

def safe_log(widget, msg):
    timestamp = datetime.now().strftime("%H:%M:%S")
    line = f"[{timestamp}] {msg}\n"
    try:
        if widget and widget.winfo_exists():
            widget.config(state=NORMAL)
            widget.insert(END, line)
            widget.see(END)
            widget.config(state=DISABLED)
        else:
            print(line, end="")
    except Exception:
        print(line, end="")
