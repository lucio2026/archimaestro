
import os
from flask import Flask, request, render_template_string

app = Flask(__name__)
app.secret_key = "archimaestro-secret"

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

MAX_SIZE_MB = 5  # oltre questo facciamo modalità smart

HTML_PAGE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <title>Archimaestro DXF → Grock</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 980px; margin: 40px auto; }
        textarea { width: 100%; }
        #dxf-box { height: 200px; }
        #semantic-box { height: 140px; }
        #prompt-box { height: 220px; }
        .msg { background: #ffe4e4; padding: .5rem .8rem; border: 1px solid #ffb4b4; margin-bottom: 1rem; }
        h1 { margin-bottom: 0.3rem; }
        button { cursor: pointer; margin-right: .4rem; }
    </style>
</head>
<body>
    <h1>🏗️ Archimaestro – versione “Bagno realistico”</h1>
    <p>Carica un DXF e genero: lettura tecnica → descrizione ambiente → prompt fotorealistico per Grock.</p>

    {% if message %}
      <div class="msg">{{ message }}</div>
    {% endif %}

    <form action="/upload" method="post" enctype="multipart/form-data">
        <input type="file" name="file" accept=".dxf" required>
        <button type="submit" name="mode" value="analyze">Carica e analizza</button>
        <button type="submit" name="mode" value="grock">Carica e crea prompt Grock</button>
    </form>

    {% if filename %}
      <h2>File: {{ filename }}</h2>
    {% endif %}

    {% if dxf_dump %}
      <h3>1. Lettura tecnica (prime entità):</h3>
      <textarea id="dxf-box" readonly>{{ dxf_dump }}</textarea>
    {% endif %}

    {% if semantic %}
      <h3>2. Analisi semantica ambiente:</h3>
      <textarea id="semantic-box" readonly>{{ semantic }}</textarea>
    {% endif %}

    {% if grock_prompt %}
      <h3>3. Prompt fotorealistico per Grock:</h3>
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
        });
    }
    </script>
</body>
</html>
"""

def read_dxf_smart(path, max_lines=200):
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

def analyze_dxf_semantic(entities_dump: str):
    """Guarda il dump e prova a capire se è un bagno o stanza piccola."""
    dump_low = entities_dump.lower()
    is_bath = False
    clues = []

    # indizi dai layer
    for kw in ["wc", "bagno", "sanitari", "arredo_bagno", "bidet"]:
        if kw in dump_low:
            is_bath = True
            clues.append(f"Trovato layer o nome: {kw}")

    # se non ci sono indizi, ma è un disegno piccolo, lo dichiariamo generico
    if is_bath:
        return "Ambiente riconosciuto: BAGNO o locale sanitario. " + "; ".join(clues)
    else:
        return "Ambiente non chiaramente riconosciuto come bagno. Considerare descrizione manuale (bagno 2,5 x 1,8 m)."

def build_grock_prompt_from_semantic(filename: str, semantic: str):
    """Costruisco il super-prompt per Grock."""
    base = []
    base.append(f"Ho caricato un disegno CAD (DXF) chiamato “{filename}”.")
    if "BAGNO" in semantic.upper():
        base.append("Il contenuto sembra riferito a un BAGNO / locale sanitario.")
        base.append("Genera un rendering fotorealistico di un bagno moderno di piccole dimensioni (circa 2,5 x 1,8 m).")
        base.append("Imposta la camera a 1,5 m di altezza, vista leggermente angolata verso la parete principale.")
        base.append("Pareti chiare (bianco o sabbia), pavimento in gres grigio chiaro.")
        base.append("Inserisci: lavabo con specchio sulla parete frontale, wc e bidet sulla parete di destra, doccia a filo pavimento sul lato corto rimanente.")
        base.append("Illuminazione morbida, con luce naturale da finestra alta o luce zenitale.")
        base.append("Stile: architettura d’interni, pulito, senza persone.")
    else:
        base.append("Il contenuto non è stato riconosciuto automaticamente come bagno.")
        base.append("Genera comunque un interno architettonico pulito, con pareti chiare e arredo minimale.")
        base.append("Includi elementi sanitari se il contesto lo richiede.")
    base.append("Mostra l’ambiente come se provenisse da un disegno tecnico CAD.")
    return "\n".join(base)

@app.route("/", methods=["GET"])
def index():
    return render_template_string(HTML_PAGE,
                                  message=None,
                                  filename=None,
                                  dxf_dump=None,
                                  semantic=None,
                                  grock_prompt=None)

@app.route("/upload", methods=["POST"])
def upload():
    upfile = request.files.get("file")
    mode = request.form.get("mode", "analyze")

    if not upfile or upfile.filename == "":
        return render_template_string(HTML_PAGE, message="Nessun file selezionato.",
                                      filename=None, dxf_dump=None, semantic=None, grock_prompt=None)

    filename = upfile.filename
    if not filename.lower().endswith(".dxf"):
        return render_template_string(HTML_PAGE, message="Caricare solo DXF (esporta il DWG in DXF).",
                                      filename=None, dxf_dump=None, semantic=None, grock_prompt=None)

    save_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    upfile.save(save_path)

    size_mb = os.path.getsize(save_path) / (1024 * 1024)

    # 1) lettura tecnica
    if size_mb > MAX_SIZE_MB:
        dxf_dump = read_dxf_smart(save_path, max_lines=250)
        msg = f"File grande ({size_mb:.1f} MB). Lettura smart eseguita."
    else:
        # provo con ezdxf
        try:
            import ezdxf
            doc = ezdxf.readfile(save_path)
            msp = doc.modelspace()
            lines = []
            for e in msp:
                lines.append(f"{e.dxftype()} | layer={e.dxf.layer}")
            dxf_dump = "\n".join(lines[:250]) or "Nessun elemento trovato."
            msg = None
        except Exception as e:
            dxf_dump = read_dxf_smart(save_path, max_lines=250)
            msg = f"DXF complesso, uso lettura smart. Dettaglio: {e}"

    # 2) analisi semantica
    semantic = analyze_dxf_semantic(dxf_dump)

    # 3) prompt per grock (solo se richiesto)
    grock_prompt = None
    if mode == "grock":
        grock_prompt = build_grock_prompt_from_semantic(filename, semantic)

    return render_template_string(HTML_PAGE,
                                  message=msg,
                                  filename=filename,
                                  dxf_dump=dxf_dump,
                                  semantic=semantic,
                                  grock_prompt=grock_prompt)

if __name__ == "__main__":
    app.run(debug=True)
