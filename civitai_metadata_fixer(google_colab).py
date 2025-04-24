import os
import json
from PIL import Image, PngImagePlugin

input_folder = "/content/"  #@param {type:"string"}

def extract_prompts_from_comfyui(json_str):
    try:
        nodes = json.loads(json_str)
        node_data = {}
        prompt = ""
        negative_prompt = ""

        # Map para rastrear cuál nodo está conectado como negativo
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

        # Otros metadatos
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

        # Formato estilo A1111 compatible con Civitai
        metadata = prompt + "\n"
        metadata += f"Negative prompt: {negative_prompt}\n"
        metadata += f"Steps: {steps}, Sampler: {sampler}, CFG scale: {cfg}, Seed: {seed}, Size: {width}x{height}, Model: {model}"

        return metadata

    except Exception as e:
        return f"Error: {e}"

# Reescribir imágenes
for filename in os.listdir(input_folder):
    if filename.lower().endswith(".png"):
        image_path = os.path.join(input_folder, filename)
        with Image.open(image_path) as img:
            comfy_metadata = img.info.get("prompt", None)
            if not comfy_metadata:
                print(f"⚠️ {filename} no contiene metadatos válidos.")
                continue
            extracted = extract_prompts_from_comfyui(comfy_metadata)
            if extracted.startswith("Error:"):
                print(f"❌ {filename}: {extracted}")
                continue

            pnginfo = PngImagePlugin.PngInfo()
            pnginfo.add_text("parameters", extracted)

            out_path = os.path.join(input_folder, f"fixed_{filename}")
            img.save(out_path, "PNG", pnginfo=pnginfo)
            print(f"✅ {filename} convertido con metadata Civitai.")
