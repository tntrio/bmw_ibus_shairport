#!/usr/bin/python

"""
ultraDerShit
"""

import logging
from time import sleep
from shairportmetadatareader.util import IS_PY2
from shairportmetadatareader import AirplayListener, AirplayCommand, DEFAULT_SOCKET
import ibus as ibus_
import threading
try:
    from gi.repository import GObject
except ImportError:
    import gobject as GObject

ibus = None	
remote = None
	
# show all warnings
logging.basicConfig(level=logging.DEBUG)

# python2 support
if IS_PY2:
    input = raw_input

# list of all possible commands
allowed_cmds = [cmd.value for cmd in AirplayCommand]

DATA = {
    "shairport": {
        "adapter": None,
        "connected": False,
    },
    "player": {
        "state": None,
        "artist": None,
        "title": None
    },
    "obc": {
        "vin": None,
        "ignition": None,
        "speed": None,
        "rpm": None,
        "limit": None,
        "outside": None,
        "coolant": None,
        "mileage": None,
		"distance": None,
        "fuel_1": None,
        "fuel_2": None,
        "range": None,
        "avg_speed": None
    },
    "pdc": {
        "active": False,
        "sensor_1": None,
        "sensor_2": None,
        "sensor_3": None,
        "sensor_4": None
    },
    "radio": {
        "active": False,
        "to_resume": False
    },
    "lights": {
        "parking": None,
        "lowbeam": None,
        "highbeam": None,
        "fog_front": None,
        "fog_rear": None,
        "turn_left": None,
        "turn_right": None,
        "turn-fast": None
    },
    "dimmer": None,
    "io_status": None
}


def hex2int(v, nbits=7):
    v = int(v, 16)
    return v if v < (1 << nbits) else v - (1 << nbits + 1)

def check_bitmask(xand, bit):
    return xand & bit and True or False;

def set_bitmask(xor, bit):
    xor |= bit
    return xor

def onIBUSready():
    ibus.cmd.clown_nose_on()
    
    ibus.cmd.reset_fuel_2()

    ibus.cmd.request_for_ignition()
    ibus.cmd.request_for_mileage()
    ibus.cmd.request_for_fuel_1()
    ibus.cmd.request_for_range()
    ibus.cmd.request_for_distance()
    ibus.cmd.request_for_avg_speed()
    ibus.cmd.request_for_limit()
    ibus.cmd.request_for_sensors()
    ibus.cmd.request_for_radio_status()
    ibus.cmd.request_for_vin()	

def onIBUSpacket(packet):
    global DATA

    """
    MFL Multi Functional Steering Wheel Buttons:
    50 04 68 32 10 1E - Volume Down button pressed
    50 04 68 32 11 1F - Volume Up button pressed
    50 04 68 3B 08 0F - Previous button pressed once
    50 04 68 3B 18 1F - Previous button (long press)
    50 04 68 3B 28 2f - Previous button released 
    50 04 68 3B 01 06 - Next button pressed once
    50 04 68 3B 11 16 - Next button (long press)
    50 04 68 3B 21 26 - Next button released
    50 04 C8 3B 80 27 - DIAL button
    50 04 C8 3B 90 37 - DIAL button (long press)
    50 04 C8 3B a0 07 - DIAL button released
    50 03 C8 01 9A    - R/T button
    """
	
	"""
	Shairport Remote Controls
	1.      beginff
	2.      beginrew
	3.      nextitem
	4.      pause
	5.      play
	6.      playpause
	7.      playresume
	8.      previtem
	9.      shuffle_songs
	10.     stop
	11.     volumedown
	12.     volumeup
	"""
	
    if packet.raw == "5004683b080f":
        print("### Pressed: Previous button")
        if DATA["shairport"]["connected"]:
            print("      -> Previous song")
            cmd2airplay(8)
            return

    if packet.raw == "5004683b181f":
        print("### Pressed (long): Previous button")
        if DATA["shairport"]["connected"]:
            print("      -> Rewind")
            cmd2airplay(2)
            return

    if packet.raw == "5004683b0106":
        print("### Pressed: Next button")
        if DATA["shairport"]["connected"]:
            print("      -> Next song")
            cmd2airplay(3)
            return
            
    if packet.raw == "5004683b1116":
        print("### Pressed (long): Next button")
        if DATA["shairport"]["connected"]:
            print("      -> Fast Forward")
            cmd2airplay(1)
            return

    if packet.raw == "5004c83b8027":
        print("### Pressed: DIAL button")
        if DATA["shairport"]["connected"]:
            if DATA["player"]["state"] == "play":
                print("      -> Pause song")
                cmd2airplay(4)
            else:
                print("      -> Play song")
                cmd2airplay(5)
            return
    """            
    if packet.raw == "5004c83b9037":
        print("### Pressed (long): DIAL button")
        if not DATA["shairport"]["connected"]:
            print("      -> BT Connecting")
            packet = ibus.cmd.get_display_packet("CONNECTING", "connect")
            ibus.send(packet.raw)
            if not bluetooth.reconnect():
                print("      -> BT Error")
                packet = ibus.cmd.get_display_packet("ERROR", "connect")
                ibus.send(packet.raw)
        else:
            print("      -> BT Disconnecting")
            packet = ibus.cmd.get_display_packet("DISABLING", "connect")
            ibus.send(packet.raw)
            bluetooth.disconnect(DATA["shairport"]["adapter"])
        return
	"""
    if packet.raw == "5003c8019a":
        print("### Pressed: R/T button")

        ibus.cmd.clown_nose_on()
        ibus.cmd.set_clock()        
        return

    # split hex string into list of values
    data = []
    data = [packet.data[i:i+2] for i in range(0, len(packet.data), 2)]
    
    # looking for vehicle VIN
    if packet.source_id == "d0" and packet.destination_id == "80":
        try:
            DATA["obc"]["vin"] = data[1].decode("hex") + data[2].decode("hex") + data[3] + data[4] + data[5]
            print("VIN: %s" % DATA["obc"]["vin"])
        except:
            DATA["obc"]["vin"] = None
            print("VIN: unknown")

    """
    OBC (On Board Computer)
    Messages from the IKE to the GlobalBroadcast
    0x11 - Ignition state
    0x13 - Reversing, Handbrake, Oil presure state
    0x15 - OBC units
    0x17 - Mileage
    0x18 - Speed/RPM
    0x19 - Temp

    Base on: https://github.com/t3ddftw/DroidIBus/blob/master/app/src/main/java/com/ibus/droidibus/ibus/systems/GlobalBroadcastSystem.java
    """
    if packet.source_id == "80" and packet.destination_id == "bf":
        # Ignition status
        if data[0] == "11":
            if int(data[1], 16) == 0:
                if DATA["obc"]["ignition"] > int(data[1], 16) and DATA["shairport"]["connected"]:
                    # bluetooth.disconnect(DATA["bluetooth"]["adapter"])
					print("Ignition state: %d" % DATA["obc"]["ignition"])

            # set new ignition state
            DATA["obc"]["ignition"] = int(data[1], 16)
            print("new Ignition state: %d" % DATA["obc"]["ignition"])
            return
        """
        R_Gear detection
        80 0A BF 13 02 10 00 00 00 00 38 CK // in reverse
        80 0A BF 13 02 00 00 00 00 00 38 CK  // out of reverse
        """
        if data[0] == "13":
            if (int(data[2], 16) >> 4) == 1:
                # decrease volume while reversing
                if not DATA["pdc"]["active"]:
                    ibus.cmd.request_for_pdc()
                    ibus.cmd.volume_down()
                    if DATA["shairport"]["connected"]:
                        if DATA["player"]["state"] == "play":
                            cmd2airplay(4)
                            DATA["radio"]["to_resume"] = True
                        else:
                            DATA["radio"]["to_resume"] = False
                DATA["pdc"]["active"] = True
                print("PDC: active")
            else:
                # increase volume after reversing
                if DATA["pdc"]["active"]:
                    ibus.cmd.reset_display()       
                    if DATA["shairport"]["connected"] and DATA["radio"]["to_resume"]:
                        cmd2airplay(5)
                        DATA["radio"]["to_resume"] = False
                    ibus.cmd.volume_up()
                DATA["pdc"]["active"] = False
                print("PDC: inactive")
        # Mileage
        elif data[0] == "17":
            DATA["obc"]["mileage"] = (int(data[3], 16)*65536) + (int(data[2], 16)*256) + int(data[1], 16)
            print("Mileage: %d (km)" % DATA["obc"]["mileage"])
        # Speed/RPM
        elif data[0] == "18":
            DATA["obc"]["speed"] = int(data[1], 16) * 2
            DATA["obc"]["rpm"] = int(data[2], 16) * 100
            print("Speed: %d km/h, RPM: %d" % (DATA["obc"]["speed"], DATA["obc"]["rpm"]))
        # Temperatures
        elif data[0] == "19":
            DATA["obc"]["outside"] = hex2int(data[1])
            DATA["obc"]["coolant"] = hex2int(data[2])
            print("Outside: %d (C), Coolant: %d (C)" % (DATA["obc"]["outside"], DATA["obc"]["coolant"]))
        return

    # Lights status
    if packet.source_id == "d0" and packet.destination_id == "bf":
        if data[0] == "5b":
            hex_value = int(data[1], 16)
            DATA["lights"]["parking"] = check_bitmask(hex_value, 0x01)
            DATA["lights"]["lowbeam"] = check_bitmask(hex_value, 0x02)
            DATA["lights"]["highbeam"] = check_bitmask(hex_value, 0x04)
            DATA["lights"]["fog_front"] = check_bitmask(hex_value, 0x08)
            DATA["lights"]["fog_rear"] = check_bitmask(hex_value, 0x10)
            DATA["lights"]["turn_left"] = check_bitmask(hex_value, 0x20)
            DATA["lights"]["turn_right"] = check_bitmask(hex_value, 0x40)
            DATA["lights"]["turn-fast"] = check_bitmask(hex_value, 0x80)
            return
        
        if data[0] == "5c":
            DATA["dimmer"] = int(data[1], 16)
            return
 #    if packet.source_id == "d0" and packet.destination_id == "3f":
    if packet.source_id == "d0":
        if data[0] == "a0":
            DATA["io_status"] = packet.raw
            return  
    
    """
    * Handle OBC messages sent from IKE
    * IBus Message: 80 0C FF 24 <System> 00 <Data> <CRC>
    
    Base on: https://github.com/t3ddftw/DroidIBus/blob/master/app/src/main/java/com/ibus/droidibus/ibus/systems/BroadcastSystem.java
    https://github.com/t3ddftw/DroidIBus/blob/master/app/src/main/java/com/ibus/droidibus/ibus/systems/GFXNavigationSystem.java
    """    
    if packet.source_id == "80" and packet.destination_id == "ff":
        # Fuel 1
        if data[1] == "04":
            try:
                DATA["obc"]["fuel_1"] = float(packet.data[4:14].lstrip("00").decode("hex"))
                print("Fuel 1: %f" % DATA["obc"]["fuel_1"])
            except:
                DATA["obc"]["fuel_1"] = None
        # Fuel 2    
        elif data[1] == "05":
            try:
                DATA["obc"]["fuel_2"] = float(packet.data[4:14].lstrip("00").decode("hex"))
                print("Fuel 2: %f" % DATA["obc"]["fuel_2"])
            except:
                DATA["obc"]["fuel_2"] = None
        # Range
        elif data[1] == "06":
            try:
                DATA["obc"]["range"] = int(packet.data[4:14].lstrip("00").decode("hex"))
                print("Range: %i" % DATA["obc"]["range"])
            except:
                DATA["obc"]["range"] = None
        # Distance
        elif data[1] == "07":
            print("Distance: %s" % packet.raw)
        # Speed limit
        elif data[1] == "09":
            try:
                DATA["obc"]["limit"] = int(packet.data[4:14].lstrip("00").decode("hex"))
                print("Limit: %i" % DATA["obc"]["limit"])
            except:
                DATA["obc"]["Speed limit"] = None
        # AVG speed
        elif data[1] == "0a":
            try:
                DATA["obc"]["avg_speed"] = float(packet.data[4:14].lstrip("00").decode("hex"))
                print("AVG speed: %f" % DATA["obc"]["avg_speed"])
            except:
                DATA["obc"]["avg_speed"] = None
        return
    
    """
    RAD Radio
    """
    if packet.source_id == "68" and packet.destination_id == "3f":
        if packet.length == "0d": 
            DATA["radio"]["active"] = True if data[1] == "31" else False
            print("Radio active: %s" % str(DATA["radio"]["active"]))
            return
 
    """
    PDC Park Distance Control
    """
    # Gong status - use it for sending DIAG request for distance
    if packet.source_id == "60" and packet.destination_id == "80" and DATA["pdc"]["active"]:
        ibus.cmd.request_for_pdc()
        return

    # DIAG responce from PDC cointaing information about distance for each sensor
    if packet.source_id == "60" and packet.destination_id == "3f":
        if DATA["pdc"]["active"]:
            DATA["pdc"]["sensor_1"] = int(data[2], 16)
            DATA["pdc"]["sensor_2"] = int(data[4], 16)
            DATA["pdc"]["sensor_3"] = int(data[5], 16)
            DATA["pdc"]["sensor_4"] = int(data[3], 16)

            print("Sensor #1: %d" % DATA["pdc"]["sensor_1"])
            print("Sensor #2: %d" % DATA["pdc"]["sensor_2"])
            print("Sensor #3: %d" % DATA["pdc"]["sensor_3"])
            print("Sensor #4: %d" % DATA["pdc"]["sensor_4"])
            print("")

            pdc_display_packet = ibus.cmd.get_pdc_display_packet([DATA["pdc"]["sensor_1"],
                                                                  DATA["pdc"]["sensor_2"],
                                                                  DATA["pdc"]["sensor_3"],
                                                                  DATA["pdc"]["sensor_4"]])
            ibus.send(pdc_display_packet.raw)
            return

def on_track_info(listener, info):
    print(info["itemname"])	  #Lied
    print(info["songalbum"])  #Album
    print(info["songartist"]) #Interpret
	
	global DATA

    """
    Wait until all data is set
    to avoid sending crap to CDP display
    """
    if ibus.handle is None or \
        listener.playback_state is None or \
        info["songartist"] is None or \
        info["itemname"] is None:
        return
    
    print("[%s] %s - %s" % (listener.playback_state, info["songartist"], info["itemname"]))

    """
    Send first packet with proper icon in the beginning if only state changed
    """    
    if DATA["player"]["artist"] == info["songartist"] and \
        DATA["player"]["title"] == info["itemname"] and \
        not DATA["player"]["state"] == listener.playback_state:

        packet = ibus.cmd.get_display_packet(info["songartist"], listener.playback_state)
        ibus.send(packet.raw)

    """
    Finish ongoing display thread
    """
    try:
        while ibus.display_thread.isAlive():
            ibus.cmd.print_stop()
        ibus.cmd.print_clear()
    except:
        pass

    """
    Do animation in separated thread ...
    """
    if listener.playback_state == "play":
        ibus.display_thread = threading.Thread(target=ibus.cmd.print_on_display, \
                                   kwargs={"data": [info["songartist"], info["itemname"]]})
        ibus.display_thread.daemon = True
        ibus.display_thread.start()

    DATA["player"]["state"] = listener.playback_state
    DATA["player"]["artist"] = info["songartist"]
    DATA["player"]["title"] = info["itemname"]

def cmd2airplay(cmd):
	global remote
	
	# send command
    try:
        cmd = int(cmd)
        if not (1 <= cmd <= len(allowed_cmds)):
            print("Illegal command: {0}".format(cmd))
        else:
            # you should catch exceptions thrown by this function, in case the remote connection is lost
            remote.send_command(allowed_cmds[cmd-1])
    except Exception as e:
        print("Illegal command: {0}".format(cmd))
	
def onShairportConnected(listener):
    global ibus

    try:
        while ibus.display_thread.isAlive():
            ibus.cmd.print_stop()
        ibus.cmd.print_clear()
    except:
        pass

    if listener.connected: # connected
        packet = ibus.cmd.get_display_packet("SHAIRPORT READY", "connect")
        ibus.send(packet.raw)

        time.sleep(1.5)

        # switch to AUX
        ibus.cmd.request_for_radio_mode_switch()
        ibus.cmd.request_for_radio_mode_switch()
    else: # disconnected | stop RADIO display thread
        packet = ibus.cmd.get_display_packet("SHAIRPORT OFF", "connect")

        ibus.send(packet.raw)
        time.sleep(1.5)

        # switch back to FM
        ibus.cmd.request_for_radio_mode_switch()
	
def main():	
    global ibus

	# listen for track information changes using shairport-syncs udp port
	listener = AirplayListener()
	listener.bind(track_info=on_track_info)
	listener.start_listening(socket_addr=DEFAULT_SOCKET)

	
	# wait till all data to create an airplay remote is available
	while not listener.has_remote_data:
		print("Waiting for airplay remote")
		sleep(1)

	# get an airplay remote instance ... this might take some time
	print("Waiting for active connection...")
	remote = listener.get_remote()
	print("Connected")
	DATA["shairport"]["connected"] = True
	
	
    ibus = ibus_.IBUSService(onIBUSready, onIBUSpacket)
    ibus.cmd = ibus_.IBUSCommands(ibus)
    
    ibus.main_thread = threading.Thread(target=ibus.start)
    ibus.main_thread.daemon = True
    ibus.main_thread.start()

    try:
        mainloop = GObject.MainLoop()
        mainloop.run()
    except KeyboardInterrupt:
        pass
    except:
        print("Unable to run the gobject main loop")
    
    print("")
    shutdown()
    sys.exit(0)	
	
	
	
	
	
def shutdown():
    global ibus
    
    try:
        print("Stopping RADIO display thread...")
        while ibus.display_thread.isAlive():
            ibus.cmd.print_stop()
        ibus.cmd.print_clear()
    except:
        pass

    if ibus.main_thread.isAlive():
        print("Stopping IBUS main thread...")
        ibus.stop()

    print("Destroying IBUS service...")
    ibus.shutdown()
	
	
if __name__ == '__main__':
    main()