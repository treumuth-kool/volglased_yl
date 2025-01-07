import os
import sqlite3
import pdfplumber
import re
from datetime import datetime

def create_invoice_db():
    """Create SQLite database for storing invoice data"""
    conn = sqlite3.connect('parsed_invoices.db')
    cursor = conn.cursor()
    
    # Drop table if exists and create new one
    cursor.execute("DROP TABLE IF EXISTS arved")
    cursor.execute("""
        CREATE TABLE arved (
            number INTEGER PRIMARY KEY,
            klient TEXT NOT NULL,
            kuupaev TEXT NOT NULL,
            tahtaeg TEXT NOT NULL,
            summa INTEGER NOT NULL
        )
    """)
    
    conn.commit()
    return conn

def extract_data_from_pdf(pdf_path):
    """Extract relevant data from PDF invoice"""
    with pdfplumber.open(pdf_path) as pdf:
        text = pdf.pages[0].extract_text()
        
        # Extract invoice number
        number_match = re.search(r'Arve nr: (\d+)', text)
        number = int(number_match.group(1)) if number_match else None
        
        # Extract dates
        date_match = re.search(r'Arve kuupäev: (\d{2}\.\d{2}\.\d{4})', text)
        due_date_match = re.search(r'Maksetähtaeg: (\d{2}\.\d{2}\.\d{4})', text)
        
        # Extract client name
        client_match = re.search(r'Klient:\s*\n\s*(.*?)\n', text)
        
        # Extract amount
        amount_match = re.search(r'SUMMA\s*(\d+)\s*eur', text, re.IGNORECASE)
        
        data = {
            'number': number,
            'klient': client_match.group(1).strip() if client_match else None,
            'kuupaev': date_match.group(1) if date_match else None,
            'tahtaeg': due_date_match.group(1) if due_date_match else None,
            'summa': int(amount_match.group(1)) if amount_match else None
        }
        
        # Validate all required fields are present
        missing_fields = [field for field, value in data.items() if value is None]
        if missing_fields:
            raise ValueError(f"Puuduvad väljad: {', '.join(missing_fields)}")
            
        return data

def parse_all_invoices():
    """Parse all PDF invoices in the invoices folder"""
    conn = create_invoice_db()
    cursor = conn.cursor()
    
    invoice_folder = 'invoices'
    total_processed = 0
    
    print("Alustan arvete PDF-ide töötlemist...")
    
    for filename in os.listdir(invoice_folder):
        if filename.endswith('.pdf'):
            pdf_path = os.path.join(invoice_folder, filename)
            try:
                data = extract_data_from_pdf(pdf_path)
                
                cursor.execute("""
                    INSERT INTO arved (number, klient, kuupaev, tahtaeg, summa)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    data['number'], data['klient'], data['kuupaev'],
                    data['tahtaeg'], data['summa']
                ))
                
                total_processed += 1
                if total_processed % 100 == 0:
                    print(f"Töödeldud {total_processed} arvet...")
                
            except Exception as e:
                print(f"Viga faili {filename} töötlemisel: {str(e)}")
    
    conn.commit()
    conn.close()
    print(f"\nTöötlemine lõpetatud. Kokku töödeldud {total_processed} arvet.")

if __name__ == "__main__":
    parse_all_invoices() 