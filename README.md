Tracker for MySensors messages
===========================================

I needed a simple tool for keeping track of all the MySensors nodes which I had built and deployed around the house over the years:
* what is the battery level of a sensor node?
* what was the last time I changed the battery on that sensor node, i.e. how many months has it been running with the current battery?
* see at a glance if a sensor has crashed, i.e. has not sent any messages for, say, more than a day
* is a sensor node sending strange messages?

For a detailed description of the intended behavior of the app (i.e. the requirements specification), see [requirements](requirements.md) .

Prerequisites
-------------
The app assumes that all MySensors messages are captured by an MQTT gateway, as described on the [MySensors website](https://www.mysensors.org/build/mqtt_gateway)

The app is written in Python 3. I have tested this both on my Microsoft Windows 10 development machine, and on a Debian 10 (Buster) Linux virtual server.

The app uses an Sqlite database.

The app uses the [**Peewee**](http://docs.peewee-orm.com/en/latest/#) library  to access the database, the [**Flask**](https://palletsprojects.com/p/flask/) web framework, and the [**Eclipe Paho**](https://www.eclipse.org/paho/) MQTT library to listen to the MQTT messages published by the MySensors gateways.

On my virtual linux server that runs the app, I just did
```sh
sudo apt-get install sqlite3
sudo apt-get install python3 python3-venv python3-dev
```

Installation
------------
Install the source files in any folder, say `~/mytracker` .
Now install the required libraries
```sh
cd ~/mytracker
python3 -m venv venv
source venv/bin/activate
pip3 install peewee flask wtforms paho-mqtt
```

Now you can just run the app
```sh
venv/bin/python app.py
```
This will start the built-in webserver on port 5000. 

The Flask people recommend not to use the built-in server for a production environment, but I decided it was good enough for my use at home. This has been running for >6 months now, without a glitch. logging messsages from ~20 MySensors nodes.

Browse to http://*servername*:5000/nodes, and you should see the MySensorsTracker UI.

Configuration 
-------------
In the `main` function in `app.py`, you need to adjust the MQTT server name and topic to subscribe to. 

In my home, the MQTT broker (mosquitto) runs on a server named `ha-server`, and the MySensors messages are received by two gateways, which then publish them via MQTT as `my/1/stat/...` and `my/2/stat/...`, respectively. Some MySensors nodes are in range for both gateways, so their messages are published *twice*, which is filtered out by the app, in function `on_message()`.

Permanent Use
-------------
For long-term use, I am running this under supervisord (see http://supervisord.org/index.html). 

I created `/etc/supervisor/conf.d/mytracker.conf` and entered
```
[program:mytracker]
command=/home/admin/mytracker/venv/bin/python app.py
directory=/home/admin/mytracker
stdout_logfile=/home/admin/mytracker/stdout.log
stderr_logfile=/home/admin/mytracker/stderr.log
user=admin
startretries=1 
```
(adjust the path for your configuration)

I edited `/etc/supervisor/supervisord.conf` and made sure it contains these lines
```
[inet_http_server]
port=*:9001 
[include]
files=conf.d/*.conf
```
Now I can view the status of the app by browsing to http://*servername*:9001

