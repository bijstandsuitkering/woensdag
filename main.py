from flask import Flask, request, render_template_string
import fitz  # PyMuPDF
import pytesseract
from PIL import Image
import openai
import io
import os
from dotenv import load_dotenv

# Laad de .env file
load_dotenv()

# Haal de API key uit de omgeving
openai.api_key = os.getenv("OPENAI_API_KEY")

app = Flask(__name__)

HTML = """
<!doctype html>
<html lang="nl">
<head>
  <meta charset="utf-8">
  <title>Bezwaarschrift Generator</title>
  <style>
    body { font-family: sans-serif; margin: 2em; }
    form input[type="text"], form input[type="date"] {
      width: 300px;
      margin-bottom: 10px;
      display: block;
    }
    textarea { width: 600px; }
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
  <label>Voornaam: <input type=text name=voornaam required></label>
  <label>Achternaam: <input type=text name=achternaam required></label>
  <label>Adres: <input type=text name=adres required></label>
  <label>Postcode: <input type=text name=postcode required></label>
  <label>Plaats: <input type=text name=plaats required></label>
  <label>Geboortedatum: <input type=date name=geboortedatum required></label>
  <label>Datum van het besluit: <input type=date name=besluitdatum required></label><br>
  <label>Wat is er gebeurd? <br><textarea name=gebeurtenis rows=4 required></textarea></label><br>
  <label>Optionele toelichting: <br><textarea name=toelichting rows=4></textarea></label><br>
  <label>Upload een PDF of foto: <input type=file name=file required></label><br><br>
  <input type=submit value=Genereer>
</form>

{% if result %}
<hr>
<h2>Resultaat:</h2>
<div class="result-box" id="resultBox">{{ result }}</div>
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
            pix = page.get_pixmap(dpi=300)
            image = Image.open(io.BytesIO(pix.tobytes("png")))
            page_text = pytesseract.image_to_string(image, lang='nld')
        text += page_text + "\n"
    return text

def extract_text_from_image(file_stream):
    image = Image.open(file_stream)
    return pytesseract.image_to_string(image, lang='nld')

def generate_bezwaarschrift(gegevens, bestandstekst):
    try:
        with open("juridische_basis.txt", "r", encoding="utf-8") as f:
            juridische_basis = f.read()
    except FileNotFoundError:
        juridische_basis = ""

    prompt = f"""
Je bent een juridisch medewerker. Schrijf een bezwaarschrift aan de gemeente op basis van de volgende informatie:

Persoonsgegevens:
Naam: {gegevens['voornaam']} {gegevens['achternaam']}
Adres: {gegevens['adres']}, {gegevens['postcode']} {gegevens['plaats']}
Geboortedatum: {gegevens['geboortedatum']}
Datum van besluit: {gegevens['besluitdatum']}

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

Hieronder volgt aanvullende juridische achtergrondinformatie:
{juridische_basis}
"""
    response = openai.chat.completions.create(
        model="gpt-3.5-turbo",
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
            'voornaam': request.form['voornaam'],
            'achternaam': request.form['achternaam'],
            'adres': request.form['adres'],
            'postcode': request.form['postcode'],
            'plaats': request.form['plaats'],
            'geboortedatum': request.form['geboortedatum'],
            'besluitdatum': request.form['besluitdatum'],
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

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=10000)
