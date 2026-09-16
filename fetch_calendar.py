import json
from datetime import datetime, timezone, timedelta
import re
import cloudscraper
from bs4 import BeautifulSoup

def scrape_forex_factory_calendar():
    url = "https://www.forexfactory.com/calendar"
    
    scraper = cloudscraper.create_scraper(browser={
        'browser': 'chrome',
        'platform': 'windows',
        'desktop': True
    })

    try:
        response = scraper.get(url, timeout=15)
        response.raise_for_status()
    except Exception as e:
        print(f"Error fetching page: {e}")
        return None

    soup = BeautifulSoup(response.text, 'html.parser')
    
    now_jst = datetime.now(timezone(timedelta(hours=9)))

    result = {
        "updated_at": now_jst.strftime('%Y-%m-%d %H:%M:%S JST'),
        "events": []
    }

    rows = soup.find_all('tr', class_='calendar__row')
    
    current_date = ""
    current_time = ""

    for row in rows:
        # 日付セル
        date_cell = row.find('td', class_='calendar__date')
        if date_cell and date_cell.text.strip():
            current_date = date_cell.text.strip()

        # 時刻セル
        time_cell = row.find('td', class_='calendar__time')
        if time_cell and time_cell.text.strip():
            current_time = time_cell.text.strip()

        # 通貨
        currency_cell = row.find('td', class_='calendar__currency')
        currency = currency_cell.text.strip() if currency_cell else ""

        # イベントタイトル
        event_cell = row.find('td', class_='calendar__event')
        event_title = event_cell.text.strip() if event_cell else ""

        # 重要度 (Impact)
        impact_cell = row.find('td', class_='calendar__impact')
        impact_level = "Low"
        if impact_cell:
            impact_span = impact_cell.find('span')
            if impact_span:
                classes = " ".join(impact_span.get('class', []))
                if 'red' in classes:
                    impact_level = 'High'
                elif 'ora' in classes or 'orange' in classes:
                    impact_level = 'Medium'
                elif 'yel' in classes or 'yellow' in classes:
                    impact_level = 'Low'

        # 通貨とタイトルが存在するものを全件保持
        if currency and event_title:
            result["events"].append({
                "date": current_date,
                "time": current_time,
                "currency": currency,
                "event": event_title,
                "impact": impact_level
            })

    return result

if __name__ == "__main__":
    data = scrape_forex_factory_calendar()
    if data and data["events"]:
        with open("calendar_data.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        print(f"calendar_data.json successfully updated. ({len(data['events'])} events extracted)")
    else:
        print("Failed to retrieve data.")
