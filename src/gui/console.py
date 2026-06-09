import tkinter as tk
from tkinter import scrolledtext


FG = "#ffffff"
FG_DIM = "#888888"
BG = "#0a0a0a"
BG_INPUT = "#111111"
SUCCESS = "#00cc66"
TITLE_COLOR = "#ffffff"
INFO_COLOR = "#5ba3ec"
WARN_COLOR = "#ce9178"
ERR_COLOR = "#f44747"


class Console(tk.Frame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.commands = {}
        self.help_sections = []
        self._history = []
        self._history_index = -1
        self._saved_input = ""
        self._font_size = 11

        self.grid_propagate(False)
        self.config(bg=BG)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.rowconfigure(1, weight=0)

        self.output_area = scrolledtext.ScrolledText(
            self,
            wrap=tk.WORD,
            state=tk.DISABLED,
            bg=BG,
            fg=FG_DIM,
            insertbackground=FG,
            font=("Menlo", 11),
            borderwidth=0,
            highlightthickness=0,
        )
        self.output_area.grid(row=0, column=0, sticky="nsew")
        self.output_area.vbar.configure(bg="#333333", troughcolor="#1a1a1a", activebackground="#555555",
                                         width=10, borderwidth=0, highlightthickness=0, elementborderwidth=0)

        input_frame = tk.Frame(self, bg=BG_INPUT)
        input_frame.columnconfigure(0, weight=0)
        input_frame.columnconfigure(1, weight=1)
        input_frame.grid(row=1, column=0, sticky="ew", pady=(2, 0))

        self.prompt_label = tk.Label(
            input_frame,
            text="HSF> ",
            bg=BG_INPUT,
            fg=FG,
            font=("Menlo", 11),
        )
        self.prompt_label.grid(row=0, column=0, sticky="w")

        self.input_var = tk.StringVar()
        self.input_entry = tk.Entry(
            input_frame,
            textvariable=self.input_var,
            bg=BG,
            fg=FG,
            insertbackground=FG,
            font=("Menlo", 11),
            borderwidth=1,
            relief=tk.FLAT,
            highlightthickness=1,
            highlightcolor="#222222",
            highlightbackground="#222222",
        )
        self.input_entry.grid(row=0, column=1, sticky="ew")
        self.input_entry.bind("<Return>", self._on_enter)
        self.input_entry.bind("<Up>", self._on_up)
        self.input_entry.bind("<Down>", self._on_down)
        self.input_entry.focus()

        self.bind_all("<Control-plus>", lambda e: self._adjust_font(+1))
        self.bind_all("<Control-minus>", lambda e: self._adjust_font(-1))
        self.bind_all("<Command-plus>", lambda e: self._adjust_font(+1))
        self.bind_all("<Command-minus>", lambda e: self._adjust_font(-1))
        self.bind_all("<Control-equal>", lambda e: self._adjust_font(+1))
        self.bind_all("<Command-equal>", lambda e: self._adjust_font(+1))

        self.register_command("help", self._cmd_help, "Show this help message")
        self.register_command("clear", self._cmd_clear, "Clear the console")
        self.register_command("echo", self._cmd_echo, "Echo back the arguments")

    def register_command(self, name, handler, help_text=""):
        self.commands[name] = {"handler": handler, "help": help_text}

    def add_help_section(self, title, items):
        self.help_sections.append((title, items))

    def write(self, text, color=None):
        self.output_area.config(state=tk.NORMAL)
        is_at_bottom = self.output_area.yview()[1] >= 1.0
        tag = None
        if color:
            tag = f"color_{id(color)}"
            self.output_area.tag_configure(tag, foreground=color)
            self.output_area.insert(tk.END, text, tag)
        else:
            self.output_area.insert(tk.END, text)
        if is_at_bottom:
            self.output_area.see(tk.END)
        self.output_area.config(state=tk.DISABLED)

    def writeln(self, text="", color=None):
        self.write(text + "\n", color)

    def title(self, text):
        self.writeln(f"\u2500\u2500\u2500 {text} \u2500\u2500\u2500", TITLE_COLOR)

    def info(self, text):
        self.writeln(f"[*] {text}", INFO_COLOR)

    def success(self, text):
        self.writeln(f"[+] {text}", SUCCESS)

    def body(self, text):
        self.writeln(text, FG_DIM)

    def warning(self, text):
        self.writeln(f"[!] {text}", WARN_COLOR)

    def error(self, text):
        self.writeln(f"[!] {text}", ERR_COLOR)

    def _on_enter(self, event):
        raw = self.input_var.get().strip()
        self.input_var.set("")
        if not raw:
            return
        if not self._history or self._history[-1] != raw:
            self._history.append(raw)
        self._history_index = len(self._history)
        self._saved_input = ""
        self._execute(raw)

    def _on_up(self, event):
        if not self._history:
            return "break"
        if self._history_index == len(self._history):
            self._saved_input = self.input_var.get()
        if self._history_index > 0:
            self._history_index -= 1
            self.input_var.set(self._history[self._history_index])
            self.input_entry.icursor(tk.END)
        return "break"

    def _on_down(self, event):
        if self._history_index == len(self._history):
            return "break"
        self._history_index += 1
        if self._history_index == len(self._history):
            self.input_var.set(self._saved_input)
        else:
            self.input_var.set(self._history[self._history_index])
            self.input_entry.icursor(tk.END)
        return "break"

    def _adjust_font(self, delta):
        self._font_size = max(8, min(24, self._font_size + delta))
        new_font = ("Menlo", self._font_size)
        self.output_area.configure(font=new_font)
        self.input_entry.configure(font=new_font)
        self.prompt_label.configure(font=new_font)
        return "break"

    def _execute(self, raw):
        self.writeln(f"HSF> {raw}", color=FG)

        parts = raw.split()
        cmd = parts[0].lower()
        args = parts[1:]

        if cmd in self.commands:
            try:
                self.commands[cmd]["handler"](args)
            except Exception as e:
                self.error(str(e))
        else:
            self.body(f"Unknown command: {cmd}. Type 'help' for available commands.")

    def _cmd_help(self, args):
        self.title("Available commands")
        for name, info in sorted(self.commands.items()):
            self.body(f"  {name:<12} {info['help']}")
        for section_title, items in self.help_sections:
            self.writeln("")
            self.title(section_title)
            for item, desc in items:
                self.body(f"  {item:<12} {desc}")

    def _cmd_clear(self, args):
        self.output_area.config(state=tk.NORMAL)
        self.output_area.delete("1.0", tk.END)
        self.output_area.config(state=tk.DISABLED)

    def _cmd_echo(self, args):
        self.body(" ".join(args))
