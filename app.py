# -*- coding: utf-8 -*-
#
# @file          app.py
# Author       : Bernd Waldmann
# Created      : Sun Oct 27 23:01:35 2019
# This Revision: $Id: app.py 1315 2021-12-18 10:12:43Z  $
#
# Tracker for MySensors messages, with web viewer

#
#   Copyright (C) 2019,2021 Bernd Waldmann
#
#   This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0. 
#   If a copy of the MPL was not distributed with this file, You can obtain one at http://mozilla.org/MPL/2.0/
#
#   SPDX-License-Identifier: MPL-2.0
#

# adjust these constants to your environment
# in the author's setup, the topic is 'my/N/stat/...' where N is number of the gateway

MQTT_BROKER = "ha-server"               # the name of your MQTT broker
MQTT_TOPIC = "my/+/stat/#"              # the topic to subscribe to, includes wildcards
MQTT_PATTERN = r'my\/\d+\/stat\/(.+)'   # regular expression to extract the interesting part of topic

import sys,re,time,os
import logging
import logging.config
from datetime import datetime,timedelta
import paho.mqtt.client as mqtt         # EPL 1.0 or EDPL 1.0
from peewee import *                    # MIT license
import flask                            # BSD license
from flask import Flask,render_template,request,url_for,redirect
from playhouse.flask_utils import FlaskDB
from playhouse.flask_utils import object_list
from playhouse.hybrid import hybrid_property
import wtforms as wtf                   # BSD license

import mysensors

##############################################################################
#region Logging

def init_logging():

    logging.config.dictConfig({
        'version': 1,
        'formatters': {
            'default': {
                'format': '[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
            },
            'brief': {
                'format': '%(levelname)s in %(module)s: %(message)s',
            }
        },
        'handlers': {
            'wsgi': {
                'class': 'logging.StreamHandler',
                'stream': 'ext://flask.logging.wsgi_errors_stream',
                'formatter': 'default'
            },
            'console': {
                'class': 'logging.StreamHandler',
                'stream': 'ext://sys.stderr',
                'formatter': 'brief',
            },
        },
        'loggers': {
            'root': {
                'level': logging.INFO,
                'handlers': ['wsgi','console']
            },
            'app': {
                'level': logging.INFO,
                'handlers': ['console'],
            },
        },
        'disable_existing_loggers': False,
    })

    return logging.getLogger('app')

applog = init_logging()

#endregion

DATABASE_FILE = 'mysensors.db'
APP_DIR = os.path.dirname(os.path.realpath(__file__))
DATABASE_URI = 'sqlite:///%s' % os.path.join(APP_DIR, DATABASE_FILE)

app = Flask(__name__)
app.config['FLASK_ENV'] = 'development'
app.config['DEBUG'] = True
app.config['TESTING'] = True

##############################################################################
#region Model helpers

def make_usid(nid,cid):
    """calculate globally unique sensor id from node id and child id
    Args:
        nid (int): MySensors node id
        cid (int): MySensors child id
    Returns:
        int: unique id
    """
    return 1000*nid + cid

##----------------------------------------------------------------------------

def split_usid(usid):
    nid = usid // 1000
    cid = usid % 1000
    return (nid,cid)

##----------------------------------------------------------------------------

def make_uvid(nid,cid,typ):
    """calculate globally unique value id from node id, child id, message type
    Args:
        nid (int): MySensors node id
        cid (int): MySensors child id
        typ (int): MySensors type id
    Returns:
        int: unique id
    """
    return 1000000 *typ + 1000*nid + cid

#endregion
##############################################################################
#region Model definition

db = SqliteDatabase(None)

class BaseModel(Model):
    class Meta:
        database = db


class Node(BaseModel):
    """ table describing MySensor nodes
    """
    nid         = IntegerField( primary_key=True,       help_text="MySensors node id")      # e.g. '109'
    sk_name     = CharField( max_length=25, null=True,  help_text="sketch name")            # e.g. 'MyWindowSensor'
    sk_version  = CharField( max_length=25, null=True,  help_text="sketch version")         # e.g. '$Rev: 1315 $'
    sk_revision = IntegerField( default=0,              help_text="sketch SVN rev")          
    api_ver     = CharField( max_length=25, null=True,  help_text="MySensors API version")  # e.g. '2.3.1'
    lastseen    = DateTimeField( default=datetime.now,  help_text="last message" )
    location    = CharField( max_length=32, null=True,  help_text="where in the house is it?")
    bat_changed = DateField( null=True,                 help_text="date of last battery change")
    bat_level   = IntegerField(null=True,               help_text="battery level in %")


class Sensor(BaseModel):    
    """ table describing MySensor sensors, 
        Each row is one sensor on one node, as reported in present() calls in presentation() function
    """
    usid        = IntegerField( primary_key=True,       help_text="unique id")
    nid         = ForeignKeyField(Node)             
    cid         = IntegerField(                         help_text="MySensors child id")     # e.g. '11' (contact)
    typ         = IntegerField( null=True,              help_text="MySensors sensor type")  # e.g. '0'=S_DOOR
    name        = CharField( max_length=25, null=True,  help_text="sensor description")     # e.g. "Contact L"
    values      = BigBitField( null=True,               help_text="which V_xxx types have been seen")
    lastseen    = DateTimeField( default=datetime.now,  help_text="last message" )


class ValueType(BaseModel):
    """ table describing a sensor sub-channel, as reported by type=V_xxx messages
        Each row is one V_xxx value type sent by one sensor on one node
    """
    uvid        = IntegerField( primary_key=True,       help_text="unique channel id" )
    usid        = ForeignKeyField(Sensor)    
    nid         = ForeignKeyField(Node, backref='tvalues')
    cid         = IntegerField(                         help_text="MySensors child id")         # e.g. '11' (contact)
    typ         = IntegerField(                         help_text="MySensors value type")       # e.g. '2'=V_STATUS
    value       = CharField( max_length=25, null=True,  help_text="Current value")
    received    = DateTimeField( default=datetime.now,  help_text="timestamp" )

    @hybrid_property
    def timestamp(self):
        return self.received.to_timestamp()


class Message(BaseModel):
    """ table for all information contained in one MySensors message, as reported by gateway.
        Each row is one message received via gateway
    """
    nid         = ForeignKeyField(Node)
    cid         = IntegerField(                     help_text="MySensors child id" )        # e.g. '11' (contact)
    cmd         = IntegerField(                     help_text="MySensors command")
    typ         = IntegerField(                     help_text="MySensors type")
    payload     = CharField( max_length=25)
    received    = DateTimeField(default=datetime.now, help_text="timestamp" )

    @hybrid_property
    def usid(self):
        return make_usid(self.nid.nid, self.cid)

    @hybrid_property
    def value(self):
        return self.payload

    @hybrid_property
    def timestamp(self):
        return self.received.to_timestamp()
        

#endregion
##############################################################################
#region Model access
#     
 
def add_or_select_node(nid):
    """make sure node record exists, create if necessary
    Args:
        nid (int): MySensors node ID
    Returns:
        Node: instance
    """
    node, create = Node.get_or_create(nid=nid)
    return node 
    
##----------------------------------------------------------------------------
        
def add_or_select_sensor(nid,cid):
    """make sure sensor record exists, create if necessary
    Args:
        nid (int): node id
        cid (int): child id
    Returns:
        Sensor:    instance
    """
    sensor, create = Sensor.get_or_create(
        usid=make_usid(nid,cid),
        defaults={'nid':nid, 'cid':cid}
        )
    return sensor

##----------------------------------------------------------------------------
        
def add_or_select_tvalue(nid,cid,typ,val=None,dt=None):
    """make sure TypedValue record exists, create if necessary
    Args:
        nid (int): node id
        cid (int): child id
        typ (int): type V_xxx constant
        val (str): value string or None
        dt (datetime): timestamp or None
    Returns:
        ValueType:    instance
    """
    tvalue, create = ValueType.get_or_create(
        uvid=make_uvid(nid,cid,typ),
        defaults={'nid':nid, 'cid':cid, 'typ':typ, 'usid':make_usid(nid,cid) }
        )
    if val is not None:
        tvalue.value = val 
    if dt is not None:
        tvalue.received = dt
    return tvalue

##----------------------------------------------------------------------------

def fill_tvalues():
    """ migrate older DB version by filling ValueType table from Message table
    """
    query = Sensor.select().order_by(Sensor.usid)
    for s in query:
        for typ in range(64):
            if s.values.is_set(typ):
                try:
                    msg = Message.select().where( 
                            Message.nid == s.nid, 
                            Message.cid == s.cid, 
                            Message.cmd == mysensors.Commands.C_SET,
                            Message.typ == typ
                        ).order_by(Message.received.desc()).get()
                    tvalue = add_or_select_tvalue(
                                s.nid_id,
                                s.cid,typ,
                                msg.payload,
                                msg.received )
                    tvalue.save()
                    applog.debug("added tvalue uvid:%d nid:%d cid:%d typ:%d = '%s'", 
                        tvalue.uvid, s.nid_id, s.cid, typ, msg.payload )
                except Message.DoesNotExist:
                    pass

##----------------------------------------------------------------------------

def new_battery( nid, date=datetime.today()):
    """ declare that new battery has been inserted
    Args:
        nid (int): MySensors node ID
        date (datetime.date): date of battery change
    """
    node = add_or_select_node(nid)
    node.bat_changed = date
    node.save()

##----------------------------------------------------------------------------

def delete_node( nid ):
    """ delete a node, and all table rows that refer to it
    Args:
        nid (int): MySensors node ID
    """
    with db.atomic() as txn:
        applog.info("Deleting node {0}".format(nid))
        n = Message.delete().where(Message.nid==nid).execute()
        applog.debug("{0} messages removed".format(n))
        n = ValueType.delete().where(ValueType.nid==nid).execute()
        applog.debug("{0} types removed".format(n))
        n = Sensor.delete().where(Sensor.nid==nid).execute()
        applog.debug("{0} sensors removed".format(n))
        n = Node.delete().where(Node.nid==nid).execute()
        applog.debug("{0} nodes removed".format(n))

##----------------------------------------------------------------------------

def delete_node_requests( nid ):
    """ delete all request messages for this node
    Args:
        nid (int): MySensors node ID
    """
    with db.atomic() as txn:
        applog.info("Deleting node requests {0}".format(nid))
        n = Message.delete().where( (Message.nid==nid) & (Message.cmd == mysensors.Commands.C_REQ) ).execute()
        applog.debug("{0} request messages removed".format(n))

##----------------------------------------------------------------------------

def delete_sensor( nid, cid ):
    """ delete a sensor, and all table rows that refer to it
    Args:
        nid (int): MySensors node ID
        cid (int): MySensors child ID
    """
    usid = make_usid(nid,cid)
    with db.atomic() as txn:
        applog.info("Deleting node {0} sensor {1}".format( nid, cid ))

        n = Message.delete().where( (Message.nid==nid) & (Message.cid==cid) ).execute()
        applog.debug("{0} messages removed".format(n))

        n = ValueType.delete().where(ValueType.usid==usid).execute()
        applog.debug("{0} types removed".format(n))

        n = Sensor.delete().where(Sensor.usid==usid).execute()
        applog.debug("{0} sensors removed".format(n))

##----------------------------------------------------------------------------

def delete_old_stuff( ndays ):
    """ delete everything older than `ndays` days 
    Args:
        ndays (int): no of days to keep
    """
    cutoff = (datetime.today()-timedelta(days=ndays)).timestamp()
    applog.info("Deleting everything older than {0} days".format(ndays))

    n = ValueType.delete().where( ValueType.timestamp < cutoff ).execute()
    applog.info("{0} values removed".format(n))

    n = Message.delete().where( Message.timestamp < cutoff ).execute()
    applog.info("{0} messages removed".format(n))


#endregion
##############################################################################
#region MQTT message handling
      
def add_message( nid,cid,cmd,typ,pay ):
    """ add a record to 'messages' table
    Args:
        nid (int): MySensors node ID
        cid (int): MySensors child ID
        cmd (int): MySensors C_xxx command
        typ (int): MySensors I_xxx type
        pay (string): payload
    """
    tnow = datetime.now()

    node = add_or_select_node(nid)
    node.lastseen = tnow
    node.save()
    sensor = add_or_select_sensor(nid,cid)
    sensor.lastseen = tnow
    sensor.save()
    msg = Message.create(nid=nid,cid=cid,cmd=cmd,typ=typ,payload=pay)
    msg.save()

##----------------------------------------------------------------------------

def on_value_message( nid,cid,typ,val ):
    """ add a record to 'values' table, for a sensor
    Args:
        nid (int): MySensors node ID
        cid (int): MySensors child ID
        typ (int): MySensors I_xxx type
        val (string): payload
    """
    valname = mysensors.value_names.get(typ,"?")

    node = add_or_select_node(nid)       # make sure node exists
    
    sensor = add_or_select_sensor(nid,cid) # make sure sensor exists
    if typ >= 0:
        sensor.values.set_bit(typ)
    sensor.save()
    
    tvalue = add_or_select_tvalue(nid,cid,typ,val,datetime.now())
    tvalue.save()
    applog.debug("tvalue saved")
    
    applog.debug("on_value_message( nid:%d cid:%d typ:%d (%s) = '%s'", nid,cid,typ,valname,val)

##----------------------------------------------------------------------------
        
def on_node_value_message( nid,typ,val ):
    """ add a record to 'values' table, for sensor==255, i.e. node itself
    Args:
        nid (int): MySensors node ID
        typ (int): MySensors I_xxx type
        val (string): payload
    """
    valname = mysensors.value_names.get(typ,"?")
    applog.debug("on_node_value_message( nid:%d typ:%d (%s) = '%s'", nid,typ,valname,val)
    on_value_message( nid, 255, typ, val )

##----------------------------------------------------------------------------

def on_internal_message( nid, cid, typ, val ):
    """handle INTERNAL messages
    Args:
        nid (int): MySensors node ID
        cid (int): MySensors child ID
        typ (int): MySensors I_xxx type
        val (string): payload
    """
    typname = mysensors.internal_names.get(typ,"?")
    applog.debug("on_internal_message( nid:%d cid:%d typ:%d (%s) = '%s'", nid,cid,typ,typname,val)
    node = add_or_select_node(nid)

    #  my/2/stat/123/255/3/0/11 bwWindowSensor
    if (cid==255 and typ==mysensors.Internal.I_SKETCH_NAME):
        node.sk_name = val 
        applog.debug("sk_name='%s'", val)
        node.save()
    #  my/2/stat/123/255/3/0/12 $ Rev: 826 $ 11:34:24
    #  or
    #  my/2/stat/199/255/3/0/12 586
    elif (cid==255 and typ==mysensors.Internal.I_SKETCH_VERSION):
        node.sk_version = val
        applog.debug("sk_version='%s'", val)
        rev = 0
        if val.strip().isdigit():
            rev = int(val.strip())
        else:
            m = re.search(r"\$Rev: (\d+) *\$.*",val)
            if (m):
                rev = int(m.group(1))
        node.sk_revision = rev
        applog.debug("revision=%d", rev)
        node.save()
    elif (cid==255 and typ==mysensors.Internal.I_BATTERY_LEVEL):
        on_node_value_message( nid, int(mysensors.Values.V_PERCENTAGE), val)
        return
    else:
        return

##----------------------------------------------------------------------------

def on_presentation_message( nid, cid, typ, val ):
    """handle PRESENTATION messages for sensors
    Args:
        nid (int): MySensors node ID
        cid (int): MySensors child ID
        typ (int): MySensors I_xxx type
        val (string): payload
    """
    applog.debug("on_presentation_message( nid:%d cid:%d typ:%d = '%s'", nid,cid,typ,val)
    node = add_or_select_node(nid)
    sensor = add_or_select_sensor(nid,cid)

    #  my/2/stat/123/11/0/0/0 Contact L
    # or
    #  my/2/stat/199/81/0/0/37 Gas flow&vol [ct,l,l/h]
    if (cid!=255):
        sensor.name = val
        sensor.typ = typ
        sensor.save()

##----------------------------------------------------------------------------

def on_node_presentation_message( nid, typ, val ):
    """handle PRESENTATION messages where cid==255
    Args:
        nid (int): MySensors node ID
        typ (int): MySensors S_xxx type
        val (string): payload
    """
    applog.debug("on_node_presentation_message( nid:%d typ:%d = '%s'", nid,typ,val)
    node = add_or_select_node(nid)

    #  my/2/stat/123/255/0/0/17 2.3.1
    if (typ==mysensors.Sensors.S_ARDUINO_NODE):
        node.api_ver = val   # update node API version in payload
        node.save() 

##----------------------------------------------------------------------------

last_topic = ""
last_payload = ""
last_time = time.time()

def on_message(mqttc, userdata, msg):
    """MQTT callback function
    Args:
        mqttc (mqtt.Client): client object
        userdata (n/a): n/a
        msg (MQTTMessage): topic and payload
    """
    # example   my/3/stat/106/61/1/0/23 37
    global last_topic, last_payload, last_time, applog
    try:    
        payload = msg.payload.decode("utf-8")
        now = time.time()
        m = re.search(MQTT_PATTERN,msg.topic)
        if m is None:
            return

        topic = m.group(1)
        path = topic.split('/')
        if (len(path) < 5):
            return

        # remove duplicates
        isnew = (last_topic != topic) or (last_payload != payload) or ((now - last_time) > 1)
        last_topic = topic
        last_payload = payload
        last_time = now
        if not isnew: return

        nid = int(path[0])
        cid = int(path[1])
        cmd = int(path[2])
        typ = int(path[4])
        val = msg.payload.decode("utf-8")
        applog.debug("message nid:%d cid:%d cmd:%d typ:%d = '%s'",nid,cid,cmd,typ,val)
        add_message(nid,cid,cmd,typ,val)

        if (cmd==mysensors.Commands.C_SET and cid!=255):
            on_value_message(nid,cid,typ,val)
        elif (cmd==mysensors.Commands.C_SET and cid==255):
            on_node_value_message(nid,typ,val)
        elif (cmd==mysensors.Commands.C_PRESENTATION and cid!=255):
            on_presentation_message(nid,cid,typ,val)
        elif (cmd==mysensors.Commands.C_PRESENTATION and cid==255):
            on_node_presentation_message(nid,typ,val)
        elif (cmd==mysensors.Commands.C_INTERNAL):
            on_internal_message(nid,cid,typ,val)
    except Exception as err:
        print("Error: " + str(err))
        sys.exit(1)
        raise

#endregion  
##############################################################################
#region Routes

@app.route('/')
def index():
    return render_template('index.html')

##----------------------------------------------------------------------------

@app.route('/nodes')
def nodes():
    sort = flask.request.args.get('sort', default="nid", type=str)

    query = Node.select(Node,ValueType.value.alias('level')).join(
                ValueType, 
                JOIN.LEFT_OUTER, 
                on=(
                    (Node.nid==ValueType.nid_id) & 
                    (ValueType.cid==255) & 
                    (ValueType.typ==3),
                    ),
                )

    if (sort=="date"):
        query = query.order_by(Node.lastseen.desc())
    else:
        query = query.order_by(Node.nid)
    return object_list('nodes.html', query.objects(), sort=sort )

##----------------------------------------------------------------------------

@app.route('/sensors')
def sensors():
    sort = flask.request.args.get('sort', default="usid", type=str)
    cid = flask.request.args.get('cid', default=None, type=int)
    nid = flask.request.args.get('nid', default=None, type=int)

    query = Sensor.select().join(Node)

    # sort as requested
    if sort=="cid": 
        query = query.order_by(Sensor.cid)
    elif sort=="date": 
        query = query.order_by(Sensor.lastseen.desc())
    else: 
        query = query.order_by(Sensor.usid)

    # filter by nid if requested
    if nid is not None:
        if nid >=0:
            query = query.where(Sensor.nid==nid)
        else:
            query = query.where(Sensor.nid!=-nid)
    return object_list( 'sensors.html', query, sort=sort, nid=nid, cid=cid )

##----------------------------------------------------------------------------

@app.route('/tvalues')
def tvalues():
    # get parameters
    sort = flask.request.args.get('sort', default="usid", type=str)
    nid = flask.request.args.get('nid', default=None, type=str)
    cid = flask.request.args.get('cid', default=None, type=str)
    usid = flask.request.args.get('usid', default=None, type=str)

    query = ValueType.select().join(Node).switch(ValueType).join(Sensor)

    # sort as requested
    if sort=="cid": 
        query = query.order_by(ValueType.cid)
    elif sort=="date": 
        query = query.order_by(ValueType.received.desc())
    else: 
        query = query.order_by(ValueType.usid)

    # filter if requested
    if usid is not None and len(usid)>0:
        iusid = int(usid)
        query = query.where(ValueType.usid==iusid)
    elif nid is not None and len(nid)>0:
        inid = int(nid)
        if inid >=0:
            query = query.where(ValueType.nid==inid)
        else:
            query = query.where(ValueType.nid!=-inid)
    elif cid is not None and len(cid)>0:
        icid = int(cid)
        if (icid>=0):
            query = query.where(ValueType.cid==icid)
        else:
            query = query.where(ValueType.cid!=-icid)
    return object_list( 'types.html', query, sort=sort, nid=nid, cid=cid, usid=usid )

##----------------------------------------------------------------------------

@app.route('/values')
def values():
    # get parameters
    sort = flask.request.args.get('sort', default="usid", type=str)
    nid = flask.request.args.get('nid', default=None, type=str)
    cid = flask.request.args.get('cid', default=None, type=str)
    usid = flask.request.args.get('usid', default=None, type=str)

    query = Message.select().where(Message.cmd==mysensors.Commands.C_SET)

    # sort as requested
    if sort=="cid": 
        query = query.order_by(Message.cid)
    elif sort=="date": 
        query = query.order_by(Message.received.desc())
    else: 
        query = query.order_by(Message.nid, Message.cid)
    	    
    # filter if requested
    if usid is not None and len(usid)>0:
        iusid = int(usid)
        inid,icid = split_usid(iusid)
        query = query.where( (Message.nid==inid) & (Message.cid==icid) )
    elif nid is not None and len(nid)>0:
        inid = int(nid)
        if inid >=0:
            query = query.where(Message.nid==inid)
        else:
            query = query.where(Message.nid!=-inid)
    elif cid is not None and len(cid)>0:
        icid = int(cid)
        if (icid>=0):
            query = query.where(Message.cid==icid)
        else:
            query = query.where(Message.cid!=-icid)
    return object_list( 'values.html', query, sort=sort, nid=nid, cid=cid, usid=usid )

##----------------------------------------------------------------------------

@app.route('/messages')
def messages():
    # get parameters
    sort = flask.request.args.get('sort', default="usid", type=str)
    cid = flask.request.args.get('cid', default=None, type=str)
    nid = flask.request.args.get('nid', default=None, type=str)
    usid = flask.request.args.get('usid', default=None, type=str)

    # sort as requested
    if sort=='nid':
        query = Message.select().order_by(Message.nid)
    elif sort=="cid": 
        query = Message.select().order_by(Message.cid)
    elif sort=="cmd":
        query = Message.select().order_by(Message.cmd)
    elif sort=='typ':
        query = Message.select().order_by(Message.typ)
    else: 
        query = Message.select().order_by(Message.received.desc())

    # filter if requested
    if usid is not None and len(usid)>0:
        iusid = int(usid)
        query = query.where(Message.usid==iusid)
    elif nid is not None and len(nid)>0:
        inid = int(nid)
        if inid >=0:
            query = query.where(Message.nid==inid)
        else:
            query = query.where(Message.nid!=-inid)
    elif cid is not None and len(cid)>0:
        icid = int(cid)
        if (icid>=0):
            query = query.where(Message.cid==icid)
        else:
            query = query.where(Message.cid!=-icid)

    return object_list( 'messages.html', query, sort=sort, nid=nid, cid=cid, usid=usid )

##----------------------------------------------------------------------------

@app.route('/newbattery', methods=['GET','POST'])
def battery_today():
    if request.method=='POST':
        print("POST: ")
        print( request.form )
        if 'today' in request.form:
            nid = request.form['today']
            print("Node {0} battery changed today".format(nid))
            new_battery(int(nid))
    elif request.method=='GET':
        print("GET: ")
        print (request )
    return redirect(url_for('batteries'))

#endregion
##############################################################################
#region Jinja helpers

@app.context_processor
def my_processor():

    def command_string(cmd):
        """look up C_symbolic name for command
        Args:
            cmd (int): MySensors command, see API doc
        Returns:
            string: symbolic name like C_PRESENTATION
        """
        if cmd is None: return None
        return mysensors.command_names.get(cmd)

    def sensor_string(typ):
        """look up S_xxx symbolic name for sensor type <typ>
        Args:
            typ (int): MySensors sensor type, see API doc
        Returns:
            string: symbolic name like S_DOOR
        """
        if typ is None: return None
        return mysensors.sensor_names.get(typ)

    def type_string(cmd,typ):
        """look up symbolic name for type (sensor or value, depending on command)
        Args:
            cmd (int): MySensors command
            typ (int): MySensors type
        Returns:
            string: symbolic name like S_DOOR or V_STATUS
        """
        if (cmd is None) or (typ is None): return None
        if (cmd==mysensors.Commands.C_REQ) or (cmd==mysensors.Commands.C_SET):
            return mysensors.value_names.get(typ)
        elif (cmd==mysensors.Commands.C_PRESENTATION):
            return mysensors.sensor_names.get(typ)
        elif (cmd==mysensors.Commands.C_INTERNAL):
            return mysensors.internal_names.get(typ)
        else:
            return None

    def value_string(typ):
        """look up V_xxx symbolic name for value type
        Args:
            typ (int): MySensors value type, see API doc
        Returns:
            string: symbolic name like V_STATUS
        """
        if typ is None: return None
        return mysensors.value_names.get(typ)

    def values_string(values: BigBitField):
        """return a list of symbolic names of values types sent by this sensor
        Args:
            values (BigBitField): bit 0 set if type 0 found, etc
        Returns:
            string: comma-separated list of symbolic names
        """
        vnames = []
        for i in range(64):
            if values.is_set(i):
                vname = mysensors.value_names.get(i)
                if vname is not None:
                    vnames.append(vname)
        return ", ".join(vnames)
    
    def days_ago(dt: datetime):
        """calculate how many days ago a date was
        Args:
            dt (datetime): datestamp
        Returns:
            int: number of days in the past
        """
        if dt is not None:
            return round((dt.now()-dt).total_seconds()/(60*60*24))
        else:
            return None

    def months_ago(dt: datetime):
        """calculate how many months ago a date was
        Args:
            dt (datetime): datestamp
        Returns:
            int: number of months in the past
        """
        if dt is not None:
            return round( (datetime.today().date() - dt).total_seconds() / (60*60*24*30) )
        else:
            return None

    return dict( 
        command_string=command_string,
        sensor_string=sensor_string,
        type_string=type_string,
        value_string=value_string,
        values_string=values_string,
        days_ago=days_ago,
        months_ago=months_ago,
        )

#endregion
##############################################################################
#region Forms

class ConfirmDeleteNodeForm(wtf.Form):
    f_nid = wtf.IntegerField("Node ID:", render_kw={"class":"edit edit-node"})

    @app.route("/nodes/<int:nid>/delete", methods=['GET','POST'])
    def confirm_delete_node(nid):
        form = ConfirmDeleteNodeForm(request.form)
        # if POST, then use data from form
        if (request.method=='POST'):
            print ("Delete node {0}".format(request.form['f_nid']))
            delete_node(nid)
            return redirect(url_for('nodes'))
        # else if GET, then display form
        form.f_nid.data = nid
        return render_template('confirm_delete_node.html', form=form )

##----------------------------------------------------------------------------

class ConfirmDeleteSensorForm(wtf.Form):
    f_nid = wtf.IntegerField("Node ID:", render_kw={"class":"edit edit-node"})
    f_cid = wtf.IntegerField("Sensor ID:", render_kw={"class":"edit edit-node"})

    @app.route("/sensors/<int:usid>/delete", methods=['GET','POST'])
    def confirm_delete_sensor(usid):
        nid,cid = split_usid(usid)
        form = ConfirmDeleteSensorForm(request.form)
        # if POST, then use data from form
        if (request.method=='POST'):
            print ("Delete node {0} sensor {1}".format( request.form['f_nid'], request.form['f_cid'] ))
            delete_sensor(nid,cid)
            return redirect(url_for('sensors'))
        # else if GET, then display form
        form.f_nid.data = nid
        form.f_cid.data = cid
        return render_template('confirm_delete_sensor.html', form=form )

##----------------------------------------------------------------------------

class ConfirmDeleteNodeRequestsForm(wtf.Form):
    f_nid = wtf.IntegerField("Node ID:", render_kw={"class":"edit edit-node"})

    @app.route("/nodes/<int:nid>/delete-requests", methods=['GET','POST'])
    def confirm_delete_node_requests(nid):
        form = ConfirmDeleteNodeRequestsForm(request.form)
        # if POST, then use data from form
        if (request.method=='POST'):
            print ("Delete node {0} requests".format(request.form['f_nid']))
            delete_node_requests(nid)
            return redirect(url_for('nodes'))
        # else if GET, then display form
        form.f_nid.data = nid
        return render_template('confirm_delete_node_req.html', form=form )

##----------------------------------------------------------------------------

class ConfirmDeleteOldForm(wtf.Form):
    f_ndays = wtf.IntegerField("", render_kw={"class":"edit edit-node"})

    @app.route("/messages/delete/<int:ndays>", methods=['GET','POST'])
    def confirm_delete_old(ndays):
        ndays = 365
        form = ConfirmDeleteOldForm(request.form)
        # if POST, then use data from form
        if (request.method=='POST'):
            ndays = int(request.form['f_ndays'])
            print ("Delete records older than {0} days".format(ndays))
            delete_old_stuff(ndays)
            return redirect(url_for('nodes'))
        # else if GET, then display form
        form.f_ndays.data = ndays
        return render_template('confirm_delete_old.html', form=form )

##----------------------------------------------------------------------------

class ConfirmNewBatteryForm(wtf.Form):
    f_nid = wtf.IntegerField("Node ID:", render_kw={"class":"edit edit-node"})
    f_bat = wtf.DateField("Date:", render_kw={"class":"edit edit-date"})

    @app.route("/nodes/<int:nid>/battery", methods=['GET','POST'])
    def confirm_new_battery(nid):
        form = ConfirmNewBatteryForm(request.form)
        # if POST, then use data from form
        if (request.method=='POST'):
            fnid = request.form['f_nid']
            fbat = request.form['f_bat']
            print ("New battery in node {0} at {1}".format(fnid, fbat))
            new_battery(fnid,fbat)
            return redirect(url_for('nodes'))
        # else if GET, then display form
        form.f_nid.data = nid
        form.f_bat.data = datetime.today()
        return render_template('confirm_new_battery.html', form=form )

##----------------------------------------------------------------------------

class LocationForm(wtf.Form):
    nid = wtf.IntegerField("Node:", render_kw={"class":"td-id edit ro", "tabindex":-1 })
    sketch = wtf.TextField("Sketch:", render_kw={"class":"edit ro", "tabindex":-1 })
    location = wtf.TextField("Location:", render_kw={"class":"edit", })

class LocationsForm(wtf.Form):
    locs = wtf.FieldList(wtf.FormField(LocationForm))

    @app.route('/locations', methods=['GET','POST'])
    def locations():
        form = LocationsForm(request.form)
        # if POST, then use data from form
        if (request.method=='POST'):
            for lf in form.locs.entries:
                try:
                    node = Node.get(Node.nid==lf.nid.data)
                    if node.location != lf.location.data:
                        applog.info("update %d location to '%s'",lf.nid.data, lf.location.data)
                        node.location = lf.location.data
                        node.save()
                    elif lf.location.data is None or len(lf.location.data)==0:
                        node.location = None
                        applog.info("update %d location to None",lf.nid.data)
                        node.save()
                except DoesNotExist:
                    print("Error: " + str(err))
                    sys.exit(1)
                    raise
            return redirect(url_for('nodes'))
        # else if GET, then display form
        nodes = Node.select().order_by(Node.nid)
        for node in nodes:
            lf = LocationForm()
            lf.nid = node.nid
            lf.sketch = node.sk_name
            lf.location = node.location
            form.locs.append_entry(lf)
        return render_template('locations.html', form=form )

##----------------------------------------------------------------------------

class BatteryForm(wtf.Form):
    nid = wtf.IntegerField("Node:", render_kw={"class":"td-id edit ro", "tabindex":-1 })
    sketch = wtf.TextField("Sketch:", render_kw={"class":"edit ro", "tabindex":-1 })
    location = wtf.TextField("Location:", render_kw={"class":"edit ro", "tabindex":-1 })
    bat_changed = wtf.DateField("Date:", render_kw={"class":"edit edit-date"})

class BatteriesForm(wtf.Form):
    bats = wtf.FieldList(wtf.FormField(BatteryForm))

    @app.route('/batteries', methods=['GET','POST'])
    def batteries():
        form = BatteriesForm(request.form)
        # if POST, then use data from form
        if (request.method=='POST'):
            for lf in form.bats.entries:
                try:
                    node = Node.get(Node.nid==lf.nid.data)
                    if node.bat_changed != lf.bat_changed.data:
                        applog.info("update %d battery date to '%s'",lf.nid.data, lf.bat_changed.data)
                        node.bat_changed = lf.bat_changed.data
                        node.save()
                    elif lf.bat_changed.data is None:
                        node.bat_changed = None
                        applog.info("update %d battery date to None",lf.nid.data)
                        node.save()
                except DoesNotExist:
                    print("Error: " + str(err))
                    sys.exit(1)
                    raise
            return redirect(url_for('nodes'))
        # else if GET, then display form
        nodes = Node.select().order_by(Node.nid)
        for node in nodes:
            lf = BatteryForm()
            lf.nid = node.nid
            lf.sketch = node.sk_name
            lf.location = node.location
            lf.bat_changed = node.bat_changed
            form.bats.append_entry(lf)
        return render_template('batteries.html', form=form )

#endregion
#############################################################################

def main():
    db.init(os.path.join(APP_DIR, DATABASE_FILE))
    db.connect()
    tables = [Node,Sensor,ValueType,Message]
    db.create_tables(tables)
    applog.info("opened database")

    if ValueType.select().count()==0:
        fill_tvalues()

    mqttc = mqtt.Client()
    mqttc.on_message = on_message
    mqttc.connect(MQTT_BROKER, 1883, 60)
    mqttc.subscribe(MQTT_TOPIC)                   
    mqttc.loop_start()
    applog.info("listening to MQTT")

    app.run( debug=True, use_reloader=False, host='0.0.0.0' )


if __name__ == '__main__':
    main()
