from src.gui import fonts
import tkinter as tk
import tkinter.font as tkfont
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
    def __init__(self, parent, initial_font_size=11, **kwargs):
        super().__init__(parent, **kwargs)
        self.commands = {}
        self.help_sections = []
        self._history = []
        self._history_index = -1
        self._saved_input = ""
        self._font_size = initial_font_size
        self._system_handler = None
        self._system_stop_handler = None
        self._is_system = False
        self._skip_release = False
        self._autocomplete_popup = None
        self._autocomplete_listbox = None
        self._autocomplete_matches = []
        self._autocomplete_index = -1
        self._autocomplete_names = []
        self._track_id = None
        self._filter_id = None
        self._last_popup_y = None
        self._subcommands = {}
        self._arg_popup = None
        self._arg_listbox = None
        self._arg_matches = []
        self._arg_index = -1

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
            font=(fonts.family(), 11),
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
            font=(fonts.family(), 11),
        )
        self.prompt_label.grid(row=0, column=0, sticky="w")

        self.input_var = tk.StringVar()
        self.input_entry = tk.Entry(
            input_frame,
            textvariable=self.input_var,
            bg=BG,
            fg=FG,
            insertbackground=FG,
            font=(fonts.family(), 11),
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
        self.input_entry.bind("<KeyPress>", self._on_key_press)
        self.input_entry.bind("<KeyRelease>", self._on_key_release)
        self.input_entry.bind("<Tab>", self._on_tab)
        self.input_entry.bind("<Escape>", self._on_escape)
        self.input_entry.bind("<FocusIn>", self._on_focus_in)
        self.input_entry.bind("<FocusOut>", self._on_focus_out)
        self.input_entry.focus()

        self.winfo_toplevel().bind("<Button-1>", self._on_root_click, add="+")
        self.winfo_toplevel().bind("<Escape>", self._on_escape, add="+")

        self.bind_all("<Control-plus>", lambda e: self._adjust_font(+1))
        self.bind_all("<Control-minus>", lambda e: self._adjust_font(-1))
        self.bind_all("<Command-plus>", lambda e: self._adjust_font(+1))
        self.bind_all("<Command-minus>", lambda e: self._adjust_font(-1))
        self.bind_all("<Control-equal>", lambda e: self._adjust_font(+1))
        self.bind_all("<Command-equal>", lambda e: self._adjust_font(+1))

        self.register_command("help", self._cmd_help, "Show this help message")
        self.register_command("clear", self._cmd_clear, "Clear the console")

        if self._font_size != 11:
            self.after(0, self._apply_font_size)

    def _apply_font_size(self):
        new_font = (fonts.family(), self._font_size)
        self.output_area.configure(font=new_font)
        self.input_entry.configure(font=new_font)
        self.prompt_label.configure(font=new_font)

    def register_command(self, name, handler, help_text=""):
        self.commands[name] = {"handler": handler, "help": help_text}

    def set_subcommands(self, name, items):
        self._subcommands[name] = items

    def set_system_handler(self, handler):
        self._system_handler = handler

    def set_system_stop_handler(self, handler):
        self._system_stop_handler = handler

    def add_help_section(self, title, items):
        self.help_sections.append((title, items))

    def write(self, text, color=None):
        if not self.winfo_exists():
            return
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
        self._close_autocomplete()
        raw = self.input_var.get().strip()
        self.input_var.set("")
        if self._is_system:
            if raw == "stop":
                self._is_system = False
                self.prompt_label.config(text="HSF> ")
                self.writeln(f"! stop", color=FG)
                if self._system_stop_handler:
                    self._system_stop_handler()
                return
            if not raw:
                return
            if not self._history or self._history[-1] != raw:
                self._history.append(raw)
            self._history_index = len(self._history)
            self._saved_input = ""
            self.writeln(f"! {raw}", color=FG)
            if self._system_handler:
                self._system_handler(raw)
            return

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
        new_font = (fonts.family(), self._font_size)
        self.output_area.configure(font=new_font)
        self.input_entry.configure(font=new_font)
        self.prompt_label.configure(font=new_font)
        if self._autocomplete_popup:
            self._close_arg_popup()
            self._autocomplete_listbox.configure(font=new_font)
            items = list(self._autocomplete_listbox.get(0, tk.END))
            longest = max((len(it.strip()) for it in items), default=10)
            self._autocomplete_listbox.configure(width=longest + 3)
            self._autocomplete_listbox.delete(0, tk.END)
            for item in items:
                self._autocomplete_listbox.insert(tk.END, item)
            self._autocomplete_listbox.selection_set(self._autocomplete_index)
            fs = self._font_size
            f = tkfont.Font(font=(fonts.family(), fs))
            line_h = f.metrics("linespace")
            h = len(self._autocomplete_matches) * line_h + 4 + len(self._autocomplete_matches)
            longest = max((len(it.strip()) for it in items), default=10)
            w = f.measure(" " * (longest + 3)) + 4
            con_top = self.winfo_rooty() - self.master.winfo_rooty()
            y = con_top - h
            self._autocomplete_popup.place_configure(x=0, y=y, width=w, height=h)
        from src.settings import set as _set_setting, save as _save_settings
        _set_setting("console_font_size", self._font_size)
        _save_settings()
        return "break"

    def _execute(self, raw):
        if raw.startswith("!"):
            cmd = raw[1:].strip()
            self.writeln(f"! {cmd}", color=FG)
            if self._system_handler and cmd:
                self._system_handler(cmd)
            return

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

    def _on_key_press(self, event):
        if event.char == "!" and not self._is_system:
            self._is_system = True
            self.prompt_label.config(text="Local> ")
            self._skip_release = True
            self._close_autocomplete()
            return "break"
        if event.keysym not in ("Tab", "Return", "Escape", "Up", "Down", "Shift_L", "Shift_R",
                                "Control_L", "Control_R", "Alt_L", "Alt_R", "Meta_L", "Meta_R",
                                "Command", "Caps_Lock", "BackSpace", "Delete"):
            if self._filter_id:
                self.after_cancel(self._filter_id)
            self._filter_id = self.after(80, self._filter_autocomplete)

    def _on_key_release(self, event):
        if self._skip_release:
            self._skip_release = False
            return
        if self._is_system and not self.input_var.get() and event.keysym in ("BackSpace", "Delete"):
            self._is_system = False
            self.prompt_label.config(text="HSF> ")
            return
        if event.keysym in ("BackSpace", "Delete"):
            if self._filter_id:
                self.after_cancel(self._filter_id)
            self._filter_id = self.after(80, self._filter_autocomplete)

    def _on_tab(self, event):
        if self._is_system:
            return "break"
        raw = self.input_var.get()
        prefix = raw.strip()

        parts = prefix.split(None, 1)
        cmd_prefix = parts[0]
        arg_prefix = parts[1] if len(parts) > 1 else ""
        in_arg_mode = " " in raw.lstrip()

        if in_arg_mode and cmd_prefix in self._subcommands:
            arg1 = arg_prefix.split(None, 1)[0] if arg_prefix else ""
            sc_matches = [s for s in self._subcommands[cmd_prefix] if s.startswith(arg1)]
            if sc_matches:
                if len(sc_matches) == 1 and arg_prefix:
                    self.input_var.set(f"{cmd_prefix} {sc_matches[0]} ")
                    self.input_entry.icursor(tk.END)
                    return "break"
                if self._arg_popup:
                    self._arg_index = (self._arg_index + 1) % len(sc_matches)
                    self._arg_listbox.selection_clear(0, tk.END)
                    self._arg_listbox.selection_set(self._arg_index)
                    self._arg_listbox.activate(self._arg_index)
                return "break"

        matches = [(n, info["help"]) for n, info in self.commands.items()
                   if n.startswith(prefix)]
        matches.sort(key=lambda x: x[0])
        if not matches:
            return "break"
        if len(matches) == 1 and prefix:
            self.input_var.set(matches[0][0] + " ")
            self.input_entry.icursor(tk.END)
            return "break"

        if self._autocomplete_popup:
            self._autocomplete_index = (self._autocomplete_index + 1) % len(self._autocomplete_matches)
            self._autocomplete_listbox.selection_clear(0, tk.END)
            self._autocomplete_listbox.selection_set(self._autocomplete_index)
            self._autocomplete_listbox.activate(self._autocomplete_index)
            return "break"

        self._show_or_update(matches)
        return "break"

    def _on_escape(self, event):
        if self._autocomplete_popup:
            self._close_autocomplete()
            return "break"

    def _show_autocomplete(self, matches):
        self._close_autocomplete()
        fs = self._font_size
        f = tkfont.Font(font=(fonts.family(), fs))
        line_h = f.metrics("linespace")
        longest = max((len(name) for name, _ in matches), default=10)
        frame = tk.Frame(self.master, bg="#111111", highlightbackground="#333333", highlightthickness=1)

        lb = tk.Listbox(frame, bg="#111111", fg="#FFFFFF", selectbackground="#333333",
                        selectforeground="#FFFFFF", font=(fonts.family(), fs),
                        width=longest + 3, borderwidth=0,
                        highlightthickness=0, activestyle="none", exportselection=False)
        lb.pack(fill=tk.BOTH, expand=True)
        for name, help_text in matches:
            lb.insert(tk.END, f"  {name}")
        lb.selection_set(0)
        lb.activate(0)
        lb.bind("<ButtonRelease-1>", self._on_popup_click)
        lb.bind("<Escape>", lambda e: (self._close_autocomplete(), self.input_entry.focus()))

        popup_w = f.measure(" " * (longest + 3)) + 4
        h = len(matches) * line_h + 4 + len(matches)
        con_top = self.winfo_rooty() - self.master.winfo_rooty()
        y = con_top - h

        frame.place(x=0, y=y, width=popup_w, height=h)
        frame.lift()

        self._autocomplete_popup = frame
        self._autocomplete_listbox = lb
        self._start_tracking()

    def _show_or_update(self, matches):
        names = [m[0] for m in matches]
        self._autocomplete_names = names
        if self._autocomplete_popup:
            lb = self._autocomplete_listbox
            lb.delete(0, tk.END)
            for name, help_text in matches:
                lb.insert(tk.END, f"  {name}")
            lb.selection_set(0)
            lb.activate(0)
            self._autocomplete_matches = matches
            self._autocomplete_index = 0
            fs = self._font_size
            f = tkfont.Font(font=(fonts.family(), fs))
            line_h = f.metrics("linespace")
            longest = max((len(name) for name, _ in matches), default=10)
            lb.configure(width=longest + 3)
            popup_w = f.measure(" " * (longest + 3)) + 4
            h = len(matches) * line_h + 4 + len(matches)
            con_top = self.winfo_rooty() - self.master.winfo_rooty()
            y = con_top - h
            self._autocomplete_popup.place_configure(x=0, y=y, width=popup_w, height=h)
            self._autocomplete_popup.lift()
        else:
            self._show_autocomplete(matches)

    def _filter_autocomplete(self):
        if self._is_system:
            return
        raw = self.input_var.get()
        prefix = raw.strip()
        if not prefix:
            all_cmds = [(n, info["help"]) for n, info in self.commands.items()]
            all_cmds.sort(key=lambda x: x[0])
            self._close_arg_popup()
            self._show_or_update(all_cmds)
            return

        parts = prefix.split(None, 1)
        cmd_prefix = parts[0]
        arg_prefix = parts[1] if len(parts) > 1 else ""
        in_arg_mode = " " in raw.lstrip()

        cmd_matches = [(n, info["help"]) for n, info in self.commands.items()
                       if n.startswith(cmd_prefix)]
        cmd_matches.sort(key=lambda x: x[0])

        if not cmd_matches:
            self._close_autocomplete()
            return

        if in_arg_mode and cmd_prefix in self._subcommands:
            sc_items = self._subcommands[cmd_prefix]
            arg1 = arg_prefix.split(None, 1)[0] if arg_prefix else ""
            sc_matches = [s for s in sc_items if s.startswith(arg1)]
            self._show_or_update(cmd_matches)
            self._show_arg_popup(sc_matches)
        else:
            self._close_arg_popup()
            self._show_or_update(cmd_matches)

    def _show_arg_popup(self, items):
        if not self._autocomplete_popup:
            return
        fs = self._font_size
        f = tkfont.Font(font=(fonts.family(), fs))
        line_h = f.metrics("linespace")
        longest = max((len(s) for s in items), default=10)
        h = len(items) * line_h + 4 + len(items)
        popup_w = f.measure(" " * (longest + 3)) + 4

        cmd_x = self._autocomplete_popup.winfo_x()
        cmd_w = self._autocomplete_popup.winfo_width()
        cmd_y = self._autocomplete_popup.winfo_y()
        cmd_h = self._autocomplete_popup.winfo_height()
        bottom = cmd_y + cmd_h

        if self._arg_popup:
            lb = self._arg_listbox
            lb.delete(0, tk.END)
            for s in items:
                lb.insert(tk.END, f"  {s}")
            lb.selection_set(0)
            lb.activate(0)
            lb.configure(width=longest + 3)
            self._arg_matches = items
            self._arg_index = 0
            self._arg_popup.place_configure(
                x=cmd_x + cmd_w, y=bottom - h, width=popup_w, height=h)
            self._arg_popup.lift()
        else:
            frame = tk.Frame(self.master, bg="#111111", highlightbackground="#333333", highlightthickness=1)
            lb = tk.Listbox(frame, bg="#111111", fg="#FFFFFF", selectbackground="#333333",
                            selectforeground="#FFFFFF", font=(fonts.family(), fs),
                            width=longest + 3, borderwidth=0,
                            highlightthickness=0, activestyle="none", exportselection=False)
            lb.pack(fill=tk.BOTH, expand=True)
            for s in items:
                lb.insert(tk.END, f"  {s}")
            lb.selection_set(0)
            lb.activate(0)
            lb.bind("<ButtonRelease-1>", lambda e: self._on_arg_click())
            lb.bind("<Escape>", lambda e: (self._close_autocomplete(), self.input_entry.focus()))

            frame.place(x=cmd_x + cmd_w, y=bottom - h, width=popup_w, height=h)
            frame.lift()

            self._arg_popup = frame
            self._arg_listbox = lb
            self._arg_matches = items
            self._arg_index = 0

    def _close_arg_popup(self):
        if self._arg_popup:
            self._arg_popup.destroy()
            self._arg_popup = None
            self._arg_listbox = None
            self._arg_matches = []
            self._arg_index = -1

    def _on_arg_click(self):
        if self._arg_index >= 0 and self._arg_matches:
            current = self.input_var.get().strip()
            parts = current.split(None, 1)
            cmd = parts[0]
            arg = self._arg_matches[self._arg_index]
            self.input_var.set(f"{cmd} {arg} ")
            self.input_entry.icursor(tk.END)
        self._close_autocomplete()
        self.input_entry.focus()

    def _on_focus_in(self, event):
        if not self._is_system:
            self.after(50, self._filter_autocomplete)

    def _on_focus_out(self, event):
        pass

    def _on_root_click(self, event):
        if not self._autocomplete_popup:
            return
        if event.widget == self.input_entry:
            return
        popup = self._autocomplete_popup
        if popup.winfo_containing(event.x_root, event.y_root) == popup:
            return
        self._close_autocomplete()

    def _close_autocomplete(self):
        self._close_arg_popup()
        if self._filter_id:
            self.after_cancel(self._filter_id)
            self._filter_id = None
        if self._track_id:
            self.after_cancel(self._track_id)
            self._track_id = None
        if self._autocomplete_popup:
            self._autocomplete_popup.destroy()
            self._autocomplete_popup = None
            self._autocomplete_listbox = None
            self._autocomplete_matches = []
            self._autocomplete_index = -1

    def _autocomplete_navigate(self, delta):
        idx = self._autocomplete_index + delta
        if 0 <= idx < len(self._autocomplete_matches):
            self._autocomplete_index = idx
            self._autocomplete_listbox.selection_clear(0, tk.END)
            self._autocomplete_listbox.selection_set(idx)
            self._autocomplete_listbox.activate(idx)

    def _autocomplete_select(self):
        if self._autocomplete_index >= 0 and self._autocomplete_matches:
            self.input_var.set(self._autocomplete_matches[self._autocomplete_index][0] + " ")
            self.input_entry.icursor(tk.END)
        self._close_autocomplete()
        self.input_entry.focus()

    def _on_popup_click(self, event):
        idx = self._autocomplete_listbox.nearest(event.y)
        if 0 <= idx < len(self._autocomplete_matches):
            self._autocomplete_index = idx
            self._autocomplete_select()

    def _start_tracking(self):
        self._stop_tracking()
        self._track_id = self.after(100, self._track_popup)

    def _stop_tracking(self):
        if self._track_id:
            self.after_cancel(self._track_id)
            self._track_id = None

    def _track_popup(self):
        if not self._autocomplete_popup:
            return
        h = self._autocomplete_popup.winfo_height()
        con_top = self.winfo_rooty() - self.master.winfo_rooty()
        y = con_top - h
        if y != self._last_popup_y:
            self._last_popup_y = y
            self._autocomplete_popup.place_configure(y=y)
        self._track_id = self.after(100, self._track_popup)
