import traceback
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from PyPDF2 import PdfMerger, PdfReader, PdfWriter
import fitz  # PyMuPDF
from PIL import Image, ImageOps
import requests
import io
import zipfile
from fastapi.responses import HTMLResponse

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>FileWay Backend</title>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;700&display=swap" rel="stylesheet">
  <style>
    body {
      margin: 0;
      padding: 0;
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      background: #121212;
      font-family: 'Inter', Arial, sans-serif;
    }
    .container {
      background: #000;
      border-radius: 18px;
      box-shadow: 0 8px 32px rgba(20, 20, 40, 0.32);
      padding: 48px 36px;
      max-width: 420px;
      text-align: center;
    }
    h1 {
      font-size: 2.2rem;
      font-weight: 700;
      margin-bottom: 18px;
      color: #74a1af;
      letter-spacing: -1px;
      line-height: 1.1;
    }
    .fileway {
      font-size: 3.6rem;
      font-weight: 800;
      color: #943900;
      letter-spacing: -2px;
      display: inline-block;
      margin: 10px 0 4px 0;
    }
    .backend {
      color: #b8b8b8;
    }
    p {
      font-size: 1.1rem;
      color: #b8b8b8;
      margin: 16px 0;
    }
    a {
      color: #ff9800;
      text-decoration: none;
      font-weight: 600;
      transition: color 0.2s;
    }
    a:hover {
      color: #7a3306;
      text-decoration: underline;
    }
    .status {
      display: inline-block;
      background: #1a1a1a;
      color: #943900;
      font-weight: 600;
      border-radius: 8px;
      padding: 4px 12px;
      margin-bottom: 8px;
      font-size: 1rem;
      box-shadow: 0 2px 8px rgba(122,51,6,0.10);
    }
    .tagline {
      font-size: 1.08rem;
      color: #ffb26b;
      font-weight: 500;
      margin: 18px 0 0 0;
      letter-spacing: 0.01em;
      background: #1a1a1a;
      border-radius: 8px;
      padding: 10px 0 10px 0;
      box-shadow: 0 2px 8px rgba(122,51,6,0.10);
      text-align: center;
      transition: background 0.2s;
    }
    .tagline .emoji {
      font-size: 1.2em;
      margin-left: 4px;
    }
  </style>
</head>
<body>
  <div class="container">
    <h1>
      Welcome to <br>
      <span class="fileway">FileWay</span><br>
      backend
    </h1>
    <div class="status">Backend is running ✅</div>
    <p>Go to <a href="https://fileway.vercel.app/" target="_blank">Frontend</a></p>
    <div class="tagline">One-stop solution for all your file types <span class="emoji">⚡🛠️✨</span></div>
  </div>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
async def root():
    return HTML

@app.post("/merge-pdfs")
async def merge_pdfs(request: Request):
    try:
        body = await request.json()
        pdf_urls = body.get("pdf_urls", [])

        if not pdf_urls:
            raise HTTPException(status_code=400, detail="No PDF URLs provided.")

        merger = PdfMerger()

        for url in pdf_urls:
            print(f"Downloading: {url}")
            response = requests.get(url)
            if response.status_code == 200:
                pdf_stream = io.BytesIO(response.content)
                merger.append(pdf_stream)
            else:
                print(f"Failed to download: {url}")

        output_pdf = io.BytesIO()
        merger.write(output_pdf)
        merger.close()
        output_pdf.seek(0)

        return StreamingResponse(output_pdf, media_type="application/pdf", headers={
            "Content-Disposition": "inline; filename=merged.pdf"
        })

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error merging PDFs: {str(e)}")
    
@app.post("/unlock-pdf")
async def unlock_pdf(request: Request):
    try:
        body = await request.json()
        pdf_url = body.get("pdf_urls")
        password = body.get("password")

        if not pdf_url:
            raise HTTPException(status_code=400, detail="URL are required.")
        if  not password:
            raise HTTPException(status_code=400, detail="password are required.")
        
        if isinstance(pdf_url, list):
         pdf_url = pdf_url[0]

        print(f"Downloading: {pdf_url}")
        response = requests.get(pdf_url)
        if response.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to download PDF.")

        pdf_stream = io.BytesIO(response.content)
        reader = PdfReader(pdf_stream)

        if not reader.is_encrypted:
            raise HTTPException(status_code=400, detail="PDF is not encrypted.")

        if reader.decrypt(password) == 0:
            raise HTTPException(status_code=401, detail="Incorrect password.")

        writer = PdfWriter()
        for page in reader.pages:
            writer.add_page(page)

        output_pdf = io.BytesIO()
        writer.write(output_pdf)
        output_pdf.seek(0)

        return StreamingResponse(output_pdf, media_type="application/pdf", headers={
            "Content-Disposition": "inline; filename=unlocked.pdf"
        })

    except Exception as e:
        traceback.print_exc()  # 👈 This will print the full error in the terminal
        raise HTTPException(status_code=500, detail=f"Error unlocking PDF: {str(e)}")
    
@app.post("/split-pdf")
async def split_pdf(request: Request):
    try:
        body = await request.json()
        pdf_url = body.get("pdf_urls") # type: ignore
        start = int(body.get("start"))
        end = int(body.get("end"))

        if not pdf_url:
            raise HTTPException(status_code=400, detail="Missing url")
        if start is None or end is None:
            raise HTTPException(status_code=400, detail="Missing page range.")
        if isinstance(pdf_url, list):
         pdf_url = pdf_url[0]  #
        
        

        # Download the PDF
        response = requests.get(pdf_url)
        if response.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to download PDF.")

        pdf_bytes = io.BytesIO(response.content)
        reader = PdfReader(pdf_bytes)

        if start < 1 or end > len(reader.pages) or start > end:
            raise HTTPException(status_code=400, detail="Invalid page range.")

        writer = PdfWriter()
        for i in range(start - 1, end):  # PDF page numbers are 0-based
            writer.add_page(reader.pages[i])

        output_pdf = io.BytesIO()
        writer.write(output_pdf)
        output_pdf.seek(0)

        return StreamingResponse(output_pdf, media_type="application/pdf", headers={
            "Content-Disposition": "inline; filename=split_pages.pdf"
        })

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error splitting PDF: {str(e)}")
    
@app.post("/dark-mode-pdf")
async def convert_to_dark_mode(request: Request):
    try:
        data = await request.json()
        pdf_url = data.get("pdf_urls")
        if not pdf_url:
            raise HTTPException(status_code=400, detail="Missing PDF URL")
        if isinstance(pdf_url, list):
            pdf_url = pdf_url[0]  # ✅ Take the first item

        response = requests.get(pdf_url)
        if response.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to download PDF")

        input_pdf_stream = io.BytesIO(response.content)
        doc = fitz.open(stream=input_pdf_stream, filetype="pdf")

        dark_pdf = fitz.open()
        for page in doc:
            pix = page.get_pixmap(dpi=150) # type: ignore
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples) # type: ignore

            dark_img = ImageOps.invert(img)

            img_buffer = io.BytesIO()
            dark_img.save(img_buffer, format="PNG")
            img_buffer.seek(0)

            rect = fitz.Rect(0, 0, pix.width, pix.height)
            pdf_page = dark_pdf.new_page(width=rect.width, height=rect.height) # type: ignore
            pdf_page.insert_image(rect, stream=img_buffer.read())

        output_buffer = io.BytesIO()
        dark_pdf.save(output_buffer)
        dark_pdf.close()
        output_buffer.seek(0)

        return StreamingResponse(output_buffer, media_type="application/pdf", headers={
            "Content-Disposition": "inline; filename=dark_mode.pdf"
        })

    except Exception as e:
        print(f"[ERROR] {str(e)}")  # 🧠 Print error in console
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
    
@app.post("/compress-pdf")
async def compress_pdf(request: Request):
    try:
        data = await request.json()
        pdf_url = data.get("pdf_urls")
        target_kb = float(data.get("target_kb", 500))

        if isinstance(pdf_url, list):
            pdf_url = pdf_url[0]

        response = requests.get(pdf_url)
        if response.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to download PDF.")

        original_pdf = fitz.open(stream=response.content, filetype="pdf")

        best_pdf_bytes = None
        best_quality = None
        best_size_kb = None

        for quality in range(80, 5, -5):  # Try different compression qualities
            compressed_pdf = fitz.open()
            for page in original_pdf:
                pix = page.get_pixmap(dpi=100)  # type: ignore # Lower DPI = smaller file
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples) # type: ignore
                img_io = io.BytesIO()
                img.save(img_io, format="JPEG", quality=quality)
                img_io.seek(0)

                rect = fitz.Rect(0, 0, pix.width, pix.height)
                new_page = compressed_pdf.new_page(width=rect.width, height=rect.height) # type: ignore
                new_page.insert_image(rect, stream=img_io.read())

            output_stream = io.BytesIO()
            compressed_pdf.save(output_stream)
            compressed_pdf.close()

            size_kb = len(output_stream.getvalue()) / 1024

            print(f"📦 Quality {quality}: {int(size_kb)} KB")

            # Store the best compressed result
            if best_size_kb is None or size_kb < best_size_kb:
                best_size_kb = size_kb
                best_pdf_bytes = output_stream.getvalue()
                best_quality = quality

            if size_kb <= target_kb:
                output_stream.seek(0)
                return StreamingResponse(io.BytesIO(best_pdf_bytes), media_type="application/pdf", headers={ # type: ignore
                    "Content-Disposition": f"inline; filename=compressed_q{quality}.pdf"
                })

        # If target was not met, return info about min possible
        return JSONResponse({
            "message": "❌ Cannot compress to desired size.",
            "min_possible_kb": round(best_size_kb, 2), # type: ignore
            "best_quality": best_quality
        }, status_code=200)

    except Exception as e:
        print("❌ Error:", e)
        raise HTTPException(status_code=500, detail=str(e))
    
@app.post("/encrypt-pdf")
async def encrypt_pdf(request: Request):
    try:
        data = await request.json()
        pdf_url = data.get("pdf_urls")
        password = data.get("password")

        if not pdf_url or not password:
            raise HTTPException(status_code=400, detail="Missing PDF URL or password.")

        # Handle case where URL is a list
        if isinstance(pdf_url, list):
            pdf_url = pdf_url[0]

        response = requests.get(pdf_url)
        if response.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to download PDF.")

        # Read the PDF
        input_stream = io.BytesIO(response.content)
        reader = PdfReader(input_stream)
        writer = PdfWriter()

        for page in reader.pages:
            writer.add_page(page)

        # Set encryption
        writer.encrypt(user_password=password)

        output_stream = io.BytesIO()
        writer.write(output_stream)
        output_stream.seek(0)

        return StreamingResponse(output_stream, media_type="application/pdf", headers={
            "Content-Disposition": "inline; filename=protected.pdf"
        })

    except Exception as e:
        print("❌ Error:", e)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/pdf-to-images")
async def pdf_to_images(request: Request):
    try:
        data = await request.json()
        pdf_url = data.get("pdf_urls")
        
        if not pdf_url:
            raise HTTPException(status_code=400, detail="Missing PDF URL.")
        
        if isinstance(pdf_url, list):
            pdf_url = pdf_url[0]
        
        response = requests.get(pdf_url)
        if response.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to download PDF.")
        
        pdf_stream = io.BytesIO(response.content)
        doc = fitz.open(stream=pdf_stream, filetype="pdf")
        
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for page_num in range(len(doc)):
                page = doc[page_num]
                pix = page.get_pixmap(dpi=150)  # type: ignore
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)  # type: ignore
                
                img_buffer = io.BytesIO()
                img.save(img_buffer, format="JPEG")
                img_buffer.seek(0)
                
                zip_file.writestr(f"page_{page_num + 1}.jpg", img_buffer.getvalue())
        
        doc.close()
        zip_buffer.seek(0)
        
        return StreamingResponse(zip_buffer, media_type="application/zip", headers={
            "Content-Disposition": "attachment; filename=pdf_images.zip"
        })
    
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error converting PDF to images: {str(e)}")