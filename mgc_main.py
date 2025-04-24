import os
import sys
from tkinterdnd2 import DND_FILES, TkinterDnD
import tkinter as tk
from tkinter import ttk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk, PngImagePlugin
import json
import pyperclip
import re
import urllib.request
from urllib.parse import urlparse
import uuid
from PIL import ImageOps
from PIL import ImageEnhance
import shutil

def extract_prompts_from_comfyui(json_str):
    try:
        nodes = json.loads(json_str)
        prompt = ""
        negative_prompt = ""

        negative_nodes = set()
        for node_id, node in nodes.items():
            inputs = node.get("inputs", {})
            if node.get("class_type", "").startswith("KSampler"):
                neg = inputs.get("negative")
                if isinstance(neg, list) and len(neg) >= 1:
                    negative_nodes.add(str(neg[0]))

        for node_id, node in nodes.items():
            inputs = node.get("inputs", {})
            text = inputs.get("text", "")
            if node.get("class_type", "").startswith("CLIPTextEncode") or "TextEncode" in node.get("class_type", ""):
                if str(node_id) in negative_nodes:
                    negative_prompt = text
                elif not prompt:
                    prompt = text

        prompt = prompt.replace("\n", ", ").strip()
        negative_prompt = negative_prompt.replace("\n", ", ").strip()

        steps = sampler = cfg = seed = width = height = model = None

        for node in nodes.values():
            t = node.get("class_type", "")
            i = node.get("inputs", {})

            if t in ["KSampler", "KSampler_A1111"]:
                steps = i.get("steps", steps)
                sampler = i.get("sampler_name", sampler)
                cfg = i.get("cfg", cfg)
                seed = i.get("seed", seed)

            if t in ["EmptyLatentImage", "LatentImage"]:
                width = i.get("width", width)
                height = i.get("height", height)

            if "ckpt_name" in i:
                model = i.get("ckpt_name", model)

        metadata = prompt + "\n"
        metadata += f"Negative prompt: {negative_prompt}\n"
        metadata += f"Steps: {steps}, Sampler: {sampler}, CFG scale: {cfg}, Seed: {seed}, Size: {width}x{height}, Model: {model}"
        return metadata

    except Exception as e:
        return f"Error: {e}"

VENTANA_TAM = "857x607"
IMG_MAX_SIZE = (699, 602)
THUMB_SIZE = (200, 111)
GALERIA_WIDTH = 128
CONFIG_FILE = "mgc_config.json"

def cargar_ultima_carpeta():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            config = json.load(f)
            return config.get("ultima_carpeta", "")
    return ""

def guardar_ultima_carpeta(carpeta):
    with open(CONFIG_FILE, "w") as f:
        json.dump({"ultima_carpeta": carpeta}, f)

def extraer_prompt(img_path, app=None):
    def separar_parametros(data):
        positivo = data.get("prompt", "").strip()
        negativo = data.get("negativePrompt", "").strip()
        parametros = []

        claves_a_extraer = [
            "width", "height", "steps", "cfgScale", "samplerName",
            "ksamplerName", "schedule", "guidance", "sdVae", "v1Clip", "seed"
        ]

        añadidos = set()
        for clave in claves_a_extraer:
            if clave in data and clave not in añadidos:
                valor = data[clave]
        
                if isinstance(valor, dict):
                    valor = valor.get("value", valor)
                if valor is not None:
                    parametros.append(f"{clave}: {valor}")
                    añadidos.add(clave)

        if isinstance(data.get("baseModel"), dict):
            modelo = data["baseModel"]
            label = modelo.get("label", "")
            model_file = modelo.get("modelFileName", "")
            if label:
                try:
                    label = label.encode("latin1", errors="ignore").decode("utf-8", errors="ignore")
                except:
                    pass
                parametros.append(f"baseModel: {label}")
            elif model_file:
                parametros.append(f"baseModel: {model_file}")

        return positivo, negativo, parametros

    try:
        img = Image.open(img_path)
        info = img.info
        texto = ""

        for k, v in info.items():
            if isinstance(v, str) and ('"prompt"' in v or '"Prompt"' in v or '"inputs"' in v) and "{" in v:
                texto = v.strip()
                break
            if k.lower() == "parameters":
                texto = v.strip()
                break

        if not texto:
            if app and hasattr(app, "mostrar_aviso_sin_metadatos"):
                app.mostrar_aviso_sin_metadatos()
            return "", "", []

        try:
            match = re.search(r'\{.*\}', texto, re.DOTALL)
            if match:
                json_text = match.group(0)
                data = json.loads(json_text)

                if isinstance(data, dict) and all(isinstance(v, dict) for v in data.values()):
                    comfy_text = extract_prompts_from_comfyui(json_text)
                    return comfy_text, "", []
                else:
                    return separar_parametros(data)
        except json.JSONDecodeError:
            pass

        # Estilo A1111 plano
        positivo = ""
        negativo = ""
        parametros = []
        lines = texto.splitlines()
        recolectando = "positivo"

        for line in lines:
            line = line.strip()
            if not line:
                continue
            if line.lower().startswith("negative prompt:"):
                negativo = line.split(":", 1)[1].strip()
                recolectando = "negativo"
            elif line.lower().startswith("steps:") or ":" in line:
                parametros.append(line.strip())
            else:
                if recolectando == "positivo":
                    positivo += line + ", "
                elif recolectando == "negativo":
                    negativo += line + ", "

        return positivo.strip(", "), negativo.strip(", "), parametros

    except Exception as e:
        print(f"[ERROR al leer {img_path}]: {e}")
        if app and hasattr(app, "mostrar_aviso_sin_metadatos"):
            app.mostrar_aviso_sin_metadatos()
        return "", "", []

def convertir_a_civitai(prompt):
    return f"<civitai>\n{prompt.strip()}\n</civitai>"

class MGCApp:
    def __init__(self, root, imagen_inicial=None):
        self.root = root
        self.root.title("MGC - Metadata Gallery Converter")
        self.root.maxsize(857, 607)
        self.root.resizable(False, False)
        self.root.geometry(VENTANA_TAM)
        
        self.miniatura_actual = None
        self.root.protocol("WM_DELETE_WINDOW", self.confirmar_salida)
        self.idioma = "es"  # Idioma por defecto

        self.folder = ""
        self.images = []
        self.thumbs = []
        self.thumb_refs = []
        self.miniatura_labels = []
        self.miniatura_actual = None
        self.current_index = 0
        self.textos = {
    "es": {
        "lbl_positivo": "Prompt positivo",
        "lbl_negativo": "Prompt negativo",
        "lbl_parametros": "Parámetros",
        "aviso_salida": "📁 Carpeta sin imágenes cargadas.\nSe mostrará la galería por defecto en la próxima sesión.",
        "btn_abrir": "📂 Abrir Carpeta",
        "btn_guardar_txt": "💾 Guardar como .txt",
        "btn_guardar_png": "🖼️Guardar PNG con Mtadatos (For_Civitai)",
        "btn_copiar_todo": "📋 Copiar Todo",
        "aviso": (
            "📷 Esta imagen parece ser .jpg y no contiene metadatos visibles "
            "(recomiendo usar Tiefsee para mayor comodidad).\n\n"
            "✅ Prueba con una imagen .png generada directamente desde ComfyUI, "
            "Stable Diffusion o TensorART para ver y convertir los prompts a una versión más compatible con Civitai.\n\n"
            "ℹ️ No olvides que esta aplicación fue hecha para mostrar los metadatos de imágenes hechas en TensorART "
            "que se ocultan en Civitai.\n\n"
            "Un saludo~"
        ),
        "btn_idioma": "🌐 English",
    },
    "en": {
        "lbl_positivo": "Positive prompt",
        "lbl_negativo": "Negative prompt",
        "lbl_parametros": "Parameters",
        "aviso_salida": "📁 No images loaded.\nDefault gallery will be shown next time.",
        "btn_abrir": "📂 Open Folder",
        "btn_guardar_txt": "💾 Save as .txt",
        "btn_guardar_png": "🖼️ Save PNG with Metadata (For_Civitai)",
        "btn_copiar_todo": "📋 Copy All",
        "aviso": (
            "📷 This image appears to be .jpg and contains no visible metadata "
            "(I recommend using Tiefsee for convenience).\n\n"
            "✅ Try with a .png image generated directly from ComfyUI, Stable Diffusion or TensorART to view "
            "and convert prompts into a more Civitai-compatible format.\n\n"
            "ℹ️ This app was made to show hidden metadata from TensorART images downloaded from Civitai.\n\n"
            "Best regards~"
        ),
        "btn_idioma": "🌐 Español",
    }
}
        
        # Soporte para arrastrar imágenes al programa
        self.root.drop_target_register(DND_FILES)
        self.root.dnd_bind('<<Drop>>', self.procesar_arrastre)

        # Estilos para botones
        self.boton_estilo = {
            "bg": "#e0e0e0",
            "fg": "#000000",
            "activebackground": "#d0d0d0",
            "relief": tk.RAISED,
            "bd": 2,
            "font": ("Segoe UI", 9, "bold"),
            "padx": 6,
            "pady": 3
        }

        self.setup_gui()
        self.preparar_galeria_demo()  # Solo si no hay carpeta anterior
        self.root.iconbitmap("assets/iconos/mgc_icon.ico")
    def preparar_galeria_demo(self):
        try:
            temp_folder = os.path.join(os.getcwd(), "assets/temp_demo")
            os.makedirs(temp_folder, exist_ok=True)

            # Verifica que haya imágenes reales
            imagenes = [f for f in os.listdir(temp_folder) if f.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))]
            imagenes.sort()

            if imagenes:
                imagen_objetivo = os.path.join(temp_folder, imagenes[0])
                self.cargar_carpeta(temp_folder, imagen_objetivo=imagen_objetivo)
            else:
                print("[INFO] La carpeta demo no contiene imágenes.")
        except Exception as e:
            print(f"[ERROR al preparar galería demo]: {e}")

    def mostrar_aviso_sin_metadatos(self):
        if hasattr(self, "aviso_widget") and self.aviso_widget.winfo_exists():
            self.aviso_widget.destroy()

        self.aviso_widget = tk.Toplevel(self.root)
        self.aviso_widget.title("Aviso")
        self.aviso_widget.transient(self.root)
        self.aviso_widget.geometry("420x200+{}+{}".format(
            self.root.winfo_rootx() + 200, self.root.winfo_rooty() + 150))
        self.aviso_widget.resizable(False, False)
        self.aviso_widget.attributes("-topmost", True)

        mensaje = self.textos[self.idioma]["aviso"]

        label = tk.Label(self.aviso_widget, text=mensaje, wraplength=400, justify="left", padx=10, pady=10)
        label.pack(fill="both", expand=True)

        cerrar = tk.Button(self.aviso_widget, text="Cerrar", command=self.aviso_widget.destroy)
        cerrar.pack(pady=(0, 10))

    def toggle_height(self, text_widget):
        current_height = text_widget.cget("height")
        new_height = 12 if current_height < 6 else 4
        text_widget.config(height=new_height)

    def traducir(self):
        t = self.textos[self.idioma]
        self.btn_abrir.config(text=t["btn_abrir"])
        self.btn_guardar_txt.config(text=t["btn_guardar_txt"])
        self.btn_guardar_png.config(text=t["btn_guardar_png"])
        self.btn_copiar_todo.config(text=t["btn_copiar_todo"])
        self.btn_idioma.config(text=t["btn_idioma"])
        # 👇 Traducción de etiquetas de texto
        self.lbl_pos.config(text=t["lbl_positivo"])
        self.lbl_neg.config(text=t["lbl_negativo"])
        self.lbl_param.config(text=t["lbl_parametros"])

    def cambiar_idioma(self):
        self.idioma = "en" if self.idioma == "es" else "es"
        self.traducir()

    def procesar_arrastre(self, event):
        data = event.data.strip()

        if not data:
            return

        # Si viene como HTML desde navegador (contiene <img src="...">)
        if data.startswith("{") and "src=" in data:
            import re
            match = re.search(r'src="([^"]+)"', data)
            if match:
                url = match.group(1)
                self.descargar_y_abrir_desde_url(url)
                return

        archivos = self.root.tk.splitlist(data)
        if not archivos:
            return

        primera = archivos[0]

        # Si es una URL directa
        if primera.startswith("http"):
            self.descargar_y_abrir_desde_url(primera)

            # Si es un archivo local
        elif os.path.isfile(primera):
            folder = os.path.dirname(primera)
            self.cargar_carpeta(folder, primera)
            guardar_ultima_carpeta(folder)

    def setup_gui(self):
        self.frame_gallery = tk.Frame(self.root, width=GALERIA_WIDTH)
        self.frame_gallery.pack(side=tk.LEFT, fill=tk.Y)

        self.canvas_gallery = tk.Canvas(self.frame_gallery, width=GALERIA_WIDTH)
        # Crear estilo personalizado para scrollbar delgada
        style = ttk.Style()
        style.theme_use('default')
        style.configure("Modern.Vertical.TScrollbar",
    gripcount=0,
    background="a0a0a0",        # Color del "thumb"
    darkcolor="#a0a0a0",
    lightcolor="#a0a0a0",
    troughcolor="#f8f8f8",       # Color del canal (más claro)
    bordercolor="#a0a0a0",
    arrowcolor="#a0a0a0",        # Flechas invisibles
    relief="flat",
    width=2                      # Ancho del scrollbar
)

        # Scrollbar con estilo moderno
        self.scrollbar = ttk.Scrollbar(
        self.frame_gallery,
        orient="vertical",
        command=self.canvas_gallery.yview,
        style="Modern.Vertical.TScrollbar"
        )

        self.scroll_frame = tk.Frame(self.canvas_gallery)
        self.scroll_frame.bind("<Configure>", lambda e: self.canvas_gallery.configure(scrollregion=self.canvas_gallery.bbox("all")))
        self.canvas_gallery.create_window((0, 0), window=self.scroll_frame, anchor="nw")
        self.canvas_gallery.configure(yscrollcommand=self.scrollbar.set)
        self.canvas_gallery.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.frame_main = tk.Frame(self.root)
        self.frame_main.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.canvas_img = tk.Canvas(
            self.frame_main,
            width=404,
            height=600,
            bg="#f8f8f8",
            highlightthickness=5,
            highlightbackground="#f8f8f8",  # borde pastel azul claro
            relief=tk.SOLID
        )

        self.canvas_img.pack()

        self.prompt_frame = tk.Frame(self.root, width=380, bg="#f8f8f8")
        self.prompt_frame.pack_propagate(False)  # 🔒 No deja que el contenido estire este frame
        self.prompt_frame.pack(side=tk.RIGHT, fill=tk.Y)

        self.text_scroll_frame = tk.Frame(self.prompt_frame, bg="#f8f8f8")
        self.text_scroll_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        self.label_instruccion = tk.Label(
        self.frame_main,
        text="📁 Arrastra una imagen aquí o haz clic en 'Abrir carpeta'",
        font=("Segoe UI", 12, "italic"),
        fg="#777777"
    )
        self.label_instruccion.pack(pady=15)

        # Prompt Positivo
        self.lbl_pos_frame = tk.Frame(self.text_scroll_frame, bg="#f8f8f8")
        self.lbl_pos_frame.pack(fill=tk.X, pady=(6, 2))

        self.lbl_pos = tk.Label(
            self.lbl_pos_frame,
            text=self.textos[self.idioma]["lbl_positivo"],
            bg="#f8f8f8",
            fg="#000000",
            font=("Segoe UI", 10, "bold"),
            relief=tk.SOLID,
            bd=1,
            padx=10,         # espaciado interno horizontal
            pady=6,          # espaciado interno vertical
            anchor="center", # centra el texto
            width=24         # ❗ aumenta el ancho visible (en caracteres aprox.)
        )
        self.lbl_pos.pack(side=tk.LEFT)

        self.btn_copiar_pos = tk.Button(
            self.lbl_pos_frame, text="📋", command=self.copiar_prompt_positivo,
            width=3, bg="#e0e0e0", relief=tk.RIDGE      
        )
        self.btn_copiar_pos.pack(side=tk.LEFT, padx=4)

        self.btn_expandir_pos = tk.Button(
            self.lbl_pos_frame, text="⬆⬇", command=lambda: self.toggle_height(self.text_pos),
            width=4, bg="#e0e0e0", relief=tk.RIDGE      
        )
        self.btn_expandir_pos.pack(side=tk.LEFT)

        self.text_pos_frame = tk.Frame(self.text_scroll_frame)
        self.text_pos_frame.pack(fill=tk.X, pady=(0, 3))

        self.text_pos_scroll = ttk.Scrollbar(self.text_pos_frame, orient="vertical", style="Modern.Vertical.TScrollbar")
        self.text_pos_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.text_pos = tk.Text(
            self.text_pos_frame, height=5, width=80, wrap="word",
            bg="#fdfdfd", bd=2, relief=tk.SOLID, font=("Consolas", 10),
            yscrollcommand=self.text_pos_scroll.set
        )
        self.text_pos.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.text_pos_scroll.config(command=self.text_pos.yview)

        # Prompt Negativo
        self.lbl_neg_frame = tk.Frame(self.text_scroll_frame, bg="#f8f8f8")
        self.lbl_neg_frame.pack(fill=tk.X, pady=(6, 2))

        self.lbl_neg = tk.Label(
            self.lbl_neg_frame,
            text=self.textos[self.idioma]["lbl_negativo"],
            bg="#f8f8f8",
            fg="#000000",
            font=("Segoe UI", 10, "bold"),
            relief=tk.SOLID,
            bd=1,
            padx=10,         # espaciado interno horizontal
            pady=6,          # espaciado interno vertical
            anchor="center", # centra el texto
            width=24         # ❗ aumenta el ancho visible (en caracteres aprox.)
        )
        self.lbl_neg.pack(side=tk.LEFT)

        self.btn_copiar_neg = tk.Button(
                self.lbl_neg_frame, text="📋", command=self.copiar_prompt_negativo,
                width=3, bg="#e0e0e0", relief=tk.RIDGE      
        )
        self.btn_copiar_neg.pack(side=tk.LEFT, padx=4)

        self.btn_expandir_neg = tk.Button(
            self.lbl_neg_frame, text="⬆⬇", command=lambda: self.toggle_height(self.text_neg),
                width=4, bg="#e0e0e0", relief=tk.RIDGE      
        )
        self.btn_expandir_neg.pack(side=tk.LEFT)

        self.text_neg_frame = tk.Frame(self.text_scroll_frame)
        self.text_neg_frame.pack(fill=tk.X, pady=(0, 3))

        self.text_neg_scroll = ttk.Scrollbar(self.text_neg_frame, orient="vertical", style="Modern.Vertical.TScrollbar")
        self.text_neg_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.text_neg = tk.Text(
            self.text_neg_frame, height=5, width=80, wrap="word",
            bg="#fdfdfd", bd=2, relief=tk.SOLID, font=("Consolas", 10),
            yscrollcommand=self.text_neg_scroll.set
        )
        self.text_neg.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.text_neg_scroll.config(command=self.text_neg.yview)

        # Parámetros
        self.lbl_param_frame = tk.Frame(self.text_scroll_frame, bg="#f8f8f8")
        self.lbl_param_frame.pack(fill=tk.X, pady=(6, 2))

        self.lbl_param = tk.Label(
            self.lbl_param_frame,
            text=self.textos[self.idioma]["lbl_parametros"],
            bg="#f8f8f8",
            fg="#000000",
            font=("Segoe UI", 10, "bold"),
            relief=tk.SOLID,
            bd=1,
            padx=10,         # espaciado interno horizontal
            pady=6,          # espaciado interno vertical
            anchor="center", # centra el texto
            width=24         # ❗ aumenta el ancho visible (en caracteres aprox.)
        )
        self.lbl_param.pack(side=tk.LEFT)

        self.btn_expandir_param = tk.Button(
            self.lbl_param_frame, text="⬆⬇", command=lambda: self.toggle_height(self.text_param),
            width=19, bg="#f8f8f8", relief=tk.GROOVE      
        )
        self.btn_expandir_param.pack(side=tk.LEFT, padx=4)

        self.text_param_frame = tk.Frame(self.text_scroll_frame)
        self.text_param_frame.pack(fill=tk.X, pady=(0, 2))

        self.text_param_scroll = ttk.Scrollbar(self.text_param_frame, orient="vertical", style="Modern.Vertical.TScrollbar")
        self.text_param_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.text_param = tk.Text(
            self.text_param_frame, height=10, width=80, wrap="word",
            bg="#fdfdfd", bd=2, relief=tk.SOLID, font=("Consolas", 10),
            yscrollcommand=self.text_param_scroll.set
        )
        self.text_param.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.text_param_scroll.config(command=self.text_param.yview)

        self.btn_frame_param = tk.Frame(self.text_scroll_frame, bg="#f8f8f8")
        self.btn_frame_param.pack(anchor="e")

        self.btn_copiar_todo = tk.Button(self.prompt_frame, text="📋 Copiar Todo", command=self.copiar_prompt_total, **self.boton_estilo)
        self.btn_copiar_todo.pack(fill=tk.X, padx=6, pady=(3, 0))

        self.btn_guardar_txt = tk.Button(self.prompt_frame, text="💾 Guardar como .txt", command=self.guardar_como_txt, **self.boton_estilo)
        self.btn_guardar_txt.pack(fill=tk.X, padx=6, pady=(3, 0))

        self.btn_guardar_png = tk.Button(self.prompt_frame, text="🖼️Guardar PNG con Metadatos ", command=self.guardar_como_png, **self.boton_estilo)
        self.btn_guardar_png.pack(fill=tk.X, padx=6, pady=(3, 0))

        self.root.bind("<Up>", lambda e: self.mostrar_imagen(self.current_index - 1))
        self.root.bind("<Down>", lambda e: self.mostrar_imagen(self.current_index + 1))
        
        # Botones en una misma fila: [Idioma] [Abrir carpeta]
        boton_fila = tk.Frame(self.prompt_frame, bg="#f8f8f8")
        boton_fila.pack(padx=6, pady=(6, 5), fill=tk.X)

        self.btn_idioma = tk.Button(boton_fila, command=self.cambiar_idioma, width=10, **self.boton_estilo)
        self.btn_idioma.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 4))

        self.btn_abrir = tk.Button(boton_fila, command=self.seleccionar_carpeta, **self.boton_estilo)
        self.btn_abrir.pack(side=tk.LEFT, expand=True, fill=tk.X)
        
        self.traducir()  # Aplica idioma inicial

    def confirmar_salida(self):
        if not self.images:
            aviso = tk.Toplevel(self.root)
            aviso.title("📁 Aviso" if self.idioma == "es" else "📁 Notice")
            aviso.geometry("440x100+{}+{}".format(
                self.root.winfo_rootx() + 150, self.root.winfo_rooty() + 200))
            aviso.configure(bg="#f8f8f8")
            aviso.resizable(False, False)
            aviso.attributes("-topmost", True)

            mensaje = tk.Label(
                aviso,
                text=self.textos[self.idioma]["aviso_salida"],
                font=("Segoe UI", 10),
                bg="#f8f8f8",
                justify="center"
            )
            mensaje.pack(expand=True)

            aviso.after(2500, lambda: (aviso.destroy(), self.root.destroy()))
        else:
            self.root.destroy()

    def seleccionar_carpeta(self):
        carpeta = filedialog.askdirectory()
        if carpeta:
            self.cargar_carpeta(carpeta)
            guardar_ultima_carpeta(carpeta)

    def cargar_carpeta(self, folder, imagen_objetivo=None):
        self.folder = folder
        self.images = [f for f in os.listdir(folder) if f.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))]
        self.images.sort()
        self.thumb_refs.clear()
        self.miniatura_labels = []
        
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()

        self.thumb_refs_color = []
        self.thumb_refs_gray = []
        self.miniatura_actual = None  # 🔁 Resetea la referencia a la miniatura activa

        THUMB_SIZE = (200, 125)

        for index, filename in enumerate(self.images):
            path = os.path.join(folder, filename)
            try:
               img = Image.open(path)
               img.thumbnail((THUMB_SIZE[0] - 2, THUMB_SIZE[0] - 4))
               # Miniatura en color
               thumb_color = ImageTk.PhotoImage(img.copy())
               self.thumb_refs_color.append(thumb_color)

               # Miniatura en gris (oscurecida)
               img_gray = ImageOps.grayscale(img.copy()).convert("RGB")
               img_gray = ImageEnhance.Brightness(img_gray).enhance(0.6)  # Opcional: más oscuro
               thumb_gray = ImageTk.PhotoImage(img_gray)
               self.thumb_refs_gray.append(thumb_gray)

               # 📦 Contenedor de tamaño fijo para centrar la imagen
               frame = tk.Frame(self.scroll_frame, width=THUMB_SIZE[1], height=THUMB_SIZE[1], bg=self.scroll_frame["bg"])
               frame.pack_propagate(False)
               frame.pack(pady=1, padx=(2, 0), anchor="w")

               lbl = tk.Label(frame, image=thumb_gray, cursor="hand2", bd=2, relief=tk.FLAT, bg="#ffffff")
               lbl.pack(expand=True)  # Centra dentro del frame

               lbl.bind("<Button-1>", lambda e, idx=index: self.mostrar_imagen(idx))
               self.miniatura_labels.append((frame, lbl))

            except:
                continue

        if self.images:
            idx = 0
            if imagen_objetivo:
                base = os.path.basename(imagen_objetivo)
                if base in self.images:
                    idx = self.images.index(base)
            self.current_index = idx  # 🔧 <--- Añade esta línea para que las flechas funcionen
            self.mostrar_imagen(idx)

    def mostrar_imagen(self, index):
        if not self.images:
            return
        
        index %= len(self.images)
        self.current_index = index
        # Marcar la miniatura seleccionada
        if self.miniatura_actual:
           self.miniatura_actual.config(bd=2, relief=tk.FLAT, bg=self.scroll_frame["bg"])

        if index < len(self.miniatura_labels):
           frame, lbl = self.miniatura_labels[index]
           lbl.config(bd=3, relief=tk.SOLID, bg="#d8ecff")  # Color de marco activo
           self.miniatura_actual = lbl

           # 📜 Scroll automático
           self.canvas_gallery.update_idletasks()
           self.canvas_gallery.yview_moveto(frame.winfo_y() / max(1, self.scroll_frame.winfo_height()))

        # 📷 Mostrar imagen principal
        path = os.path.join(self.folder, self.images[index])
        img = Image.open(path)
        img.thumbnail(IMG_MAX_SIZE)
        self.tk_img = ImageTk.PhotoImage(img)
        self.canvas_img.delete("all")  # Borra la imagen anterior del canvas
        canvas_w = 422
        canvas_h = 616
        img_w = self.tk_img.width()
        img_h = self.tk_img.height()
        x = (canvas_w - img_w) // 2
        y = (canvas_h - img_h) // 2
        self.canvas_img.create_image(x, y, anchor="nw", image=self.tk_img)

        positivo, negativo, parametros = extraer_prompt(path, self)
   
        self.text_pos.delete("1.0", tk.END)
        self.text_pos.insert(tk.END, positivo)

        self.text_neg.delete("1.0", tk.END)
        self.text_neg.insert(tk.END, negativo)

        print("PARAMETROS EXTRAÍDOS:\n", parametros)
        self.text_param.delete("1.0", tk.END)
        self.text_param.insert(tk.END, "\n".join(parametros))

        # 🔁 Desaturar todas primero
        for i, (frame, lbl) in enumerate(self.miniatura_labels):
            lbl.config(image=self.thumb_refs_gray[i], bd=2, relief=tk.FLAT, bg=self.scroll_frame["bg"])

        # ✅ Resaltar la actual
        frame, lbl = self.miniatura_labels[index]
        lbl.config(image=self.thumb_refs_color[index], bd=3, relief=tk.SOLID, bg="#d8ecff")
        self.miniatura_actual = lbl

    def copiar_prompt_positivo(self):
        pyperclip.copy(self.text_pos.get("1.0", tk.END).strip())

    def copiar_prompt_negativo(self):
        pyperclip.copy(self.text_neg.get("1.0", tk.END).strip())

    def copiar_prompt_total(self):
        positivo = self.text_pos.get("1.0", tk.END).strip()
        negativo = self.text_neg.get("1.0", tk.END).strip()
        parametros = self.text_param.get("1.0", tk.END).strip().splitlines()

        # Diccionario para mantener el orden
        campos = {
            "Steps": "",
            "CFG scale": "",
            "Sampler": "",
            "Seed": "",
            "Size": "",
            "Model": ""
        }

        for linea in parametros:
            if ":" in linea:
                clave, valor = [x.strip() for x in linea.split(":", 1)]
                if clave.lower() == "steps":
                    campos["Steps"] = valor
                elif clave.lower() == "cfgscale":
                    campos["CFG scale"] = valor
                elif clave.lower() == "samplername":
                    campos["Sampler"] = valor
                elif clave.lower() == "seed":
                    campos["Seed"] = valor
                elif clave.lower() in ["width", "height"]:
                    if "x" not in campos["Size"]:
                        campos["Size"] = valor + "x"
                    else:
                        campos["Size"] = campos["Size"].rstrip("x") + "x" + valor
                elif clave.lower() == "basemodel":
                    campos["Model"] = valor

        prompt_completo = (
            f"{positivo}\n"
            f"Negative prompt: {negativo}\n"
            f"Steps: {campos['Steps']}, CFG scale: {campos['CFG scale']}, Sampler: {campos['Sampler']}, "
            f"Seed: {campos['Seed']}, Size: {campos['Size']}, Model: {campos['Model']}"
        )

        pyperclip.copy(prompt_completo)

    def convertir_prompt(self):
        if not self.images:
            return
        positivo = self.text_pos.get("1.0", tk.END).strip()
        negativo = self.text_neg.get("1.0", tk.END).strip()
        parametros = self.text_param.get("1.0", tk.END).strip()
        prompt = (
            "[Prompt positivo]\n" + positivo +
            "\n\n[Prompt negativo]\n" + negativo +
            "\n\n[Parámetros]\n" + parametros
        )
        if not prompt:
            messagebox.showwarning("Sin contenido", "No hay prompt para convertir.")
            return
        carpeta_destino = filedialog.askdirectory(title="Seleccionar carpeta de destino")
        if not carpeta_destino:
            return
        convertido = convertir_a_civitai(prompt)
        nombre_archivo = self.images[self.current_index]
        base, _ = os.path.splitext(nombre_archivo)
        salida = os.path.join(carpeta_destino, f"{base}_civitai.txt")
        with open(salida, "w", encoding="utf-8") as f:
            f.write(convertido)
        messagebox.showinfo("Listo", f"Prompt convertido guardado como:\n{salida}")
    def guardar_como_txt(self):
        if not self.images:
            return
        positivo = self.text_pos.get("1.0", tk.END).strip()
        negativo = self.text_neg.get("1.0", tk.END).strip()
        parametros = self.text_param.get("1.0", tk.END).strip()
        prompt = (
            "[Prompt positivo]\n" + positivo +
            "\n\n[Prompt negativo]\n" + negativo +
            "\n\n[Parámetros]\n" + parametros
        )
        if not prompt:
            messagebox.showwarning("Sin contenido", "No hay prompt para guardar.")
            return
        nombre_archivo = self.images[self.current_index]
        base, _ = os.path.splitext(nombre_archivo)
        archivo = filedialog.asksaveasfilename(
            defaultextension=".txt", initialfile=f"{base}_prompt.txt",
            filetypes=[("Archivos de texto", "*.txt")]
        )
        if archivo:
            with open(archivo, "w", encoding="utf-8") as f:
                f.write(prompt)
            messagebox.showinfo("Listo", f"Prompt guardado en:\n{archivo}")

    def guardar_como_png(self):
        if not self.images:
            return
        path_original = os.path.join(self.folder, self.images[self.current_index])
        try:
            with Image.open(path_original) as img:
                comfy_metadata = img.info.get("prompt", None)
                if not comfy_metadata:
                    messagebox.showwarning("Sin metadatos", "⚠️ La imagen no contiene metadatos válidos.")
                    return

                extracted = extract_prompts_from_comfyui(comfy_metadata)
                if extracted.startswith("Error:"):
                    messagebox.showerror("Error", f"❌ Error al procesar: {extracted}")
                    return

                pnginfo = PngImagePlugin.PngInfo()
                pnginfo.add_text("parameters", extracted)

                out_path = filedialog.asksaveasfilename(
                    defaultextension=".png",
                    initialfile=f"fixed_{self.images[self.current_index]}",
                    filetypes=[("PNG", "*.png")]
                )
                if out_path:
                    img.save(out_path, "PNG", pnginfo=pnginfo)
                    messagebox.showinfo("Éxito", f"✅ Imagen guardada como:\n{out_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Ocurrió un error al guardar la imagen: {e}")

if __name__ == "__main__":
    imagen_entrada = sys.argv[1] if len(sys.argv) > 1 else None
    root = TkinterDnD.Tk()
    app = MGCApp(root, imagen_inicial=imagen_entrada)
    root.mainloop()