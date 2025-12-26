from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import time
import pandas as pd
from bs4 import BeautifulSoup
import re

# Setup Selenium with Chrome
options = webdriver.ChromeOptions()
options.add_argument('--headless')  # Run in headless mode
driver = webdriver.Chrome(options=options)  # Assume chromedriver is in PATH

def get_daily_matches():
    driver.get('https://www.flashscorekz.com/football/')
    time.sleep(5)  # Wait for page load
    
    # Find today's upcoming matches
    matches = []
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    match_rows = soup.find_all('div', class_=re.compile('event__match--scheduled'))
    
    for row in match_rows:
        match_id = row['id'].split('_')[-1]
        home_team = row.find('div', class_='event__participant--home').text.strip()
        away_team = row.find('div', class_='event__participant--away').text.strip()
        league = row.find_previous('div', class_='event__header').text.strip() if row.find_previous('div', class_='event__header') else 'Unknown'
        match_url = f'https://www.flashscorekz.com/match/{match_id}/#match-summary'
        matches.append({
            'home': home_team,
            'away': away_team,
            'league': league,
            'match_url': match_url
        })
    
    return matches

def get_team_stats(team_name, is_home=True):
    # Search for team page
    search_url = f'https://www.flashscorekz.com/search/?q={team_name.replace(" ", "+")}'
    driver.get(search_url)
    time.sleep(3)
    
    # Click on the first team result
    try:
        team_link = driver.find_element(By.CSS_SELECTOR, 'a.search__result')
        team_link.click()
        time.sleep(3)
    except:
        return None
    
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    
    # Get last 15 matches
    last_matches = []
    match_table = soup.find('div', id='tabid_1_0')  # Results tab
    if match_table:
        rows = match_table.find_all('div', class_='event__match')
        for row in rows[:15]:  # Last 15
            home = row.find('div', class_='event__participant--home').text.strip()
            away = row.find('div', class_='event__participant--away').text.strip()
            score = row.find('div', class_='event__score').text.strip()
            if score:
                goals = list(map(int, re.findall(r'\d+', score)))
                total_goals = sum(goals)
                btts = goals[0] > 0 and goals[1] > 0
                result = 'W' if (home == team_name and goals[0] > goals[1]) or (away == team_name and goals[1] > goals[0]) else 'D' if goals[0] == goals[1] else 'L'
                last_matches.append({
                    'total_goals': total_goals,
                    'btts': btts,
                    'result': result
                })
    
    return last_matches

def get_standings(league):
    # Assume league url from match
    # This is simplified; may need to search for league page
    # For example, click on league in match page
    # Here, placeholder
    positions = {'home_pos': 1, 'away_pos': 2}  # Dummy
    return positions

def calculate_probabilities(home_stats, away_stats):
    if not home_stats or not away_stats:
        return None
    
    # Home not lose prob
    home_not_lose = len([m for m in home_stats if m['result'] != 'L']) / len(home_stats)
    
    # Away not lose
    away_not_lose = len([m for m in away_stats if m['result'] != 'L']) / len(away_stats)
    
    # Over 1.5 avg
    over_15_home = len([m for m in home_stats if m['total_goals'] > 1.5]) / len(home_stats)
    over_15_away = len([m for m in away_stats if m['total_goals'] > 1.5]) / len(away_stats)
    over_15_prob = (over_15_home + over_15_away) / 2
    
    # BTTS
    btts_home = len([m for m in home_stats if m['btts']]) / len(home_stats)
    btts_away = len([m for m in away_stats if m['btts']]) / len(away_stats)
    btts_prob = (btts_home + btts_away) / 2
    
    # Home win prob (simplified)
    home_win = len([m for m in home_stats if m['result'] == 'W']) / len(home_stats)
    
    # Combos
    forecasts = []
    
    # Over 1.5 and home not lose
    prob = over_15_prob * home_not_lose
    if prob > 0.5:  # Threshold
        forecasts.append({'type': 'Over 1.5 and Home not lose', 'prob': prob, 'coeff': 1 / prob * 1.1})  # Dummy coeff, parse real
    
    # BTTS
    if btts_prob > 0.5:
        forecasts.append({'type': 'Both Teams to Score', 'prob': btts_prob, 'coeff': 1 / btts_prob * 1.1})
    
    # Add more as per examples
    
    return forecasts

def get_odds(match_url):
    driver.get(match_url + '/odds/')
    time.sleep(3)
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    # Parse odds for markets: 1X2, O/U 1.5, BTTS, etc.
    # Placeholder
    odds = {'over_1.5': 1.5, 'btts': 1.8}  # Dummy
    return odds

def main():
    matches = get_daily_matches()
    for match in matches:
        home_stats = get_team_stats(match['home'], True)
        away_stats = get_team_stats(match['away'], False)
        standings = get_standings(match['league'])
        odds = get_odds(match['match_url'])
        probs = calculate_probabilities(home_stats, away_stats)
        
        if probs:
            print(f"Match: {match['home']} vs {match['away']} ({match['league']})")
            for p in probs:
                coeff = odds.get(p['type'].lower(), p['coeff'])  # Use real if available
                print(f"Forecast: {p['type']}, Prob: {p['prob']:.2f}, Coeff: {coeff:.2f}")
            print("\n")

    driver.quit()

if __name__ == "__main__":
    main()
