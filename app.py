
import os
from flask import Flask, request, render_template_string
import ezdxf

app = Flask(__name__)
app.secret_key = "archimaestro-secret"

# cartella di upload
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# limite semplice (5 MB)
MAX_FILE_SIZE_MB = 5

PAGE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <title>Archimaestro Translator</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 860px; margin: 40px auto; }
        h1 { margin-bottom: .3rem; }
        form { margin: 1rem 0 1.5rem 0; }
        textarea { width: 100%; box-sizing: border-box; }
        .msg { background: #ffe4e4; padding: .5rem .8rem; border: 1px solid #ffb4b4; margin-bottom: 1rem; }
        .ok { background: #e9fff0; border: 1px solid #b2f5c6; }
        .block { margin-bottom: 1.5rem; }
        .label { font-weight: bold; margin-bottom: .4rem; display: block; }
        .two { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
        button { cursor: pointer; }
    </style>
</head>
<body>
    <h1>🏗️ Archimaestro Translator</h1>
    <p>Carica un file <b>DXF</b> e ti mostro gli elementi. Se vuoi,
       premo “Crea prompt per Grock” e ti preparo il testo già pronto da incollare.</p>

    {% if message %}
        <div class="msg">{{ message }}</div>
    {% endif %}

    <form action="/upload" method="post" enctype="multipart/form-data">
        <input type="file" name="file" accept=".dxf" required>
        <!-- due bottoni nello stesso form -->
        <button type="submit" name="action" value="analyze">Carica e analizza</button>
        <button type="submit" name="action" value="grock">Carica e crea prompt Grock</button>
    </form>

    {% if filename %}
        <h2>Risultato per: {{ filename }}</h2>
    {% endif %}

    {% if text_result %}
        <div class="block">
            <span class="label">Elementi trovati (max 200):</span>
            <textarea rows="12" readonly>{{ text_result }}</textarea>
        </div>
    {% endif %}

    {% if grock_prompt %}
        <div class="block">
            <span class="label">Prompt per Grock (copialo e incollalo):</span>
            <textarea rows="15" readonly>{{ grock_prompt }}</textarea>
        </div>
    {% endif %}
</body>
</html>
"""

def build_grock_prompt(filename: str, summary: dict) -> str:
    """
    summary è un dizionario con i conteggi per tipo e per layer.
    Genero un testo che spiega a Grock cosa fare.
    """
    lines = []
    lines.append(f"Ho caricato un disegno CAD (file: {filename}).")
    lines.append("Queste sono le entità che ho trovato:")

    # per tipo
    if summary.get("by_type"):
        for t, n in summary["by_type"].items():
            lines.append(f"- {n} entità di tipo {t}")
    # per layer
    if summary.get("by_layer"):
        lines.append("Per layer:")
        for lay, n in summary["by_layer"].items():
            lines.append(f"  - {n} oggetti sul layer “{lay}”")

    lines.append("")
    lines.append("Crea una breve animazione tecnica in 4 step:")
    lines.append("1. mostra uno sfondo/griglia da tavola tecnica;")
    lines.append("2. disegna prima i muri e i contorni (LINE, LWPOLYLINE, layer che contengono 'MURI' o 'PERIMETRO');")
    lines.append("3. poi fai comparire gli elementi tecnici o di arredo;")
    lines.append("4. alla fine mostra le scritte/cartiglio.")
    lines.append("Stile: pulito, da presentazione architettonica.")

    return "\n".join(lines)


@app.route("/", methods=["GET"])
def index():
    return render_template_string(
        PAGE,
        message=None,
        text_result=None,
        filename=None,
        grock_prompt=None,
    )


@app.route("/upload", methods=["POST"])
def upload():
    action = request.form.get("action", "analyze")  # 'analyze' o 'grock'
    file = request.files.get("file")

    if not file or file.filename == "":
        return render_template_string(PAGE, message="Nessun file selezionato.", text_result=None, filename=None, grock_prompt=None)

    filename = file.filename
    lowername = filename.lower()

    # controllo dimensione (in MB)
    file.seek(0, os.SEEK_END)
    size_mb = file.tell() / (1024 * 1024)
    file.seek(0)
    if size_mb > MAX_FILE_SIZE_MB:
        return render_template_string(
            PAGE,
            message=f"File troppo grande ({size_mb:.1f} MB). Limite attuale: {MAX_FILE_SIZE_MB} MB.",
            text_result=None,
            filename=filename,
            grock_prompt=None,
        )

    if not lowername.endswith(".dxf"):
        return render_template_string(
            PAGE,
            message="Per ora il server accetta solo DXF. Esporta il DWG in DXF e ricarica.",
            text_result=None,
            filename=None,
            grock_prompt=None,
        )

    save_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(save_path)

    try:
        doc = ezdxf.readfile(save_path)
        msp = doc.modelspace()

        elements = []
        by_type = {}
        by_layer = {}

        for e in msp:
            etype = e.dxftype()
            layer = e.dxf.layer

            elements.append(f"{etype}  |  layer={layer}")

            by_type[etype] = by_type.get(etype, 0) + 1
            by_layer[layer] = by_layer.get(layer, 0) + 1

        text_result = "\n".join(elements[:200]) or "Nessun elemento trovato nel DXF."

        grock_prompt = None
        if action == "grock":
            grock_prompt = build_grock_prompt(filename, {"by_type": by_type, "by_layer": by_layer})

        return render_template_string(
            PAGE,
            message=None,
            text_result=text_result,
            filename=filename,
            grock_prompt=grock_prompt,
        )

    except Exception as e:
        return render_template_string(
            PAGE,
            message=f"Errore nella lettura del DXF: {e}",
            text_result=None,
            filename=filename,
            grock_prompt=None,
        )


if __name__ == "__main__":
    app.run(debug=True)
