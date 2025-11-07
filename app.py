import os
from flask import Flask, render_template, request, redirect, url_for, flash
import ezdxf

app = Flask(__name__)
app.secret_key = "metti-una-password-qualsiasi"

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER


@app.route("/", methods=["GET"])
def index():
    # pagina vuota la prima volta
    return render_template("index.html")


@app.route("/upload", methods=["POST"])
def upload():
    file = request.files.get("file")

    if not file or file.filename == "":
        flash("Nessun file selezionato.")
        return redirect(url_for("index"))

    filename = file.filename
    lowername = filename.lower()

    # SU RENDER leggiamo solo DXF, il DWG farebbe crashare ezdxf
    if not lowername.endswith(".dxf"):
        flash("Per ora il server accetta solo file DXF. Esporta il DWG in DXF e ricarica.")
        return redirect(url_for("index"))

    save_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(save_path)

    # proviamo a leggere il DXF
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
    # utile solo in locale; su Render usa gunicorn
    app.run(host="0.0.0.0", port=5000, debug=True)
