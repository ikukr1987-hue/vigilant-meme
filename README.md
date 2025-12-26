import telebot
import requests
from bs4 import BeautifulSoup

# Токен твоего бота
bot = telebot.TeleBot('YOUR_TOKEN')

@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, 'Привет! Напиши /matches, чтобы получить список сегодняшних футбольных матчей с коэффициентами (где доступны).')

@bot.message_handler(commands=['matches'])
def get_matches(message):
    url = 'https://www.flashscore.com/football/'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.3'
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Находим все матчи
        matches = soup.find_all('div', class_='event__match')
        if not matches:
            bot.send_message(message.chat.id, 'Матчи не найдены. Возможно, классы изменились или нужно использовать Selenium.')
            return
        
        result = 'Сегодняшние матчи (с коэффициентами 1X2, где доступны):\n\n'
        
        for match in matches[:15]:  # Ограничим 15 матчами, чтобы не спамить
            time = match.find('div', class_='event__time')
            time = time.text.strip() if time else 'Время неизвестно'
            
            home = match.find('div', class_='event__participant--home')
            home = home.text.strip() if home else 'Хозяева'
            
            away = match.find('div', class_='event__participant--away')
            away = away.text.strip() if away else 'Гости'
            
            # Коэффициенты 1X2
            odd_home = match.find('div', class_='event__odd--home')
            odd_home = odd_home.text.strip() if odd_home else '-'
            
            odd_draw = match.find('div', class_='event__odd--draw')
            odd_draw = odd_draw.text.strip() if odd_draw else '-'
            
            odd_away = match.find('div', class_='event__odd--away')
            odd_away = odd_away.text.strip() if odd_away else '-'
            
            result += f'{time} | {home} vs {away}\n'
            result += f'Коэффициенты (1X2): {odd_home} | {odd_draw} | {odd_away}\n\n'
        
        bot.send_message(message.chat.id, result or 'Коэффициенты не найдены для матчей.')
    
    except Exception as e:
        bot.send_message(message.chat.id, f'Ошибка парсинга: {str(e)}\nПопробуй позже или используй другой источник.')

# Запуск бота
bot.polling()
