pkg install -y termux-api git python
pkg rei -y libexpat
termux-api-start
pip install -r requirements.txt
cp start.sh /data/data/com.termux/files/home/.shortcuts/start.sh
cp stop.sh /data/data/com.termux/files/home/.shortcuts/stop.sh