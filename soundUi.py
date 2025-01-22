import os
import fitz  # PyMuPDF
import google.generativeai as genai
from dotenv import load_dotenv
import requests
from bs4 import BeautifulSoup
import PyPDF2
from urllib.parse import urljoin
import streamlit as st
import pyttsx3
import speech_recognition as sr
import threading

# Load environment variables from .env file
load_dotenv()

# Directory to save PDFs
pdf_dir = "pdfs"
os.makedirs(pdf_dir, exist_ok=True)

# Initialize text-to-speech engine
engine = pyttsx3.init()
is_speaking = False

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
    """Merges multiple PDFs into a single PDF."""
    merger = PyPDF2.PdfMerger()
    for pdf_path in pdf_paths:
        try:
            merger.append(pdf_path)
        except Exception as e:
            st.error(f"Error merging {pdf_path}: {e}")
    merged_pdf_path = os.path.join(pdf_dir, output_filename)
    with open(merged_pdf_path, "wb") as f:
        merger.write(f)
    merger.close()
    delete_downloaded_pdfs(pdf_paths)  # Delete original PDFs after merging
    return merged_pdf_path

def delete_downloaded_pdfs(pdf_paths):
    """Deletes the downloaded PDF files."""
    for pdf_path in pdf_paths:
        try:
            if os.path.exists(pdf_path):
                os.remove(pdf_path)
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

def speak_text(text):
    """Speaks the given text using text-to-speech."""
    global is_speaking
    is_speaking = True
    def speak():
        engine.say(text)
        engine.runAndWait()
        global is_speaking
        is_speaking = False
    threading.Thread(target=speak).start()

def stop_speech():
    """Stops the text-to-speech engine."""
    engine.stop()

def listen_to_voice():
    """Listens to the microphone and returns the recognized text."""
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        st.write("Listening... Please speak your question.")
        audio = recognizer.listen(source)
        try:
            text = recognizer.recognize_google(audio)
            st.write(f"You said: {text}")
            return text
        except sr.UnknownValueError:
            st.error("Sorry, I could not understand the audio.")
            return None
        except sr.RequestError as e:
            st.error(f"Could not request results from Google Speech Recognition service; {e}")
            return None

# Streamlit App
def main():
    st.title("PDF Question Assistant")
    st.sidebar.header("Options")
    
    base_url = st.sidebar.text_input("Enter Base URL for PDFs", "https://www.bvuniversity.edu.in/coepune/")
    
    # Add buttons for voice and text input
    if st.sidebar.button("🎤 Record Question"):
        question = listen_to_voice()  # Capture voice input
        if question:
            st.session_state["voice_input"] = question
    
    # Provide text input option
    question = st.text_input("Or type your question about the PDFs:")
    # Combine voice input and text input
    question = st.session_state.get("voice_input", question)
    
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
            speak_text(answer)  # Speak the answer

    # Stop button for audio output
    if st.sidebar.button("🛑 Stop Speaking"):
        stop_speech()

if __name__ == "__main__":
    main()
