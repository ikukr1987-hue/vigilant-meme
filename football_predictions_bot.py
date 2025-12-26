import time
import logging
import telebot
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from bs4 import BeautifulSoup
from apscheduler.schedulers.background import BackgroundScheduler
from contextlib import contextmanager

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Replace with your Telegram bot token and channel ID
TELEGRAM_TOKEN = '7882849253:AAFueHr2G1TUPB6-MGXg9ms9FkyA8XTqHCs'
CHANNEL_ID = '1176756945'  # or user chat_id

# League URL (example: English Premier League on Flashscore KZ)
LEAGUE_URL = 'https://www.flashscorekz.com/football/'
FIXTURES_URL = LEAGUE_URL + 'fixtures/'
STANDINGS_URL = LEAGUE_URL + 'standings/'

@contextmanager
def setup_driver():
    options = Options()
    options.add_argument('--headless')  # Run without browser window
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
    driver = webdriver.Chrome(options=options)
    try:
        yield driver
    finally:
        driver.quit()

def get_standings(driver):
    try:
        driver.get(STANDINGS_URL)
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CLASS_NAME, 'table__row')))
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        standings = {}
        table_rows = soup.find_all('div', class_='table__row')
        for row in table_rows:
            try:
                position_elem = row.find('span', class_='tableCellRank')
                team_elem = row.find('span', class_='team_name_span')
                if position_elem and team_elem:
                    position = position_elem.text.strip('.')
                    team = team_elem.text.strip()
                    standings[team] = int(position)
            except Exception as e:
                logging.warning(f"Error parsing standing row: {e}")
        return standings
    except TimeoutException:
        logging.error("Timeout loading standings page")
        return {}
    except Exception as e:
        logging.error(f"Error getting standings: {e}")
        return {}

def get_upcoming_matches(driver):
    try:
        driver.get(FIXTURES_URL)
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CLASS_NAME, 'event__match')))
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        matches = []
        match_rows = soup.find_all('div', class_=['event__match', 'event__match--scheduled'])
        for row in match_rows:
            try:
                home_elem = row.find('div', class_='event__participant--home')
                away_elem = row.find('div', class_='event__participant--away')
                if home_elem and away_elem:
                    home = home_elem.text.strip()
                    away = away_elem.text.strip()
                    home_link_tag = home_elem.find('a')
                    away_link_tag = away_elem.find('a')
                    home_link = 'https://www.flashscorekz.com' + home_link_tag['href'] if home_link_tag else None
                    away_link = 'https://www.flashscorekz.com' + away_link_tag['href'] if away_link_tag else None
                    matches.append((home, away, home_link, away_link))
            except Exception as e:
                logging.warning(f"Error parsing match row: {e}")
        return matches[:5]  # Limit to first 5 matches for example
    except TimeoutException:
        logging.error("Timeout loading fixtures page")
        return []
    except Exception as e:
        logging.error(f"Error getting upcoming matches: {e}")
        return []

def get_team_stats(driver, team_url):
    if not team_url:
        return None
    try:
        driver.get(team_url)
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CLASS_NAME, 'ui-table__row')))
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        last_matches = []
        match_rows = soup.select('div.ui-table__row')[:15]  # Last 15 matches
        for row in match_rows:
            try:
                # Detect home/away: check if the team's name is in home or away participant
                # Assuming team page shows team's matches with home/away indicator
                # Note: This might need adjustment based on actual structure
                home_part = row.find('div', class_='event__participant--home')
                away_part = row.find('div', class_='event__participant--away')
                if not home_part or not away_part:
                    continue
                home_team = home_part.text.strip()
                away_team = away_part.text.strip()
                # Assume the URL is for the team, so check which side the link is or something
                # For simplicity, check bold or class for highlighted team
                is_home = 'event__participant--home-bold' in home_part.get('class', []) or home_part.find('strong')
                score_home_elem = row.find('div', class_='event__score--home')
                score_away_elem = row.find('div', class_='event__score--away')
                if score_home_elem and score_away_elem:
                    scored_home = int(score_home_elem.text.strip())
                    scored_away = int(score_away_elem.text.strip())
                    if is_home:
                        scored = scored_home
                        conceded = scored_away
                    else:
                        scored = scored_away
                        conceded = scored_home
                    total = scored + conceded
                    win = scored > conceded
                    draw = scored == conceded
                    loss = scored < conceded
                    btts = scored > 0 and conceded > 0
                    over_15 = total > 1.5
                    under_15 = total < 1.5
                    last_matches.append({
                        'scored': scored,
                        'conceded': conceded,
                        'win': win,
                        'draw': draw,
                        'loss': loss,
                        'btts': btts,
                        'over_15': over_15,
                        'under_15': under_15
                    })
            except Exception as e:
                logging.warning(f"Error parsing team match row: {e}")
        if not last_matches:
            return None
        
        n = len(last_matches)
        if n == 0:
            return None
        win_rate = sum(m['win'] for m in last_matches) / n
        draw_rate = sum(m['draw'] for m in last_matches) / n
        loss_rate = sum(m['loss'] for m in last_matches) / n
        btts_rate = sum(m['btts'] for m in last_matches) / n
        over_15_rate = sum(m['over_15'] for m in last_matches) / n
        under_15_rate = sum(m['under_15'] for m in last_matches) / n
        avg_scored = sum(m['scored'] for m in last_matches) / n
        avg_conceded = sum(m['conceded'] for m in last_matches) / n
        
        return {
            'win_rate': win_rate,
            'draw_rate': draw_rate,
            'loss_rate': loss_rate,
            'btts_rate': btts_rate,
            'over_15_rate': over_15_rate,
            'under_15_rate': under_15_rate,
            'avg_scored': avg_scored,
            'avg_conceded': avg_conceded
        }
    except TimeoutException:
        logging.error(f"Timeout loading team page: {team_url}")
        return None
    except Exception as e:
        logging.error(f"Error getting team stats for {team_url}: {e}")
        return None

def calculate_predictions(home_stats, away_stats, home_pos, away_pos):
    if not home_stats or not away_stats:
        return []
    
    # Average rates
    avg_draw_rate = (home_stats['draw_rate'] + away_stats['draw_rate']) / 2
    
    # Prob home win: (home win rate + away loss rate)/2
    prob_home_win = (home_stats['win_rate'] + away_stats['loss_rate']) / 2
    
    # Prob away win: (home loss rate + away win rate)/2
    prob_away_win = (home_stats['loss_rate'] + away_stats['win_rate']) / 2
    
    # Normalize probabilities
    total_prob = prob_home_win + prob_away_win + avg_draw_rate
    if total_prob == 0:
        return []
    prob_home_win /= total_prob
    prob_away_win /= total_prob
    prob_draw = avg_draw_rate / total_prob
    
    prob_1x = prob_home_win + prob_draw  # Home not lose
    prob_x2 = prob_away_win + prob_draw  # Away not lose
    prob_over_15 = (home_stats['over_15_rate'] + away_stats['over_15_rate']) / 2
    prob_under_15 = (home_stats['under_15_rate'] + away_stats['under_15_rate']) / 2
    prob_btts = (home_stats['btts_rate'] + away_stats['btts_rate']) / 2
    
    # Adjust based on positions
    pos_diff = home_pos - away_pos
    adjustment = 0.05 * (pos_diff / 10) if abs(pos_diff) > 0 else 0  # Small adjustment
    prob_home_win -= adjustment
    prob_away_win += adjustment
    # Re-normalize if necessary
    total_prob = prob_home_win + prob_away_win + prob_draw
    prob_home_win /= total_prob
    prob_away_win /= total_prob
    prob_draw /= total_prob
    
    predictions = []
    
    # Total over 1.5 and 1X
    prob = prob_over_15 * prob_1x
    if prob > 0:
        coeff = round(1 / prob, 2)
        predictions.append({'type': 'Тотал больше 1.5 и 1X', 'prob': round(prob, 2), 'coeff': coeff})
    
    # Both to score
    if prob_btts > 0:
        coeff = round(1 / prob_btts, 2)
        predictions.append({'type': 'Обе забьют', 'prob': round(prob_btts, 2), 'coeff': coeff})
    
    # Home win and total over 1.5
    prob = prob_home_win * prob_over_15
    if prob > 0:
        coeff = round(1 / prob, 2)
        predictions.append({'type': 'Победа 1 и тотал больше 1.5', 'prob': round(prob, 2), 'coeff': coeff})
    
    # Total under 1.5 and X2
    prob = prob_under_15 * prob_x2
    if prob > 0:
        coeff = round(1 / prob, 2)
        predictions.append({'type': 'Тотал меньше 1.5 и X2', 'prob': round(prob, 2), 'coeff': coeff})
    
    return predictions

def send_daily_predictions():
    with setup_driver() as driver:
        bot = telebot.TeleBot(TELEGRAM_TOKEN)
        
        standings = get_standings(driver)
        matches = get_upcoming_matches(driver)
        
        for home, away, home_link, away_link in matches:
            home_stats = get_team_stats(driver, home_link)
            away_stats = get_team_stats(driver, away_link)
            home_pos = standings.get(home, 999)
            away_pos = standings.get(away, 999)
            
            preds = calculate_predictions(home_stats, away_stats, home_pos, away_pos)
            
            if preds:
                message = f"Матч: {home} vs {away}\nПозиции: {home} ({home_pos}), {away} ({away_pos})\n\nПрогнозы:\n"
                for p in preds:
                    message += f"{p['type']}: Вероятность {p['prob']*100}%, Коэффициент {p['coeff']}\n"
                try:
                    bot.send_message(CHANNEL_ID, message)
                except Exception as e:
                    logging.error(f"Error sending message: {e}")

if __name__ == '__main__':
    scheduler = BackgroundScheduler()
    scheduler.add_job(send_daily_predictions, 'cron', hour=13, minute=10)  # Every day at 8:00
    scheduler.start()
    
    print("Bot started. Waiting for scheduled tasks...")
    try:
        while True:
            time.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
