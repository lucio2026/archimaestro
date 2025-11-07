
import os
from flask import Flask, render_template, request, redirect, url_for, flash
import ezdxf

app = Flask(__name__)
app.secret_key = "metti-una-password-qualsiasi"

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# 1) test: se questa pagina si vede, la app funziona su Render
@app.route("/", methods=["GET"])
def home():
    return "Archimaestro è vivo su Render ✅"

# 2) rotta vera (per dopo)
@app.route("/upload", methods=["POST"])
def upload():
    file = request.files.get("file")

    if not file or file.filename == "":
        flash("Nessun file selezionato.")
        return redirect(url_for("home"))

    filename = file.filename.lower()

    if not filename.endswith(".dxf"):
        flash("Per ora il server accetta solo file DXF. Esporta il DWG in DXF e ricarica.")
        return redirect(url_for("home"))

    save_path = os.path.join(app.config["UPLOAD_FOLDER"], file.filename)
    file.save(save_path)

    try:
        doc = ezdxf.readfile(save_path)
        msp = doc.modelspace()
        elements = [f"{e.dxftype()} | layer={e.dxf.layer}" for e in msp]
        text_result = "\n".join(elements[:200]) or "Nessun elemento trovato nel DXF."
    except Exception as e:
        text_result = f"Errore nella lettura del DXF: {e}"

    # per adesso lo mostriamo semplice
    return text_result

if __name__ == "__main__":
    app.run()
