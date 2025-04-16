from flask import Flask, request, render_template_string, send_file
import fitz  # PyMuPDF
import pytesseract
from PIL import Image
import openai
import io
import os
from fpdf import FPDF
import textwrap

openai.api_base = "https://api.openai.eu/v1"  # Gebruik EU endpoint
openai.api_key = os.getenv("OPENAI_API_KEY")  # Zet je key in een .env bestand of als env var

app = Flask(__name__)

HTML = """
<!doctype html>
<html lang="nl">
<head>
  <meta charset="utf-8">
  <title>Bezwaarschrift Generator</title>
  <style>
    body { font-family: sans-serif; margin: 2em; }
    .result-box {
      background: #f4f4f4;
      padding: 1em;
      border: 1px solid #ccc;
      white-space: pre-wrap;
      margin-top: 1em;
    }
    button.copy-button {
      margin-top: 0.5em;
      padding: 0.4em 1em;
    }
  </style>
</head>
<body>
<h1>Genereer je bezwaarschrift</h1>
<form method=post enctype=multipart/form-data>
  <label>Naam: <input type=text name=naam required></label><br>
  <label>Adres: <input type=text name=adres required></label><br>
  <label>Geboortedatum: <input type=date name=geboortedatum required></label><br>
  <label>Wat is er gebeurd? <br><textarea name=gebeurtenis rows=4 cols=50 required></textarea></label><br><br>
  <label>Optionele toelichting: <br><textarea name=toelichting rows=4 cols=50></textarea></label><br><br>
  <label>Upload een PDF of foto: <input type=file name=file required></label><br><br>
  <input type=submit value=Genereer>
</form>

{% if result %}
<hr>
<h2>Resultaat:</h2>
<div class="result-box" id="resultBox">{{ result }}</div>
<form method="post" action="/download">
  <input type="hidden" name="tekst" value="{{ result | tojson | safe }}">
  <button type="submit">Download als PDF</button>
</form>
<button class="copy-button" onclick="copyToClipboard()">Kopieer tekst</button>
<script>
function copyToClipboard() {
  const text = document.getElementById('resultBox').innerText;
  navigator.clipboard.writeText(text).then(function() {
    alert('Tekst gekopieerd naar klembord!');
  }, function(err) {
    alert('Kopiëren mislukt: ' + err);
  });
}
</script>
{% endif %}
</body>
</html>
"""

def extract_text_from_pdf(file_stream):
    text = ""
    pdf = fitz.open(stream=file_stream.read(), filetype="pdf")
    for page in pdf:
        page_text = page.get_text()
        if not page_text.strip():
            # Geen tekst gevonden, probeer OCR op afbeelding van pagina
            pix = page.get_pixmap(dpi=300)
            image = Image.open(io.BytesIO(pix.tobytes("png")))
            page_text = pytesseract.image_to_string(image, lang='nld')
        text += page_text + "\n"
    return text

def extract_text_from_image(file_stream):
    image = Image.open(file_stream)
    return pytesseract.image_to_string(image, lang='nld')

def generate_bezwaarschrift(gegevens, bestandstekst):
    prompt = f"""
Je bent een juridisch medewerker. Schrijf een bezwaarschrift aan de gemeente op basis van de volgende informatie:

Persoonsgegevens:
Naam: {gegevens['naam']}
Adres: {gegevens['adres']}
Geboortedatum: {gegevens['geboortedatum']}

Beschrijving van de gebeurtenis:
{gegevens['gebeurtenis']}

Inhoud van het meegestuurde document:
{bestandstekst}

Eventuele extra toelichting van de gebruiker:
{gegevens['toelichting']}

Instructies:
- Vermeld altijd de datum van het besluit en het kenmerk, indien deze uit het document gehaald kunnen worden.
- Analyseer relevante wetsartikelen die genoemd worden in het besluit.
- Reageer inhoudelijk op die wetsartikelen vanuit het perspectief van de indiener.
- Controleer of fundamentele rechtsbeginselen zijn geschonden (zoals het zorgvuldigheidsbeginsel, evenredigheidsbeginsel, motiveringsbeginsel).
- Vermeld expliciet dat de indiener verzoekt om toezending van het volledige dossier.
- Sluit het bezwaarschrift correct af met de naam van de indiener en ruimte voor handtekening.
- Zorg dat het bezwaarschrift duidelijk, formeel en juridisch kloppend is.
"""

    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "Je bent een juridisch assistent die bezwaarschriften opstelt."},
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content

@app.route('/', methods=['GET', 'POST'])
def index():
    result = ""
    if request.method == 'POST':
        gegevens = {
            'naam': request.form['naam'],
            'adres': request.form['adres'],
            'geboortedatum': request.form['geboortedatum'],
            'gebeurtenis': request.form['gebeurtenis'],
            'toelichting': request.form.get('toelichting', '')
        }
        file = request.files['file']
        if file:
            filename = file.filename.lower()
            if filename.endswith('.pdf'):
                text = extract_text_from_pdf(file.stream)
            else:
                text = extract_text_from_image(file.stream)

            result = generate_bezwaarschrift(gegevens, text)

    return render_template_string(HTML, result=result)

@app.route('/download', methods=['POST'])
def download_pdf():
    tekst = request.form['tekst']
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_font("Arial", size=12)
    for paragraph in tekst.split('\n\n'):
        lines = textwrap.wrap(paragraph.strip(), width=90)
        for line in lines:
            pdf.multi_cell(0, 10, line)
        pdf.ln()
    pdf_output = io.BytesIO()
    pdf.output(pdf_output)
    pdf_output.seek(0)
    return send_file(pdf_output, as_attachment=True, download_name="bezwaarschrift.pdf", mimetype='application/pdf')

if __name__ == '__main__':
    app.run(debug=True)
