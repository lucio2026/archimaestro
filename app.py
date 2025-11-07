
import os
from flask import Flask, request, render_template_string
import ezdxf

app = Flask(__name__)
app.secret_key = "archimaestro-secret"

# cartella di upload
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# 1) limite duro di Flask: 30 MB
app.config["MAX_CONTENT_LENGTH"] = 30 * 1024 * 1024  # 30 MB

# 2) nostro limite logico
MAX_FILE_SIZE_MB = 30
PARSE_WITH_EZDXF_MB = 5  # sotto i 5 MB uso ezdxf, sopra leggo smart

PAGE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <title>Archimaestro Translator</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 860px; margin: 40px auto; }
        textarea { width: 100%; box-sizing: border-box; }
        .msg { background: #ffe4e4; padding: .5rem .8rem; border: 1px solid #ffb4b4; margin-bottom: 1rem; }
        .label { font-weight: bold; margin-bottom: .4rem; display: block; }
    </style>
</head>
<body>
    <h1>🏗️ Archimaestro Translator</h1>
    <p>Carica un DXF. Se è grande lo leggo in modalità “smart”. Puoi anche generare il prompt per Grock.</p>

    {% if message %}
        <div class="msg">{{ message }}</div>
    {% endif %}

    <form action="/upload" method="post" enctype="multipart/form-data">
        <input type="file" name="file" accept=".dxf" required>
        <button type="submit" name="action" value="analyze">Carica e analizza</button>
        <button type="submit" name="action" value="grock">Carica e crea prompt Grock</button>
    </form>

    {% if filename %}
        <h2>Risultato per: {{ filename }}</h2>
    {% endif %}

    {% if text_result %}
        <div>
            <span class="label">Elementi / righe lette:</span>
            <textarea rows="14" readonly>{{ text_result }}</textarea>
        </div>
    {% endif %}

    {% if grock_prompt %}
        <div style="margin-top:1rem;">
            <span class="label">Prompt per Grock:</span>
            <textarea rows="14" readonly>{{ grock_prompt }}</textarea>
        </div>
    {% endif %}
</body>
</html>
"""


def smart_read(path: str, max_lines: int = 400) -> str:
    """Legge il DXF come testo (riga per riga) senza caricare tutto in RAM."""
    lines = []
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for i, line in enumerate(f):
            if i >= max_lines:
                lines.append("... (tagliato perché file grande)")
                break
            lines.append(line.rstrip("\n"))
    return "\n".join(lines)


def build_grock_prompt_from_counts(filename: str, by_type: dict, by_layer: dict, smart: bool = False) -> str:
    lines = []
    lines.append(f"Ho caricato un disegno CAD (file: {filename}).")
    if smart:
        lines.append("Il file era abbastanza grande, quindi ho fatto una lettura parziale (smart) del DXF.")
    lines.append("Queste sono le entità/layer che ho rilevato:")

    if by_type:
        for t, n in by_type.items():
            lines.append(f"- {n} entità di tipo {t}")
    if by_layer:
        lines.append("Per layer:")
        for lay, n in by_layer.items():
            lines.append(f"  - {n} oggetti sul layer “{lay}”")

    lines.append("")
    lines.append("Crea una breve animazione tecnica in 4 step:")
    lines.append("1. mostra una base/griglia da tavola tecnica;")
    lines.append("2. disegna prima i muri/contorni (LINE, LWPOLYLINE, layer con 'MURI' o 'PERIMETRO');")
    lines.append("3. poi fai comparire gli elementi tecnici o di arredo;")
    lines.append("4. alla fine mostra le scritte/cartiglio.")
    lines.append("Stile: pulito, da presentazione architettonica.")
    return "\n".join(lines)


@app.route("/", methods=["GET"])
def index():
    return render_template_string(PAGE, message=None, text_result=None, filename=None, grock_prompt=None)


@app.route("/upload", methods=["POST"])
def upload():
    action = request.form.get("action", "analyze")
    file = request.files.get("file")

    if not file or file.filename == "":
        return render_template_string(PAGE, message="Nessun file selezionato.", text_result=None, filename=None, grock_prompt=None)

    filename = file.filename
    lowername = filename.lower()

    if not lowername.endswith(".dxf"):
        return render_template_string(PAGE, message="Accetto solo DXF. Esporta il DWG in DXF e ricarica.", text_result=None, filename=None, grock_prompt=None)

    save_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(save_path)

    size_mb = os.path.getsize(save_path) / (1024 * 1024)
    if size_mb > MAX_FILE_SIZE_MB:
        return render_template_string(
            PAGE,
            message=f"File troppo grande ({size_mb:.1f} MB). Limite attuale: {MAX_FILE_SIZE_MB} MB.",
            text_result=None,
            filename=filename,
            grock_prompt=None,
        )

    # se è piccolo → analisi vera
    if size_mb <= PARSE_WITH_EZDXF_MB:
        try:
            doc = ezdxf.readfile(save_path)
            msp = doc.modelspace()

            elements = []
            by_type = {}
            by_layer = {}
            for e in msp:
                et = e.dxftype()
                lay = e.dxf.layer
                elements.append(f"{et}  |  layer={lay}")
                by_type[et] = by_type.get(et, 0) + 1
                by_layer[lay] = by_layer.get(lay, 0) + 1

            text_result = "\n".join(elements[:200]) or "Nessun elemento trovato nel DXF."

            grock_prompt = None
            if action == "grock":
                grock_prompt = build_grock_prompt_from_counts(filename, by_type, by_layer, smart=False)

            return render_template_string(
                PAGE,
                message=None,
                text_result=text_result,
                filename=filename,
                grock_prompt=grock_prompt,
            )
        except Exception as e:
            # se ezdxf fallisce, torniamo alla smart
            text_result = smart_read(save_path)
            return render_template_string(
                PAGE,
                message=f"Analisi DXF completa non riuscita ({e}). Ho fatto una lettura smart.",
                text_result=text_result,
                filename=filename,
                grock_prompt=None,
            )

    # se è grande → lettura smart
    text_result = smart_read(save_path)
    grock_prompt = None
    if action == "grock":
        # con file grande non abbiamo i conteggi precisi, quindi prompt generico
        grock_prompt = build_grock_prompt_from_counts(filename, {}, {}, smart=True)

    return render_template_string(
        PAGE,
        message=f"File grande ({size_mb:.1f} MB): lettura smart eseguita.",
        text_result=text_result,
        filename=filename,
        grock_prompt=grock_prompt,
    )


if __name__ == "__main__":
    app.run(debug=True)
