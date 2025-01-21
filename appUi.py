import os
import fitz  # PyMuPDF
import google.generativeai as genai
from dotenv import load_dotenv
import requests
from bs4 import BeautifulSoup
import PyPDF2
from urllib.parse import urljoin
import streamlit as st

# Load environment variables from .env file
load_dotenv()

# Directory to save PDFs
pdf_dir = "pdfs"
os.makedirs(pdf_dir, exist_ok=True)

def scrape_pdfs(base_url):
    """Scrapes the website at base_url to find all PDF links."""
    response = requests.get(base_url)
    response.raise_for_status()
    soup = BeautifulSoup(response.content, "html.parser")
    pdf_urls = []
    for link in soup.find_all("a", href=True):
        href = link["href"]
        if href.endswith(".pdf"):
            pdf_urls.append(urljoin(base_url, href))
    return pdf_urls

def download_pdfs(pdf_urls):
    """Downloads each PDF from the provided URLs."""
    downloaded_files = []
    for pdf_url in pdf_urls:
        pdf_name = pdf_url.split("/")[-1]
        pdf_path = os.path.join(pdf_dir, pdf_name)
        if not os.path.exists(pdf_path):
            try:
                pdf_data = requests.get(pdf_url)
                pdf_data.raise_for_status()
                with open(pdf_path, "wb") as f:
                    f.write(pdf_data.content)
                downloaded_files.append(pdf_path)
            except Exception as e:
                st.error(f"Failed to download {pdf_url}: {e}")
    return downloaded_files

def merge_pdfs(pdf_paths, output_filename="merged.pdf"):
    """Merge multiple PDFs into a single PDF file."""
    merger = PyPDF2.PdfMerger()
    for pdf_path in pdf_paths:
        try:
            with open(pdf_path, "rb") as pdf_file:
                merger.append(pdf_file)
        except Exception as e:
            st.error(f"Error merging {pdf_path}: {e}")

    # Save the merged PDF
    merged_pdf_path = os.path.join(pdf_dir, output_filename)
    with open(merged_pdf_path, "wb") as f:
        merger.write(f)
    merger.close()
    st.success(f"Merged PDF saved at: {merged_pdf_path}")

    # Delete the original PDFs after merging
    delete_downloaded_pdfs(pdf_paths)

    return merged_pdf_path

def delete_downloaded_pdfs(pdf_paths):
    """Deletes the downloaded PDF files."""
    for pdf_path in pdf_paths:
        try:
            if os.path.exists(pdf_path):
                os.remove(pdf_path)
                # st.success(f"Deleted {pdf_path} after merging.")
            else:
                st.warning(f"{pdf_path} does not exist.")
        except Exception as e:
            st.warning(f"Error deleting {pdf_path}: {e}")

def extract_text_from_pdf(pdf_file):
    """Extracts text from a PDF file."""
    try:
        pdf_document = fitz.open(pdf_file)
        text = ""
        for page in pdf_document:
            text += page.get_text()
        pdf_document.close()
        return text.strip()
    except Exception as e:
        st.error(f"Error reading PDF: {e}")
        return None

def query_palm_api(context, question):
    """Queries the PaLM API using the provided context and question."""
    api_key = os.getenv("API")  # Fetch API key from environment variables
    genai.configure(api_key=api_key)
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(f"Context: {context}\n\nQuestion: {question}")
        return response.text if response else "No response generated."
    except Exception as e:
        return f"Error: {str(e)}"

# Streamlit App
def main():
    st.title("PDF Question Assistant")
    st.sidebar.header("Options")

    base_url = st.sidebar.text_input("Enter Base URL for PDFs", "https://www.bvuniversity.edu.in/coepune/")
    question = st.text_input("Ask a question about the PDFs:")

    if st.sidebar.button("Download and Process PDFs"):
        with st.spinner("Scraping and downloading PDFs..."):
            pdf_urls = scrape_pdfs(base_url)
            downloaded_pdfs = download_pdfs(pdf_urls)
            if downloaded_pdfs:
                st.success(f"Downloaded {len(downloaded_pdfs)} PDFs successfully!")
                merged_pdf = merge_pdfs(downloaded_pdfs)
                st.success("PDFs merged successfully!")
                pdf_text = extract_text_from_pdf(merged_pdf)
                if pdf_text:
                    st.session_state["pdf_text"] = pdf_text
                    st.success("Extracted text from PDFs.")
                else:
                    st.error("Failed to extract text from the merged PDF.")

    if question and "pdf_text" in st.session_state:
        pdf_text = st.session_state["pdf_text"]
        with st.spinner("Querying the PaLM API..."):
            answer = query_palm_api(pdf_text, question)
            st.success("Answer generated!")
            st.write(answer)

if __name__ == "__main__":
    main()
