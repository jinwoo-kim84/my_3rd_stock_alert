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
    '000660': 'SK하이닉스',
    '013580': '계룡건설',
    '092790': '넥스틸',
    '456160': '지투지바이오'
}

STEP = 3.0  # 3% 단위로 알림

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
    """이전 알림 기록 불러오기"""
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

def get_level(change):
    """등락률을 3% 단위 레벨로 변환
    예: +3.5% → 1, +6.2% → 2, -3.8% → -1, -7.1% → -2
    """
    if abs(change) < STEP:
        return 0
    if change > 0:
        return int(change // STEP)
    else:
        return -int(abs(change) // STEP)

def main():
    print(f"=== 실행 시간: {datetime.now()} ===")
    last_alerts = load_last_alerts()
    today = datetime.now().strftime('%Y-%m-%d')
    
    for code, name in STOCKS.items():
        price, change = get_stock_price(code)
        if price is None:
            continue
        
        current_level = get_level(change)
        print(f"{name}: {price:,}원 ({change:+.2f}%, 레벨 {current_level})")
        
        if current_level == 0:
            continue  # 3% 미만 변동은 무시
        
        # 오늘 이 종목이 최대 어느 레벨까지 알림 보냈는지 확인
        key = f"{today}_{code}"
        last_level = last_alerts.get(key, 0)
        
        # 새로운 레벨에 도달했을 때만 알림
        # 예: 이전 레벨 1 (+3%대) → 현재 레벨 2 (+6%대) 진입 시 알림
        #     이전 레벨 -1 (-3%대) → 현재 레벨 -2 (-6%대) 진입 시 알림
        should_alert = False
        if current_level > 0 and current_level > last_level:
            should_alert = True
        elif current_level < 0 and current_level < last_level:
            should_alert = True
        
        if should_alert:
            emoji = '🚀' if change > 0 else '📉'
            threshold_text = f"{current_level * STEP:+.0f}% 돌파"
            message = (
                f"{emoji} <b>{name}</b> {threshold_text}\n"
                f"등락률: {change:+.2f}%\n"
                f"현재가: {price:,}원\n"
                f"시각: {datetime.now().strftime('%H:%M')}"
            )
            if send_telegram(message):
                last_alerts[key] = current_level
                print(f"알림 전송 완료: {name} 레벨 {current_level}")
    
    # 7일 이전 기록은 삭제
    cutoff = datetime.now().strftime('%Y-%m-%d')
    last_alerts = {k: v for k, v in last_alerts.items() if k.split('_')[0] >= cutoff}
    save_last_alerts(last_alerts)

if __name__ == '__main__':
    main()
