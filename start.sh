cd /data/data/com.termux/files/home/termux-sugar-caller && git pull && bash init.sh
pip install -r /data/data/com.termux/files/home/termux-sugar-caller/requirements.txt

termux-wake-lock
python /data/data/com.termux/files/home/termux-sugar-caller/main.py
termux-wake-unlock