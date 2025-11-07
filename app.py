
import os
from flask import Flask, render_template, request, redirect, url_for, flash
import ezdxf

# diciamo a Flask dove sono template e static
app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = "archimaestro-secret"

# cartella upload
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER


@app.route("/", methods=["GET"])
def index():
    # prima apertura: pagina vuota
    return render_template("index.html", text_result=None, filename=None)


@app.route("/upload", methods=["POST"])
def upload():
    file = request.files.get("file")

    if not file or file.filename == "":
        flash("Nessun file selezionato.")
        return redirect(url_for("index"))

    filename = file.filename
    lowername = filename.lower()

    # SU RENDER: leggiamo solo DXF
    if not lowername.endswith(".dxf"):
        flash("Per ora il server accetta solo file DXF. Esporta il DWG in DXF e ricarica.")
        return redirect(url_for("index"))

    save_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(save_path)

    # prova a leggere il DXF
    try:
        doc = ezdxf.readfile(save_path)
        msp = doc.modelspace()

        elements = []
        for e in msp:
            elements.append(f"{e.dxftype()}  |  layer={e.dxf.layer}")

        text_result = "\n".join(elements[:200]) or "Nessun elemento trovato nel DXF."
    except Exception as e:
        text_result = f"Errore nella lettura del DXF: {e}"

    return render_template("index.html", text_result=text_result, filename=filename)


if __name__ == "__main__":
    # in locale
    app.run(debug=True)
