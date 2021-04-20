__MyTracker__: MySensors dashboard
==============================
Requirements marked __OK__ are implemneted and tested. The rest is ideas for future versions.

# Use Cases

`UC001` Overview of nodes: software version, sensors etc

`UC002` Overview of status of nodes: what is the battery level? has any node not sent messages for a while?

`UC002` Quantitative analyses, e.g. battery level over time, frequency of reports, etc., maybe using external service like Grafana

`UC003` Browse messages, detect any odd behavior of nodes

# Requirements

## MQTT

`R001` __OK__ capture all MQTT messages from MySensors nodes, store in database

`R002` __OK__ if same message is received multiple times, from different gateways, then ignore all but one

`R012` __OK__ capture time & date when message was received

`R013` capture which gateway received the message

### Nodes

`R003` __OK__ capture information about nodes, from MQTT messages
* `R003.1` __OK__ capture MySensors API version of node
* `R003.2` __OK__ capture sketch name (sent by node via MySensors `sendSketchInfo()` function)
* `R003.3` __OK__ capture sketch version string (sent by node via MySensors `sendSketchInfo()` function)
* `R003.4` __OK__ capture sketch SVN revision, if available
* `R003.5` __OK__ capture sensor description (sent by node via MySensors `present()` function)
* `R003.6` __OK__ capture all values reported by sensors
* `R003.7` __OK__ capture battery level reported by nodes

### Sensors
`R004` __OK__ capture information about sensors, from MQTT
* `R004.1` __OK__ capture sensor description
* `R004.2` __OK__ capture sensor type, e.g. S_DOOR
* `R004.§` __OK__ capture which V_xxx value types a sensor has reported

## UI, Input

`R005` __OK__ let user enter information about nodes
* `R005.1` __OK__ let user indicate "battery changed today"
* `R005.2` __OK__ let user enter date of last battery change
* `R005.3` __OK__ let user enter location of node

## UI, Output

### Nodes

`R006` display on a web page information about all nodes
* `R006.1` __OK__ display MySensors node ID
* `R006.2` __OK__ display MySensors API version of firmware
* `R006.3` __OK__ display sketch name
* `R006.4` display sketch version string
* `R006.5` __OK__ display sketch SVN revision, if available
* `R006.7` __OK__ display timestamp of most recent message
* `R006.6` __OK__ display date of last battery change
* `R006.8` __OK__ display months alive since last battery change, if available
* `R006.9` __OK__ display battery level
* `R006.11` __OK__ display location of node

### Sensors

`R007` __OK__ display on a web page information about all sensors
* `R007.2` __OK__ display MySensors child ID
* `R007.3` __OK__ display MySensors node ID
* `R007.4` __OK__ display sensor type, such as S_DOOR
* `R007.5` __OK__ display list of value types reported by sensor, such as V_TRIPPED
* `R007.6` __OK__ display timestamp of most recent message

`R020` filter content
* `R020.1` __OK__ display all sensors
* `R020.2` __OK__ display all sensors for one node

`R019` navigate from this screen to other screens, with filtering
* `R019.1` __OK__ offer to show all values for one node
* `R019.2` __OK__ offer to show all messages for one node
* `R019.3` __OK__ offer to show all values for one sensor instance
* `R019.4` offer to show all values for one sensor type

### Types and current values

`R018` __OK__ display on a web page information about all sensor types seen
* `R018.1` __OK__ display either information for all sensors, or all sensors for one node
* `R018.2` __OK__ display MySensors child ID
* `R018.3` __OK__ display MySensors parent node ID
* `R018.4` __OK__ display sensor type, such as S_DOOR
* `R018.5` __OK__ display value type reported by sensor, such as V_TRIPPED
* `R018.6` __OK__ display most recent value
* `R018.8` __OK__ display timestamp of most recent message

`R017` allow user to select which types/values to display
* `R017.1` __OK__ display all types/values for all sensors
* `R017.2` __OK__ display types/values for one node
* `R017.3` __OK__ display types/values for one sensor type
* `R017.4` __OK__ display types/values for one sensor instance

### Value messages

`R008` display information about values reported by sensors
* `R008.1` __OK__ display MySensors child ID
* `R008.2` __OK__ display MySensors parent node ID
* `R007.3` __OK__ display value type, such as V_STATUS
* `R007.4` __OK__ display value text, as originally received
* `R007.5` display value as number, if possible
* `R007.6` __OK__ display timestamp when value was received

`R009` __OK__ allow user to select which values to display
* `R009.1` __OK__ display all values for all sensors
* `R009.2` __OK__ display values for one node
* `R009.3` __OK__ display values for one sensor type
* `R009.4` __OK__ display values for one sensor instance

### Messages

`R010` __OK__ display information about messages sent by nodes
* `R010.1` __OK__ display MySensors node ID
* `R010.2` __OK__ display MySensors child ID
* `R010.3` __OK__ display MySensors command
* `R010.4` __OK__ display MySensors command symbol like I_PRESENTATION
* `R010.5` __OK__ display MySensors type
* `R010.6` __OK__ display MySensors type symbol, such as V_STATUS
* `R010.7` __OK__ display payload text, as originally received
* `R010.8` __OK__ display timestamp when value was received

`R011` __OK__ allow user to select which messages to display
* `R011.1` __OK__ display all messages
* `R011.2` __OK__ display messages for one node
* `R011.3` __OK__ display messages for one sensor type

### Statistics

`R014` display # of messages per node
* `R014.1` display total # of messages per node
* `R014.2` display # of messages per node, per day
* `R014.3` display min,max,average interval between messages, per node

`R015` display # of messages per sensor
* `R015.1` display total # of messages per sensor
* `R015.2` display # of messages per sensor, per day
* `R015.3` display min,max,average interval between messages, per sensor

`R021` display # of messages per V_xxx type per sensor instance
* `R021.1` display total # of messages per V_xxx type per sensor instance
* `R021.2` display # of messages per day, per V_xxx type per sensor instance
* `R021.3` display min,max,average interval between messages, per V_xxx type per sensor instance

## Admin

`R022` __OK__ allow to delete a node, and all sensors, values and messages that refer to it

`R023` allow to delete all messages and values older than a specified date

