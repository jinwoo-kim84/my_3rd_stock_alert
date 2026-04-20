import os
import json
import requests
from datetime import datetime

# 환경변수에서 비밀 정보 읽기
BOT_TOKEN = os.environ['BOT_TOKEN']
CHAT_ID = os.environ['CHAT_ID']
GIST_TOKEN = os.environ['GIST_TOKEN']
GIST_ID = os.environ['GIST_ID']

# 보유 종목: {종목코드: (종목명, 평단가)}
# 손해 중인 종목만 감시 (평단가 대비 -5%, -3%, 0%, +1% 도달 시 알림)
HOLDINGS = {
    '0015G0': ('그린광학', 47100),
    '005930': ('삼성전자', 217000),
    '006400': ('삼성SDI', 535000),
    '010140': ('삼성중공업', 30055),
    '002300': ('삼익제약', 16670),
    '039860': ('나노엔텍', 7340),
    '046120': ('오르비텍', 12930),
    '054940': ('엑사이엔씨', 780),
    '098660': ('휴림에이텍', 1498),
    '090430': ('아모레퍼시픽', 167980),
    '171090': ('선익시스템', 109988),
    '196170': ('알테오젠', 433800),
    '204320': ('HL만도', 55833),
    '321260': ('유투바이오', 30533),
    '319400': ('현대무벡스', 33150),
    '476760': ('오가노이드사이언스', 29540),
    '000250': ('삼천당제약', 501500),
    '0009K0': ('에임드바이오', 51600),
    '002700': ('신일전자', 1506),
    '005380': ('현대차', 658750),
    '024060': ('흥구석유', 34367),
    '030530': ('원익홀딩스', 31150),
    '035420': ('NAVER', 260275),
    '047040': ('대우건설', 28650),
    '052690': ('한전기술', 189700),
    '066570': ('LG전자', 132342),
    '084850': ('아이티엠반도체', 18530),
    '100790': ('미래에셋벤처투자', 47500),
    '226950': ('올릭스', 179400),
    '293490': ('카카오게임즈', 20456),
    '339770': ('교촌에프앤비', 5870),
    '361610': ('SK아이이테크놀로지', 37646),
    '389470': ('인벤티지랩', 77800),
    '417200': ('LS머트리얼즈', 24516),
    '475150': ('SK이터닉스', 54700),
    '475830': ('오름테라퓨틱', 123100),
    '476080': ('알지노믹스', 237000),
    '252670': ('KODEX 200선물인버스', 225),
    '013580': ('계룡건설', 29350),
}

# 기존 당일 등락률 3% 단위 알림 (유지)
STEP = 3.0

# 평단가 대비 알림 구간 (수익률 %)
# 음수는 손실, 양수는 수익 구간
TARGET_LEVELS = [-5.0, -3.0, 0.0, 1.0]


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


def get_daily_level(change):
    """당일 등락률을 STEP 단위 레벨로 변환 (기존 알림)"""
    if abs(change) < STEP:
        return 0
    if change > 0:
        return int(change // STEP)
    else:
        return -int(abs(change) // STEP)


def get_profit_rate(current_price, avg_price):
    """평단가 대비 수익률(%) 계산"""
    return (current_price - avg_price) / avg_price * 100


def check_target_hit(profit_rate, last_hit_levels):
    """평단가 대비 구간 도달 여부 확인
    반환: 새로 도달한 레벨 리스트
    """
    new_hits = []
    for level in TARGET_LEVELS:
        # 이미 오늘 알림 보낸 구간이면 스킵
        if level in last_hit_levels:
            continue
        
        # -5%, -3%는 "이하로 떨어졌을 때" 알림
        if level < 0:
            if profit_rate <= level:
                new_hits.append(level)
        # 0%(본전), +1%(수익전환)은 "이상으로 올라왔을 때" 알림
        else:
            if profit_rate >= level:
                new_hits.append(level)
    
    return new_hits


def format_level_text(level):
    """레벨을 사람이 읽기 좋은 텍스트로"""
    if level == -5.0:
        return "⚠️ -5% 도달"
    elif level == -3.0:
        return "📉 -3% 도달"
    elif level == 0.0:
        return "🟡 본전 도달"
    elif level == 1.0:
        return "🎉 수익 전환!"
    else:
        return f"{level:+.1f}%"


def main():
    print(f"=== 실행 시간: {datetime.now()} ===")
    last_alerts = load_last_alerts()
    today = datetime.now().strftime('%Y-%m-%d')

    for code, (name, avg_price) in HOLDINGS.items():
        price, change = get_stock_price(code)
        if price is None:
            continue

        # 평단가 대비 수익률 계산
        profit_rate = get_profit_rate(price, avg_price)
        print(f"{name}: {price:,.0f}원 (당일 {change:+.2f}%, 평단대비 {profit_rate:+.2f}%)")

        # ===== 1. 평단가 대비 알림 (신규) =====
        profit_key = f"{today}_{code}_profit"
        last_hit_levels = last_alerts.get(profit_key, [])
        
        new_hits = check_target_hit(profit_rate, last_hit_levels)
        
        for level in new_hits:
            level_text = format_level_text(level)
            profit_amount = (price - avg_price) * 1  # 주당 손익
            
            message = (
                f"{level_text}\n"
                f"<b>{name}</b>\n"
                f"평단가: {avg_price:,.0f}원\n"
                f"현재가: {price:,.0f}원\n"
                f"수익률: {profit_rate:+.2f}%\n"
                f"당일 등락: {change:+.2f}%\n"
                f"시각: {datetime.now().strftime('%H:%M')}"
            )
            
            if send_telegram(message):
                last_hit_levels.append(level)
                last_alerts[profit_key] = last_hit_levels
                print(f"  → 평단가 알림 전송: {name} {level_text}")

        # ===== 2. 당일 등락률 3% 단위 알림 (기존) =====
        current_level = get_daily_level(change)
        if current_level == 0:
            continue

        daily_key = f"{today}_{code}_daily"
        last_level = last_alerts.get(daily_key, 0)

        should_alert = False
        if current_level > 0 and current_level > last_level:
            should_alert = True
        elif current_level < 0 and current_level < last_level:
            should_alert = True

        if should_alert:
            blocks = '🟥🟥🟥' if change > 0 else '🟦🟦🟦'
            threshold_text = f"{current_level * STEP:+.1f}% 돌파"
            message = (
                f"{blocks}\n"
                f"<b>{name}</b> {threshold_text}\n"
                f"당일 등락: {change:+.2f}%\n"
                f"현재가: {price:,.0f}원\n"
                f"평단대비: {profit_rate:+.2f}%\n"
                f"시각: {datetime.now().strftime('%H:%M')}"
            )
            if send_telegram(message):
                last_alerts[daily_key] = current_level
                print(f"  → 당일 등락 알림 전송: {name} 레벨 {current_level}")

    # 오늘 이전 데이터 정리
    cutoff = datetime.now().strftime('%Y-%m-%d')
    last_alerts = {k: v for k, v in last_alerts.items() if k.split('_')[0] >= cutoff}
    save_last_alerts(last_alerts)


if __name__ == '__main__':
    main()
