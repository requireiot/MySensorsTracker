__MySensorsTracker__: MySensors dashboard
==============================

- [x] requirement is implemented and tested. 
- [ ] requirement is not implemented or tested, ideas for future versions.

# Use Cases

`UC001` Overview of nodes: software version, sensors etc

`UC002` Overview of status of nodes: what is the battery level? has any node not sent messages for a while?

`UC002` Quantitative analyses, e.g. battery level over time, frequency of reports, etc., maybe using external service like Grafana

`UC003` Browse messages, detect any odd behavior of nodes

# Requirements

## MQTT

- [x] `R001` capture all MQTT messages from MySensors nodes, store in database

- [x] `R002` if same message is received multiple times, from different gateways, then ignore all but one

- [x] `R012` capture time & date when message was received

- [ ] `R013` capture which gateway received the message

### Nodes

- [x] `R003` capture information about nodes, from MQTT messages
  - [x] `R003.1` capture MySensors API version of node
  - [x] `R003.2` capture sketch name (sent by node via MySensors `sendSketchInfo()` function)
  - [x] `R003.3` capture sketch version string (sent by node via MySensors `sendSketchInfo()` function)
  - [x] `R003.4` capture sketch SVN revision, if available
  - [x] `R003.5` capture sensor description (sent by node via MySensors `present()` function)
  - [x] `R003.6` capture all values reported by sensors
  - [x] `R003.7` capture battery level reported by nodes

### Sensors
- [x] `R004` capture information about sensors, from MQTT
  - [x] `R004.1` capture sensor description
  - [x] `R004.2` capture sensor type, e.g. S_DOOR
  - [x] `R004.§` capture which V_xxx value types a sensor has reported

## UI, Input

- [x] `R005` let user enter information about nodes
  - [x] `R005.1` let user indicate "battery changed today"
  - [x] `R005.2` let user enter date of last battery change
  - [x] `R005.3` let user enter location of node

## UI, Output

### Nodes

- [ ] `R006` display on a web page information about all nodes
  - [x] `R006.1` display MySensors node ID
  - [x] `R006.2` display MySensors API version of firmware
  - [x] `R006.3` display sketch name
  - [ ] `R006.4` display sketch version string
  - [x] `R006.5` display sketch SVN revision, if available
  - [x] `R006.7` display timestamp of most recent message
  - [x] `R006.6` display date of last battery change
  - [x] `R006.8` display months alive since last battery change, if available
  - [x] `R006.9` display battery level
  - [x] `R006.11` display location of node

### Sensors

- [x] `R007` display on a web page information about all sensors
  - [x] `R007.2` display MySensors child ID
  - [x] `R007.3` display MySensors node ID
  - [x] `R007.4` display sensor type, such as S_DOOR
  - [x] `R007.5` display list of value types reported by sensor, such as V_TRIPPED
  - [x] `R007.6` display timestamp of most recent message

- [x] `R020` filter content
  - [x] `R020.1` display all sensors
  - [x] `R020.2` display all sensors for one node

- [ ] `R019` navigate from this screen to other screens, with filtering
  - [x] `R019.1` offer to show all values for one node
  - [x] `R019.2` offer to show all messages for one node
  - [x] `R019.3` offer to show all values for one sensor instance
  - [ ] `R019.4` offer to show all values for one sensor type

### Types and current values

- [x] `R018` display on a web page information about all sensor types seen
  - [x] `R018.1` display either information for all sensors, or all sensors for one node
  - [x] `R018.2` display MySensors child ID
  - [x] `R018.3` display MySensors parent node ID
  - [x] `R018.4` display sensor type, such as S_DOOR
  - [x] `R018.5` display value type reported by sensor, such as V_TRIPPED
  - [x] `R018.6` display most recent value
  - [x] `R018.8` display timestamp of most recent message

- [x] `R017` allow user to select which types/values to display
  - [x] `R017.1` display all types/values for all sensors
  - [x] `R017.2` display types/values for one node
  - [x] `R017.3` display types/values for one sensor type
  - [x] `R017.4` display types/values for one sensor instance

### Value messages

- [ ] `R008` display information about values reported by sensors
  - [x] `R008.1` display MySensors child ID
  - [x] `R008.2` display MySensors parent node ID
  - [x] `R007.3` display value type, such as V_STATUS
  - [x] `R007.4` display value text, as originally received
  - [ ] `R007.5` display value as number, if possible
  - [x] `R007.6` display timestamp when value was received

- [x] `R009` allow user to select which values to display
  - [x] `R009.1` display all values for all sensors
  - [x] `R009.2` display values for one node
  - [x] `R009.3` display values for one sensor type
  - [x] `R009.4` display values for one sensor instance

### Messages

- [x] `R010` display information about messages sent by nodes
  - [x] `R010.1` display MySensors node ID
  - [x] `R010.2` display MySensors child ID
  - [x] `R010.3` display MySensors command
  - [x] `R010.4` display MySensors command symbol like I_PRESENTATION
  - [x] `R010.5` display MySensors type
  - [x] `R010.6` display MySensors type symbol, such as V_STATUS
  - [x] `R010.7` display payload text, as originally received
  - [x] `R010.8` display timestamp when value was received

- [x] `R011` allow user to select which messages to display
  - [x] `R011.1` display all messages
  - [x] `R011.2` display messages for one node
  - [x] `R011.3` display messages for one sensor type

### Statistics

- [ ] `R014` display # of messages per node
  - [ ] `R014.1` display total # of messages per node
  - [ ] `R014.2` display # of messages per node, per day
  - [ ] `R014.3` display min,max,average interval between messages, per node

- [ ] `R015` display # of messages per sensor
  - [ ] `R015.1` display total # of messages per sensor
  - [ ] `R015.2` display # of messages per sensor, per day
  - [ ] `R015.3` display min,max,average interval between messages, per sensor

- [ ] `R021` display # of messages per V_xxx type per sensor instance
  - [ ] `R021.1` display total # of messages per V_xxx type per sensor instance
  - [ ] `R021.2` display # of messages per day, per V_xxx type per sensor instance
  - [ ] `R021.3` display min,max,average interval between messages, per V_xxx type per sensor instance

## Admin

- [x] `R022` allow to delete a node, and all sensors, values and messages that refer to it

- [ ] `R023` allow to delete all messages and values older than a specified date

