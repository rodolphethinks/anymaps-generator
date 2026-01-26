import tkinter as tk
from tkinter import ttk, messagebox, colorchooser
import json
import subprocess
import threading
import os
from pathlib import Path

CONFIG_PATH = "config.json"

class MapGeneratorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("AnyMaps Generator")
        self.root.geometry("500x700")
        
        # Style
        self.style = ttk.Style()
        self.style.theme_use('clam')
        
        # Colors: Light Beige Palette
        self.bg_color = "#FDF6E3" # Solarized Base3 (Light Cream)
        self.fg_color = "#586E75" # Solarized Base01
        self.accent_color = "#B58900" # Solarized Yellow/Orange
        self.section_bg = "#EEE8D5" # Solarized Base2 (Darker Beige)
        
        self.root.configure(bg=self.bg_color)
        
        self.style.configure('.', background=self.bg_color, foreground=self.fg_color, font=('Segoe UI', 10))
        self.style.configure('TLabel', background=self.bg_color, foreground=self.fg_color)
        self.style.configure('TButton', background=self.section_bg, foreground=self.fg_color, borderwidth=0, focuscolor=self.bg_color)
        self.style.map('TButton', background=[('active', self.accent_color), ('disabled', '#E0E0E0')], foreground=[('active', 'white')])
        
        self.style.configure('TEntry', fieldbackground='white', borderwidth=1, relief='flat')
        self.style.configure('TFrame', background=self.bg_color)
        self.style.configure('Section.TFrame', background=self.section_bg, relief='flat')
        self.style.configure('Header.TLabel', font=('Segoe UI Light', 24), foreground=self.accent_color)
        self.style.configure('SubHeader.TLabel', font=('Segoe UI Semibold', 12), foreground=self.fg_color)
        
        # Variables
        self.location_name = tk.StringVar()
        self.location_type = tk.StringVar(value="country")
        self.parent_country = tk.StringVar()
        self.low_color = [0.95, 0.98, 1.0, 1.0] # Default White/Blue
        self.high_color = [0.02, 0.1, 0.5, 1.0]
        
        # Advanced Vars
        self.z_scale = tk.DoubleVar(value=3.5)
        self.sun_angle = tk.DoubleVar(value=25.0)
        self.render_samples = tk.IntVar(value=128)
        self.show_text = tk.BooleanVar(value=True)

        self.load_config()
        self.create_widgets()

    def create_widgets(self):
        # Header
        header_frame = ttk.Frame(self.root, padding="20 20 20 10")
        header_frame.pack(fill='x')
        ttk.Label(header_frame, text="AnyMaps", style='Header.TLabel').pack(side='left')
        ttk.Label(header_frame, text="Generator", font=('Segoe UI Light', 24)).pack(side='left', padx=(5,0))

        # Main Scrollable Area (Simplification: Just pack for now)
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill='both', expand=True)

        # LOCATION SECTION
        self.create_section_label(main_frame, "Location Settings")
        
        loc_frame = ttk.Frame(main_frame)
        loc_frame.pack(fill='x', pady=(0, 15))
        
        self.create_form_row(loc_frame, "Name:", self.location_name, "e.g. Greece, Hérault")
        
        # Type Row
        type_frame = ttk.Frame(loc_frame)
        type_frame.pack(fill='x', pady=5)
        ttk.Label(type_frame, text="Type:", width=15).pack(side='left')
        ttk.Radiobutton(type_frame, text="Country", variable=self.location_type, value="country").pack(side='left', padx=(0, 10))
        ttk.Radiobutton(type_frame, text="Region", variable=self.location_type, value="region").pack(side='left')
        
        self.create_form_row(loc_frame, "Parent Country:", self.parent_country, "(Optional for regions)")

        # COLORS SECTION
        self.create_section_label(main_frame, "Elevation Colors")
        
        color_frame = ttk.Frame(main_frame)
        color_frame.pack(fill='x', pady=(0, 15))
        
        self.create_color_row(color_frame, "Low Elevation:", "low")
        self.create_color_row(color_frame, "High Elevation:", "high")

        # ADVANCED TOGGLE
        self.advanced_frame = ttk.Frame(main_frame)
        self.advanced_content = ttk.Frame(self.advanced_frame, padding="10", style='Section.TFrame')
        
        toggle_btn = ttk.Button(main_frame, text="▼ Advanced Settings", command=self.toggle_advanced, style='TButton')
        toggle_btn.pack(anchor='w', pady=(5, 0))
        self.toggle_btn = toggle_btn
        
        # Advanced Content (Hidden by default)
        self.advanced_frame.pack(fill='x', pady=5)
        
        # Sliders
        self.create_slider_row(self.advanced_content, "Vertical Scale:", self.z_scale, 0.5, 10.0)
        self.create_slider_row(self.advanced_content, "Sun Angle:", self.sun_angle, 0.0, 90.0)
        self.create_slider_row(self.advanced_content, "Samples:", self.render_samples, 32, 512, is_int=True)
        
        ttk.Checkbutton(self.advanced_content, text="Show Text Labels", variable=self.show_text).pack(anchor='w', pady=5)


        # ACTION BUTTONS
        btn_frame = ttk.Frame(self.root, padding="20")
        btn_frame.pack(fill='x', side='bottom')
        
        save_btn = ttk.Button(btn_frame, text="Save Config", command=self.save_config)
        save_btn.pack(side='left', expand=True, fill='x', padx=(0, 5))
        
        prep_btn = ttk.Button(btn_frame, text="1. Prepare Data", command=lambda: self.run_process("prepare_data.py"))
        prep_btn.pack(side='left', expand=True, fill='x', padx=5)
        
        render_btn = ttk.Button(btn_frame, text="2. Render Map", command=lambda: self.run_blender_process())
        render_btn.pack(side='left', expand=True, fill='x', padx=(5, 0))

        # Status Bar
        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(self.root, textvariable=self.status_var, background="#E0E0E0", padding=5).pack(side='bottom', fill='x')

    def create_section_label(self, parent, text):
        ttk.Label(parent, text=text, style='SubHeader.TLabel').pack(anchor='w', pady=(10, 5))
        # Separator line
        ttk.Frame(parent, height=2, style='Section.TFrame').pack(fill='x', pady=(0, 10))

    def create_form_row(self, parent, label_text, variable, placeholder=""):
        frame = ttk.Frame(parent)
        frame.pack(fill='x', pady=5)
        
        ttk.Label(frame, text=label_text, width=15).pack(side='left')
        entry = ttk.Entry(frame, textvariable=variable)
        entry.pack(side='left', fill='x', expand=True)
        
        if placeholder:
            # Simple placeholder logic could go here, or just a tooltip/label
            pass

    def create_color_row(self, parent, label_text, type_key):
        frame = ttk.Frame(parent)
        frame.pack(fill='x', pady=5)
        
        ttk.Label(frame, text=label_text, width=15).pack(side='left')
        
        # Color Preview/Button
        canvas = tk.Canvas(frame, width=50, height=25, bg="white", highlightthickness=1, highlightbackground="#AAA")
        canvas.pack(side='left', padx=5)
        
        # Store canvas ref to update later
        setattr(self, f"canvas_{type_key}", canvas)
        self.update_color_preview(type_key)
        
        btn = ttk.Button(frame, text="Pick Color", command=lambda: self.pick_color(type_key))
        btn.pack(side='left')
        
    def create_slider_row(self, parent, label_text, variable, min_val, max_val, is_int=False):
        frame = ttk.Frame(parent)
        frame.pack(fill='x', pady=5)
        
        ttk.Label(frame, text=label_text, width=15).pack(side='left')
        
        scale = ttk.Scale(frame, from_=min_val, to=max_val, variable=variable, orient='horizontal')
        scale.pack(side='left', fill='x', expand=True, padx=5)
        
        # Value Label
        if is_int:
             val_lbl = ttk.Label(frame, text="0", width=4)
        else:
             val_lbl = ttk.Label(frame, text="0.0", width=4)
        val_lbl.pack(side='left')
        
        # Trace variable to update label
        def update_label(*args):
            val = variable.get()
            if is_int:
                 val_lbl.config(text=f"{int(val)}")
            else:
                 val_lbl.config(text=f"{val:.1f}")
        
        variable.trace_add("write", update_label)
        update_label() # Init
    
    def toggle_advanced(self):
        if self.advanced_content.winfo_ismapped():
            self.advanced_content.pack_forget()
            self.toggle_btn.config(text="▼ Advanced Settings")
        else:
            self.advanced_content.pack(fill='x', expand=True)
            self.toggle_btn.config(text="▲ Advanced Settings")

    def pick_color(self, type_key):
        curr_rgba = self.low_color if type_key == 'low' else self.high_color
        # Convert 0-1 RGBA to #RRGGBB
        curr_rgb = (int(curr_rgba[0]*255), int(curr_rgba[1]*255), int(curr_rgba[2]*255))
        color_code = '#%02x%02x%02x' % curr_rgb
        
        color = colorchooser.askcolor(color=color_code, title=f"Choose {type_key} color")
        
        if color[0]: # If custom color chosen ((r,g,b), '#hex')
            r, g, b = color[0]
            # Convert back to 0-1 RGBA list for config
            new_rgba = [r/255.0, g/255.0, b/255.0, 1.0]
            
            if type_key == 'low':
                self.low_color = new_rgba
            else:
                self.high_color = new_rgba
                
            self.update_color_preview(type_key)

    def update_color_preview(self, type_key):
        rgba = self.low_color if type_key == 'low' else self.high_color
        rgb = (int(rgba[0]*255), int(rgba[1]*255), int(rgba[2]*255))
        hex_col = '#%02x%02x%02x' % rgb
        
        canvas = getattr(self, f"canvas_{type_key}")
        canvas.config(bg=hex_col)

    def load_config(self):
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, 'r') as f:
                    data = json.load(f)
                    
                self.location_name.set(data.get('location_name', ''))
                self.location_type.set(data.get('location_type', 'country'))
                self.parent_country.set(data.get('parent_country') or '')
                
                colors = data.get('colors', {})
                if 'low_color' in colors: self.low_color = colors['low_color']
                if 'high_color' in colors: self.high_color = colors['high_color']
                
                # Advanced
                self.z_scale.set(data.get('z_scale', 3.5))
                self.sun_angle.set(data.get('sun_angle', 25.0))
                self.render_samples.set(data.get('render_samples', 128))
                self.show_text.set(data.get('show_text', True))

            except Exception as e:
                print(f"Error loading config: {e}")

    def save_config(self):
        data = {
            "location_name": self.location_name.get(),
            "location_type": self.location_type.get(),
            "parent_country": self.parent_country.get() if self.parent_country.get() else None,
            "colors": {
                "low_color": self.low_color,
                "high_color": self.high_color
            },
            "z_scale": self.z_scale.get(),
            "sun_angle": self.sun_angle.get(),
            "render_samples": self.render_samples.get(),
            "show_text": self.show_text.get()
        }
        
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
        
        self.status_var.set("Configuration saved.")
        return True

    def run_process(self, script_name):
        if not self.save_config(): return
        
        self.status_var.set(f"Running {script_name}...")
        
        def task():
            try:
                # Assuming running in venv on windows
                python_exe = ".\\venv\\Scripts\\python.exe"
                if not os.path.exists(python_exe):
                    python_exe = "python" # Fallback
                
                result = subprocess.run([python_exe, script_name], capture_output=True, text=True)
                
                if result.returncode == 0:
                     self.root.after(0, lambda: self.status_var.set(f"{script_name} completed successfully."))
                     self.root.after(0, lambda: messagebox.showinfo("Success", f"{script_name} finished!"))
                else:
                     self.root.after(0, lambda: self.status_var.set(f"Error in {script_name}"))
                     self.root.after(0, lambda: messagebox.showerror("Error", result.stderr))
            except Exception as e:
                 self.root.after(0, lambda: messagebox.showerror("Exception", str(e)))

        threading.Thread(target=task).start()

    def run_blender_process(self):
        if not self.save_config(): return
        self.status_var.set("Rendering in Blender...")
        
        def task():
            try:
                # Path to blender
                blender_exe = r"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe"
                
                cmd = [blender_exe, "--background", "--python", "render_map.py"]
                result = subprocess.run(cmd, capture_output=True, text=True)
                
                if result.returncode == 0:
                     self.root.after(0, lambda: self.status_var.set("Render completed! Check output folder."))
                     self.root.after(0, lambda: messagebox.showinfo("Success", "Render Finished!"))
                else:
                     self.root.after(0, lambda: self.status_var.set("Blender Error"))
                     self.root.after(0, lambda: messagebox.showerror("Blender Error", result.stderr[-500:])) # Show last 500 chars
            except Exception as e:
                 self.root.after(0, lambda: messagebox.showerror("Exception", str(e)))

        threading.Thread(target=task).start()

if __name__ == "__main__":
    root = tk.Tk()
    app = MapGeneratorGUI(root)
    root.mainloop()
