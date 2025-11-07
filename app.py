
import os
from flask import Flask, request, render_template_string

app = Flask(__name__)
app.secret_key = "archimaestro-secret"

# cartella per i file caricati
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# limite "normale" del server (5 MB circa su Render free)
MAX_SIZE_MB = 5


HTML_PAGE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <title>Archimaestro Translator</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 900px; margin: 40px auto; }
        h1 { margin-bottom: .3rem; }
        form { margin: 1rem 0; }
        textarea { width: 100%; }
        #dxf-box { height: 240px; }
        #prompt-box { height: 220px; }
        .msg { background: #ffe4e4; padding: .5rem .8rem; border: 1px solid #ffb4b4; margin-bottom: 1rem; }
        .ok { background: #e9fff0; border: 1px solid #b2f5c6; }
        .topbar { margin-bottom: 1rem; }
        button { cursor: pointer; }
    </style>
</head>
<body>
    <h1>🟧 Archimaestro Translator</h1>
    <p>Carica un DXF. Se è grande lo leggo in modalità “smart”. Puoi anche generare il prompt per Grock.</p>

    {% if message %}
        <div class="msg">{{ message }}</div>
    {% endif %}

    <form action="/upload" method="post" enctype="multipart/form-data">
        <input type="file" name="file" accept=".dxf" required>
        <button type="submit" name="mode" value="normal">Carica e analizza</button>
        <button type="submit" name="mode" value="grock">Carica e crea prompt Grock</button>
    </form>

    {% if filename %}
        <h2>Risultato per: {{ filename }}</h2>
    {% endif %}

    {% if text_result %}
        <h3>Elementi / righe lette:</h3>
        <textarea id="dxf-box" readonly>{{ text_result }}</textarea>
    {% endif %}

    {% if grock_prompt %}
        <h3>Prompt per Grock:</h3>
        <textarea id="prompt-box" readonly>{{ grock_prompt }}</textarea>
        <p><button onclick="copyPrompt()">📋 Copia prompt</button></p>
    {% endif %}

    <script>
    function copyPrompt() {
        const ta = document.getElementById('prompt-box');
        if (!ta) return;
        ta.select();
        ta.setSelectionRange(0, 99999);
        navigator.clipboard.writeText(ta.value).then(() => {
            alert("✅ Prompt copiato negli appunti.");
        }).catch(() => {
            alert("Copia non riuscita, copia a mano.");
        });
    }
    </script>
</body>
</html>
"""


def read_dxf_smart(path, max_lines=250):
    """Lettura 'smart' per DXF grandi: leggo il file di testo e prendo solo le prime righe."""
    try:
        lines = []
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for i, line in enumerate(f):
                if i >= max_lines:
                    break
                lines.append(line.rstrip("\n"))
        return "\n".join(lines) if lines else "Nessun contenuto leggibile."
    except Exception as e:
        return f"Errore lettura smart: {e}"


def build_grock_prompt(filename, text_excerpt):
    """Costruisce il testo già pronto da incollare su Grock."""
    return (
        f"Ho caricato un disegno CAD (file: {filename}).\\n"
        "Il file era grande, quindi ho fatto una lettura parziale (smart) del DXF.\\n"
        "Queste sono alcune righe/entità che ho rilevato:\\n"
        "------------------------------\\n"
        f"{text_excerpt}\\n"
        "------------------------------\\n"
        "Crea una breve animazione tecnica in 4 step:\\n"
        "1. mostra una base/griglia da tavola tecnica;\\n"
        "2. disegna prima i muri/contorni (LINE, LWPOLYLINE, layer con 'MURI' o 'PERIMETRO');\\n"
        "3. poi fai comparire gli elementi tecnici o di arredo;\\n"
        "4. alla fine mostra le scritte/cartiglio.\\n"
        "Stile: pulito, da presentazione architettonica."
    )


@app.route("/", methods=["GET"])
def index():
    return render_template_string(
        HTML_PAGE,
        message=None,
        text_result=None,
        filename=None,
        grock_prompt=None,
    )


@app.route("/upload", methods=["POST"])
def upload():
    upfile = request.files.get("file")
    mode = request.form.get("mode", "normal")

    if not upfile or upfile.filename == "":
        return render_template_string(
            HTML_PAGE,
            message="Nessun file selezionato.",
            text_result=None,
            filename=None,
            grock_prompt=None,
        )

    filename = upfile.filename
    lowername = filename.lower()

    if not lowername.endswith(".dxf"):
        return render_template_string(
            HTML_PAGE,
            message="Per ora il server accetta solo DXF. Esporta il DWG in DXF e ricarica.",
            text_result=None,
            filename=None,
            grock_prompt=None,
        )

    save_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    upfile.save(save_path)

    # controllo dimensione
    size_mb = os.path.getsize(save_path) / (1024 * 1024)

    # se è troppo grande uso lettura smart
    if size_mb > MAX_SIZE_MB:
        text_result = read_dxf_smart(save_path, max_lines=300)
        msg = f"File grande ({size_mb:.1f} MB): lettura smart eseguita."
    else:
        # provo a usare ezdxf normalmente
        try:
            import ezdxf
            doc = ezdxf.readfile(save_path)
            msp = doc.modelspace()
            lines = []
            for e in msp:
                lines.append(f"{e.dxftype()}  |  layer={e.dxf.layer}")
            text_result = "\n".join(lines[:300]) or "Nessun elemento trovato nel DXF."
            msg = None
        except Exception as e:
            # se fallisce uso comunque la smart
            text_result = read_dxf_smart(save_path, max_lines=300)
            msg = f"DXF complesso, passo alla lettura smart. Dettaglio: {e}"

    grock_prompt = None
    if mode == "grock":
        grock_prompt = build_grock_prompt(filename, text_result[:1200])

    return render_template_string(
        HTML_PAGE,
        message=msg,
        text_result=text_result,
        filename=filename,
        grock_prompt=grock_prompt,
    )


if __name__ == "__main__":
    app.run(debug=True)
