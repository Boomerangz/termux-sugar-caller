import npyscreen
import pickle
import os
import requests
import time
from datetime import datetime
import traceback

min_bg = 4
max_bg = 10
phone_number = '+7981247517'

class App(npyscreen.NPSAppManaged):
    def onStart(self):
        self.addForm('MAIN', MainForm, name="Input Form")

class MainForm(npyscreen.ActionForm):
    def create(self):
        self.filename = 'user_data.pkl'
        # Load previous data if it exists
        if os.path.exists(self.filename):
            with open(self.filename, 'rb') as f:
                data = pickle.load(f)
        else:
            data = {'min_bg': min_bg, 'max_bg': max_bg, 'phone_number': phone_number}
        
        self.min_bg = self.add(npyscreen.TitleText, name='Minimum BG:', value=str(data['min_bg']))
        self.max_bg = self.add(npyscreen.TitleText, name='Maximum BG:', value=str(data['max_bg']))
        self.phone_number = self.add(npyscreen.TitleText, name='Phone Number:', value=data['phone_number'])

        # This will set the focus on the OK button by default
        self.editw = len(self._widgets__) - 2  # Focus the widget just before the last (OK button)

    def on_ok(self):
        # Save current data to disk
        data = {
            'min_bg': float(self.min_bg.value),
            'max_bg': float(self.max_bg.value),
            'phone_number': self.phone_number.value
        }
        with open(self.filename, 'wb') as f:
            pickle.dump(data, f)
        self.parentApp.setNextForm(None)
        global min_bg, max_bg, phone_number
        min_bg = data['min_bg']
        max_bg = data['max_bg']
        phone_number = data['phone_number']
        run_loop()

    def on_cancel(self):
        self.parentApp.setNextForm(None)

def run_loop():
    os.system('clear')
    while True:
        try:
            r = requests.get('http://mark2.oulu.io/api/v1/entries/current.json', timeout=5)
        except Exception as e:
            traceback.print_exc()
            time.sleep(5)
            continue
        js = r.json()
        dt = datetime.now()
        delta = round(js[0].get('delta') * 0.0555, 1)
        current_sgv = js[0]['sgv'] * 0.0555
        bad = False

        output = []

        output.append(f"SGV: {current_sgv:.1f}")
        output.append(f"Delta: {delta:.1f}")
        output.append(f"Time: {dt} {dt.second} seconds, next check in {30 - (dt.second % 30)} seconds")

        if current_sgv < min_bg and delta <= 0:
            bad = True
        elif current_sgv > max_bg and delta >= 0:
            bad = True

        if bad:
            output.append('Bad')
            if current_sgv < min_bg and delta <= 0:
                output.append('Low')
            else:
                output.append('High')
            try:
                r = requests.get('https://mark2.oulu.io/api/v1/treatments.json', timeout=5)
            except Exception as e:
                traceback.print_exc()
                time.sleep(5)
                continue
            treatments = r.json()
            if delta > 0:
                filtered_treatments = [t for t in treatments if t['eventType'] == 'Meal Bolus']
            else:
                filtered_treatments = [t for t in treatments if t['eventType'] == 'Carb Correction']

            last_treatment = sorted(filtered_treatments, key=lambda x: x['date'])[-1]
            since_last_treatment = (datetime.now().timestamp()) - last_treatment['date']
            output.append(f"{last_treatment['date']} Last treatment date")
            output.append(f"{(datetime.now().timestamp())} Now")
            output.append(f"{(datetime.now())} Now")
            output.append(f"{since_last_treatment} Since last treatment")

            if since_last_treatment > 1000 * 60 * 45:
                output.append('Calling')
                # Join all parts of the output and print in one go
                print("\t".join(output))
                # run termux call command
                os.system(f'termux-telephony-call {phone_number}')
                time.sleep(60 * 5)
            else:
                # Join all parts of the output and print in one go
                print("\t".join(output))

        time.sleep(30 - (dt.second % 30))

if __name__ == '__main__':
    app = App()
    app.run()
    
