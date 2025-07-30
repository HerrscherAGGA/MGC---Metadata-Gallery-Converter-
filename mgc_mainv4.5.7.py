# ==============================
# 📦 IMPORTS
# ==============================

# Librerías estándar
import os, sys, json, re, shutil, subprocess, uuid
from urllib.parse import urlparse
import urllib.request

# Tkinter y UI
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinterdnd2 import DND_FILES, TkinterDnD

# Imágenes
from PIL import Image, ImageTk, PngImagePlugin, ImageOps, ImageEnhance

# Otros
import pyperclip
import requests

# ==============================
# ⚙️ CONSTANTES GLOBALES
# ==============================
VENTANA_TAM = "857x607"
IMG_MAX_SIZE = (699, 602)
THUMB_SIZE = (200, 122)
GALERIA_WIDTH = 127
CONFIG_FILE = "mgc_config.json"

# ==============================
# 🧰 FUNCIONES AUXILIARES
# ==============================
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
import subprocess

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

def cargar_ultima_carpeta():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            config = json.load(f)
            return config.get("ultima_carpeta", "")
    return ""

def guardar_ultima_carpeta(carpeta, config):
    config["ultima_carpeta"] = carpeta
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f)

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

# ==============================
# 🧠 CLASE PRINCIPAL: MGCApp
# ==============================

class MGCApp:
    
    # 🔹 A. Inicialización
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
        self.has_manual_metadata = False  # Nuevo: Indica si se están usando metadatos manuales
        self.textos = {
        "es": {
            "tab_metadatos": "Metadatos",
            "tab_generador": "Generador de Prompt",
            "tab_herramientas": "Otras Herramientas",
            "lbl_positivo": "Prompt positivo",
            "lbl_negativo": "Prompt negativo",
            "lbl_parametros": "Parámetros",
            "btn_abrir": "📂 Abrir Carpeta",
            "btn_guardar_txt": "💾 Guardar como .txt",
            "btn_guardar_png": "🖼️ Guardar PNG con Metadatos (For_Civitai)",
            "btn_copiar_todo": "📋 Copiar Todo",
            "btn_idioma": "🌐 English",
            "prompt_gen_titulo": "🧹 Generador de Prompt Limpio",
            "btn_limpiar": "🔁 Limpiar y convertir",
            "btn_ordenar": "🔠 Ordenar alfabéticamente",
            "btn_comas": "📎 Separar con comas",
            "btn_pro": "🌟 Generar prompt profesional",
            "btn_copiar": "📋 Copiar resultado",
            "btn_volver": "🔙 Volver",
            "btn_copiar_pos": "Copiar prompt positivo",
            "btn_copiar_neg": "Copiar prompt negativo",
            "btn_expandir_pos": "Expandir/Contraer positivo",
            "btn_expandir_neg": "Expandir/Contraer negativo",
            "btn_expandir_param": "Expandir/Contraer parámetros",
            "btn_guardar_metadatos": "💾 Guardar Metadatos",
            # Nuevas claves para Herramientas Avanzadas
            "herramientas_titulo": "⚙️ Herramientas Avanzadas",
            "tab_atajos": "Atajos Personalizables",
            "tab_previa": "Vista Previa Ampliada",
            "tab_exportar": "Exportación Masiva",
            "tab_filtro": "Filtro y Búsqueda",
            "tab_lote": "Edición en Lote",
            "tab_externo": "Integración Externa",
            "tab_tema": "Modo Oscuro/Light",
            "tab_autoguardar": "Guardado Automático",
            "tab_validacion": "Validación de Metadatos",
            "desc_atajos": " Personaliza los atajos de teclado para navegar    por la galería de imágenes.",
            "desc_previa": "Habilita vistas previas ampliadas al pasar el cursor sobre las miniaturas.",
            "desc_exportar": "Exporta los metadatos de todas las imágenes o de una sola a archivos de texto.",
            "desc_filtro": "Busca imágenes por palabras clave en prompts o parámetros.",
            "desc_lote": "Aplica cambios masivos a prompts positivos o negativos de varias imágenes.",
            "desc_externo": "Configura un editor externo para abrir imágenes directamente.",
            "desc_tema": "Alterna entre los modos claro y oscuro para la interfaz.",
            "desc_autoguardar": "Activa el guardado automático de metadatos manuales cada cierto tiempo.",
            "desc_validacion": "Verifica la integridad y validez de los metadatos de la imagen actual.",
            "lbl_atajo_izquierda": "Atajo Izquierda:",
            "lbl_atajo_derecha": "Atajo Derecha:",
            "lbl_atajo_arriba": "Atajo Arriba:",
            "lbl_atajo_abajo": "Atajo Abajo:",
            "btn_guardar_atajos": "💾 Guardar Atajos",
            "nota_atajos": "Usa teclas como '<Left>', '<Right>', '<Control-a>'.",
            "lbl_autozoom": "Habilitar autozoom",
            "btn_exportar_todo": "📄 Exportar Todo a TXT",
            "btn_exportar_individual": "📄 Exportar Individual",
            "lbl_solo_prompts": "Incluir solo prompts",
            "lbl_buscar_keyword": "Buscar por palabra clave:",
            "btn_filtrar": "🔍 Filtrar",
            "btn_restablecer": "🔄 Restablecer",
            "lbl_prefijo_positivo": "Prefijo para Prompt Positivo:",
            "lbl_prefijo_negativo": "Prefijo para Prompt Negativo:",
            "btn_aplicar_seleccionadas": "✅ Aplicar a Seleccionadas",
            "lbl_aplicar_todas": "Aplicar a todas las imágenes",
            "lbl_ruta_editor": "Ruta del Editor Externo:",
            "btn_abrir_editor": "🖌️ Abrir en Editor",
            "btn_guardar_ruta": "💾 Guardar Ruta",
            "lbl_intervalo_autoguardar": "Intervalo de autoguardado (segundos):",
            "btn_validar_metadatos": "🔎 Validar Metadatos Actuales",
            "msg_atajos_guardados": "Atajos guardados correctamente.",
            "msg_exportacion_exitosa": "Metadatos exportados a {path}.",
            "msg_filtro_vacio": "Ingresa una palabra clave para filtrar.",
            "msg_lote_exito": "Edición en lote aplicada correctamente.",
            "msg_ruta_guardada": "Ruta del editor guardada correctamente.",
            "msg_autoguardar_actualizado": "Configuración de guardado automático actualizada.",
            "msg_validacion_resultado": "Validación de Metadatos:\n{resultado}",
            "err_atajo_invalido": "Uno o más atajos son inválidos. Usa formatos como '<Left>' o '<Control-a>'.",
            "err_sin_imagenes": "No hay imágenes cargadas.",
            "err_editor_no_configurado": "Configura la ruta del editor primero.",
            "err_editor_no_existe": "El editor especificado no existe en la ruta proporcionada.",
            "err_stats_no_validas": "No se encontraron estadísticas válidas.",
            "aviso_salida": "📁 Carpeta sin imágenes cargadas.\nSe mostrará la galería por defecto en la próxima sesión.",
            "aviso": (
                "📷 Esta imagen parece ser .jpg y no contiene metadatos visibles "
                "(recomiendo usar Tiefsee para mayor comodidad).\n\n"
                "✅ Prueba con una imagen .png generada directamente desde ComfyUI, "
                "Stable Diffusion o TensorART para ver y convertir los prompts a una versión más compatible con Civitai.\n\n"
                "ℹ️ No olvides que esta aplicación fue hecha para mostrar los metadatos de imágenes hechas en TensorART "
                "que se ocultan en Civitai.\n\n"
                "Un saludo~"
            ),
        },
        "en": {
            "tab_metadatos": "Metadata",
            "tab_generador": "Prompt Generator",
            "tab_herramientas": "Advanced Tools",
            "lbl_positivo": "Positive prompt",
            "lbl_negativo": "Negative prompt",
            "lbl_parametros": "Parameters",
            "btn_abrir": "📂 Open Folder",
            "btn_guardar_txt": "💾 Save as .txt",
            "btn_guardar_png": "🖼️ Save PNG with Metadata (For_Civitai)",
            "btn_copiar_todo": "📋 Copy All",
            "btn_idioma": "🌐 Español",
            "prompt_gen_titulo": "🧹 Clean Prompt Generator",
            "btn_limpiar": "🔁 Clean and convert",
            "btn_ordenar": "🔠 Sort alphabetically",
            "btn_comas": "📎 Separate with commas",
            "btn_pro": "🌟 Generate professional prompt",
            "btn_copiar": "📋 Copy result",
            "btn_volver": "🔙 Back",
            "btn_copiar_pos": "Copy positive prompt",
            "btn_copiar_neg": "Copy negative prompt",
            "btn_expandir_pos": "Expand/Collapse positive",
            "btn_expandir_neg": "Expand/Collapse negative",
            "btn_expandir_param": "Expand/Collapse parameters",
            "btn_guardar_metadatos": "💾 Save Metadata",
            # Nuevas claves para Herramientas Avanzadas
            "herramientas_titulo": "⚙️ Advanced Tools",
            "tab_atajos": "Custom Shortcuts",
            "tab_previa": "Enlarged Preview",
            "tab_exportar": "Mass Export",
            "tab_filtro": "Filter and Search",
            "tab_lote": "Batch Editing",
            "tab_externo": "External Integration",
            "tab_tema": "Dark/Light Mode",
            "tab_autoguardar": "Auto-Save",
            "tab_validacion": "Metadata Validation",
            "desc_atajos": "Customize keyboard shortcuts for navigating the image gallery.",
            "desc_previa": "Enable enlarged previews when hovering over thumbnails.",
            "desc_exportar": "Export metadata from all images or a single one to text files.",
            "desc_filtro": "Search images by keywords in prompts or parameters.",
            "desc_lote": "Apply bulk changes to positive or negative prompts of multiple images.",
            "desc_externo": "Configure an external editor to open images directly.",
            "desc_tema": "Toggle between light and dark modes for the interface.",
            "desc_autoguardar": "Enable automatic saving of manual metadata at regular intervals.",
            "desc_validacion": "Verify the integrity and validity of the current image's metadata.",
            "lbl_atajo_izquierda": "Left Shortcut:",
            "lbl_atajo_derecha": "Right Shortcut:",
            "lbl_atajo_arriba": "Up Shortcut:",
            "lbl_atajo_abajo": "Down Shortcut:",
            "btn_guardar_atajos": "💾 Save Shortcuts",
            "nota_atajos": "Use keys like '<Left>', '<Right>', '<Control-a>'.",
            "lbl_autozoom": "Enable autozoom",
            "btn_exportar_todo": "📄 Export All to TXT",
            "btn_exportar_individual": "📄 Export Individual",
            "lbl_solo_prompts": "Include only prompts",
            "lbl_buscar_keyword": "Search by keyword:",
            "btn_filtrar": "🔍 Filter",
            "btn_restablecer": "🔄 Reset",
            "lbl_prefijo_positivo": "Prefix for Positive Prompt:",
            "lbl_prefijo_negativo": "Prefix for Negative Prompt:",
            "btn_aplicar_seleccionadas": "✅ Apply to Selected",
            "lbl_aplicar_todas": "Apply to all images",
            "lbl_ruta_editor": "External Editor Path:",
            "btn_abrir_editor": "🖌️ Open in Editor",
            "btn_guardar_ruta": "💾 Save Path",
            "lbl_intervalo_autoguardar": "Auto-save interval (seconds):",
            "btn_validar_metadatos": "🔎 Validate Current Metadata",
            "msg_atajos_guardados": "Shortcuts saved successfully.",
            "msg_exportacion_exitosa": "Metadata exported to {path}.",
            "msg_filtro_vacio": "Enter a keyword to filter.",
            "msg_lote_exito": "Batch editing applied successfully.",
            "msg_ruta_guardada": "Editor path saved successfully.",
            "msg_autoguardar_actualizado": "Auto-save configuration updated.",
            "msg_validacion_resultado": "Metadata Validation:\n{resultado}",
            "err_atajo_invalido": "One or more shortcuts are invalid. Use formats like '<Left>' or '<Control-a>'.",
            "err_sin_imagenes": "No images loaded.",
            "err_editor_no_configurado": "Configure the editor path first.",
            "err_editor_no_existe": "The specified editor does not exist at the provided path.",
            "err_stats_no_validas": "No valid statistics found.",
            "aviso_salida": "📁 No images loaded.\nDefault gallery will be shown next time.",
            "aviso": (
                "📷 This image appears to be .jpg and contains no visible metadata "
                "(I recommend using Tiefsee for convenience).\n\n"
                "✅ Try with a .png image generated directly from ComfyUI, Stable Diffusion or TensorART to view "
                "and convert prompts into a more Civitai-compatible format.\n\n"
                "ℹ️ This app was made to show hidden metadata from TensorART images downloaded from Civitai.\n\n"
                "Best regards~"
            ),
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

        # Configuración para Herramientas Avanzadas
        self.config = {"atajos": {"left": "<Left>", "right": "<Right>", "up": "<Up>", "down": "<Down>"}, "editor_path": "", "tema_oscuro": False, "autoguardar": False, "autoguardar_intervalo": 60}
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r") as f:
                self.config.update(json.load(f))
        self.herramienta_seleccionada = self.config.get("herramienta_seleccionada", self.textos[self.idioma]["tab_atajos"])
        self.autoguardar_intervalo = self.config.get("autoguardar_intervalo", 60)
        self.imagenes_seleccionadas = set()
        self.herramientas_frames = {}
        self.preview_enabled = tk.BooleanVar(value=False)
        self.solo_prompts = tk.BooleanVar(value=False)
        self.aplicar_todas = tk.BooleanVar(value=False)
        self.var_tema = tk.BooleanVar(value=self.config.get("tema_oscuro", False))
        self.var_autoguardar = tk.BooleanVar(value=self.config.get("autoguardar", False))
        self.autoguardar_job = None

        self.setup_gui()
        if self.config["autoguardar"]:
           self.iniciar_autoguardar()
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

    
    # 🔹 E. UI y eventos
    def toggle_height(self, text_widget):
        current_height = text_widget.cget("height")
        new_height = 12 if current_height < 6 else 4
        text_widget.config(height=new_height)

    
    def traducir(self):
        t = self.textos[self.idioma]
        # Actualizar pestaña de metadatos
        self.btn_abrir.config(text=t["btn_abrir"])
        self.btn_guardar_txt.config(text=t["btn_guardar_txt"])
        self.btn_guardar_png.config(text=t["btn_guardar_png"])
        self.btn_copiar_todo.config(text=t["btn_copiar_todo"])
        self.btn_idioma.config(text=t["btn_idioma"])
        self.lbl_pos.config(text=t["lbl_positivo"])
        self.lbl_neg.config(text=t["lbl_negativo"])
        self.lbl_param.config(text=t["lbl_parametros"])
        self.lbl_manual_pos.config(text=t["lbl_positivo"])
        self.lbl_manual_neg.config(text=t["lbl_negativo"])
        self.lbl_manual_param.config(text=t["lbl_parametros"])
        self.btn_guardar_metadatos.config(text=t["btn_guardar_metadatos"])
        # Actualizar pestaña de generador de prompt
        self.lbl_titulo_generador.config(text=t["prompt_gen_titulo"])
        self.boton_convertir.config(text=t["btn_limpiar"])
        self.boton_ordenar.config(text=t["btn_ordenar"])
        self.boton_espacios.config(text=t["btn_comas"])
        self.boton_profesional.config(text=t["btn_pro"])
        self.boton_copiar.config(text=t["btn_copiar"])
        self.btn_volver.config(text=t["btn_volver"])
        # Actualizar pestaña de herramientas avanzadas
        self.lbl_titulo_herramientas.config(text=t["herramientas_titulo"])
        self.notebook.tab(self.tab_metadatos, text=t["tab_metadatos"])
        self.notebook.tab(self.tab_generador, text=t["tab_generador"])
        self.notebook.tab(self.tab_herramientas, text=t["tab_herramientas"])
        self.lbl_titulo_herramientas.config(text=t["herramientas_titulo"])
        # Actualizar valores del Combobox y mantener la selección
        valores_originales = [
            t["tab_atajos"],
            t["tab_previa"],
            t["tab_exportar"],
            t["tab_filtro"],
            t["tab_lote"],
            t["tab_externo"],
            t["tab_tema"],
            t["tab_autoguardar"],
            t["tab_validacion"],
        ]
        seleccion_actual = self.herramientas_var.get()
        self.herramientas_combobox["values"] = valores_originales
        # Mapear la selección actual a la nueva traducción si existe
        if seleccion_actual:
            for key, value in t.items():
                if key.startswith("tab_") and value == seleccion_actual:
                    self.herramientas_var.set(seleccion_actual)
                    break
            else:
                self.herramientas_var.set(valores_originales[0])  # Valor por defecto si no se encuentra
        else:
            self.herramientas_var.set(valores_originales[0])
        # Reasignar frames con claves basadas en índices para evitar dependencia del idioma
        temp_frames = self.herramientas_frames.copy()
        self.herramientas_frames.clear()
        for i, (key, frame) in enumerate(temp_frames.items()):
            self.herramientas_frames[valores_originales[i]] = frame
        # Actualizar textos de las herramientas avanzadas
        for frame_key in self.herramientas_frames:
            frame = self.herramientas_frames[frame_key]
            for widget in frame.winfo_children():
                if isinstance(widget, tk.Button):
                    if frame == self.tab_atajos and widget["text"] == self.textos["es"]["btn_guardar_atajos"]:
                        widget.config(text=t["btn_guardar_atajos"])
                    elif frame == self.tab_exportar and widget["text"] == self.textos["es"]["btn_exportar_todo"]:
                        widget.config(text=t["btn_exportar_todo"])
                    elif frame == self.tab_exportar and widget["text"] == self.textos["es"]["btn_exportar_individual"]:
                        widget.config(text=t["btn_exportar_individual"])
                    elif frame == self.tab_filtro and widget["text"] == self.textos["es"]["btn_filtrar"]:
                        widget.config(text=t["btn_filtrar"])
                    elif frame == self.tab_filtro and widget["text"] == self.textos["es"]["btn_restablecer"]:
                        widget.config(text=t["btn_restablecer"])
                    elif frame == self.tab_lote and widget["text"] == self.textos["es"]["btn_aplicar_seleccionadas"]:
                        widget.config(text=t["btn_aplicar_seleccionadas"])
                    elif frame == self.tab_externo and widget["text"] == self.textos["es"]["btn_abrir_editor"]:
                        widget.config(text=t["btn_abrir_editor"])
                    elif frame == self.tab_externo and widget["text"] == self.textos["es"]["btn_guardar_ruta"]:
                        widget.config(text=t["btn_guardar_ruta"])
                    elif frame == self.tab_autoguardar and widget["text"] == self.textos["es"]["btn_guardar_atajos"]:  # Reutiliza el botón de guardar
                        widget.config(text=t["btn_guardar_atajos"])  # Ajuste para consistencia
                    elif frame == self.tab_validacion and widget["text"] == self.textos["es"]["btn_validar_metadatos"]:
                        widget.config(text=t["btn_validar_metadatos"])
        self.mostrar_herramienta(None)
        # Actualizar tooltips
        for btn, tooltip_text in [
            (self.btn_copiar_pos, t["btn_copiar_pos"]),
            (self.btn_copiar_neg, t["btn_copiar_neg"]),
            (self.btn_expandir_pos, t["btn_expandir_pos"]),
            (self.btn_expandir_neg, t["btn_expandir_neg"]),
            (self.btn_expandir_param, t["btn_expandir_param"])
        ]:
            self.crear_tooltip(btn, tooltip_text)
                                
    def crear_tooltip(self, widget, text):
        def entrar(event):
            if not hasattr(self, "tooltip_window") or not self.tooltip_window.winfo_exists():
                self.tooltip_window = tk.Toplevel(widget)
                self.tooltip_window.wm_overrideredirect(True)
                self.tooltip_window.wm_geometry(f"+{widget.winfo_rootx() + 20}+{widget.winfo_rooty() + 20}")
                label = tk.Label(self.tooltip_window, text=text, bg="#ffffe0", fg="#000000", relief=tk.SOLID, borderwidth=1, font=("Segoe UI", 8))
                label.pack()
        def salir(event):
            if hasattr(self, "tooltip_window") and self.tooltip_window.winfo_exists():
                self.tooltip_window.destroy()
        widget.bind("<Enter>", entrar)
        widget.bind("<Leave>", salir)

    
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
            guardar_ultima_carpeta(folder, self.config)

    def mostrar_herramienta(self, event):
        for frame in self.herramientas_frames.values():
            frame.pack_forget()
        seleccion = self.herramientas_var.get()
        if seleccion in self.herramientas_frames:
            self.herramientas_frames[seleccion].pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            # Mapear dinámicamente según el idioma actual
            desc_map = {
                self.textos["es"]["tab_atajos"]: "desc_atajos",
                self.textos["es"]["tab_previa"]: "desc_previa",
                self.textos["es"]["tab_exportar"]: "desc_exportar",
                self.textos["es"]["tab_filtro"]: "desc_filtro",
                self.textos["es"]["tab_lote"]: "desc_lote",
                self.textos["es"]["tab_externo"]: "desc_externo",
                self.textos["es"]["tab_tema"]: "desc_tema",
                self.textos["es"]["tab_autoguardar"]: "desc_autoguardar",
                self.textos["es"]["tab_validacion"]: "desc_validacion",
                self.textos["en"]["tab_atajos"]: "desc_atajos",
                self.textos["en"]["tab_previa"]: "desc_previa",
                self.textos["en"]["tab_exportar"]: "desc_exportar",
                self.textos["en"]["tab_filtro"]: "desc_filtro",
                self.textos["en"]["tab_lote"]: "desc_lote",
                self.textos["en"]["tab_externo"]: "desc_externo",
                self.textos["en"]["tab_tema"]: "desc_tema",
                self.textos["en"]["tab_autoguardar"]: "desc_autoguardar",
                self.textos["en"]["tab_validacion"]: "desc_validacion"
            }
            desc_key = desc_map.get(seleccion, "desc_default")
            self.tools_descriptions.config(text=self.textos[self.idioma].get(desc_key, "Description not available." if self.idioma == "en" else "Descripción no disponible."))
        self.config["herramienta_seleccionada"] = seleccion
        guardar_ultima_carpeta(self.folder, self.config)

    def guardar_atajos(self):
        try:
            atajos = {
                "left": self.entry_left.get(),
                "right": self.entry_right.get(),
                "up": self.entry_up.get(),
                "down": self.entry_down.get()
            }
            for key, value in atajos.items():
                if not value.startswith("<") or not value.endswith(">"):
                    raise ValueError(f"Atajo inválido: {value}")
            self.config["atajos"] = atajos
            for key in ["left", "right", "up", "down"]:
                self.root.bind(atajos[key], lambda e, k=key: self.mostrar_imagen(
                    (self.current_index + (-1 if k in ["left", "up"] else 1)) % len(self.images) if self.images else 0
                ))
            guardar_ultima_carpeta(self.folder, self.config)
            messagebox.showinfo("Éxito", self.textos[self.idioma]["msg_atajos_guardados"])
        except Exception as e:
            messagebox.showerror("Error", self.textos[self.idioma]["err_atajo_invalido"])

    def mostrar_previa(self, index):
        if not self.preview_enabled.get() or not self.images:
            return
        if hasattr(self, "preview_window") and self.preview_window.winfo_exists():
            self.preview_window.destroy()
        try:
            path = os.path.join(self.folder, self.images[index])
            img = Image.open(path)
            img.thumbnail((650, 650))
            self.tk_preview = ImageTk.PhotoImage(img)
            self.preview_window = tk.Toplevel(self.root)
            self.preview_window.wm_overrideredirect(True)
            self.preview_window.wm_geometry(f"+{self.root.winfo_rootx() + 450}+{self.root.winfo_rooty() + 50}")
            tk.Label(self.preview_window, image=self.tk_preview).pack()
        except Exception as e:
            print(f"[ERROR al mostrar previa {self.images[index]}]: {e}")

    def ocultar_previa(self):
        if hasattr(self, "preview_window") and self.preview_window.winfo_exists():
            self.preview_window.destroy()

    def exportar_todo_txt(self):
        if not self.images:
            messagebox.showwarning("Advertencia", self.textos[self.idioma]["err_sin_imagenes"])
            return
        carpeta_destino = filedialog.askdirectory(title="Seleccionar carpeta de destino")
        if not carpeta_destino:
            return
        all_metadata = ""
        for img in self.images:
            path = os.path.join(self.folder, img)
            positivo, negativo, params = extraer_prompt(path, self)
            if self.solo_prompts.get():
                metadata = f"--- {img} ---\n[Prompt positivo]\n{positivo}\n\n[Prompt negativo]\n{negativo}\n\n"
            else:
                metadata = f"--- {img} ---\n[Prompt positivo]\n{positivo}\n\n[Prompt negativo]\n{negativo}\n\n[Parámetros]\n{'\n'.join(params)}\n\n"
            all_metadata += metadata
        output_path = os.path.join(carpeta_destino, "all_metadata.txt")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(all_metadata)
        messagebox.showinfo("Éxito", self.textos[self.idioma]["msg_exportacion_exitosa"].format(path=output_path))

    def exportar_individual(self):
        if not self.images:
            messagebox.showwarning("Advertencia", self.textos[self.idioma]["err_sin_imagenes"])
            return
        carpeta_destino = filedialog.askdirectory(title="Seleccionar carpeta de destino")
        if not carpeta_destino:
            return
        for img in self.images:
            path = os.path.join(self.folder, img)
            positivo, negativo, params = extraer_prompt(path, self)
            if self.solo_prompts.get():
                metadata = f"[Prompt positivo]\n{positivo}\n\n[Prompt negativo]\n{negativo}\n"
            else:
                metadata = f"[Prompt positivo]\n{positivo}\n\n[Prompt negativo]\n{negativo}\n\n[Parámetros]\n{'\n'.join(params)}"
            output_path = os.path.join(carpeta_destino, f"{os.path.splitext(img)[0]}_metadata.txt")
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(metadata)
        messagebox.showinfo("Éxito", self.textos[self.idioma]["msg_exportacion_exitosa"].format(path=carpeta_destino))

    def filtrar_imagenes(self):
        query = self.entry_filtro.get().lower()
        if not query:
            messagebox.showwarning("Advertencia", self.textos[self.idioma]["msg_filtro_vacio"])
            return
        if not self.images:
            messagebox.showwarning("Advertencia", self.textos[self.idioma]["err_sin_imagenes"])
            return
        filtered = []
        for img in self.images:
            path = os.path.join(self.folder, img)
            positivo, negativo, params = extraer_prompt(path, self)
            if query in positivo.lower() or query in negativo.lower() or any(query in p.lower() for p in params):
                filtered.append(img)
        self.images = filtered
        self.cargar_carpeta(self.folder)

    def toggle_seleccion_imagen(self, index):
        img = self.images[index]
        if img in self.imagenes_seleccionadas:
            self.imagenes_seleccionadas.remove(img)
            self.miniatura_labels[index][1].config(relief=tk.FLAT)
        else:
            self.imagenes_seleccionadas.add(img)
            self.miniatura_labels[index][1].config(relief=tk.RAISED, bd=2)

    def editar_lote(self):
        prefijo_pos = self.entry_prefijo_pos.get()
        prefijo_neg = self.entry_prefijo_neg.get()
        if not prefijo_pos and not prefijo_neg:
            messagebox.showwarning("Advertencia", "Ingresa al menos un prefijo.")
            return
        if not self.images:
            messagebox.showwarning("Advertencia", self.textos[self.idioma]["err_sin_imagenes"])
            return
        target_images = self.images if self.aplicar_todas.get() else list(self.imagenes_seleccionadas)
        if not target_images:
            messagebox.showwarning("Advertencia", "Selecciona al menos una imagen o activa 'Aplicar a todas'.")
            return
        for img in target_images:
            path = os.path.join(self.folder, img)
            with Image.open(path) as img_obj:
                positivo, negativo, params = extraer_prompt(path, self)
                if prefijo_pos:
                    positivo = f"{prefijo_pos} {positivo}"
                if prefijo_neg:
                    negativo = f"{prefijo_neg} {negativo}"
                pnginfo = PngImagePlugin.PngInfo()
                metadata = f"{positivo}\nNegative prompt: {negativo}\n{'\n'.join(params)}"
                pnginfo.add_text("parameters", metadata)
                img_obj.save(path, "PNG", pnginfo=pnginfo)
        messagebox.showinfo("Éxito", self.textos[self.idioma]["msg_lote_exito"])
        self.cargar_carpeta(self.folder)  # Recargar para reflejar cambios

    def abrir_externo(self):
        if not self.images:
            messagebox.showwarning("Advertencia", self.textos[self.idioma]["err_sin_imagenes"])
            return
        editor_path = self.config.get("editor_path", "")
        if not editor_path:
            messagebox.showwarning("Advertencia", self.textos[self.idioma]["err_editor_no_configurado"])
            return
        if not os.path.exists(editor_path):
            messagebox.showwarning("Advertencia", self.textos[self.idioma]["err_editor_no_existe"])
            return
        path = os.path.join(self.folder, self.images[self.current_index])
        subprocess.Popen([editor_path, path])

    def guardar_editor(self):
        editor_path = self.entry_editor.get()
        if editor_path and os.path.exists(editor_path):
            self.config["editor_path"] = editor_path
            guardar_ultima_carpeta(self.folder, self.config)
            messagebox.showinfo("Éxito", self.textos[self.idioma]["msg_ruta_guardada"])
        else:
            messagebox.showwarning("Advertencia", self.textos[self.idioma]["err_editor_no_existe"])

    def cambiar_tema(self):
        self.config["tema_oscuro"] = self.var_tema.get()
        style = ttk.Style()
        if self.config["tema_oscuro"]:
            style.configure("TFrame", background="#333333")
            style.configure("TLabel", background="#333333", foreground="#ffffff")
            style.configure("TText", background="#444444", foreground="#ffffff")
            style.configure("TButton", background="#555555", foreground="#ffffff")
            style.configure("Modern.Vertical.TScrollbar", background="#333333", troughcolor="#444444")
            self.frame_gallery.config(bg="#333333")
            self.canvas_gallery.config(bg="#333333")
            self.scroll_frame.config(bg="#333333")
            self.frame_main.config(bg="#333333")
            self.canvas_img.config(bg="#333333", highlightbackground="#333333")
            self.text_scroll_frame.config(bg="#333333")
            self.manual_frame.config(bg="#333333")
            self.herramientas_frame.config(bg="#333333")
            self.contenido_herramienta.config(bg="#333333")
            for frame in self.herramientas_frames.values():
                frame.config(bg="#333333")
                for child in frame.winfo_children():
                    if isinstance(child, tk.Label):
                        child.config(bg="#333333", fg="#ffffff")
                    elif isinstance(child, tk.Entry):
                        child.config(bg="#444444", fg="#ffffff", insertbackground="#ffffff")
                    elif isinstance(child, tk.Button):
                        child.config(bg="#555555", fg="#ffffff")
            self.label_instruccion.config(bg="#333333", fg="#cccccc")
            self.btn_frame_param.config(bg="#333333")
        else:
            style.configure("TFrame", background="#f8f8f8")
            style.configure("TLabel", background="#f8f8f8", foreground="#000000")
            style.configure("TText", background="#fdfdfd", foreground="#000000")
            style.configure("TButton", background="#e0e0e0", foreground="#000000")
            style.configure("Modern.Vertical.TScrollbar", background="#a0a0a0", troughcolor="#f8f8f8")
            self.frame_gallery.config(bg="#a0a0a0")
            self.canvas_gallery.config(bg="#a0a0a0")
            self.scroll_frame.config(bg="#f8f8f8")
            self.frame_main.config(bg="#f8f8f8")
            self.canvas_img.config(bg="#f8f8f8", highlightbackground="#f8f8f8")
            self.text_scroll_frame.config(bg="#f8f8f8")
            self.manual_frame.config(bg="#f8f8f8")
            self.herramientas_frame.config(bg="#f8f8f8")
            self.contenido_herramienta.config(bg="#f8f8f8")
            for frame in self.herramientas_frames.values():
                frame.config(bg="#f8f8f8")
                for child in frame.winfo_children():
                    if isinstance(child, tk.Label):
                        child.config(bg="#f8f8f8", fg="#000000")
                    elif isinstance(child, tk.Entry):
                        child.config(bg="#ffffff", fg="#000000", insertbackground="#000000")
                    elif isinstance(child, tk.Button):
                        child.config(bg="#e0e0e0", fg="#000000")
            self.label_instruccion.config(bg="#f8f8f8", fg="#777777")
            self.btn_frame_param.config(bg="#f8f8f8")
        guardar_ultima_carpeta(self.folder, self.config)

    def toggle_autoguardar(self):
        self.config["autoguardar"] = self.var_autoguardar.get()
        guardar_ultima_carpeta(self.folder, self.config)
        if self.config["autoguardar"]:
            self.iniciar_autoguardar()
        else:
            self.detener_autoguardar()
        messagebox.showinfo("Éxito", self.textos[self.idioma]["msg_autoguardar_actualizado"])

    def iniciar_autoguardar(self):
        if self.autoguardar_job:
            self.root.after_cancel(self.autoguardar_job)
        if self.config["autoguardar"] and self.has_manual_metadata and self.images:
            self.guardar_como_png_manual()
            self.autoguardar_job = self.root.after(self.autoguardar_intervalo * 1000, self.iniciar_autoguardar)

    def detener_autoguardar(self):
        if self.autoguardar_job:
            self.root.after_cancel(self.autoguardar_job)
            self.autoguardar_job = None

    def guardar_autoguardar_intervalo(self):
        try:
            intervalo = int(self.entry_autoguardar_intervalo.get())
            if intervalo < 10:
                raise ValueError("Intervalo demasiado corto.")
            self.autoguardar_intervalo = intervalo
            self.config["autoguardar_intervalo"] = intervalo
            guardar_ultima_carpeta(self.folder, self.config)
            if self.config["autoguardar"]:
                self.iniciar_autoguardar()
            messagebox.showinfo("Éxito", self.textos[self.idioma]["msg_autoguardar_actualizado"])
        except ValueError:
            messagebox.showerror("Error", "Ingresa un número válido (mínimo 10 segundos).")

    def validar_metadatos(self):
        if not self.images:
            messagebox.showwarning("Advertencia", self.textos[self.idioma]["err_sin_imagenes"])
            return
        path = os.path.join(self.folder, self.images[self.current_index])
        positivo, negativo, params = extraer_prompt(path, self)
        if self.has_manual_metadata:
            positivo = self.text_manual_pos.get("1.0", tk.END).strip()
            negativo = self.text_manual_neg.get("1.0", tk.END).strip()
            params = self.text_manual_param.get("1.0", tk.END).strip().splitlines()
        resultado = []
        if not positivo:
            resultado.append("- Prompt positivo: No encontrado o vacío.")
        else:
            resultado.append("- Prompt positivo: OK")
        if not negativo:
            resultado.append("- Prompt negativo: No encontrado o vacío.")
        else:
            resultado.append("- Prompt negativo: OK")
        if not params:
            resultado.append("- Parámetros: No encontrados o vacíos.")
        else:
            resultado.append("- Parámetros: OK")
            for param in params:
                if ":" not in param:
                    resultado.append(f" - Parámetro inválido: {param}")
                else:
                    clave, valor = param.split(":", 1)
                    if not valor.strip():
                        resultado.append(f" - Valor vacío en parámetro: {clave}")
        messagebox.showinfo("Validación", self.textos[self.idioma]["msg_validacion_resultado"].format(resultado="\n".join(resultado)))
    
    def inicializar_herramientas(self):
        # Atajos Personalizables
        self.tab_atajos = tk.Frame(self.contenido_herramienta, bg="#f8f8f8")
        tk.Label(self.tab_atajos, text=self.textos[self.idioma]["lbl_atajo_izquierda"], bg="#f8f8f8").pack(anchor="w", padx=5)
        self.entry_left = tk.Entry(self.tab_atajos)
        self.entry_left.insert(0, self.config["atajos"]["left"])
        self.entry_left.pack(fill=tk.X, padx=5, pady=2)
        tk.Label(self.tab_atajos, text=self.textos[self.idioma]["lbl_atajo_derecha"], bg="#f8f8f8").pack(anchor="w", padx=5)
        self.entry_right = tk.Entry(self.tab_atajos)
        self.entry_right.insert(0, self.config["atajos"]["right"])
        self.entry_right.pack(fill=tk.X, padx=5, pady=2)
        tk.Label(self.tab_atajos, text=self.textos[self.idioma]["lbl_atajo_arriba"], bg="#f8f8f8").pack(anchor="w", padx=5)
        self.entry_up = tk.Entry(self.tab_atajos)
        self.entry_up.insert(0, self.config["atajos"]["up"])
        self.entry_up.pack(fill=tk.X, padx=5, pady=2)
        tk.Label(self.tab_atajos, text=self.textos[self.idioma]["lbl_atajo_abajo"], bg="#f8f8f8").pack(anchor="w", padx=5)
        self.entry_down = tk.Entry(self.tab_atajos)
        self.entry_down.insert(0, self.config["atajos"]["down"])
        self.entry_down.pack(fill=tk.X, padx=5, pady=2)
        tk.Button(self.tab_atajos, text=self.textos[self.idioma]["btn_guardar_atajos"], command=self.guardar_atajos, **self.boton_estilo).pack(pady=10)
        tk.Label(self.tab_atajos, text=self.textos[self.idioma]["nota_atajos"], bg="#f8f8f8", font=("Segoe UI", 8)).pack(anchor="w", padx=5)
        self.crear_tooltip(self.entry_left, self.textos[self.idioma]["nota_atajos"])
        self.herramientas_frames[self.textos[self.idioma]["tab_atajos"]] = self.tab_atajos

        # Vista Previa Ampliada
        self.tab_previa = tk.Frame(self.contenido_herramienta, bg="#f8f8f8")
        tk.Checkbutton(self.tab_previa, text=self.textos[self.idioma]["lbl_autozoom"], variable=self.preview_enabled, 
                       command=lambda: self.recargar_galeria_con_preview(), bg="#f8f8f8").pack(anchor="w", padx=5, pady=5)
        tk.Label(self.tab_previa, text=self.textos[self.idioma]["desc_previa"], bg="#f8f8f8", wraplength=300, justify="left").pack(anchor="w", padx=5)
        self.herramientas_frames[self.textos[self.idioma]["tab_previa"]] = self.tab_previa
    
        # Exportación Masiva
        self.tab_exportar = tk.Frame(self.contenido_herramienta, bg="#f8f8f8")
        tk.Button(self.tab_exportar, text=self.textos[self.idioma]["btn_exportar_todo"], command=self.exportar_todo_txt, **self.boton_estilo).pack(fill=tk.X, padx=5, pady=5)
        tk.Button(self.tab_exportar, text=self.textos[self.idioma]["btn_exportar_individual"], command=self.exportar_individual, **self.boton_estilo).pack(fill=tk.X, padx=5, pady=5)
        tk.Checkbutton(self.tab_exportar, text=self.textos[self.idioma]["lbl_solo_prompts"], variable=self.solo_prompts, bg="#f8f8f8").pack(anchor="w", padx=5, pady=5)
        self.herramientas_frames[self.textos[self.idioma]["tab_exportar"]] = self.tab_exportar

        # Filtro y Búsqueda
        self.tab_filtro = tk.Frame(self.contenido_herramienta, bg="#f8f8f8")
        tk.Label(self.tab_filtro, text=self.textos[self.idioma]["lbl_buscar_keyword"], bg="#f8f8f8").pack(anchor="w", padx=5)
        self.entry_filtro = tk.Entry(self.tab_filtro)
        self.entry_filtro.pack(fill=tk.X, padx=5, pady=2)
        tk.Button(self.tab_filtro, text=self.textos[self.idioma]["btn_filtrar"], command=self.filtrar_imagenes, **self.boton_estilo).pack(fill=tk.X, padx=5, pady=5)
        tk.Button(self.tab_filtro, text=self.textos[self.idioma]["btn_restablecer"], command=lambda: self.cargar_carpeta(self.folder), **self.boton_estilo).pack(fill=tk.X, padx=5, pady=5)
        self.crear_tooltip(self.entry_filtro, "Ejemplo: 'portrait' o 'steps:50'")
        self.herramientas_frames[self.textos[self.idioma]["tab_filtro"]] = self.tab_filtro

        # Edición en Lote
        self.tab_lote = tk.Frame(self.contenido_herramienta, bg="#f8f8f8")
        tk.Label(self.tab_lote, text=self.textos[self.idioma]["lbl_prefijo_positivo"], bg="#f8f8f8").pack(anchor="w", padx=5)
        self.entry_prefijo_pos = tk.Entry(self.tab_lote)
        self.entry_prefijo_pos.pack(fill=tk.X, padx=5, pady=2)
        tk.Label(self.tab_lote, text=self.textos[self.idioma]["lbl_prefijo_negativo"], bg="#f8f8f8").pack(anchor="w", padx=5)
        self.entry_prefijo_neg = tk.Entry(self.tab_lote)
        self.entry_prefijo_neg.pack(fill=tk.X, padx=5, pady=2)
        tk.Button(self.tab_lote, text=self.textos[self.idioma]["btn_aplicar_seleccionadas"], command=self.editar_lote, **self.boton_estilo).pack(fill=tk.X, padx=5, pady=5)
        tk.Checkbutton(self.tab_lote, text=self.textos[self.idioma]["lbl_aplicar_todas"], variable=self.aplicar_todas, bg="#f8f8f8").pack(anchor="w", padx=5, pady=5)
        tk.Label(self.tab_lote, text="Haz clic derecho en miniaturas para seleccionar/deseleccionar.", bg="#f8f8f8", font=("Segoe UI", 8)).pack(anchor="w", padx=5)
        self.herramientas_frames[self.textos[self.idioma]["tab_lote"]] = self.tab_lote

        # Integración Externa
        self.tab_externo = tk.Frame(self.contenido_herramienta, bg="#f8f8f8")
        tk.Label(self.tab_externo, text=self.textos[self.idioma]["lbl_ruta_editor"], bg="#f8f8f8").pack(anchor="w", padx=5)
        self.entry_editor = tk.Entry(self.tab_externo)
        self.entry_editor.insert(0, self.config.get("editor_path", ""))
        self.entry_editor.pack(fill=tk.X, padx=5, pady=2)
        tk.Button(self.tab_externo, text=self.textos[self.idioma]["btn_abrir_editor"], command=self.abrir_externo, **self.boton_estilo).pack(fill=tk.X, padx=5, pady=5)
        tk.Button(self.tab_externo, text=self.textos[self.idioma]["btn_guardar_ruta"], command=self.guardar_editor, **self.boton_estilo).pack(fill=tk.X, padx=5, pady=5)
        self.herramientas_frames[self.textos[self.idioma]["tab_externo"]] = self.tab_externo

        # Modo Oscuro/Light
        self.tab_tema = tk.Frame(self.contenido_herramienta, bg="#f8f8f8")
        tk.Checkbutton(self.tab_tema, text=self.textos[self.idioma]["tab_tema"], variable=self.var_tema, command=self.cambiar_tema, bg="#f8f8f8").pack(anchor="w", padx=5, pady=5)
        tk.Label(self.tab_tema, text=self.textos[self.idioma]["desc_tema"], bg="#f8f8f8", wraplength=300, justify="left").pack(anchor="w", padx=5)
        self.herramientas_frames[self.textos[self.idioma]["tab_tema"]] = self.tab_tema

        # Guardado Automático
        self.tab_autoguardar = tk.Frame(self.contenido_herramienta, bg="#f8f8f8")
        tk.Checkbutton(self.tab_autoguardar, text=self.textos[self.idioma]["tab_autoguardar"], variable=self.var_autoguardar, command=self.toggle_autoguardar, bg="#f8f8f8").pack(anchor="w", padx=5, pady=5)
        tk.Label(self.tab_autoguardar, text=self.textos[self.idioma]["lbl_intervalo_autoguardar"], bg="#f8f8f8").pack(anchor="w", padx=5)
        self.entry_autoguardar_intervalo = tk.Entry(self.tab_autoguardar)
        self.entry_autoguardar_intervalo.insert(0, str(self.autoguardar_intervalo))
        self.entry_autoguardar_intervalo.pack(fill=tk.X, padx=5, pady=2)
        tk.Button(self.tab_autoguardar, text=self.textos[self.idioma]["btn_guardar_atajos"], command=self.guardar_autoguardar_intervalo, **self.boton_estilo).pack(fill=tk.X, padx=5, pady=5)
        self.herramientas_frames[self.textos[self.idioma]["tab_autoguardar"]] = self.tab_autoguardar

        # Validación de Metadatos
        self.tab_validacion = tk.Frame(self.contenido_herramienta, bg="#f8f8f8")
        tk.Button(self.tab_validacion, text=self.textos[self.idioma]["btn_validar_metadatos"], command=self.validar_metadatos, **self.boton_estilo).pack(fill=tk.X, padx=5, pady=5)
        tk.Label(self.tab_validacion, text=self.textos[self.idioma]["desc_validacion"], bg="#f8f8f8", wraplength=300, justify="left").pack(anchor="w", padx=5)
        self.herramientas_frames[self.textos[self.idioma]["tab_validacion"]] = self.tab_validacion

        # Mostrar la herramienta seleccionada
        self.mostrar_herramienta(None)
                                        
    def cargar_carpeta(self, folder, imagen_objetivo=None):
        self.folder = folder
        self.images = [f for f in os.listdir(folder) if f.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))]
        self.images.sort()
        self.thumb_refs.clear()
        self.thumb_refs_color.clear()
        self.thumb_refs_gray.clear()
        self.miniatura_labels = []
        self.imagenes_seleccionadas.clear()
        self.miniatura_actual = None
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()
        for index, filename in enumerate(self.images):
            path = os.path.join(folder, filename)
            try:
                img = Image.open(path)
                img.thumbnail((THUMB_SIZE[0] - 2, THUMB_SIZE[0] - 4))
                thumb_color = ImageTk.PhotoImage(img.copy())
                img_gray = ImageOps.grayscale(img.copy()).convert("RGB")
                img_gray = ImageEnhance.Brightness(img_gray).enhance(0.6)
                thumb_gray = ImageTk.PhotoImage(img_gray)
                self.thumb_refs_color.append(thumb_color)
                self.thumb_refs_gray.append(thumb_gray)
                frame = tk.Frame(self.scroll_frame, width=THUMB_SIZE[1], height=THUMB_SIZE[1], bg=self.scroll_frame["bg"])
                frame.pack_propagate(False)
                frame.pack(pady=1, padx=(2, 0), anchor="w")
                lbl = tk.Label(frame, image=thumb_gray, cursor="hand2", bd=2, relief=tk.FLAT, bg="#ffffff")
                lbl.pack(expand=True)
                lbl.bind("<Button-1>", lambda e, idx=index: self.mostrar_imagen(idx))
                lbl.bind("<Button-3>", lambda e, idx=index: self.toggle_seleccion_imagen(idx))
                if self.preview_enabled.get():
                    lbl.bind("<Enter>", lambda e, idx=index: self.mostrar_previa(idx))
                    lbl.bind("<Leave>", lambda e: self.ocultar_previa())
                self.miniatura_labels.append((frame, lbl))
            except Exception as e:
                print(f"[ERROR al cargar miniatura {filename}]: {e}")
                continue
        if self.images:
            idx = 0
            if imagen_objetivo:
                base = os.path.basename(imagen_objetivo)
                if base in self.images:
                    idx = self.images.index(base)
            self.current_index = idx
            self.mostrar_imagen(idx)
                                
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
            width=0                      # Ancho del scrollbar
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

        # Añadir bindings de teclado para flechas solo en la galería
        self.canvas_gallery.bind("<Up>", lambda e: self.mostrar_imagen((self.current_index - 1) % len(self.images) if self.images else 0))
        self.canvas_gallery.bind("<Down>", lambda e: self.mostrar_imagen((self.current_index + 1) % len(self.images) if self.images else 0))

        # Restaurar bindings de teclado en toda la ventana
        self.root.bind("<Left>", lambda e: self.mostrar_imagen((self.current_index - 1) % len(self.images) if self.images else 0))
        self.root.bind("<Right>", lambda e: self.mostrar_imagen((self.current_index + 1) % len(self.images) if self.images else 0))
        self.root.bind("<Up>", lambda e: self.mostrar_imagen((self.current_index - 1) % len(self.images) if self.images else 0))
        self.root.bind("<Down>", lambda e: self.mostrar_imagen((self.current_index + 1) % len(self.images) if self.images else 0))

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

        # Crear notebook para pestañas
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # Pestaña de Metadatos
        self.tab_metadatos = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_metadatos, text=self.textos[self.idioma]["tab_metadatos"])
        self.text_scroll_frame = tk.Frame(self.tab_metadatos, bg="#f8f8f8")
        self.text_scroll_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        self.label_instruccion = tk.Label(
            self.frame_main,
            text="📁 Arrastra una imagen aquí o haz clic en 'Abrir carpeta'",
            font=("Segoe UI", 12, "italic"),
            fg="#777777"
        )
        self.label_instruccion.pack(pady=15)

        # Prompt Positivo (automático)
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
            padx=10,
            pady=6,
            anchor="center",
            width=24
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
    
        # Prompt Negativo (automático)
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
            padx=10,
            pady=6,
            anchor="center",
            width=24
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

        # Parámetros (automático)
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
            padx=10,
            pady=6,
            anchor="center",
            width=24
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
            self.text_param_frame, height=8, width=10, wrap="word",
            bg="#fdfdfd", bd=2, relief=tk.SOLID, font=("Consolas", 10),
            yscrollcommand=self.text_param_scroll.set
        )
        self.text_param.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.text_param_scroll.config(command=self.text_param.yview)

        # Campos manuales (ocultos por defecto)
        self.manual_frame = tk.Frame(self.tab_metadatos, bg="#f8f8f8")
        self.manual_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        self.lbl_manual_pos_frame = tk.Frame(self.manual_frame, bg="#f8f8f8")
        self.lbl_manual_pos_frame.pack(fill=tk.X, pady=(6, 2))

        self.lbl_manual_pos = tk.Label(
            self.lbl_manual_pos_frame,
            text=self.textos[self.idioma]["lbl_positivo"],
            bg="#f8f8f8",
            fg="#000000",
            font=("Segoe UI", 10, "bold"),
            relief=tk.SOLID,
            bd=1,
            padx=10,
            pady=6,
            anchor="center",
            width=24
        )
        self.lbl_manual_pos.pack(side=tk.LEFT)

        self.text_manual_pos_frame = tk.Frame(self.manual_frame)
        self.text_manual_pos_frame.pack(fill=tk.X, pady=(0, 3))

        self.text_manual_pos_scroll = ttk.Scrollbar(self.text_manual_pos_frame, orient="vertical", style="Modern.Vertical.TScrollbar")
        self.text_manual_pos_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.text_manual_pos = tk.Text(
            self.text_manual_pos_frame, height=5, width=80, wrap="word",
            bg="#fdfdfd", bd=2, relief=tk.SOLID, font=("Consolas", 10),
            yscrollcommand=self.text_manual_pos_scroll.set
        )
        self.text_manual_pos.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.text_manual_pos_scroll.config(command=self.text_manual_pos.yview)

        self.lbl_manual_neg_frame = tk.Frame(self.manual_frame, bg="#f8f8f8")
        self.lbl_manual_neg_frame.pack(fill=tk.X, pady=(6, 2))

        self.lbl_manual_neg = tk.Label(
            self.lbl_manual_neg_frame,
            text=self.textos[self.idioma]["lbl_negativo"],
            bg="#f8f8f8",
            fg="#000000",
            font=("Segoe UI", 10, "bold"),
            relief=tk.SOLID,
            bd=1,
            padx=10,
            pady=6,
            anchor="center",
            width=24
        )
        self.lbl_manual_neg.pack(side=tk.LEFT)

        self.text_manual_neg_frame = tk.Frame(self.manual_frame)
        self.text_manual_neg_frame.pack(fill=tk.X, pady=(0, 3))

        self.text_manual_neg_scroll = ttk.Scrollbar(self.text_manual_neg_frame, orient="vertical", style="Modern.Vertical.TScrollbar")
        self.text_manual_neg_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.text_manual_neg = tk.Text(
            self.text_manual_neg_frame, height=5, width=80, wrap="word",
            bg="#fdfdfd", bd=2, relief=tk.SOLID, font=("Consolas", 10),
            yscrollcommand=self.text_manual_neg_scroll.set
        )
        self.text_manual_neg.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.text_manual_neg_scroll.config(command=self.text_manual_neg.yview)

        self.lbl_manual_param_frame = tk.Frame(self.manual_frame, bg="#f8f8f8")
        self.lbl_manual_param_frame.pack(fill=tk.X, pady=(6, 2))

        self.lbl_manual_param = tk.Label(
            self.lbl_manual_param_frame,
            text=self.textos[self.idioma]["lbl_parametros"],
            bg="#f8f8f8",
            fg="#000000",
            font=("Segoe UI", 10, "bold"),
            relief=tk.SOLID,
            bd=1,
            padx=10,
            pady=6,
            anchor="center",
            width=24
        )
        self.lbl_manual_param.pack(side=tk.LEFT)

        self.text_manual_param_frame = tk.Frame(self.manual_frame)
        self.text_manual_param_frame.pack(fill=tk.X, pady=(0, 2))

        self.text_manual_param_scroll = ttk.Scrollbar(self.text_manual_param_frame, orient="vertical", style="Modern.Vertical.TScrollbar")
        self.text_manual_param_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.text_manual_param = tk.Text(
            self.text_manual_param_frame, height=8, width=10, wrap="word",
            bg="#fdfdfd", bd=2, relief=tk.SOLID, font=("Consolas", 10),
            yscrollcommand=self.text_manual_param_scroll.set
        )
        self.text_manual_param.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.text_manual_param_scroll.config(command=self.text_manual_param.yview)

        self.btn_guardar_metadatos = tk.Button(self.manual_frame, text="💾 Guardar Metadatos", command=self.guardar_como_png_manual, **self.boton_estilo)
        self.btn_guardar_metadatos.pack(pady=(10, 0))

        # Ocultar campos manuales por defecto
        self.manual_frame.pack_forget()

        self.btn_frame_param = tk.Frame(self.text_scroll_frame, bg="#f8f8f8")
        self.btn_frame_param.pack(anchor="e")

        self.btn_copiar_todo = tk.Button(self.tab_metadatos, text="📋 Copiar Todo", command=self.copiar_prompt_total, **self.boton_estilo)
        self.btn_copiar_todo.pack(fill=tk.X, padx=6, pady=(3, 0))

        self.btn_guardar_txt = tk.Button(self.tab_metadatos, text="💾 Guardar como .txt", command=self.guardar_como_txt, **self.boton_estilo)
        self.btn_guardar_txt.pack(fill=tk.X, padx=6, pady=(3, 0))

        self.btn_guardar_png = tk.Button(self.tab_metadatos, text="🖼️ Guardar PNG con Metadatos", command=self.guardar_como_png, **self.boton_estilo)
        self.btn_guardar_png.pack(fill=tk.X, padx=6, pady=(3, 0))
    
        # Botones en una misma fila: [Idioma] [Abrir carpeta]
        boton_fila = tk.Frame(self.tab_metadatos, bg="#f8f8f8")
        boton_fila.pack(padx=6, pady=(6, 5), fill=tk.X)

        self.btn_idioma = tk.Button(boton_fila, command=self.cambiar_idioma, width=10, **self.boton_estilo)
        self.btn_idioma.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 4))

        self.btn_abrir = tk.Button(boton_fila, command=self.seleccionar_carpeta, **self.boton_estilo)
        self.btn_abrir.pack(side=tk.LEFT, expand=True, fill=tk.X)

        # Pestaña de Generador de Prompt
        self.tab_generador = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_generador, text=self.textos[self.idioma]["tab_generador"])

        def obtener_tags_limpios():
            texto = self.entrada.get("1.0", tk.END)
            categorias_a_ignorar = {"artist", "copyright", "characters", "general", "meta", "tag", "tags", "?", "civitai"}
            lineas = texto.splitlines()
            lineas_filtradas = [linea for linea in lineas if linea.strip().lower() not in categorias_a_ignorar and linea.strip() != "?"]
            texto = "\n".join(lineas_filtradas)
            texto = re.sub(r"[^a-zA-Z0-9 ()_\-.,\n]", "", texto)
            texto = re.sub(r"\s+\d+(\.\d+)?[kKmM%+]*\b", "", texto)
            texto = texto.replace("\n", ",").replace(";", ",")
            partes = [parte.strip() for parte in texto.split(",") if parte.strip()]
            return list(dict.fromkeys(partes))

        def limpiar_texto():
            tags = obtener_tags_limpios()
            resultado = ", ".join(tags)
            self.salida.delete("1.0", tk.END)
            self.salida.insert(tk.END, resultado)

        def ordenar_alfabeticamente():
            tags = obtener_tags_limpios()
            resultado = ", ".join(sorted(tags, key=str.lower))
            self.salida.delete("1.0", tk.END)
            self.salida.insert(tk.END, resultado)

        def separar_por_comas():
            texto = self.entrada.get("1.0", tk.END)
            categorias_a_ignorar = {"artist", "copyright", "characters", "general", "meta", "tag", "tags", "?", "civitai"}
            lineas = texto.splitlines()
            lineas_filtradas = [linea for linea in lineas if linea.strip().lower() not in categorias_a_ignorar and linea.strip() != "?"]
            texto = "\n".join(lineas_filtradas)
            texto = re.sub(r"[^a-zA-Z0-9 ()_\-.,\n]", "", texto)
            texto = re.sub(r"\s+\d+(\.\d+)?[kKmM%+]*\b", "", texto)
            if "," not in texto and "\n" not in texto:
                partes = re.split(r"\s+", texto)
            else:
                texto = texto.replace("\n", ",").replace(";", ",")
                partes = [p.strip() for p in texto.split(",")]
            limpio = [p for p in dict.fromkeys(partes) if p.strip()]
            resultado = ", ".join(limpio)
            self.salida.delete("1.0", tk.END)
            self.salida.insert(tk.END, resultado)

        def generar_prompt_profesional():
            tags = obtener_tags_limpios()
            quality_tags = ["masterpiece", "best quality", "ultra-detailed", "high resolution"]
            resultado = ", ".join(quality_tags + tags)
            self.salida.delete("1.0", tk.END)
            self.salida.insert(tk.END, resultado)

        def copiar_texto():
            texto_resultado = self.salida.get("1.0", tk.END).strip()
            self.root.clipboard_clear()
            self.root.clipboard_append(texto_resultado)
            self.root.update()

        def volver():
            self.notebook.select(self.tab_metadatos)

        t = self.textos[self.idioma]
        self.lbl_titulo_generador = tk.Label(self.tab_generador, text=t["prompt_gen_titulo"], font=("Segoe UI", 11, "bold"))
        self.lbl_titulo_generador.pack(pady=(10, 0))

        self.entrada = tk.Text(self.tab_generador, height=10, width=70)
        self.entrada.pack(pady=(5, 0), padx=6)

        self.boton_convertir = tk.Button(self.tab_generador, text=t["btn_limpiar"], command=limpiar_texto, **self.boton_estilo)
        self.boton_convertir.pack(pady=(4, 0), padx=6, fill=tk.X)

        self.boton_ordenar = tk.Button(self.tab_generador, text=t["btn_ordenar"], command=ordenar_alfabeticamente, **self.boton_estilo)
        self.boton_ordenar.pack(pady=(4, 0), padx=6, fill=tk.X)

        self.boton_espacios = tk.Button(self.tab_generador, text=t["btn_comas"], command=separar_por_comas, **self.boton_estilo)
        self.boton_espacios.pack(pady=(4, 0), padx=6, fill=tk.X)

        self.boton_profesional = tk.Button(self.tab_generador, text=t["btn_pro"], command=generar_prompt_profesional, **self.boton_estilo)
        self.boton_profesional.pack(pady=(4, 0), padx=6, fill=tk.X)

        self.boton_copiar = tk.Button(self.tab_generador, text=t["btn_copiar"], command=copiar_texto, **self.boton_estilo)
        self.boton_copiar.pack(pady=(4, 0), padx=6, fill=tk.X)

        self.salida = tk.Text(self.tab_generador, height=10, width=70)
        self.salida.pack(pady=(5, 10), padx=6)

        self.btn_volver = tk.Button(self.tab_generador, text=t["btn_volver"], command=volver, **self.boton_estilo)
        self.btn_volver.pack(padx=6, fill=tk.X)

        # Pestaña de Herramientas Avanzadas
        self.tab_herramientas = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_herramientas, text=self.textos[self.idioma]["tab_herramientas"])

        self.herramientas_frame = tk.Frame(self.tab_herramientas, bg="#f8f8f8")
        self.herramientas_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # Título
        self.lbl_titulo_herramientas = tk.Label(
            self.herramientas_frame,
            text=self.textos[self.idioma]["herramientas_titulo"],
            font=("Segoe UI", 11, "bold"),
            bg="#f8f8f8"
        )

        # Combobox para seleccionar herramienta
        self.herramientas_var = tk.StringVar(value=self.herramienta_seleccionada)
        self.herramientas_combobox = ttk.Combobox(
            self.herramientas_frame,
            textvariable=self.herramientas_var,
            state="readonly",
            values=[
                self.textos[self.idioma]["tab_atajos"],
                self.textos[self.idioma]["tab_previa"],
                self.textos[self.idioma]["tab_exportar"],
                self.textos[self.idioma]["tab_filtro"],
                self.textos[self.idioma]["tab_lote"],
                self.textos[self.idioma]["tab_externo"],
                self.textos[self.idioma]["tab_tema"],
                self.textos[self.idioma]["tab_autoguardar"],
                self.textos[self.idioma]["tab_validacion"],
            ]
        )
        self.herramientas_combobox.pack(pady=5, padx=5, fill=tk.X)
        self.herramientas_combobox.bind("<<ComboboxSelected>>", self.mostrar_herramienta)

        # Descripción de la herramienta
        self.tools_descriptions = tk.Label(
            self.herramientas_frame,
            text="",
            bg="#e6e6e8",
            relief=tk.RAISED,
            bd=2,
            padx=10,
            pady=5,
            font=("Segoe UI", 10, "italic"),
            wraplength=300,
            justify="center"
        )
        self.tools_descriptions.pack(fill=tk.X, pady=(0, 5))

        # Área de contenido de la herramienta
        self.contenido_herramienta = tk.Frame(self.herramientas_frame, bg="#f8f8f8")
        self.contenido_herramienta.pack(fill=tk.BOTH, expand=True)

        # Inicializar herramientas
        self.inicializar_herramientas()

        self.traducir()  # Aplica idioma inicial 
    
    def recargar_galeria_con_preview(self):
        if self.images:  # Solo recargar si hay imágenes cargadas
            self.cargar_carpeta(self.folder, imagen_objetivo=os.path.join(self.folder, self.images[self.current_index]))
           
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

    
    # 🔹 B. Manejo de carpetas y archivos
    def seleccionar_carpeta(self):
        carpeta = filedialog.askdirectory()
        if carpeta:
            self.cargar_carpeta(carpeta)
            guardar_ultima_carpeta(carpeta, self.config)

    def cargar_carpeta(self, folder, imagen_objetivo=None):
        self.folder = folder
        self.images = [f for f in os.listdir(folder) if f.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))]
        self.images.sort()
        self.thumb_refs.clear()
        self.thumb_refs_color = []
        self.thumb_refs_gray = []
        self.miniatura_labels = []
        self.imagenes_seleccionadas.clear()
        self.miniatura_actual = None

        for widget in self.scroll_frame.winfo_children():
            widget.destroy()

        for index, filename in enumerate(self.images):
            path = os.path.join(folder, filename)
            try:
                img = Image.open(path)
                img.thumbnail((THUMB_SIZE[0] - 2, THUMB_SIZE[0] - 4))
                thumb_color = ImageTk.PhotoImage(img.copy())
                img_gray = ImageOps.grayscale(img.copy()).convert("RGB")
                img_gray = ImageEnhance.Brightness(img_gray).enhance(0.6)
                thumb_gray = ImageTk.PhotoImage(img_gray)
                self.thumb_refs_color.append(thumb_color)
                self.thumb_refs_gray.append(thumb_gray)
                frame = tk.Frame(self.scroll_frame, width=THUMB_SIZE[1], height=THUMB_SIZE[1], bg=self.scroll_frame["bg"])
                frame.pack_propagate(False)
                frame.pack(pady=1, padx=(2, 0), anchor="w")
                lbl = tk.Label(frame, image=thumb_gray, cursor="hand2", bd=2, relief=tk.FLAT, bg="#ffffff")
                lbl.pack(expand=True)
                lbl.bind("<Button-1>", lambda e, idx=index: self.mostrar_imagen(idx))
                lbl.bind("<Button-3>", lambda e, idx=index: self.toggle_seleccion_imagen(idx))
                if self.preview_enabled.get():
                    lbl.bind("<Enter>", lambda e, idx=index: self.mostrar_previa(idx))
                    lbl.bind("<Leave>", lambda e: self.ocultar_previa())
                self.miniatura_labels.append((frame, lbl))
            except Exception as e:
                print(f"[ERROR al cargar miniatura {filename}]: {e}")
                continue

        if self.images:
            idx = 0
            if imagen_objetivo:
                base = os.path.basename(imagen_objetivo)
                if base in self.images:
                    idx = self.images.index(base)
            self.current_index = idx
            self.mostrar_imagen(idx)
            
    # 🔹 C. Galería e imagen actual
    def mostrar_imagen(self, index):
        if not self.images:
            return
        
        index %= len(self.images)
        self.current_index = index
        # Marcar la miniatura seleccionada
        if self.miniatura_actual:
           self.miniatura_actual.config(bd=0, relief=tk.FLAT, bg=self.scroll_frame["bg"])

        if index < len(self.miniatura_labels):
           frame, lbl = self.miniatura_labels[index]
           lbl.config(bd=3, relief=tk.SOLID, bg="#d8ecff")  # Color de marco activo
           self.miniatura_actual = lbl

           # 📜 Scroll automático
           self.canvas_gallery.update_idletasks()
           self.canvas_gallery.yview_moveto(frame.winfo_y() / max(0, self.scroll_frame.winfo_height()))

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
   
        if not positivo and not negativo and not parametros:  # Sin metadatos
            self.has_manual_metadata = True
            self.text_scroll_frame.pack_forget()
            self.manual_frame.pack(fill=tk.BOTH, expand=True)
            self.text_manual_pos.delete("1.0", tk.END)
            self.text_manual_neg.delete("1.0", tk.END)
            self.text_manual_param.delete("1.0", tk.END)
            # Añadir parámetros básicos por defecto
            default_params = (
                "width:\n"
                "height:\n"
                "steps:\n"
                "cfgScale:\n"
                "samplerName:\n"
                "ksamplerName:\n"
                "schedule:\n"
                "guidance:\n"
                "sdVae:\n"
                "v1Clip:\n"
                "seed:\n"
                "baseModel:"
            )
            self.text_manual_param.insert(tk.END, default_params)
        else:
            self.has_manual_metadata = False
            self.manual_frame.pack_forget()
            self.text_scroll_frame.pack(fill=tk.BOTH, expand=True)
            self.text_pos.delete("1.0", tk.END)
            self.text_pos.insert(tk.END, positivo)
            self.text_neg.delete("1.0", tk.END)
            self.text_neg.insert(tk.END, negativo)
            self.text_param.delete("1.0", tk.END)
            self.text_param.insert(tk.END, "\n".join(parametros))

        # 🔁 Desaturar todas primero
        for i, (frame, lbl) in enumerate(self.miniatura_labels):
            lbl.config(image=self.thumb_refs_gray[i], bd=0, relief=tk.FLAT, bg=self.scroll_frame["bg"])

        # ✅ Resaltar la actual
        frame, lbl = self.miniatura_labels[index]
        lbl.config(image=self.thumb_refs_color[index], bd=3, relief=tk.SOLID, bg="#d8ecff")
        self.miniatura_actual = lbl

    
    # 🔹 D. Prompt (copiar, guardar, convertir)
    def copiar_prompt_positivo(self):
        pyperclip.copy(self.text_pos.get("1.0", tk.END).strip() if not self.has_manual_metadata else self.text_manual_pos.get("1.0", tk.END).strip())

    
    def copiar_prompt_negativo(self):
        pyperclip.copy(self.text_neg.get("1.0", tk.END).strip() if not self.has_manual_metadata else self.text_manual_neg.get("1.0", tk.END).strip())

    
    def copiar_prompt_total(self):
        if self.has_manual_metadata:
            positivo = self.text_manual_pos.get("1.0", tk.END).strip()
            negativo = self.text_manual_neg.get("1.0", tk.END).strip()
            parametros = self.text_manual_param.get("1.0", tk.END).strip().splitlines()
        else:
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
        if self.has_manual_metadata:
            positivo = self.text_manual_pos.get("1.0", tk.END).strip()
            negativo = self.text_manual_neg.get("1.0", tk.END).strip()
            parametros = self.text_manual_param.get("1.0", tk.END).strip()
        else:
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
        if self.has_manual_metadata:
            positivo = self.text_manual_pos.get("1.0", tk.END).strip()
            negativo = self.text_manual_neg.get("1.0", tk.END).strip()
            parametros = self.text_manual_param.get("1.0", tk.END).strip()
        else:
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
                if not comfy_metadata and not self.has_manual_metadata:
                    messagebox.showwarning("Sin metadatos", "⚠️ La imagen no contiene metadatos válidos ni se han ingresado manualmente.")
                    return

                extracted = extract_prompts_from_comfyui(comfy_metadata) if comfy_metadata else ""
                if extracted.startswith("Error:"):
                    messagebox.showerror("Error", f"❌ Error al procesar: {extracted}")
                    return

                pnginfo = PngImagePlugin.PngInfo()
                if self.has_manual_metadata:
                    metadata = (self.text_manual_pos.get("1.0", tk.END).strip() + "\n"
                              + f"Negative prompt: {self.text_manual_neg.get('1.0', tk.END).strip()}\n"
                              + self.text_manual_param.get("1.0", tk.END).strip())
                else:
                    metadata = extracted if extracted else comfy_metadata

                if metadata:
                    pnginfo.add_text("parameters", metadata)

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

    def guardar_como_png_manual(self):
        if not self.images:
            return
        path_original = os.path.join(self.folder, self.images[self.current_index])
        try:
            with Image.open(path_original) as img:
                positivo = self.text_manual_pos.get("1.0", tk.END).strip()
                negativo = self.text_manual_neg.get("1.0", tk.END).strip()
                parametros = self.text_manual_param.get("1.0", tk.END).strip()
                if not positivo and not negativo and not parametros:
                    messagebox.showwarning("Sin metadatos", "⚠️ No se han ingresado metadatos manuales.")
                    return

                metadata = (positivo + "\n"
                          + f"Negative prompt: {negativo}\n"
                          + parametros)
                pnginfo = PngImagePlugin.PngInfo()
                pnginfo.add_text("parameters", metadata)

                out_path = filedialog.asksaveasfilename(
                    defaultextension=".png",
                    initialfile=f"manual_{self.images[self.current_index]}",
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