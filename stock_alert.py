import os
import json
import requests
from datetime import datetime

# 환경변수에서 비밀 정보 읽기
BOT_TOKEN = os.environ['BOT_TOKEN']
CHAT_ID = os.environ['CHAT_ID']
GIST_TOKEN = os.environ['GIST_TOKEN']
GIST_ID = os.environ['GIST_ID']

# 감시할 종목
STOCKS = {
    '005930': '삼성전자',
    '000660': 'SK하이닉스'
}

THRESHOLD = 0.1  # ±3% 변동 감지

def get_stock_price(code):
    """네이버 금융에서 현재가 가져오기"""
    url = f"https://m.stock.naver.com/api/stock/{code}/basic"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        data = r.json()
        price = float(data['closePrice'].replace(',', ''))
        change_rate = float(data['fluctuationsRatio'])
        return price, change_rate
    except Exception as e:
        print(f"가격 조회 실패 ({code}): {e}")
        return None, None

def send_telegram(message):
    """텔레그램으로 메시지 전송"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {'chat_id': CHAT_ID, 'text': message, 'parse_mode': 'HTML'}
    try:
        r = requests.post(url, data=data, timeout=10)
        return r.status_code == 200
    except Exception as e:
        print(f"텔레그램 전송 실패: {e}")
        return False

def load_last_alerts():
    """이전 알림 기록 불러오기 (중복 알림 방지용)"""
    url = f"https://api.github.com/gists/{GIST_ID}"
    headers = {'Authorization': f'token {GIST_TOKEN}'}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        content = r.json()['files']['alerts.json']['content']
        return json.loads(content)
    except:
        return {}

def save_last_alerts(alerts):
    """알림 기록 저장"""
    url = f"https://api.github.com/gists/{GIST_ID}"
    headers = {'Authorization': f'token {GIST_TOKEN}'}
    data = {'files': {'alerts.json': {'content': json.dumps(alerts)}}}
    try:
        requests.patch(url, headers=headers, json=data, timeout=10)
    except Exception as e:
        print(f"기록 저장 실패: {e}")

def main():
    print(f"=== 실행 시간: {datetime.now()} ===")
    last_alerts = load_last_alerts()
    today = datetime.now().strftime('%Y-%m-%d')
    
    for code, name in STOCKS.items():
        price, change = get_stock_price(code)
        if price is None:
            continue
        
        print(f"{name}: {price:,}원 ({change:+.2f}%)")
        
        # ±3% 이상 변동 시 알림
        if abs(change) >= THRESHOLD:
            # 오늘 이미 같은 방향으로 알림 보냈는지 확인
            key = f"{today}_{code}_{'up' if change > 0 else 'down'}"
            if key not in last_alerts:
                emoji = '🚀' if change > 0 else '📉'
                message = (
                    f"{emoji} <b>{name}</b> {change:+.2f}%\n"
                    f"현재가: {price:,}원\n"
                    f"시각: {datetime.now().strftime('%H:%M')}"
                )
                if send_telegram(message):
                    last_alerts[key] = True
                    print(f"알림 전송 완료: {name}")
    
    # 7일 이전 기록은 삭제
    cutoff = datetime.now().strftime('%Y-%m-%d')
    last_alerts = {k: v for k, v in last_alerts.items() if k.split('_')[0] >= cutoff}
    save_last_alerts(last_alerts)

if __name__ == '__main__':
    main()
