import requests
import time
from datetime import datetime
import os
import traceback


min_bg = 4
max_bg = 8
phone_number = '+7981247517'

while True:
    try:
        r = requests.get('http://mark2.oulu.io/api/v1/entries/current.json', timeout=5)
    except Exception as e:
        traceback.print_exc()
        time.sleep(5)
        continue
    js = r.json()
    dt = datetime.now()
    delta = round(js[0].get('delta')* 0.0555, 1)
    print(js[0]['sgv'] * 0.0555)
    print(delta)
    print(dt, dt.second, 30 - (dt.second % 30))

    current_sgv = js[0]['sgv'] * 0.0555

    bad = False
    if current_sgv < min_bg and delta <= 0:
        bad = True
    elif current_sgv > max_bg and delta >= 0:
        bad = True

    bad = True

    if bad:
        print('Bad')
        try:
            r = requests.get('https://mark2.oulu.io/api/v1/treatments.json', timeout=5)
        except Exception as e:
            traceback.print_exc()
            time.sleep(5)
            continue
        treatments = r.json()
        filtered_treatments = None
        if delta > 0:
            filtered_treatments = [t for t in treatments if t['eventType'] == 'Meal Bolus']
        else:
            filtered_treatments = [t for t in treatments if t['eventType'] == 'Carb Correction']

            
        last_treatment = sorted(filtered_treatments, key=lambda x: x['date'])[-1]
        since_last_treatment = (datetime.now().timestamp()*1000) - last_treatment['date']
        print(since_last_treatment, "Since last treatment")
        if since_last_treatment > 1000 * 60 * 3:
            print('Calling')
            # run termux call command
            os.system(f'termux-telephony-call +79992467159')


    


    time.sleep(30 - (dt.second % 30))
