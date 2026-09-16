import json
from datetime import datetime, timezone
import cloudscraper
from bs4 import BeautifulSoup

def scrape_forex_factory_calendar():
    url = "https://www.forexfactory.com/calendar"
    
    # cloudscraperを使用して Cloudflare 対策を回避
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
    
    now_str = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
    
    result = {
        "updated_at": now_str,
        "events": []
    }

    # カレンダーの行（calendar__row）を取得
    rows = soup.find_all('tr', class_='calendar__row')
    
    current_date = ""

    for row in rows:
        # 日付セル（日付がまとまっている行と空の行があるため、前の日付を保持する）
        date_cell = row.find('td', class_='calendar__date')
        if date_cell and date_cell.text.strip():
            current_date = date_cell.text.strip()

        # 通貨（ペア関連）
        currency_cell = row.find('td', class_='calendar__currency')
        currency = currency_cell.text.strip() if currency_cell else ""

        # イベント内容
        event_cell = row.find('td', class_='calendar__event')
        event_title = event_cell.text.strip() if event_cell else ""

        # 重要度（impact）の判定
        impact_cell = row.find('td', class_='calendar__impact')
        impact_level = "Unknown"
        if impact_cell:
            impact_span = impact_cell.find('span')
            if impact_span:
                # class名（icon--ff-impact-red, icon--ff-impact-ora など）から判定
                classes = " ".join(impact_span.get('class', []))
                if 'red' in classes:
                    impact_level = 'High'
                elif 'ora' in classes or 'orange' in classes:
                    impact_level = 'Medium'
                elif 'yel' in classes or 'yellow' in classes:
                    impact_level = 'Low'
                elif 'gra' in classes or 'gray' in classes:
                    impact_level = 'Non-Economic'

        # 通貨とイベントタイトルが存在する場合のみデータに追加
        if currency and event_title:
            result["events"].append({
                "date": current_date,
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
        print("calendar_data.json successfully updated.")
    else:
        print("Failed to retrieve calendar data or data is empty.")
        fallback_data = {
            "updated_at": datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC'),
            "events": [],
            "error": "Failed to scrape"
        }
        with open("calendar_data.json", "w", encoding="utf-8") as f:
            json.dump(fallback_data, f, ensure_ascii=False, indent=4)
