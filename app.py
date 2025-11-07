import os
from flask import Flask, request, redirect, url_for, flash, render_template_string
import ezdxf

app = Flask(__name__)
app.secret_key = "archimaestro-secret"

# cartella per i file caricati
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# HTML INLINE (così non dipendiamo da /templates)
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
    </style>
</head>
<body>
    <h1>🏗️ Archimaestro Translator</h1>
    <p>Carica un file <b>DXF</b> (da AutoCAD / DWG esportato in DXF) e ti mostro i primi elementi trovati.</p>

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
</body>
</html>
"""


@app.route("/", methods=["GET"])
def index():
    return render_template_string(PAGE, message=None, text_result=None, filename=None)


@app.route("/upload", methods=["POST"])
def upload():
    file = request.files.get("file")

    if not file or file.filename == "":
        return render_template_string(PAGE, message="Nessun file selezionato.", text_result=None, filename=None)

    filename = file.filename
    lowername = filename.lower()

    # su Render leggiamo SOLO DXF
    if not lowername.endswith(".dxf"):
        return render_template_string(
            PAGE,
            message="Per ora il server accetta solo DXF. Esporta il DWG in DXF e ricarica.",
            text_result=None,
            filename=None
        )

    save_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(save_path)

    # provo a leggere il DXF
    try:
        doc = ezdxf.readfile(save_path)
        msp = doc.modelspace()
        elements = []
        for e in msp:
            elements.append(f"{e.dxftype()}  |  layer={e.dxf.layer}")
        text_result = "\n".join(elements[:200]) or "Nessun elemento trovato nel DXF."
        return render_template_string(PAGE, message=None, text_result=text_result, filename=filename)
    except Exception as e:
        return render_template_string(
            PAGE,
            message=f"Errore nella lettura del DXF: {e}",
            text_result=None,
            filename=filename
        )


if __name__ == "__main__":
    # questo serve solo se lo lanci in locale
    app.run(debug=True)
