
import os
from flask import Flask, request, render_template_string, send_from_directory
import ezdxf
from ezdxf.lldxf.const import DXFStructureError

app = Flask(__name__)
app.secret_key = "archimaestro-secret"

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

MAX_FILE_MB = 5  # limite file

PAGE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <title>Archimaestro Translator</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 820px; margin: 40px auto; }
        h1 { margin-bottom: .3rem; }
        form { margin: 1rem 0; }
        textarea { width: 100%; height: 320px; }
        .msg { background: #ffe4e4; padding: .5rem .8rem; border: 1px solid #ffb4b4; margin-bottom: 1rem; }
        .ok { background: #e9fff0; border: 1px solid #b2f5c6; }
        a.btn { display:inline-block; margin-top:10px; padding:8px 12px; background:#0077cc; color:white; text-decoration:none; border-radius:4px; }
        a.btn:hover { background:#005fa3; }
    </style>
</head>
<body>
    <h1>🏗️ Archimaestro Translator</h1>
    <p>Carica un file <b>DXF</b> e vedi gli elementi. Poi puoi anche scaricare il risultato.</p>

    {% if message %}
        <div class="msg">{{ message }}</div>
    {% endif %}

    <form action="/upload" method="post" enctype="multipart/form-data">
        <input type="file" name="file" accept=".dxf" required>
        <button type="submit">Carica e analizza</button>
    </form>

    {% if filename %}
        <h2>Risultato per: {{ filename }}</h2>
    {% endif %}

    {% if text_result %}
        <textarea readonly>{{ text_result }}</textarea>
    {% endif %}

    {% if download_name %}
        <p><a class="btn" href="/download/{{ download_name }}">⬇ Scarica risultato (.txt)</a></p>
    {% endif %}
</body>
</html>
"""


@app.route("/", methods=["GET"])
def index():
    return render_template_string(PAGE, message=None, text_result=None, filename=None, download_name=None)


@app.route("/upload", methods=["POST"])
def upload():
    file = request.files.get("file")

    if not file or file.filename == "":
        return render_template_string(PAGE, message="Nessun file selezionato.", text_result=None, filename=None, download_name=None)

    filename = file.filename
    lowername = filename.lower()

    if not lowername.endswith(".dxf"):
        return render_template_string(
            PAGE,
            message="Per ora il server accetta solo DXF. Esporta il DWG in DXF e ricarica.",
            text_result=None,
            filename=None,
            download_name=None
        )

    save_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(save_path)

    # controllo dimensione
    file_size_mb = os.path.getsize(save_path) / (1024 * 1024)
    if file_size_mb > MAX_FILE_MB:
        return render_template_string(
            PAGE,
            message=f"File troppo grande ({file_size_mb:.1f} MB). Limite attuale: {MAX_FILE_MB} MB.",
            text_result=None,
            filename=filename,
            download_name=None
        )

    try:
        doc = ezdxf.readfile(save_path)
        msp = doc.modelspace()

        elements = []
        for i, e in enumerate(msp):
            if i >= 300:
                elements.append("... (tagliato: file molto grande)")
                break
            layer = getattr(e.dxf, "layer", "sconosciuto")
            elements.append(f"{e.dxftype()}  |  layer={layer}")

        text_result = "\n".join(elements) or "Nessun elemento trovato nel DXF."

        # salviamo anche il txt così l'architetto può scaricarlo
        txt_name = filename + ".txt"
        txt_path = os.path.join(app.config["UPLOAD_FOLDER"], txt_name)
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(text_result)

        return render_template_string(
            PAGE,
            message=None,
            text_result=text_result,
            filename=filename,
            download_name=txt_name
        )

    except DXFStructureError as e:
        return render_template_string(
            PAGE,
            message=f"Il DXF è stato caricato ma ha una struttura non standard: {e}",
            text_result=None,
            filename=filename,
            download_name=None
        )
    except Exception as e:
        return render_template_string(
            PAGE,
            message=f"Errore nella lettura del DXF (forse troppo complesso): {e}",
            text_result=None,
            filename=filename,
            download_name=None
        )


@app.route("/download/<path:fname>")
def download(fname):
    # restituisce il txt salvato
    return send_from_directory(app.config["UPLOAD_FOLDER"], fname, as_attachment=True)


if __name__ == "__main__":
    app.run(debug=True)
