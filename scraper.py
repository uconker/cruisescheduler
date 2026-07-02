import requests
from bs4 import BeautifulSoup
import json
import time

def scrape_ehoi():
    # The URL from your previous search parameters
    url = "https://www.e-hoi.de/?fuseaction=search.doSearch&usersearch=1&sort=price-asc&departdate=07.07.2026&arrivdate=07.09.2026&daterange=07.07.2026_20-_2007.09.2026&cruisingareaid=64&reisedauer=6-9"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    print("Fetching cruise data...")
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    cruises = []
    
    # Find all cruise cards (e-hoi typically uses these list items)
    # Note: We may need to tweak these class names if e-hoi updates their site!
    cards = soup.find_all('div', class_='result-item') # Approximated class name based on standard structure
    
    for card in cards:
        try:
            title_elem = card.find('h2')
            price_elem = card.find(class_='price') # Approximated class
            
            if title_elem and price_elem:
                cruises.append({
                    "title": title_elem.text.strip(),
                    "price": price_elem.text.strip(),
                    "scraped_at": time.strftime("%Y-%m-%d %H:%M:%S")
                })
        except Exception as e:
            print(f"Skipped a card due to error: {e}")

    # Save to JSON
    with open('cruises.json', 'w', encoding='utf-8') as f:
        json.dump(cruises, f, indent=4, ensure_ascii=False)
        
    print(f"Successfully saved {len(cruises)} cruises to cruises.json")

if __name__ == "__main__":
    scrape_ehoi()
