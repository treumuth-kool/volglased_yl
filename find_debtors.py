import sqlite3
import re
from datetime import datetime
import pandas as pd

def normalize_name(name):
    """Normalize different name formats to 'Firstname Lastname'"""
    # Handle "Lastname, Firstname" format (both regular and uppercase)
    if ',' in name:
        lastname, firstname = name.split(',')
        # Convert to title case regardless of original case
        normalized = f"{firstname.strip().title()} {lastname.strip().title()}"
        return {normalized}  # Return as single-element set
    
    # Handle "Lastname Firstname" format (reversed without comma)
    parts = name.split()
    if len(parts) == 2:
        # Return both possible orderings as a set
        return {
            f"{parts[0]} {parts[1]}",  # Original order
            f"{parts[1]} {parts[0]}"   # Reversed order
        }
    
    return {name}  # Return single name as a set for consistency

def extract_invoice_number(description):
    """Extract invoice number from various description formats"""
    patterns = [
        r'Arve nr[.: ]*(\d+)',
        r'ARVE NR[.: ]*(\d+)',
        r'Arve number[.: ]*(\d+)',
        r'ARVE[.: ]*(\d+)',
        r'Arve[.: ]*(\d+)',
        r'Tasumine arve[.: ]*(\d+)',
        r'.*?(\d+).*'  # Last resort - try to find any number
    ]
    
    for pattern in patterns:
        match = re.search(pattern, description, re.IGNORECASE)
        if match:
            return int(match.group(1))
    return None

def load_invoices():
    """Load invoices from parsed database"""
    conn = sqlite3.connect('parsed_invoices.db')
    df = pd.read_sql_query("SELECT * FROM arved", conn)
    conn.close()
    return df

def load_payments():
    """Load payments from CSV file"""
    df = pd.read_csv('payments.csv', delimiter=';', encoding='utf-8')
    
    # Rename columns to match our code
    column_mapping = {
        'Saaja/Maksja': 'payer',
        'Kuupäev': 'payment_date',
        'Selgitus': 'description',
        'Summa': 'amount',
        'Valuuta': 'currency',
        'Deebet/Kreedit': 'debit_credit'
    }
    df = df.rename(columns=column_mapping)
    
    # Convert amount to float - handle both string and numeric formats
    if df['amount'].dtype == 'object':  # if it's string
        df['amount'] = df['amount'].str.replace(',', '.').astype(float)
    else:  # if it's already numeric
        df['amount'] = df['amount'].astype(float)
    
    return df

def analyze_debts():
    # Load data
    invoices_df = load_invoices()
    payments_df = load_payments()
    
    # Create dictionary to store payment info per invoice
    invoice_payments = {}
    unmatched_payments = []
    
    # Process each payment
    for _, payment in payments_df.iterrows():
        possible_names = normalize_name(payment['payer'])
        invoice_number = extract_invoice_number(payment['description'])
        
        if invoice_number:
            # Try all possible name formats
            matched = False
            for name in possible_names:
                key = (name, invoice_number)
                if key not in invoice_payments:
                    invoice_payments[key] = 0
                invoice_payments[key] += payment['amount']
                matched = True
            if not matched:
                # Store as unmatched if no name format matched
                unmatched_payments.append({
                    'name': payment['payer'],  # Store original name
                    'amount': payment['amount'],
                    'date': payment['payment_date']
                })
        else:
            # Store unmatched payments for later processing
            unmatched_payments.append({
                'name': payment['payer'],  # Store original name
                'amount': payment['amount'],
                'date': payment['payment_date']
            })
    
    # Find debts
    debtors = []
    
    for _, invoice in invoices_df.iterrows():
        key = (invoice['klient'], invoice['number'])
        paid_amount = invoice_payments.get(key, 0)
        
        if paid_amount < invoice['summa']:
            # Try to find matching unmatched payment
            matching_payment = None
            invoice_name_variants = normalize_name(invoice['klient'])
            for payment in unmatched_payments:
                payment_name_variants = normalize_name(payment['name'])
                if (len(invoice_name_variants & payment_name_variants) > 0 and 
                    payment['amount'] == invoice['summa']):
                    matching_payment = payment
                    break
            
            if matching_payment:
                unmatched_payments.remove(matching_payment)
                continue
                
            debtors.append({
                'client': invoice['klient'],
                'invoice_number': invoice['number'],
                'invoice_date': invoice['kuupaev'],
                'invoice_amount': invoice['summa'],
                'paid_amount': paid_amount,
                'debt': invoice['summa'] - paid_amount
            })
    
    return debtors

def print_debts(debtors):
    print("\nVÕLGLASTE ARUANNE")
    print("=" * 80)
    print(f"{'Klient':<30} {'Arve nr':<8} {'Kuupäev':<12} {'Summa':>8} {'Makstud':>8} {'Võlg':>8}")
    print("-" * 80)
    
    total_debt = 0
    for debtor in sorted(debtors, key=lambda x: x['debt'], reverse=True):
        print(f"{debtor['client']:<30} "
              f"{debtor['invoice_number']:<8} "
              f"{debtor['invoice_date']:<12} "
              f"{debtor['invoice_amount']:>8.2f} "
              f"{debtor['paid_amount']:>8.2f} "
              f"{debtor['debt']:>8.2f}")
        total_debt += debtor['debt']
    
    print("-" * 80)
    print(f"Võlgnevusi kokku: {total_debt:.2f} EUR")
    print(f"Võlglasi kokku: {len(debtors)}")

def main():
    print("Analüüsin võlgnevusi...")
    debtors = analyze_debts()
    print_debts(debtors)

if __name__ == "__main__":
    main() 