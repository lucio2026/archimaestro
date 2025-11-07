
import os
import uuid
from flask import (
    Flask,
    request,
    render_template_string,
    send_from_directory,
)
import ezdxf

app = Flask(__name__)
app.secret_key = "archimaestro-smart"

# cartella per i file caricati e per i risultati
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# limiti
MAX_FILE_MB = 50          # limite massimo accettato dal server
PARSE_WITH_EZDXF_MB = 5   # sotto questo valore proviamo l’analisi “bella” con ezdxf

# HTML INLINE
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
        .download { margin-top: 1rem; }
        a.btn { display:inline-block; padding: 6px 12px; background:#2b6cb0; color:#fff; text-decoration:none; border-radius:4px; }
        a.btn:hover { background:#2c5282; }
    </style>
</head>
<body>
    <h1>🏗️ Archimaestro Translator</h1>
    <p>Carica un file <b>DXF</b> e vedi gli elementi. Se è molto grande lo leggo in modalità “smart”.</p>

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

    {% if download_id %}
        <div class="download">
            <a class="btn" href="{{ url_for('download_result', result_id=download_id) }}">⬇️ Scarica il risultato (.txt)</a>
        </div>
    {% endif %}
</body>
</html>
"""


def file_size_mb(path: str) -> float:
    return os.path.getsize(path) / (1024 * 1024)


@app.route("/", methods=["GET"])
def index():
    return render_template_string(
        PAGE,
        message=None,
        text_result=None,
        filename=None,
        download_id=None,
    )


@app.route("/upload", methods=["POST"])
def upload():
    upfile = request.files.get("file")

    if not upfile or upfile.filename == "":
        return render_template_string(
            PAGE,
            message="Nessun file selezionato.",
            text_result=None,
            filename=None,
            download_id=None,
        )

    filename = upfile.filename
    lowername = filename.lower()

    if not lowername.endswith(".dxf"):
        return render_template_string(
            PAGE,
            message="Per ora il server accetta solo DXF. Esporta il DWG in DXF e ricarica.",
            text_result=None,
            filename=None,
            download_id=None,
        )

    # salviamo il file
    save_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    upfile.save(save_path)

    size_mb = file_size_mb(save_path)
    if size_mb > MAX_FILE_MB:
        return render_template_string(
            PAGE,
            message=f"File troppo grande ({size_mb:.1f} MB). Limite attuale: {MAX_FILE_MB} MB.",
            text_result=None,
            filename=filename,
            download_id=None,
        )

    # se il file è piccolo proviamo l'analisi vera con ezdxf
    text_result = ""
    info_msg = None

    if size_mb <= PARSE_WITH_EZDXF_MB:
        try:
            doc = ezdxf.readfile(save_path)
            msp = doc.modelspace()

            elements = []
            for e in msp:
                elements.append(f"{e.dxftype()}  |  layer={e.dxf.layer}")
            text_result = "\n".join(elements[:200]) or "Nessun elemento trovato nel DXF."
        except Exception as e:
            # fallback a lettura smart
            info_msg = f"Analisi DXF completa non riuscita: {e}. Ho usato la lettura smart."
            text_result = smart_read(save_path)
    else:
        # file grande: lettura smart
        info_msg = (
            f"File grande ({size_mb:.1f} MB). Ho fatto una lettura smart delle prime righe del DXF."
        )
        text_result = smart_read(save_path)

    # salviamo il risultato in un .txt per il download
    result_id = str(uuid.uuid4()) + ".txt"
    result_path = os.path.join(app.config["UPLOAD_FOLDER"], result_id)
    with open(result_path, "w", encoding="utf-8") as f:
        f.write(text_result)

    return render_template_string(
        PAGE,
        message=info_msg,
        text_result=text_result,
        filename=filename,
        download_id=result_id,
    )


def smart_read(path: str, max_lines: int = 400) -> str:
    """Legge il DXF come testo e restituisce le prime N righe.
    Utile per file molto grandi o corrotti per ezdxf.
    """
    lines = []
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for i, line in enumerate(f):
                if i >= max_lines:
                    break
                lines.append(line.rstrip("\n"))
    except Exception as e:
        return f"Impossibile leggere il DXF in modalità smart: {e}"
    return "\n".join(lines)


@app.route("/download/<result_id>")
def download_result(result_id):
    # il file sta in uploads
    return send_from_directory(
        app.config["UPLOAD_FOLDER"],
        result_id,
        as_attachment=True,
        download_name="archimaestro_risultato.txt",
    )


if __name__ == "__main__":
    app.run(debug=True)
