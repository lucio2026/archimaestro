import os
from flask import Flask, request, render_template_string
import ezdxf

app = Flask(__name__)
app.secret_key = "archimaestro-secret"

# cartella dove salvo temporaneamente i DXF
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# limite "fisico" – oltre questo facciamo solo lettura smart
MAX_SIZE = 5 * 1024 * 1024   # 5 MB

# -----------------------------------------------------
# HTML unico (una pagina sola)
# -----------------------------------------------------
PAGE = r"""
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <title>Archimaestro Translator</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 980px; margin: 30px auto 80px; line-height: 1.4; }
        h1 { display: flex; align-items: center; gap: .6rem; margin-bottom: .2rem; }
        h1 span.logo { width: 26px; height: 26px; background: #ff9944; border-radius: 7px; display: inline-block; }
        .sub { color: #555; margin-bottom: 1rem; }
        .alert { background: #ffe4e4; border: 1px solid #ffb4b4; padding: .5rem .8rem; margin-bottom: 1rem; }
        .ok { background: #edfdf3; border: 1px solid #c6f6d5; }
        textarea { width: 100%; height: 180px; font-family: ui-monospace, SFMono-Regular, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace; font-size: .8rem; }
        form { margin-bottom: 1rem; }
        button { cursor: pointer; }
        .btn { background: #f3f4f6; border: 1px solid #ccc; padding: .4rem .8rem; border-radius: 4px; }
        .btn-primary { background: #ef4444; color: white; border-color: #ef4444; }
        .section-title { margin: 1.6rem 0 .4rem; font-weight: bold; }
        .muted { color: #666; font-size: .8rem; }
    </style>
    <script>
      function copiaPrompt() {
        const el = document.getElementById('prompt_grock');
        if (!el) return;
        el.select();
        el.setSelectionRange(0, 99999);
        document.execCommand("copy");
        alert("Prompt copiato!");
      }
    </script>
</head>
<body>
    <h1><span class="logo"></span> Archimaestro Translator</h1>
    <div class="sub">Carica un DXF. Se è grande lo leggo in modalità “smart”. Puoi anche generare il prompt per Grock.</div>

    {% if message %}
      <div class="alert {{ 'ok' if ok else '' }}">{{ message }}</div>
    {% endif %}

    <form action="/upload" method="post" enctype="multipart/form-data">
        <input type="file" name="file" accept=".dxf" required>
        <button type="submit" name="azione" value="analizza" class="btn">Carica e analizza</button>
        <button type="submit" name="azione" value="prompt" class="btn">Carica e crea prompt Grock</button>
    </form>

    {% if filename %}
      <h2>File: {{ filename }}</h2>
    {% endif %}

    {% if dxf_preview %}
      <div class="section-title">1. Lettura tecnica (prime entità):</div>
      <textarea readonly>{{ dxf_preview }}</textarea>
    {% endif %}

    {% if ambiente %}
      <div class="section-title">2. Analisi semantica ambiente:</div>
      <textarea readonly>{{ ambiente }}</textarea>
    {% endif %}

    {% if prompt_grock %}
      <div class="section-title">3. Prompt fotorealistico per Grock:</div>
      <textarea id="prompt_grock" readonly>{{ prompt_grock }}</textarea>
      <p><button class="btn" onclick="copiaPrompt()">📋 Copia prompt</button></p>
    {% endif %}

    <p class="muted">Link app: {{ app_url }}</p>
</body>
</html>
"""

# -----------------------------------------------------
# funzioni di utilità
# -----------------------------------------------------
def detect_locale(filename: str, text_snippet: str) -> str | None:
    """Prova a capire che ambiente è dal nome file o dalle prime righe."""
    name = (filename or "").lower()
    txt = (text_snippet or "").lower()

    # lista di (parole, etichetta)
    mapping = [
        (["bagno", "wc", "toilet"], "bagno"),
        (["cucina", "kitchen"], "cucina"),
        (["soggiorno", "living", "salone", "zona giorno"], "soggiorno"),
        (["camera", "bedroom"], "camera da letto"),
        (["ufficio", "office"], "ufficio"),
    ]

    for keywords, label in mapping:
        for kw in keywords:
            if kw in name or kw in txt:
                return label

    return None  # non riconosciuto


def build_prompt_specifico(tipo: str, filename: str, info: str) -> str:
    """Prompt quando sappiamo il tipo di ambiente."""
    base = (
        f"Ho caricato un disegno CAD (DXF) chiamato “{filename}”.\n"
        f"Il contenuto sembra riferito a un {tipo}.\n"
        "Genera un rendering fotorealistico coerente con un progetto architettonico.\n"
        "Mantieni proporzioni e impostazione del disegno CAD.\n"
    )

    if tipo == "bagno":
        extra = (
            "Mostra un bagno moderno di piccole/medie dimensioni.\n"
            "Inserisci sanitari e lavabo con mobile, doccia o vasca secondo logica, finiture chiare.\n"
        )
    elif tipo == "cucina":
        extra = (
            "Mostra una cucina moderna lineare o ad angolo, piani in materiale tecnico, pensili, zona lavello e cottura.\n"
        )
    elif tipo == "soggiorno":
        extra = (
            "Mostra una zona giorno luminosa con pavimento continuo, arredi essenziali, stile contemporaneo.\n"
        )
    elif tipo == "camera da letto":
        extra = (
            "Mostra una camera da letto con letto matrimoniale, comodini e armadio, toni neutri e luce morbida.\n"
        )
    elif tipo == "ufficio":
        extra = (
            "Mostra un piccolo ufficio/studio con scrivania, seduta ergonomica e scaffalature.\n"
        )
    else:
        extra = ""

    coda = (
        "Illuminazione morbida, da interno, senza persone.\n"
        "Mostra l’ambiente come se provenisse da un disegno tecnico CAD ma reso.\n"
        f"(Prime righe lette dal DXF, utili al modello):\n{info}\n"
    )

    return base + extra + coda


def build_prompt_neutro(filename: str, info: str) -> str:
    """Prompt quando non sappiamo che cos'è."""
    return (
        f"Ho caricato un disegno CAD (DXF) chiamato “{filename}”.\n"
        "Il tipo di ambiente non è esplicito, quindi interpreta il DXF come un locale architettonico standard.\n"
        "Genera un rendering fotorealistico dell'ambiente rispettando le proporzioni del disegno.\n"
        "Usa materiali e colori neutri (pareti chiare, pavimento tecnico o gres).\n"
        "Inquadratura leggermente angolata, stile presentazione architettonica.\n"
        "Mostra l’ambiente come derivato da un disegno tecnico CAD.\n"
        f"(Prime righe lette dal DXF, utili al modello):\n{info}\n"
    )


# -----------------------------------------------------
# route principale
# -----------------------------------------------------
@app.route("/", methods=["GET"])
def index():
    return render_template_string(
        PAGE,
        message=None,
        ok=False,
        filename=None,
        dxf_preview=None,
        ambiente=None,
        prompt_grock=None,
        app_url="https://archimaestro.onrender.com/"
    )


@app.route("/upload", methods=["POST"])
def upload():
    file = request.files.get("file")
    azione = request.form.get("azione", "analizza")

    if not file or file.filename == "":
        return render_template_string(
            PAGE,
            message="Nessun file selezionato.",
            ok=False,
            filename=None,
            dxf_preview=None,
            ambiente=None,
            prompt_grock=None,
            app_url="https://archimaestro.onrender.com/"
        )

    filename = file.filename
    if not filename.lower().endswith(".dxf"):
        return render_template_string(
            PAGE,
            message="Per ora il server accetta solo file DXF. Esporta il DWG in DXF e ricarica.",
            ok=False,
            filename=None,
            dxf_preview=None,
            ambiente=None,
            prompt_grock=None,
            app_url="https://archimaestro.onrender.com/"
        )

    # salvataggio
    save_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(save_path)

    # controllo dimensione
    file_size = os.path.getsize(save_path)
    smart_mode = file_size > MAX_SIZE

    try:
        if smart_mode:
            # lettura "smart": apriamo il file grezzo e prendiamo solo l'inizio
            with open(save_path, "r", encoding="latin-1", errors="ignore") as f:
                raw = f.readlines()
            # prendo le prime 200 righe
            preview_lines = raw[:200]
            dxf_preview = "".join(preview_lines)
            message = f"File grande ({round(file_size/1024/1024,1)} MB): lettura smart eseguita."
        else:
            # lettura normale con ezdxf
            doc = ezdxf.readfile(save_path)
            msp = doc.modelspace()
            preview_lines = []
            for e in msp:
                preview_lines.append(f"{e.dxftype()} | layer={e.dxf.layer}")
                if len(preview_lines) >= 200:
                    break
            dxf_preview = "\n".join(preview_lines)
            message = "File letto correttamente."
    except Exception as e:
        return render_template_string(
            PAGE,
            message=f"Errore nella lettura del DXF: {e}",
            ok=False,
            filename=filename,
            dxf_preview=None,
            ambiente=None,
            prompt_grock=None,
            app_url="https://archimaestro.onrender.com/"
        )

    # analisi semantica molto semplice
    ambiente_rilevato = detect_locale(filename, dxf_preview)
    if ambiente_rilevato:
        ambiente_text = f"Ambiente riconosciuto come: {ambiente_rilevato}."
    else:
        ambiente_text = "Ambiente non chiaramente riconosciuto. Descriverlo meglio nel prompt se serve."

    # se l’utente ha chiesto il prompt
    if azione == "prompt":
        if ambiente_rilevato:
            prompt = build_prompt_specifico(ambiente_rilevato, filename, dxf_preview[:500])
        else:
            prompt = build_prompt_neutro(filename, dxf_preview[:500])
    else:
        prompt = None

    return render_template_string(
        PAGE,
        message=message,
        ok=not smart_mode,
        filename=filename,
        dxf_preview=dxf_preview,
        ambiente=ambiente_text,
        prompt_grock=prompt,
        app_url="https://archimaestro.onrender.com/"
    )


if __name__ == "__main__":
    # per esecuzione locale
    app.run(debug=True)
