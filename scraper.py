import requests
from bs4 import BeautifulSoup
import json
import re
import time

def scrape_ehoi():
    # The updated base URL including your new date range and duration filters (1-9 days)
    # Notice we kept usersearch=1 OUT of this base string so pagination works
    base_url = "https://www.e-hoi.de/mittelmeer-kreuzfahrten/fahrgebiet-64.html?sort=price-asc&departdate=08.07.2026&arrivdate=11.10.2026&daterange=08.07.2026%20-%2011.10.2026&reisedauer=1-5&reisedauer=6-9&filterby=arrivdate"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7"
    }

    cruise_db = {}
    passenger_counts = [2, 3, 4]
    pages_per_query = 3 # Scrape the first 3 pages

    session = requests.Session()
    session.headers.update(headers)

    for p_count in passenger_counts:
        print(f"\n--- FINDING CRUISES FOR {p_count} ADULT OCCUPANCY ---")
        
        # Initialize session for this passenger count
        init_url = f"{base_url}&personen={p_count}"
        session.get(init_url)
        time.sleep(1)
        
        for page_num in range(1, pages_per_query + 1):
            url = f"{init_url}&page={page_num}"
            print(f"Fetching page {page_num}...")
            
            try:
                response = session.get(url, timeout=15)
                response.encoding = 'utf-8'
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # e-hoi usually wraps search results in divs with class 'route' or similar
                # We need to look for the cards that contain the "Termine" section
                # Based on typical e-hoi structure, we look for list items or divs that hold a route
                cruise_cards = soup.find_all('div', class_=re.compile(r'route.*|result.*'))
                
                # If we can't find cards the standard way, let's try a broader search for elements containing "Termine:"
                if not cruise_cards:
                     term_elements = soup.find_all(string=re.compile("Termine:"))
                     cruise_cards = [elem.find_parent('div', class_=True) for elem in term_elements if elem.find_parent('div', class_=True)]
                     # Filter none
                     cruise_cards = [card for card in cruise_cards if card]
                     # Go up a few levels to get the whole card
                     if cruise_cards:
                         cruise_cards = [card.parent.parent for card in cruise_cards if card.parent and card.parent.parent]

                if not cruise_cards:
                    print(f"No cruise cards found on page {page_num}. Trying next page.")
                    break
                    
                found_on_page = 0
                for card in cruise_cards:
                    # Attempt to extract ID from links or data attributes
                    link_elem = card.find('a', href=re.compile(r'/kreuzfahrt/.*'))
                    if not link_elem:
                        continue
                        
                    url_str = link_elem.get('href')
                    if url_str.startswith('/'):
                        url_str = "https://www.e-hoi.de" + url_str
                        
                    # Extract ID from URL (e.g., .../128485_0/...)
                    id_match = re.search(r'/(\d+)_\d+/', url_str)
                    if not id_match:
                        continue
                    route_id = id_match.group(1)
                    
                    # Extract Price
                    price_elem = card.find(class_=re.compile(r'price|preis', re.I))
                    best_price = None
                    if price_elem:
                        # Find the first number in the text
                        price_match = re.search(r'(\d+[\.,]?\d*)', price_elem.text.replace('.', ''))
                        if price_match:
                            best_price = int(price_match.group(1))

                    if not best_price:
                         continue # Skip if we can't find a price

                    if route_id not in cruise_db:
                        # Extract Title
                        title_elem = card.find('h2') or card.find('h3') or link_elem
                        title = title_elem.text.strip() if title_elem else "Unbekannte Kreuzfahrt"
                        
                        # Extract Ship & Duration & Cabin - Usually in a subtitle or list
                        # This is tricky without exact HTML, so we do generic text searches
                        text_content = card.text
                        
                        ship_match = re.search(r'(Costa|MSC|AIDA|Norwegian|Mein Schiff|Queen)\s+([A-Za-z]+)', text_content)
                        ship = ship_match.group(0) if ship_match else "Unbekanntes Schiff"
                        
                        dur_match = re.search(r'(\d+)\s+Tage', text_content)
                        duration = int(dur_match.group(1)) if dur_match else 0
                        
                        cabin_match = re.search(r'(Innenkabine|Außenkabine|Balkonkabine|Suite)', text_content)
                        cabin = cabin_match.group(1) if cabin_match else "Innenkabine"

                        # Extract Dates based on the screenshot format: "08.10. - 12.10.2026 | ..."
                        exact_dates = []
                        term_blocks = card.find_all(string=re.compile(r'Termine:'))
                        for block in term_blocks:
                            parent = block.parent
                            if parent and parent.parent:
                                dates_text = parent.parent.text
                                # Find all start dates in a range like "08.10. - 12.10.2026"
                                # We capture the start DD.MM. and append the year from the end
                                date_pairs = re.findall(r'(\d{2}\.\d{2}\.)\s*-\s*\d{2}\.\d{2}\.(\d{4})', dates_text)
                                for day_month, year in date_pairs:
                                     exact_dates.append(f"{day_month}{year}")
                                     
                        # Deduplicate and sort dates
                        exact_dates = sorted(list(set(exact_dates)))

                        cruise_db[route_id] = {
                            "id": route_id,
                            "title": title,
                            "ship": ship,
                            "duration_days": duration,
                            "cabin_type": cabin,
                            "url": url_str,
                            "ports": "Routen-Details siehe Link", # Ports are hard to scrape from list view reliably
                            "prices_per_person": {},
                            "exact_dates": exact_dates,
                            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")
                        }
                    
                    # Update pricing tier
                    cruise_db[route_id]["prices_per_person"][f"{p_count}_adults"] = best_price
                    found_on_page += 1
                    
                print(f"Found {found_on_page} items on this page.")
                time.sleep(2) # Be polite
                
            except Exception as e:
                print(f"Error scraping page {page_num}: {e}")
                break

    final_cruise_list = list(cruise_db.values())
    
    # Filter to only include cruises where we found dates
    # final_cruise_list = [c for c in final_cruise_list if len(c['exact_dates']) > 0]

    with open('cruises.json', 'w', encoding='utf-8') as f:
        json.dump(final_cruise_list, f, indent=4, ensure_ascii=False)
        
    print(f"\nCompleted! Saved {len(final_cruise_list)} unique itineraries.")

if __name__ == "__main__":
    scrape_ehoi()
