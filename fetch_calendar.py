import json
from datetime import datetime, timedelta, timezone
import re
import cloudscraper
from bs4 import BeautifulSoup

# 日本時間 (JST) 定義
JST = timezone(timedelta(hours=9))

def parse_forex_factory_date(date_str, year):
    """'Wed Sep 16' のような文字列を datetime.date オブジェクトに変換"""
    try:
        # 曜日を取り除いて解析 ('Sep 16')
        clean_date = re.sub(r'^[A-Za-z]+ ', '', date_str.strip())
        dt = datetime.strptime(f"{year} {clean_date}", "%Y %b %d")
        return dt.date()
    except Exception:
        return None

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
    
    now_jst = datetime.now(JST)
    today_jst_date = now_jst.date()
    current_year = now_jst.year

    result = {
        "updated_at": now_jst.strftime('%Y-%m-%d %H:%M:%S JST'),
        "events": []
    }

    rows = soup.find_all('tr', class_='calendar__row')
    
    current_date_str = ""
    current_time_str = ""

    for row in rows:
        # 日付の更新
        date_cell = row.find('td', class_='calendar__date')
        if date_cell and date_cell.text.strip():
            current_date_str = date_cell.text.strip()

        # 時刻の更新
        time_cell = row.find('td', class_='calendar__time')
        if time_cell and time_cell.text.strip():
            current_time_str = time_cell.text.strip()

        currency_cell = row.find('td', class_='calendar__currency')
        currency = currency_cell.text.strip() if currency_cell else ""

        event_cell = row.find('td', class_='calendar__event')
        event_title = event_cell.text.strip() if event_cell else ""

        # 重要度 (Impact) の判定（新仕様のクラス名に対応）
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

        if currency and event_title and current_date_str:
            base_date = parse_forex_factory_date(current_date_str, current_year)
            if not base_date:
                continue

            # 時刻の解析とJSTへの変換
            jst_time_str = current_time_str
            event_jst_date = base_date

            # '8:30am', '1:00pm' などの時刻フォーマットを処理
            time_match = re.match(r'^(\d{1,2}):(\d{2})(am|pm)$', current_time_str.lower())
            if time_match:
                hour = int(time_match.group(1))
                minute = int(time_match.group(2))
                ampm = time_match.group(3)

                if ampm == 'pm' and hour != 12:
                    hour += 12
                elif ampm == 'am' and hour == 12:
                    hour = 0

                # 米国東部標準時（EDT: UTC-4）として生成し、JSTへ変換
                edt = timezone(timedelta(hours=-4))
                dt_edt = datetime(base_date.year, base_date.month, base_date.day, hour, minute, tzinfo=edt)
                dt_jst = dt_edt.astimezone(JST)

                event_jst_date = dt_jst.date()
                jst_time_str = dt_jst.strftime('%H:%M')

            # ★ フィルタリング: 日本時間で「今日」のイベントのみを抽出
            if event_jst_date == today_jst_date:
                result["events"].append({
                    "date": event_jst_date.strftime('%Y-%m-%d'),
                    "time": jst_time_str,
                    "currency": currency,
                    "event": event_title,
                    "impact": impact_level
                })

    return result

if __name__ == "__main__":
    data = scrape_forex_factory_calendar()
    if data:
        with open("calendar_data.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        print(f"calendar_data.json updated. ({len(data['events'])} events today)")
