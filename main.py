from flask import Flask, request, render_template_string, send_file
import fitz  # PyMuPDF
import pytesseract
from PIL import Image
import openai
import io
import os
from dotenv import load_dotenv
from fpdf import FPDF
import textwrap

# Load the .env file
load_dotenv()

# Get the API key from the environment variable
openai.api_key = os.getenv("OPENAI_API_KEY")

app = Flask(__name__)

HTML = """...
</body>
</html>"""

... 
