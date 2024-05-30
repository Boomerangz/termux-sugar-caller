pkg install -y termux-api git python libexpat
termux-api-start
pip install -r requirements.txt
mkdir -p /data/data/com.termux/files/home/.shortcuts
cp start.sh /data/data/com.termux/files/home/.shortcuts/start.sh
cp stop.sh /data/data/com.termux/files/home/.shortcuts/stop.sh