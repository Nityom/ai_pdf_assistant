import os
import fitz  # PyMuPDF
import google.generativeai as genai
from dotenv import load_dotenv
import speech_recognition as sr  # For voice input
import pyttsx3  # For text-to-speech
import tkinter as tk
from tkinter import filedialog
from PIL import Image, ImageTk
import requests
from bs4 import BeautifulSoup
import PyPDF2
import time
from urllib.parse import urljoin
import threading

# Load environment variables from .env file
load_dotenv()

# Initialize text-to-speech engine
engine = pyttsx3.init()

# Directory to save PDFs
pdf_dir = "pdfs"
os.makedirs(pdf_dir, exist_ok=True)

# Global variables for managing PDF mode and text extraction
pdf_mode = False
pdf_text = ""
stop_event = threading.Event()  # Event to stop conversation

def speak(text, text_widget):
    """Function to convert text to speech and display it in the text widget."""
    text_widget.insert(tk.END, f"Robot: {text}\n")
    text_widget.yview(tk.END)  # Scroll to the end of the text widget
    engine.say(text)
    engine.runAndWait()

def listen(text_widget):
    """Function to capture voice input and convert it to text."""
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        text_widget.insert(tk.END, "Listening...\n")
        text_widget.yview(tk.END)
        audio = recognizer.listen(source)
        try:
            query = recognizer.recognize_google(audio)
            text_widget.insert(tk.END, f"You: {query}\n")
            text_widget.yview(tk.END)
            return query
        except sr.UnknownValueError:
            speak("Sorry, I did not understand that.", text_widget)
            return None
        except sr.RequestError:
            speak("Could not request results from the speech recognition service.", text_widget)
            return None

def scrape_pdfs(base_url):
    """Scrapes the website at base_url to find all PDF links."""
    response = requests.get(base_url)
    response.raise_for_status()  # Ensure we got a valid response
    soup = BeautifulSoup(response.content, "html.parser")
    pdf_urls = []

    # Find all links to PDFs
    for link in soup.find_all("a", href=True):
        href = link["href"]
        if href.endswith(".pdf"):
            # Convert relative URLs to absolute URLs
            full_url = urljoin(base_url, href)
            pdf_urls.append(full_url)

    return pdf_urls

def download_pdfs(pdf_urls):
    """Downloads each PDF from the provided URLs if not already downloaded."""
    downloaded_files = []
    for pdf_url in pdf_urls:
        pdf_name = pdf_url.split("/")[-1]
        pdf_path = os.path.join(pdf_dir, pdf_name)
        
        # Download only if it doesn't already exist
        if not os.path.exists(pdf_path):
            try:
                pdf_data = requests.get(pdf_url)
                pdf_data.raise_for_status()  # Ensure successful download
                with open(pdf_path, "wb") as f:
                    f.write(pdf_data.content)
                print(f"Downloaded: {pdf_name}")
            except requests.exceptions.RequestException as e:
                print(f"Failed to download {pdf_url}: {e}")
        
        downloaded_files.append(pdf_path)
    
    return downloaded_files

def merge_pdfs(pdf_paths, output_filename="merged.pdf"):
    """Merges multiple PDFs into a single PDF file."""
    merger = PyPDF2.PdfMerger()  # Use PdfMerger instead of PdfFileMerger
    for pdf_path in pdf_paths:
        try:
            with open(pdf_path, "rb") as pdf_file:
                merger.append(pdf_file)
        except Exception as e:
            print(f"Error merging {pdf_path}: {e}")

    # Save the merged PDF
    merged_pdf_path = os.path.join(pdf_dir, output_filename)
    with open(merged_pdf_path, "wb") as f:
        merger.write(f)
    merger.close()
    print(f"Merged PDF saved at: {merged_pdf_path}")
    
    # Delete the original PDFs after merging
    for pdf_path in pdf_paths:
        if os.path.exists(pdf_path):
            try:
                os.remove(pdf_path)
                print(f"Deleted {pdf_path} after merging.")
            except Exception as e:
                print(f"Error deleting {pdf_path}: {e}")
    
    return merged_pdf_path

def extract_text_from_pdf(pdf_file):
    """Function to extract text from a PDF file."""
    try:
        pdf_document = fitz.open(pdf_file)
        text = ""
        for page in pdf_document:
            text += page.get_text()
        pdf_document.close()
        return text.strip()  # Return cleaned text
    except Exception as e:
        print(f"Error reading PDF: {e}")
        return None

def query_palm_api(context, question):
    """Function to query the PaLM API using the provided context and question."""
    api_key = os.getenv("API")  # Fetch API key from environment variables
    genai.configure(api_key=api_key)
    
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(f"Context: {context}\n\nQuestion: {question}")
        return response.text if response else "No response generated."
    except Exception as e:
        return f"Error: {str(e)}"

def answer_question(pdf_text, query, text_widget):
    """Function to answer questions based on extracted PDF text."""
    if not pdf_text:
        return "No content extracted from the PDF."

    answer = query_palm_api(pdf_text, query)
    return answer

def handle_pdf_mode(text_widget):
    """Function to automatically download, merge PDFs and extract text."""
    global pdf_mode, pdf_text
    
    base_url = "https://www.bvuniversity.edu.in/coepune/"  # Target URL
    print(f"Starting PDF download and merge at {time.strftime('%Y-%m-%d %H:%M:%S')}")

    pdf_urls = scrape_pdfs(base_url)
    downloaded_pdfs = download_pdfs(pdf_urls)
    merged_pdf_path = merge_pdfs(downloaded_pdfs)
    
    # Extract text from the merged PDF
    pdf_text = extract_text_from_pdf(merged_pdf_path)
    if pdf_text:
        speak("PDFs merged and text extracted successfully. You can now ask questions about the content.", text_widget)
        pdf_mode = True
    else:
        speak("Failed to extract text from the merged PDF. Please try again.", text_widget)
        pdf_mode = False

def stop_conversation(root):
    """Stop the conversation and close the GUI."""
    stop_event.set()  # Trigger stop_event to break the loop
    root.quit()  # Close the Tkinter window

def start_conversation(text_widget):
    """Main function to handle the conversation loop."""
    global pdf_mode, pdf_text
    pdf_mode = False
    pdf_text = ""
    stop_event.clear()  # Clear any previous stop events
    handle_pdf_mode(text_widget)

    while not stop_event.is_set():
        query = listen(text_widget)  # Capture user query
        if query is None:
            continue
        
        if pdf_mode:
            answer = answer_question(pdf_text, query, text_widget)
            speak(answer, text_widget)
        else:
            speak("You are not in PDF mode. Please upload a PDF first.", text_widget)

def create_gui():
    """Function to create the robot GUI."""
    root = tk.Tk()
    root.title("PDF Question Assistant")
    root.geometry("600x600")

    # Load robot image
    robot_img = Image.open("robot_face.png")
    robot_img = robot_img.resize((100, 100), Image.LANCZOS)

    robot_photo = ImageTk.PhotoImage(robot_img)

    # Create robot image label
    robot_label = tk.Label(root, image=robot_photo)
    robot_label.pack(pady=10)

    # Create text area for displaying conversation
    text_widget = tk.Text(root, height=20, width=70)
    text_widget.pack(pady=10)

    # Create buttons for user interaction
  

    start_button = tk.Button(root, text="Start Conversation", command=lambda: threading.Thread(target=start_conversation, args=(text_widget,), daemon=True).start())
    start_button.pack(pady=5)

    stop_button = tk.Button(root, text="Stop Conversation", command=lambda: stop_conversation(root))
    stop_button.pack(pady=5)

    root.mainloop()

if __name__ == '__main__':
    create_gui()
