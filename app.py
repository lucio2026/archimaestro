from flask import Flask, render_template, request
import ezdxf
import os

app = Flask(__name__)

@app.route("/", methods=["GET", "POST"])
def index():
    text_result = ""
    filename = ""
    if request.method == "POST":
        file = request.files["file"]
        if file and file.filename.endswith((".dwg", ".dxf")):
            filename = file.filename
            filepath = os.path.join("/tmp", filename)
            file.save(filepath)
            try:
                doc = ezdxf.readfile(filepath)
                text_result = "\n".join([e.dxftype() for e in doc.modelspace()])
            except Exception as e:
                text_result = f"Errore nell’analisi del file: {e}"
        else:
            text_result = "Formato non supportato. Carica un file DWG o DXF."
    return render_template("index.html", text_result=text_result, filename=filename)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
