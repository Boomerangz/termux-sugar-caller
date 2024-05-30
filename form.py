import npyscreen
import pickle
import os

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
            data = {'min_bg': 4, 'max_bg': 10, 'phone_number': '+7981247517'}
        
        self.min_bg = self.add(npyscreen.TitleText, name='Minimum BG:', value=str(data['min_bg']))
        self.max_bg = self.add(npyscreen.TitleText, name='Maximum BG:', value=str(data['max_bg']))
        self.phone_number = self.add(npyscreen.TitleText, name='Phone Number:', value=data['phone_number'])

    def on_ok(self):
        # Save current data to disk
        data = {
            'min_bg': int(self.min_bg.value),
            'max_bg': int(self.max_bg.value),
            'phone_number': self.phone_number.value
        }
        with open(self.filename, 'wb') as f:
            pickle.dump(data, f)
        self.parentApp.setNextForm(None)

    def on_cancel(self):
        self.parentApp.setNextForm(None)

if __name__ == '__main__':
    app = App()
    app.run()
