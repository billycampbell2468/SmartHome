from sys import exc_info
while True:
    if True:
    #try:
        import io
        from fcntl import ioctl
        from array import array
        from RPi import GPIO
        from time import sleep, time
        from os import stat, path, remove, system
        from math import ceil, asin, floor
        from datetime import datetime
        import socket
        from CONFIG import config
        from struct import pack
        from random import uniform
        import sys
        sys.path.append("/home/pi/.local/lib/python2.7/site-packages/nmap/")
        import nmap
        import select

        calculate_optimal_sleep_time = False
        
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BOARD)

        base16bit_adr = 0x20
        base8bit_adr  = 0x21
        baseLED_adr   = 0x60
        PWM_0   = 0xF0  # 6.25% brightness
        PWM_1   = 0x90  # 43% for fan

        i2c_mux_adr  = 0x70
        i2c_mux_adr2 = 0x71
        
        dimmer_adr    = 0x10
        hum_temp_adr  = 0x40
        air_qual_adr  = 0x5A
        io_adr        = 0x41
        
        extra_8bit_adr = 0x27
        
        cfg = config(r'/var/lib/homebridge/config.ini','ALL')
        
        num_boards      = cfg.num_boards #3 # max = 3 (need to expand arrays init below if increasing to 4)
        is_master       = cfg.is_master
        board_3         = cfg.board_3
        num_board_3     = len(board_3)
        two_i2c_boards  = cfg.two_i2c_boards

        wd_powercycle = cfg.wd_powercycle
        powercycle_req = False
        powercycle_timer = 3

        post_box = cfg.post_box
        
        if is_master:
            access_points   = cfg.access_points
        
        blinds = cfg.blinds
        blind_wait_time = 0.1
        num_blinds = blinds[1]

        blinds_to_close = cfg.blinds_to_close
        if len(blinds_to_close) > 3:
            btc = True
            blinds_closed_mid = False
            blinds_closed_full = False
        else:
            btc = False

        outside_temp = 0
        outdoor_temp_thresh = 24

        shower_blinds = cfg.shower_blinds
        shower_blinds_EN = True
        extractor = cfg.extractor
        n_last_extractor_status = False
        n_last_extractor_light_status = False
        extractor_timer = 0
        extractor_long = False
        extractor_en = True
            
        FAN = cfg.fan
        fan_temps = cfg.fan_temps
        fan_hyst = cfg.fan_hyst
        
        fan_speed = 2 # startup value
        
        garage_control = cfg.garage_control
        if garage_control:
            garage_io = cfg.garage_io
            garage_open_last = False
            garage_closed_last = True
            garage_ts = stat(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_GarageDoorOpener_TargetDoorState').st_mtime
            clear_garage_pulse = False
            
        first_time = True
        garage_keepout = False
        
        zone_indicators = cfg.zone_indicators
        bedroom_indicators = cfg.bedroom_indicators
        
        LOOP_TIME       = cfg.loop_time #0.04 # +0.01 from i2c mux reset
        RELAY_ON_TIME   = 2 # relays will be energised for RELAY_ON_TIME x LOOP_TIME
        MAX_RELAYS_ON   = 10
        STATUS_SETTLE_TIME = 25 # amount of loops it takes for power status to stabalise after a change
            
        GPIO_REGISTER_16    = 0x12
        GPIO_REGISTER_8     = 0x09
        LED_REGISTER        = 0x15

        GLOBAL_16bit    = [0x0000]*num_boards
        GLOBAL_8bit     = [0x00]*num_boards
        GLOBAL_LED      = [0x0000]*num_boards
        GLOBAL_LED_DISP = [0x0000]*num_boards   # displayed value, taking IND power status into account

        interrupt_pins = [16,15,13,11]

        STATUS = [[False, False, False, False, False, False, False, False],
                  [False, False, False, False, False, False, False, False],
                  [False, False, False, False, False, False, False, False],
                  [False, False, False, False, False, False, False, False],
                  [False, False, False, False, False, False, False, False]]
                  
        ACTIVATED_AS_NIGHTLIGHT = [[False, False, False, False, False, False, False, False],
                                   [False, False, False, False, False, False, False, False],
                                   [False, False, False, False, False, False, False, False],
                                   [False, False, False, False, False, False, False, False],
                                   [False, False, False, False, False, False, False, False]]
                  
        LAST_STATUS  = [[False, False, False, False, False, False, False, False],
                        [False, False, False, False, False, False, False, False],
                        [False, False, False, False, False, False, False, False],
                        [False, False, False, False, False, False, False, False]]
                        
        RELAY_STATE = [[False, False, False, False, False, False, False, False],
                       [False, False, False, False, False, False, False, False],
                       [False, False, False, False, False, False, False, False],
                       [False, False, False, False, False, False, False, False]]

        RELAY_QUEUE = [[[False,False],[False,False],[False,False],[False,False],[False,False],[False,False],[False,False],[False,False]],
                       [[False,False],[False,False],[False,False],[False,False],[False,False],[False,False],[False,False],[False,False]],
                       [[False,False],[False,False],[False,False],[False,False],[False,False],[False,False],[False,False],[False,False]],
                       [[False,False],[False,False],[False,False],[False,False],[False,False],[False,False],[False,False],[False,False]]]
                       
        led_flashing = [[False, False, False, False, False, False, False, False],
                        [False, False, False, False, False, False, False, False],
                        [False, False, False, False, False, False, False, False],
                        [False, False, False, False, False, False, False, False]]   # for making light switch flash

        NUM_RELAYS_ON = [0]
        QUEUED_RELAYS = 0

        RELAY_CLR_TIMER     = [[0,0,0,0,0,0,0,0],[0,0,0,0,0,0,0,0],[0,0,0,0,0,0,0,0],[0,0,0,0,0,0,0,0]]
        STATUS_SETTLE_TIMER = [[0,0,0,0,0,0,0,0],[0,0,0,0,0,0,0,0],[0,0,0,0,0,0,0,0],[0,0,0,0,0,0,0,0]]
                       
        SET_MAPPING     = [[0,6], [0,11], [0,10], [0,13], [0,3], [0,0], [1,5], [1,0]]   # not 1-1 to simplify layout
        RST_MAPPING     = [[0,5], [0,12], [0,9], [0,14], [0,2], [1,7], [1,4], [1,1]]    # not 1-1 to simplify layout
        LED_MAPPING     = [3,2,1,0,6,5,4,7] # not 1-1 to simplify layout
        LED_SETTING     = [0b01, 0b00, 0b10, 0b11]
        
        TRANSFER_STATUS = cfg.transfer_status

        INDICATOR_TYPE = cfg.indicator_type #[[0,0,0,0,0,0,0,0],[0,0,0,0,0,0,0,0],[0,0,0,0,0,0,0,0]]    # 0 = normal, 1 = socket indicator
        IND_SETTING = [[[1,2],[0,3]],[[3,2],[0,3]]] # first set for normal operation, second set for bed. 0 = off, 1 = on, 2= 6.25% brightness, 3 = 43% brightness
        IND_MAP = cfg.indicator_mapping

        DIMMER_EN = cfg.dimmer_en
        DIMMER_SWITCH = cfg.dimmer_switch #[[0,1],[0,2],[0,5],[0,6]]# commented out any dimmers that aren't on board 0 temporarily ,[1,0],[1,2],[2,4]]  # board/chan number of switch that dimmer is paired with
        dimmer_mux = cfg.dimmer_mux
        num_dimmers = len(DIMMER_SWITCH)
        DIM_PROFILE = cfg.dim_profile #[1, 0, 0 ,0 ,0 ,0 ,0]            # 0 = incandescent, 1 = IKEA LED edison bulb, 2 = IKEA/Osram Recessed LED
        UP_DOWN_SPEED = cfg.up_down_speed #[[2,2],[5,2.5],[5,2.5],[5,2.5],[5,2.5],[5,2.5],[5,2.5]]  # in % per loop

        powersocket = cfg.socket
        num_sockets = len(powersocket)

        DIMMER_SET_BRIGHTNESS = [0.0] * num_dimmers
        DIMMER_CURRENT_BRIGHTNESS = [0.0] * num_dimmers
        LAST_DIMMER_WRITE = [0] * num_dimmers
        wait_power_up = [0] * num_dimmers   

        IND =    [[False, False, False, False, False, False, False, False],
                  [False, False, False, False, False, False, False, False],
                  [False, False, False, False, False, False, False, False],
                  [False, False, False, False, False, False, False, False]]
        
        currentIOmux_chan = [-1]
        
        tempmux = cfg.tempmux #[]#0]                            # i2c mux channel temp & humdity sensor is at
        numtemp = len(tempmux)
        air_qual = cfg.air_quality #[]#0]                            # i2c mux channel temp & humdity sensor is at
        num_air_qual = len(air_qual)

        IOmux = cfg.IOmux #[] #0]                               # i2c mux channel remote I/O expander is at
        num_IO = len(IOmux)
        IO = [0]*num_IO                         # value returned by read from remote I/O expanders
        
        PIRsens = cfg.PIRsens #[] #[0,3]] # max 4 due to PIR array init below - expand if required                      # remote I/O expander num, GPIO num on I/O expander
        num_PIR = len(PIRsens)
        PIR = [[False,False,False],[False,False,False],[False,False,False],[False,False,False],[False,False,False]]     # PIR active in last LOOP, 30secs, 10min
        PIRtimer = [[0,0]]*num_PIR
        PIR30s = 600    # num loop cycles for 30s
        PIR10m = 12000  # num loop cycles for 10min

        NIGHT_LIGHTS = cfg.night_lights #[] #[0,1,0,7,0]###,0,0]]   # PIR sensor num, Switch(0) or Dimmer(1), NightLight brd num, NightLight ch num, NightLight dimmer num #######, MainLight brd num, MainLight ch num
        num_night_lights = len(NIGHT_LIGHTS)
        night_light_timer = [0]*num_night_lights
        night_light_on_time = 600 # 30s
        night_light_on_time_ext = 1200 # 1min, will be extended to 4min when guest mode on
        guest = False
        #night_light_brightness = '60' # % brightness if night light is a dimmer - read from config file now so can be set differently for differnt night lights
        night_light_store_val = ['0']*num_night_lights # array to back up previous dimmer setting before used as night light
        night_light_activated = [False]*num_night_lights
        NIGHT_LIGHT_MAINS = cfg.night_light_main_lights

        I2C_SLAVE=0x0703
        fw = io.open("/dev/i2c-1", "wb", buffering=0)
        fr = io.open("/dev/i2c-1", "rb", buffering=0)

        i2c_error = [False]
        end_error_assert = False
        
        # Scene Buttons
        SceneButton = cfg.SceneButton
        num_buttons = len(SceneButton)
        lights_under_button_control = cfg.lights_under_button_control # entry 0: type (0: light on board, 1: dimmer on board, 2: led strip), can add other board too
        lights_under_button_control_off = cfg.lights_button_off
        button_scene_0 = cfg.button_scene_0
        button_scene_1 = cfg.button_scene_1
        button_scene_2 = cfg.button_scene_2
        if(not is_master):
            button_scene_0_bed = cfg.button_scene_0_bed
            button_scene_1_bed = cfg.button_scene_1_bed
            button_scene_2_bed = cfg.button_scene_2_bed
        
        ReorderSceneNight = cfg.ReorderSceneNight

        button_led_ind = cfg.button_led_ind
        button_flashing_timeout = 120

        eightAM = False
        
        # Special Button
        special_button = cfg.special_button
        num_special_buttons = len(special_button)
        num_buttons_p_num_special_buttons = num_buttons+num_special_buttons
        if num_special_buttons > 0:
            special_button_led = cfg.special_button_led
            
        # Toggle Button
        toggle_button = cfg.toggle_button
        num_toggle_buttons = len(toggle_button)
        
        # Fire Alarm/Doorbell
        if is_master:
            cfg_firealarm = cfg.firealarm
            cfg_doorbell = cfg.doorbell
            doorbell_ip_adr = cfg.doorbell_ip_adr
            
        SECURITY_LIGHTS = cfg.security_lights
        num_security_lights = len(SECURITY_LIGHTS)
        security_light_timer = [0]*num_security_lights
        #security_light_on_time = 400 # 20s
        security_light_activated = [False]*num_security_lights
        
        FIRE_LIGHTS = cfg.fire_lights
        num_fire_lights = len(FIRE_LIGHTS)
        
        # LED strip control
        led_mac = cfg.led_strips
        num_zones = cfg.num_zones
        led_strip_not_in_bedroom = cfg.led_strip_not_in_bedroom
        led_strip_dnd_suppress_allowed = cfg.led_strip_dnd_suppress_allowed
        led_strip_confirm = cfg.led_strip_confirm
        num_led_strips = len(led_mac)
        led_strips = cfg.led_ip #['-1']*num_led_strips
        led_locate_holdoff = 5  # wait 25 seconds after power up before launching any LED rediscovery (was happening at same time as blind setup)
        led_retry = [True]*num_led_strips
        led_retry_pwr = [False]*num_led_strips
        led_retry_counter = [0]*num_led_strips
        first_time_led_locate = [True]*num_led_strips
        led_solid_colour = [True]*num_led_strips
        repeat_led_colour = [False]*num_led_strips
        led_reset_ts = [False]*num_led_strips
        led_confirm = [0]*num_led_strips
        led_repeat_pwr = [0]*num_led_strips
        led_repeat_confirm = [False]*num_led_strips
        led_retry_delay = True
        max_led_retries = 360   # retry for 1 hour
        led_relocate_rate = 10  # relocate every 10 retries
        led_strip_UDP_port = 56700
        led_response = ('', led_strip_UDP_port)
        
        led_strip_timer = [0]*num_led_strips
        led_strip_timer_next = [0]*num_led_strips
        led_strip_power = [False]*num_led_strips
        led_strip_power_on = [False]*num_led_strips
        
        colours = [[[49333, 30000, 40000, 3500, 3, 0], [49333, 65535, 65535, 3500, 11, 0], [57707, 65535, 64486, 3500, 7, 0], [46057, 65535, 65535, 3500, 11, 0], [36772, 60096, 65273, 3500, 11, 0], [32403, 57081, 65535, 3500, 8, 0]],#, [49333, 65535, 0, 3500, 8]],    # neon
                   [[9338, 61996, 32748, 2500, 7, 0], [10833, 55535, 31561, 2500, 11, 0], [10833, 65535, 40561, 2500, 11, 0], [8738, 61996, 32748, 2500, 7, 0], [11833, 52297, 32768, 2500, 5, 0]], # warm
                   [[51882, 34340, 36765, 3500, 9, 6],[29673, 53003, 43919, 3500, 11, 7]], # yoga by zoe  #, [29673, 1000, 45535, 3500, 0] original green brightness: 51904
                   [[37501, 17015, 65535, 7000, 11, 6], [6371, 17671, 65535, 2500, 8, 6]], # beach #, [37501, 10, 65535, 9500, 0, 0]
                   [[29491, 65535, 29661, 3500, 11, 6], [6371, 17671, 24000, 2500, 4, 0]]] # office
                   #[[0, 16000, 65535, 9000, 11, 6], [0, 54000, 65535, 9000, 4, 0]]] # valentines

                   
        #fade_through_black = [False, False, True, False]
        extra_long_mode = [False, False, True, True, False]
        theme_identifier = [[[284, 100], [33, 73], [160, 44], [188, 58], [154, 100]]] # Hue/Saturation combination to recall theme - will have to add a unique one for each LED strip as it's too difficult to select exact values on colour wheel
        
        num_themes = len(colours)

        # Frame Header
        lifx_size         = 0x0033 # 2 bytes 0x33 is packet length for set zone
        lifx_size_bulb    = 0x0031 # 2 bytes 0x33 is packet length for set zone
        lifx_power_size   = 0x0029
        lifx_getpower_size = 0x0025

        origin            = 0b00
        tagged            = 0b0 # update - was 1
        addressable       = 0b1
        protocol          = 0x400
        frm_hdr_ctrl_word = (origin << 14)|(tagged << 13)|(addressable << 12)|protocol # 2 bytes

        source            = 0x00000002  # update - was 0        # 4 bytes

        # Frame Address
        target            = 0x0000000000000000 # 8 bytes: 0 = all devices
        reserved_48_1     = 0x00000000 #
        reserved_48_2     = 0x0000     # 6 bytes

        reserved_6        = 0b000000
        ack_required      = 0b0
        res_required      = 0b0
        res_required_onoff = 0b1
        frm_adr_ctrl_word = (reserved_6 << 2)|(ack_required << 1)|res_required # 1 byte
        frm_adr_ctrl_word_onoff = (reserved_6 << 2)|(ack_required << 1)|res_required_onoff # 1 byte

        sequence          = 0x00

        # Protocol Header
        reserved_64       = 0x0000000000000000
        typeSetColour     = 0x0066 # 0x66 = SetColour
        typeSetZone       = 0x01F5 # 0x1F5 = SetColourZones
        typeSetPower      = 0x0075 # SetLightPower
        typeGetPower      = 0x0074 # GetLightPower
        reserved_16       = 0x0000

        # Set Colour Zones Payload
        lifx_apply             = 0x01

        lifx_header =    pack('<HHIQIHBBQHH',         lifx_size, frm_hdr_ctrl_word, source, target, reserved_48_1, reserved_48_2, frm_adr_ctrl_word, sequence, reserved_64, typeSetZone,  reserved_16)
        lifx_header_bulb =    pack('<HHIQIHBBQHH',         lifx_size_bulb, frm_hdr_ctrl_word, source, target, reserved_48_1, reserved_48_2, frm_adr_ctrl_word, sequence, reserved_64, typeSetColour,  reserved_16)
        lifx_header_res =    pack('<HHIQIHBBQHH',         lifx_size, frm_hdr_ctrl_word, source, target, reserved_48_1, reserved_48_2, frm_adr_ctrl_word_onoff, sequence, reserved_64, typeSetZone,  reserved_16)
        lifx_header_bulb_res =    pack('<HHIQIHBBQHH',         lifx_size_bulb, frm_hdr_ctrl_word, source, target, reserved_48_1, reserved_48_2, frm_adr_ctrl_word_onoff, sequence, reserved_64, typeSetColour,  reserved_16)
        lifx_power_on =  pack('<HHIQIHBBQHHHI', lifx_power_size, frm_hdr_ctrl_word, source, target, reserved_48_1, reserved_48_2, frm_adr_ctrl_word_onoff, sequence, reserved_64, typeSetPower, reserved_16, 65535, 0)
        lifx_power_on_slow =  pack('<HHIQIHBBQHHHI', lifx_power_size, frm_hdr_ctrl_word, source, target, reserved_48_1, reserved_48_2, frm_adr_ctrl_word_onoff, sequence, reserved_64, typeSetPower, reserved_16, 65535, 2000)
        lifx_power_off = pack('<HHIQIHBBQHHHI', lifx_power_size, frm_hdr_ctrl_word, source, target, reserved_48_1, reserved_48_2, frm_adr_ctrl_word_onoff, sequence, reserved_64, typeSetPower, reserved_16, 0, 2000)
        lifx_get_light_power = pack('<HHIQIHBBQHH', lifx_getpower_size, frm_hdr_ctrl_word, source, target, reserved_48_1, reserved_48_2, frm_adr_ctrl_word_onoff, sequence, reserved_64, typeGetPower, reserved_16)

        def log_i2c_error(adr, name, data):
            addresses = {   0x20: "Board 0 16 bit IO expander",
                            0x22: "Board 1 16 bit IO expander",
                            0x24: "Board 2 16 bit IO expander",
                            0x21: "Board 0 8 bit IO expander",
                            0x23: "Board 1 8 bit IO expander",
                            0x25: "Board 2 8 bit IO expander",
                            0x60: "Board 0 LED controller",
                            0x62: "Board 0 LED controller",
                            0x64: "Board 0 LED controller",
                            0x70: "i2c mux 0",
                            0x71: "i2c mux 1",
                            0x41: "4 bit IO expander",
                            0x27: "Remote 8 bit IO expander",
                            0x10: "Dimmer",
                            0x40: "Humidity/Temp",
                            0x5A: "Air quality" 
                        }

            if is_master:
                io_mux_channels = { 8 : "Kitchen Outer",
                                    9 : "Kitchen Counter",
                                    10: "Kitchen Wall",
                                    11: "Sitting Lamp 1",
                                    12: "Sitting Side",
                                    13: "Sitting Lamp 2",
                                    14: "Dining Lamp",
                                    15: "Hall Lamp",
                                    0: "Outdoor Front",
                                    1: "DS Bathroom",
                                    2: "Stairs NL",
                                    3: "Garage",
                                    4: "Dining Salt Lamp"
                                }
            else:   
                io_mux_channels = { 0: "Bedroom Lamp 1",
                                    1: "Bedroom Lamp 2",
                                    2: "Bedroom 2 Lamp (Unused?!)",
                                    3: "Office Lamp",
                                    4: "Upstairs Bathroom"
                                }

            try:
                device_name = addresses[adr]
            except:
                device_name = "Unknown i2c Device"

            try:
                channel_name = io_mux_channels[currentIOmux_chan[0]]
            except:
                channel_name = "Unknown Channel"

            now = datetime.now()
            errorlog = open(r'/var/lib/homebridge/crash.log','a')
            errorlog.write(now.strftime('%d/%m/%Y %H:%M:%S - Error communicating with '))
            errorlog.write(device_name+' (address ')
            errorlog.write(hex(adr))
            errorlog.write(') from function '+name)
            if currentIOmux_chan[0] == -1:
                errorlog.write(' (i2c mux disabled)')
            else:
                errorlog.write(' when i2c mux was set to '+channel_name+' (channel '+str(currentIOmux_chan[0]))
            try:    
                errorlog.write('). Data:'+hex(data)+'\n')
            except:
                errorlog.write('). Data:'+str(data)+'\n')
            errorlog.close()
            i2c_error[0] = True
            GPIO.setup(10, GPIO.OUT)    # error LED
            GPIO.output(10, GPIO.HIGH)
            
        def log_error(msg):
            now = datetime.now()
            errorlog = open(r'/var/lib/homebridge/crash.log','a')
            errorlog.write(now.strftime("%d/%m/%Y %H:%M:%S - Error message: "))
            errorlog.write(str(msg))
            errorlog.write('\n')
            errorlog.close()
            i2c_error[0] = True
            GPIO.setup(10, GPIO.OUT)    # error LED
            GPIO.output(10, GPIO.HIGH)
            
        def write_word_reg(adr, reg, word):
            try:
                ioctl(fw, I2C_SLAVE, adr)
                s = [reg, word%256, word>>8]
                s2 = bytearray(s)
                fw.write(s2)
            except:
                log_i2c_error(adr, 'write_word_reg', hex(word))

        def write_four_bytes_reg(adr, reg, byte0, byte1, byte2, byte3, ok_to_have_error = False):
            try:
                ioctl(fw, I2C_SLAVE, adr)
                s = [reg, byte0, byte1, byte2, byte3]
                s2 = bytearray(s)
                fw.write(s2)
            except:
                if not ok_to_have_error:
                    log_i2c_error(adr, 'write_four_bytes_reg', hex(byte0)+hex(byte1)+hex(byte2)+hex(byte3))
                else:
                    print 'write_four_bytes_reg i2c_error logging supressed'
            
        def write_two_bytes_reg(adr, reg, byte0, byte1):
            try:
                ioctl(fw, I2C_SLAVE, adr)
                s = [reg, byte0, byte1]
                s2 = bytearray(s)
                fw.write(s2)
            except:
                log_i2c_error(adr, 'write_two_bytes_reg', hex(byte0)+hex(byte1))
            
        def write_byte_reg(adr, reg, byte):
            try:
                ioctl(fw, I2C_SLAVE, adr)
                s = [reg, byte]
                s2 = bytearray(s)
                fw.write(s2)
            except:
                log_i2c_error(adr, 'write_byte_reg', hex(byte))

        def write_byte_reg_retry(adr, reg, byte):
            try:
                ioctl(fw, I2C_SLAVE, adr)
                s = [reg, byte]
                s2 = bytearray(s)
                fw.write(s2)
            except:
                sleep(0.1)
                try:
                    ioctl(fw, I2C_SLAVE, adr)
                    s = [reg, byte]
                    s2 = bytearray(s)
                    fw.write(s2)
                except:
                    log_i2c_error(adr, 'write_byte_reg_retry FAILED TWICE!!', hex(byte))
            
        def write_byte(adr, byte, ok_to_have_error = False):
            try:
                ioctl(fw, I2C_SLAVE, adr)
                s = [byte]
                s2 = bytearray(s)
                fw.write(s2)
            except:
                if not ok_to_have_error:
                    log_i2c_error(adr, 'write_byte', hex(byte))
                else:
                    print 'write_byte i2c_error logging supressed'
        
        def write_byte_retry(adr, byte, ok_to_have_error = False):
            try:
                ioctl(fw, I2C_SLAVE, adr)
                s = [byte]
                s2 = bytearray(s)
                fw.write(s2)
            except:
                sleep(0.1)
                try:
                    ioctl(fw, I2C_SLAVE, adr)
                    s = [byte]
                    s2 = bytearray(s)
                    fw.write(s2)
                except:
                    if not ok_to_have_error:
                        log_i2c_error(adr, 'write_byte_retry FAILED TWICE!!', hex(byte))
                    else:
                        print 'write_byte_retry i2c_error logging supressed twice'

        def write_byte_i2c_mux(adr, byte, ok_to_have_error = False):
            try:
                ioctl(fw, I2C_SLAVE, adr)
                s = [byte]
                s2 = bytearray(s)
                fw.write(s2)
            except:
                sleep(0.010)
                try:
                    ioctl(fw, I2C_SLAVE, adr)
                    s = [byte]
                    s2 = bytearray(s)
                    fw.write(s2)
                except:
                    sleep(0.050)
                    try:
                        ioctl(fw, I2C_SLAVE, adr)
                        s = [byte]
                        s2 = bytearray(s)
                        fw.write(s2)
                    except:
                        if not ok_to_have_error:
                            log_i2c_error(adr, 'write_byte_i2c_mux FAILED THREE TIMES!!', hex(byte))
                        else:
                            print 'write_byte_i2c_mux i2c_error logging supressed three times'
            
        def read_two_bytes_reg(adr, reg):
            try:
                ioctl(fr, I2C_SLAVE, adr)
                ioctl(fw, I2C_SLAVE, adr)
                s = [reg]
                s2 = bytearray(s)
                fw.write(s2)
                data = fr.read(2)
                buf = array('B', data)
                return buf[0], buf[1]
            except:
                log_i2c_error(adr, 'read_two_bytes_reg', 'N/A - reading op')
                return 0, 0
            
        def read_byte_reg(adr, reg, ok_to_have_error = False):
            try:
                ioctl(fr, I2C_SLAVE, adr)
                ioctl(fw, I2C_SLAVE, adr)
                s = [reg]
                s2 = bytearray(s)
                fw.write(s2)
                data = fr.read(1)
                buf = array('B', data)
                return buf[0]
            except:
                if not ok_to_have_error:
                    log_i2c_error(adr, 'read_byte_reg', 'N/A - reading op')
                else:
                    print 'read_byte_reg i2c_error logging supressed'
                return 0

        def read_byte_reg_remote_io(adr, reg):
            try:
                ioctl(fr, I2C_SLAVE, adr)
                ioctl(fw, I2C_SLAVE, adr)
                s = [reg]
                s2 = bytearray(s)
                fw.write(s2)
                data = fr.read(1)
                buf = array('B', data)
                return buf[0]
            except:
                log_i2c_error(adr, 'read_byte_reg_remote_io', 'N/A - reading op')
                return 0xFF
            
        def read_temp_hum(adr, ok_to_have_error = False): # have to run write byte first and wait a minimum of 6.25 ms
            try:
                ioctl(fr, I2C_SLAVE, adr)
                data = fr.read(4)
                buf = array('B', data)
                temp = (buf[0] << 8) + buf[1]
                cTemp = (temp / 65536.0) * 165.0 - 40
                temp_rounded = round(cTemp * 2) / 2

                humidity = (buf[2] << 8) + buf[3]
                humidity = (humidity / 65536.0) * 100.0
                humidity_rounded = round(humidity)
                
                return temp_rounded, humidity_rounded, cTemp, humidity
            except:
                if not ok_to_have_error:
                    log_i2c_error(adr, 'read_temp_hum', 'N/A - reading op')
                else:
                    print 'read_temp_hum i2c_error logging supressed'
                return -100, -100, -100, -100

        def read_air_qual(adr, reg, ok_to_have_error = True):
            try:
                ioctl(fr, I2C_SLAVE, adr)
                ioctl(fw, I2C_SLAVE, adr)
                s = [reg]
                s2 = bytearray(s)
                fw.write(s2)
                data = fr.read(4) #8)
                buf = array('B', data)
                eco2 = (buf[0] << 8) + buf[1]

                etvoc = (buf[2] << 8) + buf[3]

                # sts = buf[4]
                # err_id = buf[5]
                # raw = (buf[6] << 8) + buf[7]
                
                return eco2, etvoc #, sts, err_id, raw
            except:
                if not ok_to_have_error:
                    log_i2c_error(adr, 'read_air_qual', 'N/A - reading op')
                else:
                    print 'read_air_qual i2c_error logging supressed'
                return -100, -100

        def refresh_config(board_no):   
            # I/O SETUP
            IO_CON_REGISTER_16  = 0x0A
            IO_CON_REGISTER_8   = 0x05
            IO_DIR_REGISTER     = 0x00
            GPINTEN_REGISTER_16 = 0x04
            GPINTEN_REGISTER_8  = 0x02
            IO_POL_REGISTER_16  = 0x02
            IO_POL_REGISTER_8   = 0x01
            
            IOCON   = 0b01000100    # same for 16 bit and 8 bit
            
            dir16_A = 0b10010010    # 1 = input, 0 = output
            dir16_B = 0b10000001
            dir8    = 0b01001100
            
            # LED SETUP
            LED_CONFIG_REGISTER = 0x11
            
            PS_0    = 0x00  # no blinking
            #PWM_0  = 0xF0  # 6.25% brightness # defined globally - changes at bed
            
            PS_1    = 0x00  # no blinking
            #PWM_1   = 0xE0 #0x90  # ~43% for low speed fan # defined globally - changes at bed
            
            # ADDRESS CALCULATION
            board_offset = board_no * 2
            ADR16  = base16bit_adr + board_offset
            ADR8   = base8bit_adr + board_offset
            ADRLED = baseLED_adr + board_offset
            
            # I/O Expander config
            write_two_bytes_reg(ADR16, IO_CON_REGISTER_16, IOCON, IOCON)        # Register configuration for ports A and B on 16 bit I/O
            write_byte_reg(ADR8, IO_CON_REGISTER_8, IOCON)                      # Register configuration for 8 bit I/O
            
            write_two_bytes_reg(ADR16, IO_DIR_REGISTER, dir16_A, dir16_B)       # Set up directions of ports A and B of 16 bit I/O
            write_byte_reg(ADR8, IO_DIR_REGISTER, dir8)                         # Set up direction of 8 bit I/O
            
            write_two_bytes_reg(ADR16, GPINTEN_REGISTER_16, dir16_A, dir16_B)   # Attach intterupts to all inputs
            write_byte_reg(ADR8, GPINTEN_REGISTER_8, dir8)                      # Attach intterupts to all inputs
            
            write_two_bytes_reg(ADR16, IO_POL_REGISTER_16, 0x00, 0x00)          # Ensure no IOs inverted
            write_byte_reg(ADR8, IO_POL_REGISTER_8, 0x00)                       # Ensure no IOs inverted
            
            # LED driver config
            write_four_bytes_reg(ADRLED, LED_CONFIG_REGISTER, PS_0, PWM_0, PS_1, PWM_1)
            
            #print 'All devices on board',board_no,'refreshed'
            
        def refresh_board_3_config(mux):
            set_i2c_mux(mux)
            
            # I/O SETUP
            IO_CON_REGISTER_8   = 0x05
            IO_DIR_REGISTER     = 0x00
            IO_POL_REGISTER_8   = 0x01
            
            IOCON   = 0b01000100    # same for 16 bit and 8 bit
            
            dir8    = 0b00000000    # 1 = input, 0 = output
            
            # ADDRESS
            ADR8   = extra_8bit_adr
            
            # I/O Expander config
            write_byte_reg(ADR8, IO_CON_REGISTER_8, IOCON)                      # Register configuration for 8 bit I/O
            
            write_byte_reg(ADR8, IO_DIR_REGISTER, dir8)                         # Set up direction of 8 bit I/O
            
            write_byte_reg(ADR8, IO_POL_REGISTER_8, 0x00)                       # Ensure no IOs inverted

        def check_ind_status(board_no):
            for j in range(8):
                if path.isfile(r'/var/lib/homebridge/ind_'+str(board_no)+'/'+str(j)):
                    if not IND[board_no][j]:
                        IND[board_no][j] = True
                else:
                    if IND[board_no][j]:
                        IND[board_no][j] = False
                        
        def initial_states(board_no, bed):
            # DEFAULT VALUES
            IO_init = 0x00
            
            # ADDRESS CALCULATION
            board_offset = board_no * 2
            ADR16  = base16bit_adr + board_offset
            ADR8   = base8bit_adr + board_offset
            ADRLED = baseLED_adr + board_offset
            
            write_two_bytes_reg(ADR16, GPIO_REGISTER_16, IO_init, IO_init)      # Set all output I/Os to 0
            GLOBAL_16bit[board_no] = (IO_init << 8) + IO_init
            write_byte_reg(ADR8, GPIO_REGISTER_8, IO_init)                      # Set all output I/Os to 0
            GLOBAL_8bit[board_no] = IO_init
            
            for j in range(8):
                if (board_no != FAN[0] and j != FAN[1]): 
                    if STATUS[IND_MAP[board_no][j][0]][IND_MAP[board_no][j][1]]:
                        if bed:
                            GLOBAL_LED[board_no] = GLOBAL_LED[board_no] + (LED_SETTING[IND_SETTING[1][INDICATOR_TYPE[board_no][j]][1]] << (LED_MAPPING[j] * 2))
                        else:
                            GLOBAL_LED[board_no] = GLOBAL_LED[board_no] + (LED_SETTING[IND_SETTING[0][INDICATOR_TYPE[board_no][j]][1]] << (LED_MAPPING[j] * 2))
                        if IND[board_no][j]:
                            if bed:
                                GLOBAL_LED_DISP[board_no] = GLOBAL_LED_DISP[board_no] + (LED_SETTING[IND_SETTING[1][INDICATOR_TYPE[board_no][j]][1]] << (LED_MAPPING[j] * 2))
                            else:
                                GLOBAL_LED_DISP[board_no] = GLOBAL_LED_DISP[board_no] + (LED_SETTING[IND_SETTING[0][INDICATOR_TYPE[board_no][j]][1]] << (LED_MAPPING[j] * 2))
                        else:
                            GLOBAL_LED_DISP[board_no] = GLOBAL_LED_DISP[board_no] + (LED_SETTING[0] << (LED_MAPPING[j] * 2))
                    else:
                        if bed:
                            GLOBAL_LED[board_no] = GLOBAL_LED[board_no] + (LED_SETTING[IND_SETTING[1][INDICATOR_TYPE[board_no][j]][0]] << (LED_MAPPING[j] * 2))
                        else:
                            GLOBAL_LED[board_no] = GLOBAL_LED[board_no] + (LED_SETTING[IND_SETTING[0][INDICATOR_TYPE[board_no][j]][0]] << (LED_MAPPING[j] * 2))
                        if IND[board_no][j]:
                            if bed:
                                GLOBAL_LED_DISP[board_no] = GLOBAL_LED_DISP[board_no] + (LED_SETTING[IND_SETTING[1][INDICATOR_TYPE[board_no][j]][0]] << (LED_MAPPING[j] * 2))
                            else:
                                GLOBAL_LED_DISP[board_no] = GLOBAL_LED_DISP[board_no] + (LED_SETTING[IND_SETTING[0][INDICATOR_TYPE[board_no][j]][0]] << (LED_MAPPING[j] * 2))
                        else:
                            GLOBAL_LED_DISP[board_no] = GLOBAL_LED_DISP[board_no] + (LED_SETTING[0] << (LED_MAPPING[j] * 2))
            
            write_word_reg(ADRLED, LED_REGISTER, GLOBAL_LED_DISP[board_no]) # Set all LEDs to match current state w/ IND power status reflected
            
            print 'All devices on board',board_no,'initialised'
            
        def initial_states_board_3(mux):
            # DEFAULT VALUES
            IO_init = 0x00
            
            # ADDRESS
            ADR8   = extra_8bit_adr
            
            write_byte_reg(ADR8, GPIO_REGISTER_8, IO_init)                      # Set all output I/Os to 0
            
            print 'IO expander on board 3 at mux',mux,'initialised'

        def custom_states_board_3(mux):
            # DEFAULT VALUES
            IO_custom = 0x0A
            
            # ADDRESS
            ADR8   = extra_8bit_adr
            
            write_byte_reg(ADR8, GPIO_REGISTER_8, IO_custom)                        # Set all custom output on I/Os
            
            print 'IO expander on board 3 at mux',mux,'set with custom value'   
            
        def set_one_led(board_num, channnel, val):
            board_no = IND_MAP[board_num][channnel][0]
            chan = IND_MAP[board_num][channnel][1]
            
            #print "Setting indicator LED to value: "+str(val)+" on board: "+str(board_no)+", channel: "+str(chan)
            board_offset = board_no * 2
            ADRLED = baseLED_adr + board_offset
            
            #print "Global value before:"+bin(GLOBAL_LED[board_no])
            new_val = GLOBAL_LED[board_no] & ~(0b11 << (LED_MAPPING[chan] * 2)) # zero out old setting
            new_val = new_val + (LED_SETTING[val] << (LED_MAPPING[chan] * 2))   # shift in updated value
            GLOBAL_LED[board_no] = new_val
            #print "Global value after:"+bin(GLOBAL_LED[board_no])
            
            #print "Global display value before:"+bin(GLOBAL_LED_DISP[board_no])
            new_val = GLOBAL_LED_DISP[board_no] & ~(0b11 << (LED_MAPPING[chan] * 2)) # zero out old setting
            if IND[board_no][chan] or (board_no == FAN[0] and chan == FAN[1]):
                new_val = new_val + (LED_SETTING[val] << (LED_MAPPING[chan] * 2))   # shift in updated value if IND is ON
            else:
                new_val = new_val + (LED_SETTING[0] << (LED_MAPPING[chan] * 2)) # shift in OFF value if IND is OFF
            
            GLOBAL_LED_DISP[board_no] = new_val
            #print "Global display value after :"+bin(GLOBAL_LED_DISP[board_no])
            write_word_reg(ADRLED, LED_REGISTER, GLOBAL_LED_DISP[board_no])
                        
        def update_ind(board_no):
            board_offset = board_no * 2
            ADRLED = baseLED_adr + board_offset
            
            new_val = 0
            for j in range(8):
                if IND[board_no][j] or (board_no == FAN[0] and j == FAN[1]):
                    new_val = new_val + (GLOBAL_LED[board_no] & 0b11 << (LED_MAPPING[j] * 2))   # add in value stored in GLOBAL_LED
                else:
                    new_val = new_val + (LED_SETTING[0] << (LED_MAPPING[j] * 2))
                
            GLOBAL_LED_DISP[board_no] = new_val
            write_word_reg(ADRLED, LED_REGISTER, GLOBAL_LED_DISP[board_no])
            
        def read_status(board_no):
            LAST_STATUS[board_no] = STATUS[board_no][:]
            board_offset = board_no * 2
            ADR16  = base16bit_adr + board_offset
            ADR8   = base8bit_adr + board_offset

            portA, portB = read_two_bytes_reg(ADR16, GPIO_REGISTER_16)
            port8 = read_byte_reg(ADR8, GPIO_REGISTER_8)
            
            STATUS[board_no][0] = ((portA & 0x10) == 0x10)
            STATUS[board_no][1] = ((portA & 0x80) == 0x80)
            STATUS[board_no][2] = ((portB & 0x01) == 0x01)
            STATUS[board_no][3] = ((portB & 0x80) == 0x80)
            STATUS[board_no][4] = ((portA & 0x02) == 0x02)
            STATUS[board_no][5] = ((port8 & 0x40) == 0x40)
            STATUS[board_no][6] = ((port8 & 0x08) == 0x08)
            STATUS[board_no][7] = ((port8 & 0x04) == 0x04)
            
        def set_relay(board_no, chan):
            board_offset = board_no * 2
            ADR16  = base16bit_adr + board_offset
            ADR8   = base8bit_adr + board_offset
            
            # FIRST ENSURE RST OFF
            if RST_MAPPING[chan][0] == 0:   # 16 bit expander
                GLOBAL_16bit[board_no] = GLOBAL_16bit[board_no] &(~(0b1 << RST_MAPPING[chan][1]))   # set corresponding RST to 0
                write_word_reg(ADR16, GPIO_REGISTER_16, GLOBAL_16bit[board_no])
            elif RST_MAPPING[chan][0] == 1: # 8 bit expander
                GLOBAL_8bit[board_no] = GLOBAL_8bit[board_no] &(~(0b1 << RST_MAPPING[chan][1]))
                write_byte_reg(ADR8, GPIO_REGISTER_8, GLOBAL_8bit[board_no])
            
            # NOW TURN SET ON
            if SET_MAPPING[chan][0] == 0:   # 16 bit expander
                GLOBAL_16bit[board_no] = GLOBAL_16bit[board_no] | (0b1 << SET_MAPPING[chan][1]) # set corresponding RST to 0
                write_word_reg(ADR16, GPIO_REGISTER_16, GLOBAL_16bit[board_no])
            elif SET_MAPPING[chan][0] == 1: # 8 bit expander
                GLOBAL_8bit[board_no] = GLOBAL_8bit[board_no] | (0b1 << SET_MAPPING[chan][1])
                write_byte_reg(ADR8, GPIO_REGISTER_8, GLOBAL_8bit[board_no])
                
            RELAY_STATE[board_no][chan] = True  # Set
            f = open(r'/var/lib/homebridge/relay_'+str(board_no)+'/'+str(chan),'w')
            f.close()
            
            NUM_RELAYS_ON[0] += 1
            RELAY_CLR_TIMER[board_no][chan] = RELAY_ON_TIME + 1
            STATUS_SETTLE_TIMER[board_no][chan] = STATUS_SETTLE_TIME
            #print 'Board',board_no,'relay',chan,'set'

        def rst_relay(board_no, chan):
            board_offset = board_no * 2
            ADR16  = base16bit_adr + board_offset
            ADR8   = base8bit_adr + board_offset
            
            # FIRST ENSURE SET OFF
            if SET_MAPPING[chan][0] == 0:   # 16 bit expander
                GLOBAL_16bit[board_no] = GLOBAL_16bit[board_no] &(~(0b1 << SET_MAPPING[chan][1]))   # set corresponding SET to 0
                write_word_reg(ADR16, GPIO_REGISTER_16, GLOBAL_16bit[board_no])
            elif SET_MAPPING[chan][0] == 1: # 8 bit expander
                GLOBAL_8bit[board_no] = GLOBAL_8bit[board_no] &(~(0b1 << SET_MAPPING[chan][1]))
                write_byte_reg(ADR8, GPIO_REGISTER_8, GLOBAL_8bit[board_no])
            
            # NOW TURN RST ON
            if RST_MAPPING[chan][0] == 0:   # 16 bit expander
                GLOBAL_16bit[board_no] = GLOBAL_16bit[board_no] | (0b1 << RST_MAPPING[chan][1]) # set corresponding SET to 0
                write_word_reg(ADR16, GPIO_REGISTER_16, GLOBAL_16bit[board_no])
            elif RST_MAPPING[chan][0] == 1: # 8 bit expander
                GLOBAL_8bit[board_no] = GLOBAL_8bit[board_no] | (0b1 << RST_MAPPING[chan][1])
                write_byte_reg(ADR8, GPIO_REGISTER_8, GLOBAL_8bit[board_no])
                
            RELAY_STATE[board_no][chan] = False # Reset
            remove(r'/var/lib/homebridge/relay_'+str(board_no)+'/'+str(chan))
            
            NUM_RELAYS_ON[0] += 1
            RELAY_CLR_TIMER[board_no][chan] = RELAY_ON_TIME + 1
            STATUS_SETTLE_TIMER[board_no][chan] = STATUS_SETTLE_TIME
            #print 'Board',board_no,'relay',chan,'reset'
                
        def clr_relay(board_no, chan):
            board_offset = board_no * 2
            ADR16  = base16bit_adr + board_offset
            ADR8   = base8bit_adr + board_offset
            
            # SET OFF
            if SET_MAPPING[chan][0] == 0:   # 16 bit expander
                GLOBAL_16bit[board_no] = GLOBAL_16bit[board_no] &(~(0b1 << SET_MAPPING[chan][1]))   # set corresponding SET to 0
                write_word_reg(ADR16, GPIO_REGISTER_16, GLOBAL_16bit[board_no])
            elif SET_MAPPING[chan][0] == 1: # 8 bit expander
                GLOBAL_8bit[board_no] = GLOBAL_8bit[board_no] &(~(0b1 << SET_MAPPING[chan][1]))
                write_byte_reg(ADR8, GPIO_REGISTER_8, GLOBAL_8bit[board_no])
            
            # RST OFF
            if RST_MAPPING[chan][0] == 0:   # 16 bit expander
                GLOBAL_16bit[board_no] = GLOBAL_16bit[board_no] &(~(0b1 << RST_MAPPING[chan][1]))   # set corresponding RST to 0
                write_word_reg(ADR16, GPIO_REGISTER_16, GLOBAL_16bit[board_no])
            elif RST_MAPPING[chan][0] == 1: # 8 bit expander
                GLOBAL_8bit[board_no] = GLOBAL_8bit[board_no] &(~(0b1 << RST_MAPPING[chan][1]))
                write_byte_reg(ADR8, GPIO_REGISTER_8, GLOBAL_8bit[board_no])
                
            NUM_RELAYS_ON[0] -= 1
                
            #print 'Board',board_no,'relay',chan,'cleared'
            #print

        def power(board_no, chan, ONOFF):
            read_status(board_no)
            
            if ONOFF != STATUS[board_no][chan]: # if desired state different to current state
                if RELAY_STATE[board_no][chan]: # if relay currently set
                    rst_relay(board_no, chan)
                else:
                    set_relay(board_no, chan)
                
                # if ONOFF:
                    # print 'Board',board_no,'channel',chan,'turned ON'
                # else:
                    # print 'Board',board_no,'channel',chan,'turned OFF'
            # else:
                # if ONOFF:
                    # print 'No action taken - board',board_no,'channel',chan,'already turned ON'
                    # print
                # else:
                    # print 'No action taken - board',board_no,'channel',chan,'already turned OFF'
                    # print

        def setDimmer(dimmer_no, profile, val, last_write): # dimmer_no is only used if multiple dimmers (@different addresses) on same i2c mux line, it'll normally be 0
            adr = dimmer_adr + dimmer_no
            if profile == 0:    # incandescent
                piOver2 = 1.57
                corrected_brightness = int(((asin(val)/piOver2) * 154.0)+50)
                #if corrected_brightness >= 203:
                    #corrected_brightness = 254
                    # corrected_brightness = 204
                    # for i in range(5):
                        # write_byte(adr, corrected_brightness) #bus.write_byte(dimmer_adr, corrected_brightness)
                        # corrected_brightness += 10
                        # sleep(LOOP_TIME)
                # if corrected_brightness != last_write:
                    # write_byte(adr, corrected_brightness) #bus.write_byte(adr, corrected_brightness)
                # return corrected_brightness
                    #print 'Current brightness:',val,'    Corrected brightness:',corrected_brightness
            elif profile == 1 or profile == 2:  # IKEA LED bulb 
                corrected_brightness = int((val * 134.0)+20)
                #if corrected_brightness >= 153:
                    #corrected_brightness = 254
                    # corrected_brightness = 154
                    # for i in range(4):
                        # write_byte(adr, corrected_brightness) #bus.write_byte(dimmer_adr, corrected_brightness)
                        # corrected_brightness += 25
                        # sleep(LOOP_TIME)
                # if corrected_brightness != last_write:
                    # write_byte(adr, corrected_brightness) #bus.write_byte(adr, corrected_brightness)
                    # #print 'Current brightness:',val,'    Corrected brightness:',corrected_brightness
                # return corrected_brightness
            elif profile == 3:  # Philips GU10
                corrected_brightness = int((val * 152.0)+38)
                # if corrected_brightness >= 189:
                    # corrected_brightness = 254
            elif profile == 4:  # incandescent limited to upper 50% (to reduce EMI)
                piOver2 = 1.57
                corrected_brightness = int(((asin(val)/piOver2) * 100.0)+127)
            elif profile == 5:  # Screwfix Bathroom GU10
                corrected_brightness = int((val * 100.0)+20)
            elif profile == 6:  # Philips salt lamps (max 56%)
                corrected_brightness = int((val * 112.0)+11) # 56% = 123 counts 
            else: # linear
                corrected_brightness = int((val * 254.0)+0)
            if corrected_brightness != last_write:
                write_byte(adr, corrected_brightness) #bus.write_byte(adr, corrected_brightness)
            return corrected_brightness
                
        def set_i2c_mux(chan):
            if chan == -1:
                GPIO.output(24, GPIO.LOW)       # reset all mux channels
                GPIO.output(26, GPIO.LOW)
                sleep(0.01)
                GPIO.output(24, GPIO.HIGH)
                GPIO.output(26, GPIO.HIGH)
            elif chan == 0:
                write_byte_i2c_mux(i2c_mux_adr, 0x01)   # CH 0 on device
                if two_i2c_boards:
                    write_byte_i2c_mux(i2c_mux_adr2, 0x00)
            elif chan == 1:
                write_byte_i2c_mux(i2c_mux_adr, 0x80)   # CH 7 on device
                if two_i2c_boards:
                    write_byte_i2c_mux(i2c_mux_adr2, 0x00)
            elif chan == 2:
                write_byte_i2c_mux(i2c_mux_adr, 0x02)   # CH 1 on device
                if two_i2c_boards:
                    write_byte_i2c_mux(i2c_mux_adr2, 0x00)
            elif chan == 3:
                write_byte_i2c_mux(i2c_mux_adr, 0x40)   # CH 6 on device
                if two_i2c_boards:
                    write_byte_i2c_mux(i2c_mux_adr2, 0x00)
            elif chan == 4:
                write_byte_i2c_mux(i2c_mux_adr, 0x04)   # CH 2 on device
                if two_i2c_boards:
                    write_byte_i2c_mux(i2c_mux_adr2, 0x00)
            elif chan == 5:
                write_byte_i2c_mux(i2c_mux_adr, 0x20)   # CH 5 on device
                if two_i2c_boards:
                    write_byte_i2c_mux(i2c_mux_adr2, 0x00)
            elif chan == 6:
                write_byte_i2c_mux(i2c_mux_adr, 0x08)   # CH 3 on device
                if two_i2c_boards:
                    write_byte_i2c_mux(i2c_mux_adr2, 0x00)
            elif chan == 7:
                write_byte_i2c_mux(i2c_mux_adr, 0x10)   # CH 4 on device
                if two_i2c_boards:
                    write_byte_i2c_mux(i2c_mux_adr2, 0x00)
            elif chan == 8:
                write_byte_i2c_mux(i2c_mux_adr2, 0x01)  # CH 0 on device
                write_byte_i2c_mux(i2c_mux_adr, 0x00)
            elif chan == 9:
                write_byte_i2c_mux(i2c_mux_adr2, 0x80)  # CH 7 on device
                write_byte_i2c_mux(i2c_mux_adr, 0x00)
            elif chan == 10:
                write_byte_i2c_mux(i2c_mux_adr2, 0x02)  # CH 1 on device
                write_byte_i2c_mux(i2c_mux_adr, 0x00)
            elif chan == 11:
                write_byte_i2c_mux(i2c_mux_adr2, 0x40)  # CH 6 on device
                write_byte_i2c_mux(i2c_mux_adr, 0x00)
            elif chan == 12:
                write_byte_i2c_mux(i2c_mux_adr2, 0x04)  # CH 2 on device
                write_byte_i2c_mux(i2c_mux_adr, 0x00)
            elif chan == 13:
                write_byte_i2c_mux(i2c_mux_adr2, 0x20)  # CH 5 on device
                write_byte_i2c_mux(i2c_mux_adr, 0x00)
            elif chan == 14:
                write_byte_i2c_mux(i2c_mux_adr2, 0x08)  # CH 3 on device
                write_byte_i2c_mux(i2c_mux_adr, 0x00)
            elif chan == 15:
                write_byte_i2c_mux(i2c_mux_adr2, 0x10)  # CH 4 on device
                write_byte_i2c_mux(i2c_mux_adr, 0x00)
            currentIOmux_chan[0] = chan
            
        def setLEDpwr(led_strip_IP, index, led_retry, led_retry_pwr, led_retry_counter, on, slow, led_confirm, led_retry_delay, timeout=3):
            #print "setLEDpwr",on," run for IP:",led_strip_IP
            response_not_received = True

            if led_strip_IP == '-1':
                led_retries = timeout
            else:
                led_retries = 0

            while response_not_received and (led_retries < timeout):
                empty_socket(sock)
                if on:
                    if slow:
                        sock.sendto(lifx_power_on_slow, (led_strip_IP, led_strip_UDP_port))
                    else:
                        sock.sendto(lifx_power_on, (led_strip_IP, led_strip_UDP_port))
                else:
                    sock.sendto(lifx_power_off, (led_strip_IP, led_strip_UDP_port))
                try:
                    data, address = sock.recvfrom(1024)

                    # print 'Reply received from LED strip:',ord(data[36])
                    # print len(data)
                    # for dcnt in range(len(data)):
                    #     print ord(data[dcnt]),
                    # print

                    if address[0] == led_strip_IP:
                        response_not_received = False
                        if led_strip_confirm[index]:
                            led_confirm[index] = 2
                            led_repeat_confirm[index] = True
                        
                except:
                    led_retries += 1
                    print 'LED ON/OFF for',led_strip_IP,'took',led_retries,'retries...'

            if led_retries == timeout:
                print 'Failed to communicate with LED strip '+str(index)+'. Will retry in 5 seconds...'
                led_retry[index] = True
                led_retry_pwr[index] = on
                led_retry_counter[index] = 0
                led_retry_delay = True
                
        def relocateLED(led_strip_num, led_retry, led_retry_counter, led_strips, led_retry_pwr, led_repeat_pwr, led_strip_confirm, led_confirm, led_repeat_confirm, led_mac, first_time_led_locate, timeout=3):
            print 're-locating LED strip',i,'IP address'
            getLEDip(led_strip_num, led_mac, led_strips, led_retry)
            if led_retry[led_strip_num]:
                print 'Failed to locate LED strip '+str(led_strip_num)+'. Keeping at IP address: '+led_strips[led_strip_num]
            else:
                print 'LED strip',led_strip_num,'moved to',led_strips[led_strip_num]
                led_retry_counter[led_strip_num] = 0
                #first_time_led_locate[led_strip_num] = False

            response_not_received = True
            led_retries = 0

            if led_strips[led_strip_num] != '-1':
                if first_time_led_locate[led_strip_num]:
                    first_time_led_locate[led_strip_num] = False
                    led_repeat_pwr[led_strip_num] = 2
                    if led_strip_confirm[led_strip_num]:
                        led_confirm[led_strip_num] = 2
                        led_repeat_confirm[led_strip_num] = True
                else:
                    led_strip_IP = led_strips[led_strip_num]
                    while response_not_received and (led_retries < timeout):
                        empty_socket(sock)
                        if led_retry_pwr[led_strip_num]:
                            sock.sendto(lifx_power_on, (led_strip_IP, led_strip_UDP_port))
                            #sock.sendto(lifx_power_off, (led_strip_IP, led_strip_UDP_port)) # do the opposite of the initial power request first, will be put right by led_repeat_pwr
                        else:
                            sock.sendto(lifx_power_off, (led_strip_IP, led_strip_UDP_port))
                            #sock.sendto(lifx_power_on, (led_strip_IP, led_strip_UDP_port)) # do the opposite of the initial power request first, will be put right by led_repeat_pwr
                        try:
                            data, address = sock.recvfrom(1024)
                            if address[0] == led_strip_IP:
                                response_not_received = False
                                led_repeat_pwr[led_strip_num] = 2
                                if led_strip_confirm[led_strip_num]:
                                    led_confirm[led_strip_num] = 2
                                    led_repeat_confirm[led_strip_num] = True
                        except:
                            led_retries += 1
                            print 'LED ON/OFF for',led_strip_IP,'took',led_retries,'retries...'
                
        def retryPwrLED(led_strip_num, led_retry, led_retry_counter, led_strips, led_retry_pwr, led_repeat_pwr, led_strip_confirm, led_confirm, led_repeat_confirm, timeout=3):
            print 'retrying power command for LED strip',i

            response_not_received = True
            led_retries = 0

            if led_strips[led_strip_num] != '-1':
                led_strip_IP = led_strips[led_strip_num]
                while response_not_received and (led_retries < timeout):
                    empty_socket(sock)
                    if led_retry_pwr[led_strip_num]:
                        sock.sendto(lifx_power_on, (led_strip_IP, led_strip_UDP_port))
                        #sock.sendto(lifx_power_off, (led_strip_IP, led_strip_UDP_port)) # do the opposite of the initial power request first, will be put right by led_repeat_pwr
                    else:
                        sock.sendto(lifx_power_off, (led_strip_IP, led_strip_UDP_port))
                        #sock.sendto(lifx_power_on, (led_strip_IP, led_strip_UDP_port)) # do the opposite of the initial power request first, will be put right by led_repeat_pwr
                    try:
                        data, address = sock.recvfrom(1024)
                        if address[0] == led_strip_IP:
                            response_not_received = False
                            led_repeat_pwr[led_strip_num] = 2
                            if led_strip_confirm[led_strip_num]:
                                led_confirm[led_strip_num] = 2
                                led_repeat_confirm[led_strip_num] = True
                            led_retry[led_strip_num] = False
                            print 'LED communication re-established during retryPwrLED()'
                            led_retry_counter[led_strip_num] = 0
                    except:
                        led_retries += 1
                        print 'LED ON/OFF for',led_strip_IP,'took',led_retries,'retries...'

        def setMult(led_strip_IP, index, num, hue, saturation, brightness, kelvin, lifx_time):
            #print "setMult run for IP:",led_strip_IP
            if led_strip_IP == '-1':
                print 'LED strip not found...'
            else:
                payload = pack('<BBHHHHIB', index, index+num, hue, saturation, brightness, kelvin, lifx_time, lifx_apply)
                lifx_packet = lifx_header + payload
                sock.sendto(lifx_packet, (led_strip_IP, led_strip_UDP_port))

        def setBulb(led_strip_IP, hue, saturation, brightness, kelvin, lifx_time):
            #print "setBulb run for IP:",led_strip_IP
            if led_strip_IP == '-1':
                print 'LIFX Bulb not found...'
            else:
                payload = pack('<BHHHHI', 0x0, hue, saturation, brightness, kelvin, lifx_time)
                lifx_packet = lifx_header_bulb + payload
                sock.sendto(lifx_packet, (led_strip_IP, led_strip_UDP_port))

        def setMultRes(led_strip_IP, index, num, hue, saturation, brightness, kelvin, lifx_time):
            #print "setMult run for IP:",led_strip_IP
            if led_strip_IP == '-1':
                print 'LED strip not found...'
            else:
                payload = pack('<BBHHHHIB', index, index+num, hue, saturation, brightness, kelvin, lifx_time, lifx_apply)
                lifx_packet = lifx_header_res + payload
                sock.sendto(lifx_packet, (led_strip_IP, led_strip_UDP_port))

        def setBulbRes(led_strip_IP, hue, saturation, brightness, kelvin, lifx_time):
            #print "setBulb run for IP:",led_strip_IP
            if led_strip_IP == '-1':
                print 'LIFX Bulb not found...'
            else:
                payload = pack('<BHHHHI', 0x0, hue, saturation, brightness, kelvin, lifx_time)
                lifx_packet = lifx_header_bulb_res + payload
                sock.sendto(lifx_packet, (led_strip_IP, led_strip_UDP_port))

        def getAllLEDip(led_retry_pwr, num_led_strips, led_mac, led_strips, led_retry, first_time_led_locate):
            f = open('/var/lib/homebridge/heartbeat','w')
            f.close()
            f = open('/var/lib/homebridge/extend_watchdog','w')
            f.close()
            nm = nmap.PortScanner()
            arp_table = nm.scan(hosts='192.168.28.0/24', arguments='-sP')
            #print arp_table
            for key in arp_table['scan']:
                for i in range(num_led_strips):
                    if 'mac' in arp_table['scan'][key]['addresses']:
                        if led_mac[i] in arp_table['scan'][key]['addresses']['mac']:
                            led_strips[i] = arp_table['scan'][key]['addresses']['ipv4']
                            print 'led strip',i,'ip address is:',led_strips[i]
                            led_retry[i] = False
                            first_time_led_locate[i] = False

            for i in range(num_led_strips):
                if led_retry[i]:
                    print 'Failed to locate LED strip',i
                    f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_Led_Strip_'+str(i)+'_On','r')
                    value = f.readline()
                    f.close()
                    if 'true' in value:
                        led_retry_pwr[i] = True
                    else:
                        led_retry_pwr[i] = False

        def getLEDip(led_strip_num, led_mac, led_strips, led_retry):
            f = open('/var/lib/homebridge/heartbeat','w')
            f.close()
            f = open('/var/lib/homebridge/extend_watchdog','w')
            f.close()
            nm = nmap.PortScanner()
            arp_table = nm.scan(hosts='192.168.28.0/24', arguments='-sP')

            for key in arp_table['scan']:
                if 'mac' in arp_table['scan'][key]['addresses']:
                    if led_mac[led_strip_num] in arp_table['scan'][key]['addresses']['mac']:
                        led_strips[led_strip_num] = arp_table['scan'][key]['addresses']['ipv4']
                        print 'led strip',led_strip_num,'ip address is:',led_strips[led_strip_num]
                        led_retry[led_strip_num] = False

        def empty_socket(sock):
            """remove the data present on the socket"""
            input = [sock]
            while 1:
                inputready, o, e = select.select(input,[],[], 0.0)
                if len(inputready)==0: break
                for s in inputready: s.recv(1)

        # def getLEDip(mac_adr):
        #     system(r'arp -a > /var/lib/homebridge/arp_table')
        #     f = open('arp_table','r')
        #     arp_table = f.readlines()
        #     f.close()

        #     led_not_found = True
        #     retry_after_scan = False
        #     i=0
        #     ip = '-1'
        #     while led_not_found:
        #         if mac_adr in arp_table[i]:
        #             ip = arp_table[i].split('(')[1].split(')')[0]
        #             led_not_found = False

        #         i += 1
        #         if i == len(arp_table):
        #             led_not_found = False
        #             retry_after_scan = True
                
        #     if retry_after_scan:
                
        #         nm = nmap.PortScanner()
        #         arp_table = nm.scan(hosts='192.168.28.0/24', arguments='-sP')
                
        #         print arp_table
        #         # led_not_found = True
        #         # i=0
        #         # while led_not_found:
        #         #     if mac_adr in arp_table[i]:
        #         #         print arp_table[i]
        #         ip = '-1' #arp_table[i].split('(')[1].split(')')[0]
        #         #         led_not_found = False

        #         #     i += 1
        #         #     if i == len(arp_table):
        #         #         led_not_found = False

        #     return ip

        # def getLEDip_rescan(mac_adr):
        #     import nmap
        #     nm = nmap.PortScanner()
        #     nm.scan(hosts='192.168.28.0/24', arguments='-sn')

        #     system(r'arp -a > /var/lib/homebridge/arp_table')
        #     f = open('arp_table','r')
        #     arp_table = f.readlines()
        #     f.close()

        #     led_not_found = True
        #     i=0
        #     ip = '-1'
        #     while led_not_found:
        #         if mac_adr in arp_table[i]:
        #             ip = arp_table[i].split('(')[1].split(')')[0]
        #             led_not_found = False

        #         i += 1
        #         if i == len(arp_table):
        #             led_not_found = False

        #     return ip
            
        def readCmd4State(file):
            filename = '/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_'+file
            f = open(filename, 'r')
            line = f.readline()
            if '\n' in line:
                line = line[0:-1]
            f.close()
            print 'Read \"'+line+'\" from file '+file
            return line
            
        def writeCmd4State(file, value):
            filename = '/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_'+file
            f = open(filename, 'w')
            f.write(value+'\n')
            f.close()
            
        def accesspointLED(ip_adr, on):
            num_access_points = len(ip_adr)
            cmd = 'sudo /bin/su -c "python /var/lib/homebridge/access_point_led/ubiquiti_ap_led.py '
            cmd += str(num_access_points) + ' '
            cmd += on + ' '
            for i in range(num_access_points):
                cmd += ip_adr[i] + ' '
            cmd += '&" - pi' # run in separate subprocess
            system(cmd)

        def packageGarageMessage(doorbell_ip_adr, on):
            cmd = 'sudo /bin/su -c "python /var/lib/homebridge/package-garage/package_garage.py '
            cmd += doorbell_ip_adr + ' '
            cmd += str(on) + ' '
            cmd += '&" - pi' # run in separate subprocess
            system(cmd)

        def set_scene(button_num, scene_num, bed, is_master):
            if (not is_master) and (button_num == 0) and bed:
                if scene_num == 0:
                    scene_buffer = button_scene_0_bed
                elif scene_num == 1:
                    scene_buffer = button_scene_1_bed
                elif scene_num == 2:
                    scene_buffer = button_scene_2_bed
            else:
                if scene_num == 0:
                    scene_buffer = button_scene_0
                elif scene_num == 1:
                    scene_buffer = button_scene_1
                elif scene_num == 2:
                    scene_buffer = button_scene_2
                
            for i in range(len(lights_under_button_control[button_num])):
                if lights_under_button_control[button_num][i][0] == 0:  # if standard switch light
                    if scene_buffer[button_num][i][0]:
                        system(r'touch /var/lib/homebridge/input_'+str(lights_under_button_control[button_num][i][1])+'/'+str(lights_under_button_control[button_num][i][2]))
                        ACTIVATED_AS_NIGHTLIGHT[lights_under_button_control[button_num][i][1]][lights_under_button_control[button_num][i][2]] = False
                    else:
                        if path.isfile(r'/var/lib/homebridge/input_'+str(lights_under_button_control[button_num][i][1])+'/'+str(lights_under_button_control[button_num][i][2])):
                            remove(r'/var/lib/homebridge/input_'+str(lights_under_button_control[button_num][i][1])+'/'+str(lights_under_button_control[button_num][i][2]))
                elif lights_under_button_control[button_num][i][0] == 1:    # if dimmer
                    if scene_buffer[button_num][i][0]:
                        writeCmd4State('Dimmer_'+str(lights_under_button_control[button_num][i][1])+'_On', 'true')
                        writeCmd4State('Dimmer_'+str(lights_under_button_control[button_num][i][1])+'_Brightness', str(scene_buffer[button_num][i][1]))
                        ACTIVATED_AS_NIGHTLIGHT[DIMMER_SWITCH[lights_under_button_control[button_num][i][1]][0]][DIMMER_SWITCH[lights_under_button_control[button_num][i][1]][1]] = False
                    else:
                        writeCmd4State('Dimmer_'+str(lights_under_button_control[button_num][i][1])+'_On', 'false')
                elif lights_under_button_control[button_num][i][0] == 2:    # if led strip
                    if scene_buffer[button_num][i][0]:
                        writeCmd4State('Led_Strip_'+str(lights_under_button_control[button_num][i][1])+'_On', 'true')
                        writeCmd4State('Led_Strip_'+str(lights_under_button_control[button_num][i][1])+'_Brightness', str(scene_buffer[button_num][i][1]))
                        writeCmd4State('Led_Strip_'+str(lights_under_button_control[button_num][i][1])+'_Hue', str(scene_buffer[button_num][i][2]))
                        writeCmd4State('Led_Strip_'+str(lights_under_button_control[button_num][i][1])+'_Saturation', str(scene_buffer[button_num][i][3]))
                    else:
                        writeCmd4State('Led_Strip_'+str(lights_under_button_control[button_num][i][1])+'_On', 'false')
            
        def set_scene_off(button_num):
            for i in range(len(lights_under_button_control_off[button_num])):
                if lights_under_button_control_off[button_num][i][0] == 0:  # if standard switch light
                    if path.isfile(r'/var/lib/homebridge/input_'+str(lights_under_button_control_off[button_num][i][1])+'/'+str(lights_under_button_control_off[button_num][i][2])):
                        remove(r'/var/lib/homebridge/input_'+str(lights_under_button_control_off[button_num][i][1])+'/'+str(lights_under_button_control_off[button_num][i][2]))
                elif lights_under_button_control_off[button_num][i][0] == 1:    # if dimmer
                    writeCmd4State('Dimmer_'+str(lights_under_button_control_off[button_num][i][1])+'_On', 'false')
                elif lights_under_button_control_off[button_num][i][0] == 2:    # if led strip  
                    writeCmd4State('Led_Strip_'+str(lights_under_button_control_off[button_num][i][1])+'_On', 'false')
                    
        def set_up_blind_IOexp(mux):
            # I/O SETUP
            IO_DIR_REGISTER     = 0x00
            IO_POL_REGISTER_8   = 0x01
            dir8blind    = 0b11100000
            blind_CLEAR = 0b00000000
            
            set_i2c_mux(mux)
            
            # I/O Expander config
            write_byte_reg(extra_8bit_adr, IO_DIR_REGISTER, dir8blind)                      # Set up direction of 8 bit I/O
            write_byte_reg(extra_8bit_adr, IO_POL_REGISTER_8, 0x00)                         # Ensure no IOs inverted
            write_byte_reg(extra_8bit_adr, GPIO_REGISTER_8, blind_CLEAR)
            sleep(blind_wait_time)
            
        # def discover_position_blind_ctrls(mux):
            # set_up_blind_IOexp(mux)
            
            # blind_UP    = 0b00000001
            # blind_MID   = 0b00000010
            # blind_DOWN    = 0b00000100
            # blind_LEFT  = 0b00001000
            # blind_RIGHT   = 0b00010000
            # blind_CLEAR = 0b00000000
            
            # read_sr = 0b000000
            
            # write_byte_reg(extra_8bit_adr, GPIO_REGISTER_8, blind_RIGHT)
            # sleep(blind_wait_time)
            # write_byte_reg(extra_8bit_adr, GPIO_REGISTER_8, blind_CLEAR)
            # sleep(blind_wait_time)
            
            # for i in range(6):
                # write_byte_reg(extra_8bit_adr, GPIO_REGISTER_8, blind_RIGHT)
                # sleep(blind_wait_time)
                # write_byte_reg(extra_8bit_adr, GPIO_REGISTER_8, blind_CLEAR)
                # sleep(blind_wait_time)
                # read_sr = (read_sr << 1) + (read_byte_reg(extra_8bit_adr, GPIO_REGISTER_8) >> 7)
                
            # if read_sr == 0b010001:
                # return 0  # all channels
            # elif read_sr == 0b100010:
                # return 1  # channel 1
            # elif read_sr == 0b000101:
                # return 2  # etc
            # elif read_sr == 0b001010:
                # return 3  
            # elif read_sr == 0b010100:
                # return 4  
            # elif read_sr == 0b101000:
                # return 5  
            # else:
                # return -1
                
        def locate_1_blind_ctrls(mux):
            set_up_blind_IOexp(mux)
            
            blind_UP    = 0b00000001
            blind_MID   = 0b00000010
            blind_DOWN  = 0b00000100
            blind_LEFT  = 0b00001000
            blind_RIGHT = 0b00010000
            blind_CLEAR = 0b00000000
            
            read_sr1 = 0b000000
            read_sr2 = 0b000000
            
            write_byte_reg(extra_8bit_adr, GPIO_REGISTER_8, blind_RIGHT)
            sleep(blind_wait_time)
            write_byte_reg(extra_8bit_adr, GPIO_REGISTER_8, blind_CLEAR)
            sleep(blind_wait_time)
            
            counter = 0
            
            while(((read_sr1 & 0b111) != 0b011) or ((read_sr2 & 0b111) != 0b010)) and (counter <= 20): # max 20 tries to find channel 2
                write_byte_reg(extra_8bit_adr, GPIO_REGISTER_8, blind_RIGHT)
                sleep(blind_wait_time)
                write_byte_reg(extra_8bit_adr, GPIO_REGISTER_8, blind_CLEAR)
                sleep(blind_wait_time) #*2)
                blind_readback = read_byte_reg(extra_8bit_adr, GPIO_REGISTER_8)
                read_sr1 = (read_sr1 << 1) + ((blind_readback >> 6) & 0b1)
                read_sr2 = (read_sr2 << 1) + (blind_readback >> 7)

                print 'sr1: '+format(read_sr1, '06b')+'       sr2: '+format(read_sr2, '06b')
                counter += 1
            
            if counter >= 20:
                print 'wasn\'t able to find channel 1...'
            else:
                print 'found channel 1 in',counter,'presses...'
            
        # def activate_blind(mux, blind_no, current_selected_blind, action):    # action: 0=closed, 1=mid, 2=open
            # set_up_blind_IOexp(mux)
            
            # blind_UP    = 0b00000001
            # blind_MID   = 0b00000010
            # blind_DOWN    = 0b00000100
            # blind_LEFT  = 0b00001000
            # blind_RIGHT   = 0b00010000
            # blind_CLEAR = 0b00000000
            
            # if blind_no >= current_selected_blind:
                # num_left_presses_required = current_selected_blind - (blind_no - 6)
                # num_right_presses_required = blind_no - current_selected_blind
            # else:
                # num_left_presses_required = blind_no - current_selected_blind
                # num_right_presses_required = (blind_no + 6) - current_selected_blind
                
            # if num_left_presses_required >= num_right_presses_required:
                # for i in range(num_right_presses_required):
                    # write_byte_reg(extra_8bit_adr, GPIO_REGISTER_8, blind_RIGHT)
                    # sleep(blind_wait_time)
                    # write_byte_reg(extra_8bit_adr, GPIO_REGISTER_8, blind_CLEAR)
                    # sleep(blind_wait_time)
            # else:
                # for i in range(num_left_presses_required):
                    # write_byte_reg(extra_8bit_adr, GPIO_REGISTER_8, blind_LEFT)
                    # sleep(blind_wait_time)
                    # write_byte_reg(extra_8bit_adr, GPIO_REGISTER_8, blind_CLEAR)
                    # sleep(blind_wait_time)
                    
            # if action == 2:
                # write_byte_reg(extra_8bit_adr, GPIO_REGISTER_8, blind_UP)
                # sleep(blind_wait_time)
                # write_byte_reg(extra_8bit_adr, GPIO_REGISTER_8, blind_CLEAR)
                # sleep(blind_wait_time)
            # elif action == 1:
                # write_byte_reg(extra_8bit_adr, GPIO_REGISTER_8, blind_MID)
                # sleep(blind_wait_time)
                # write_byte_reg(extra_8bit_adr, GPIO_REGISTER_8, blind_CLEAR)
                # sleep(blind_wait_time)
            # else:
                # write_byte_reg(extra_8bit_adr, GPIO_REGISTER_8, blind_DOWN)
                # sleep(blind_wait_time)
                # write_byte_reg(extra_8bit_adr, GPIO_REGISTER_8, blind_CLEAR)
                # sleep(blind_wait_time)
                
            # return blind_no
            
        # def activate_blind_with_delay(mux, blind_no, action): # action: 0=closed, 1=mid, 2=open
            # set_up_blind_IOexp(mux)
            
            # blind_UP    = 0b00000001
            # blind_MID   = 0b00000010
            # blind_DOWN    = 0b00000100
            # blind_LEFT  = 0b00001000
            # blind_RIGHT   = 0b00010000
            # blind_CLEAR = 0b00000000
            
            # if blind_no >= 2:
                # num_left_presses_required = 2 - (blind_no - 6)
                # num_right_presses_required = blind_no - 2
            # else:
                # num_left_presses_required = 2 - blind_no
                # num_right_presses_required = (blind_no + 6) - 2
                
            # if (num_left_presses_required == 0) or (num_right_presses_required == 0):
                # return_direction = 0
                # #print 'no presses required'
                # pass
            # elif num_left_presses_required >= num_right_presses_required:
                # return_direction = 1
                # num_left_presses_required = num_right_presses_required
                # if not(read_byte_reg(extra_8bit_adr, GPIO_REGISTER_8) >> 7):
                    # num_right_presses_required += 1
                # #print num_right_presses_required,'right presses required'
                # for i in range(num_right_presses_required):
                    # write_byte_reg(extra_8bit_adr, GPIO_REGISTER_8, blind_RIGHT)
                    # sleep(blind_wait_time)
                    # write_byte_reg(extra_8bit_adr, GPIO_REGISTER_8, blind_CLEAR)
                    # sleep(blind_wait_time)
            # else:
                # return_direction = 2
                # num_right_presses_required = num_left_presses_required
                # if not(read_byte_reg(extra_8bit_adr, GPIO_REGISTER_8) >> 7):
                    # num_left_presses_required += 1
                # #print num_left_presses_required,'left presses required'
                # for i in range(num_left_presses_required):
                    # write_byte_reg(extra_8bit_adr, GPIO_REGISTER_8, blind_LEFT)
                    # sleep(blind_wait_time)
                    # write_byte_reg(extra_8bit_adr, GPIO_REGISTER_8, blind_CLEAR)
                    # sleep(blind_wait_time)
                    
            # if action == 2:
                # #print 'pressing up'
                # write_byte_reg(extra_8bit_adr, GPIO_REGISTER_8, blind_UP)
                # sleep(blind_wait_time)
                # write_byte_reg(extra_8bit_adr, GPIO_REGISTER_8, blind_CLEAR)
                # sleep(blind_wait_time)
            # elif action == 1:
                # #print 'pressing mid'
                # write_byte_reg(extra_8bit_adr, GPIO_REGISTER_8, blind_MID)
                # sleep(blind_wait_time)
                # write_byte_reg(extra_8bit_adr, GPIO_REGISTER_8, blind_CLEAR)
                # sleep(blind_wait_time)
            # else:
                # #print 'pressing down'
                # write_byte_reg(extra_8bit_adr, GPIO_REGISTER_8, blind_DOWN)
                # sleep(blind_wait_time)
                # write_byte_reg(extra_8bit_adr, GPIO_REGISTER_8, blind_CLEAR)
                # sleep(blind_wait_time)
                
            # if return_direction == 1:
                # num_left_presses_required += 1
                # #print num_left_presses_required,'left presses required to return to ch 2'
                # for i in range(num_left_presses_required):
                    # write_byte_reg(extra_8bit_adr, GPIO_REGISTER_8, blind_LEFT)
                    # sleep(blind_wait_time)
                    # write_byte_reg(extra_8bit_adr, GPIO_REGISTER_8, blind_CLEAR)
                    # sleep(blind_wait_time)
            # elif return_direction == 2:
                # num_right_presses_required += 1
                # #print num_right_presses_required,'right presses required to return to ch 2'
                # for i in range(num_right_presses_required):
                    # write_byte_reg(extra_8bit_adr, GPIO_REGISTER_8, blind_RIGHT)
                    # sleep(blind_wait_time)
                    # write_byte_reg(extra_8bit_adr, GPIO_REGISTER_8, blind_CLEAR)
                    # sleep(blind_wait_time)
            
            # sleep(1)
            # # verify back at ch 2
            # if not(read_byte_reg(extra_8bit_adr, GPIO_REGISTER_8) >> 7):
                # locate_1_blind_ctrls(mux)
                
        def activate_blind(mux, blind_no, action, sv, pause, pause_counter, movingleft, numpresses, returnpresses, starting_pos, blind_ts, test_led_or_reduce, test_led2_or_reduce): # action: 0=closed, 1=mid, 2=open
            #print 'mux:',mux, 'blind_no:',blind_no, 'action:',action, 'sv:',sv, 'pause:',pause, 'pause_counter:',pause_counter,'movingleft:', movingleft, 'numpresses:',numpresses, 'returnpresses:',returnpresses
            if pause[0]:
                if sv[0] == 7:
                    #print 'pause_counter:',pause_counter,
                    set_i2c_mux(mux)
                    blind_readback = read_byte_reg(extra_8bit_adr, GPIO_REGISTER_8)
                    test_led = ((blind_readback >> 6) & 0b1)
                    test_led2 = (blind_readback >> 7)
                    #print '\ttest_led:',test_led,
                    #print '\ttest_led2:',test_led2
                    test_led_or_reduce[0] = test_led_or_reduce[0] or test_led
                    test_led2_or_reduce[0] = test_led2_or_reduce[0] or test_led2

                if pause_counter[0] >= 1:
                    pause_counter[0] -= 1
                if pause_counter[0] == 0:
                    pause[0] = False
            else:
                blind_UP    = 0b00000001
                blind_MID   = 0b00000010
                blind_DOWN  = 0b00000100
                blind_LEFT  = 0b00001000
                blind_RIGHT = 0b00010000
                blind_CLEAR = 0b00000000
                
                #pause[0] = True
                #pause_counter[0] = 1
                
                if sv[0] == 0:
                    set_up_blind_IOexp(mux)

                    # print
                    # print 'Info passed in:'
                    # print 'blind_no:',blind_no
                    # print 'starting_pos:',starting_pos         
                
                    if blind_no >= starting_pos:
                        num_left_presses_required = starting_pos - (blind_no - 6)
                        num_right_presses_required = blind_no - starting_pos
                        if blind_no >= 1:
                            num_left_presses_home = 1 - (blind_no - 6)
                            num_right_presses_home = blind_no - 1
                        else:
                            num_left_presses_home = 1 - blind_no
                            num_right_presses_home = (blind_no + 6) - 1
                    else:
                        num_left_presses_required = starting_pos - blind_no
                        num_right_presses_required = (blind_no + 6) - starting_pos
                        if blind_no >= 1:
                            num_left_presses_home = 1 - (blind_no - 6)
                            num_right_presses_home = blind_no - 1
                        else:
                            num_left_presses_home = 1 - blind_no
                            num_right_presses_home = (blind_no + 6) - 1
                        
                    if (num_right_presses_required == 0):
                        movingleft[0] = False
                        numpresses[0] = 0
                        returnpresses[0] = num_right_presses_home
                        pause[0] = False
                        sv[0] = 3

                    elif (num_left_presses_required == 0):
                        movingleft[0] = True
                        numpresses[0] = 0
                        returnpresses[0] = num_left_presses_home
                        pause[0] = False
                        sv[0] = 3
                        
                    elif num_left_presses_required >= num_right_presses_required:
                        movingleft[0] = False
                        #if action == 0:
                        returnpresses[0] = num_right_presses_home
                        #else:
                        #   returnpresses[0] = num_right_presses_required + 1
                        blind_readback = read_byte_reg(extra_8bit_adr, GPIO_REGISTER_8)
                        test_led = ((blind_readback >> 6) & 0b1)
                        #test_led2 = (blind_readback >> 7) 
                        #print 'test_led:',test_led
                        if (not test_led) and (starting_pos == 1):
                            num_right_presses_required += 1
                        numpresses[0] = num_right_presses_required
                        
                        write_byte_reg(extra_8bit_adr, GPIO_REGISTER_8, blind_RIGHT)
                            
                        sv[0] = 1
                        pause[0] = True
                        pause_counter[0] = 1
                        numpresses[0] -= 1
                        
                    else:
                        movingleft[0] = True
                        #if action == 0:
                        returnpresses[0] = num_left_presses_home
                        #else:
                        #   returnpresses[0] = num_left_presses_required + 1
                        blind_readback = read_byte_reg(extra_8bit_adr, GPIO_REGISTER_8)
                        test_led = ((blind_readback >> 6) & 0b1)
                        #test_led2 = (blind_readback >> 7)
                        #print 'test_led:',test_led
                        if (not test_led) and (starting_pos == 1):
                            num_left_presses_required += 1
                        numpresses[0] = num_left_presses_required
                            
                        write_byte_reg(extra_8bit_adr, GPIO_REGISTER_8, blind_LEFT)
                        
                        sv[0] = 1
                        pause[0] = True
                        pause_counter[0] = 1
                        numpresses[0] -= 1

                    # print
                    # print 'Decisions made:'
                    # print 'movingleft:',movingleft
                    # print 'numpresses:',numpresses
                    # print 'returnpresses:',returnpresses
                
                elif sv[0] == 1:
                    set_i2c_mux(mux)
                    write_byte_reg(extra_8bit_adr, GPIO_REGISTER_8, blind_CLEAR)
                    if numpresses[0] >= 1:
                        sv[0] = 2
                    else:
                        sv[0] = 3
                    pause[0] = True
                    pause_counter[0] = 1
                    
                elif sv[0] == 2:
                    set_i2c_mux(mux)
                    if movingleft[0]:
                        write_byte_reg(extra_8bit_adr, GPIO_REGISTER_8, blind_LEFT)
                    else:
                        write_byte_reg(extra_8bit_adr, GPIO_REGISTER_8, blind_RIGHT)
                        
                    sv[0] = 1
                    pause[0] = True
                    pause_counter[0] = 1
                    numpresses[0] -= 1
                    
                elif sv[0] == 3:
                    set_i2c_mux(mux)
                    if action == 2:
                        #print 'pressing up'
                        write_byte_reg(extra_8bit_adr, GPIO_REGISTER_8, blind_UP)
                    elif action == 1:
                        #print 'pressing mid'
                        write_byte_reg(extra_8bit_adr, GPIO_REGISTER_8, blind_MID)
                    else:
                        #print 'pressing down'
                        write_byte_reg(extra_8bit_adr, GPIO_REGISTER_8, blind_DOWN)
                    sv[0] = 4
                    pause[0] = True
                    pause_counter[0] = 1    # can increase delay here if want to give time for pressing a few blinds
                        
                elif sv[0] == 4:
                    set_i2c_mux(mux)
                    write_byte_reg(extra_8bit_adr, GPIO_REGISTER_8, blind_CLEAR)
                    if returnpresses[0] == 0:
                        sv[0] = 9#8   # end
                        pause_counter[0] = 20
                    else:
                        sv[0] = 10#5
                        pause_counter[0] = 20#1
                    pause[0] = True

                # here is where we check (in the main script) if there are more blinds to be actioned

                elif sv[0] == 10:
                    sv[0] = 5
                    
                elif sv[0] == 5:
                    set_i2c_mux(mux)
                    if movingleft[0]:
                        write_byte_reg(extra_8bit_adr, GPIO_REGISTER_8, blind_RIGHT)
                    else:
                        write_byte_reg(extra_8bit_adr, GPIO_REGISTER_8, blind_LEFT)
                        
                    sv[0] = 6
                    pause[0] = True
                    pause_counter[0] = 1
                    returnpresses[0] -= 1
                    
                elif sv[0] == 6:
                    set_i2c_mux(mux)
                    write_byte_reg(extra_8bit_adr, GPIO_REGISTER_8, blind_CLEAR)
                    if returnpresses[0] >= 1:
                        sv[0] = 5
                        pause_counter[0] = 1
                    else:
                        sv[0] = 7
                        test_led_or_reduce[0] = False
                        test_led2_or_reduce[0] = False
                        pause_counter[0] = 20 #5 #17
                    pause[0] = True
                
                elif sv[0] == 7:
                    # set_i2c_mux(mux)
                    # blind_readback = read_byte_reg(extra_8bit_adr, GPIO_REGISTER_8)
                    # test_led = ((blind_readback >> 6) & 0b1)
                    # test_led2 = (blind_readback >> 7)
                    #print 'test_led:',test_led
                    if ((not test_led_or_reduce[0]) or (test_led_or_reduce[0] and test_led2_or_reduce[0])):  # verify back at ch 1 and not at ch 6 (all)
                        print 'not back at 1, running discovery...'
                        locate_1_blind_ctrls(mux)
                        #if action == 2 or action == 0
                        #print '...and repeating command'
                        #sv[0] = 0
                        print '...and resetting all blind timestamps'
                        #sv[0] = 0
                        for blindi in range(len(blind_ts)):
                            blind_ts[blindi] = 0
                        log_error('Not back at channel 1 after executing blind command. Locating and trying again...')
                        #else:
                        #   sv[0] = 8   # don't want to repeat command if moving to centre
                    #else:
                    sv[0] = 8

                else:
                    sv[0] = 8

        if path.isfile(r'/var/lib/homebridge/input_control/debug'):
            debug = True
            remove(r'/var/lib/homebridge/input_control/debug')
        else:
            debug = False
        debug_press = False
        debug_persist = False

        f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_Crash_Alert_MotionDetected','w')
        f.write('0')
        f.close()
        
        if calculate_optimal_sleep_time:
            loop_time_start = 0
            loop_time_sum = 0
            loop_count = 0

        for i in range(num_boards):
            GPIO.setup(interrupt_pins[i], GPIO.IN)  # interrupt from IO expanders - active LOW
            
        #i2c_mux_pins = [21,22,23,24,26]
        GPIO.setup(21, GPIO.OUT)
        GPIO.setup(22, GPIO.OUT)
        GPIO.setup(23, GPIO.OUT)
        GPIO.setup(24, GPIO.OUT)
        GPIO.setup(26, GPIO.OUT)

        GPIO.setup(29, GPIO.OUT)
        GPIO.output(29, GPIO.LOW)
        if (not is_master):
            GPIO.setup(31, GPIO.OUT)
            GPIO.output(31, GPIO.LOW)
            new_ts_rpi2 = stat(r'/var/lib/homebridge/heartbeat_rpi2').st_mtime
            last_ts_rpi2 = stat(r'/var/lib/homebridge/heartbeat_rpi2').st_mtime
            test_rpi2_this_time = False
        
        set_i2c_mux(-1) # reset both i2c muxes
        
        GPIO.output(21, GPIO.LOW)   #
        GPIO.output(22, GPIO.LOW)   # with these three low, i2c mux adr = 0x70 & 0x71. Can change address here if needed
        GPIO.output(23, GPIO.LOW)   #
        
        set_i2c_mux(-1) # reset i2c mux on start

        bed = True

        for i in range(num_boards):
            for j in range(8):
                RELAY_STATE[i][j] = path.isfile(r'/var/lib/homebridge/relay_'+str(i)+'/'+str(j))
            refresh_config(i)
            read_status(i)
            check_ind_status(i)
            initial_states(i, bed)

        if num_board_3:
            for j in range(num_board_3*4):
                RELAY_STATE[3][j] = path.isfile(r'/var/lib/homebridge/relay_3/'+str(j))
        
        #print RELAY_STATE[3]

        if num_board_3:
            new_ts_switch = [0]*(num_boards+1)
            last_ts_switch = [0]*(num_boards+1)
        else:
            new_ts_switch = [0]*num_boards
            last_ts_switch = [0]*num_boards

        new_ts_dimmer = [0]*num_dimmers
        last_ts_dimmer = [0]*num_dimmers
        new_ts_brightness = [0]*num_dimmers
        last_ts_brightness = [0]*num_dimmers

        new_ts_socket = [0]*num_sockets
        last_ts_socket = [0]*num_sockets

        new_ts_ind = [0]*num_boards
        last_ts_ind = [0]*num_boards

        new_ts_control = 0

        UDP_IP = cfg.destIP #"192.168.1.33" #"127.0.0.1" # set it to destination IP.. RPi in this case
        UDP_IP2 = cfg.destIP2   # Homebridge 2
        UDP_PORT = cfg.destUDP #52345
        UDP_PORT2 = cfg.destUDP2
        led_strip_UDP_port = 56700

        sock = False
        while not sock:
            try:
                sock = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
            except:
                print 'Failed to open network connection. Retrying...'
                sleep(1)
                
        sock.bind(led_response)
        sock.settimeout(0.2)
        
        counter = 0
        max_counter = 100   # 5 sec
        core_counter = 0

        turn_off_nightlight_dimmer = [False]*num_dimmers
        last_core_temp = '0'

        temperature = [0]*numtemp
        humidity = [0]*numtemp
        temp_prec = [0.0]*numtemp
        hum_prec = [0.0]*numtemp
        last_temperature = [-51]*numtemp
        last_humidity = [-1]*numtemp

        air_qual_eco2 = [0]*num_air_qual
        air_qual_etvoc = [0]*num_air_qual
        last_eco2 = [-1]*num_air_qual
        last_etvoc = [-1]*num_air_qual
        peak_eco2 = [0]*num_air_qual

        air_quality_config_delay = 150
        
        loopLEDval = True
        GPIO.setup(12, GPIO.OUT)    # LOOP LED
        GPIO.output(12, loopLEDval)
        
        button_input = [False]*(num_buttons_p_num_special_buttons)
        button_state = [0]*(num_buttons_p_num_special_buttons)
        button_timer = [0]*(num_buttons_p_num_special_buttons)
        button_timeout = [0]*(num_buttons_p_num_special_buttons)
        button_long_timer = [0]*(num_buttons_p_num_special_buttons)
        button = [0]*(num_buttons_p_num_special_buttons)
        
        button_flashing = [False]*num_buttons
        button_flashing_timer = [0]*num_buttons
        button_scene = [1]*num_buttons
        led_flash_variable = False
        led_flash_counter = 0
        led_flash_period = 10 # in loop cycles * 2
        button_fast_flash_state = [True]*(num_buttons_p_num_special_buttons)
        button_fast_flash_counter = [0]*(num_buttons_p_num_special_buttons)
        
        toggle_button_last = [False]*num_toggle_buttons
        
        for i in range(num_toggle_buttons):
            set_i2c_mux(IOmux[toggle_button[i][0]])
            IO_temp = read_byte_reg(io_adr, 0x00) & 0xF # only interested in lower 4 bits
            mask = 0b1 << toggle_button[i][1]
            toggle_button_last[i] = IO_temp & mask == mask
            
        set_i2c_mux(-1) # reset all i2c mux channels
        
        #print 'toggle_button_last[0]:',toggle_button_last[0]
        
        getAllLEDip(led_retry_pwr, num_led_strips, led_mac, led_strips, led_retry, first_time_led_locate)
        led_status_indicator = True
        for i in range(num_led_strips):
            if led_retry[i]:
                led_status_indicator = False
        
        if led_status_indicator:
            GPIO.output(29, GPIO.HIGH)

        new_ts_led_strip = [0]*num_led_strips
        last_ts_led_strip = [0]*num_led_strips
        new_ts_led_strip_brightness = [0]*num_led_strips
        last_ts_led_strip_brightness = [0]*num_led_strips
        new_ts_led_strip_hue = [0]*num_led_strips
        last_ts_led_strip_hue = [0]*num_led_strips
        new_ts_led_strip_sat = [0]*num_led_strips
        last_ts_led_strip_sat = [0]*num_led_strips
        #last_colour = [0]*num_led_strips
        #next_colour = [0]*num_led_strips
        #ftb_flag = [False]*num_led_strips
        #next_index = [0]*num_led_strips
        #next_led_span = [0]*num_led_strips
        #next_time = [0]*num_led_strips
        saturation_set = [0]*num_led_strips
        hue_set = [0]*num_led_strips
        saturation_set_f = [0.0]*num_led_strips
        hue_set_f = [0.0]*num_led_strips
        master_brightness = [0.0]*num_led_strips
        
        blind_ts = [0]*num_blinds
        blind_ts_last = [0]*num_blinds
        blind_set_to_middle = [False] * num_blinds
        
        time_min = 5
        time_max = 10
        time_min_long = 45
        time_max_long = 60
        colour_library = [0]*num_led_strips
        
        alert_ended = False
        alert_state = False
        
        fire_alarm = False
        fire_alarm_last = False
        fire_lights_prev_status = [False]*num_fire_lights
        doorbell = False
        doorbell_press = False
        doorbell_last = False
        doorbell_timer = 0
        
        bed_last = False
        PIR_activity_last = False
        special_PIR_activity_last = False
        evening_lights_not_activated = True
        package_garage = False
        package_garage_last = False
        package_garage_timer = 0
        garage_door_open_package = False

        do_not_disturb = False
        dnd_suppress_doorbell_msg = False
        clear_dnd_msg = False
        clear_dnd_msg2 = True
        temporarily_enable_doorbell = False
        enable_doorbell_timeout = 0
        
        security_enabled = False
        disarm_security_lights_on_sunrise = False

        if path.isfile(r'/var/lib/homebridge/input_control/FDS'):
            first_downstairs = True
        else:
            first_downstairs = False

        suppress_first_downstairs = False
        
        theme_activated = [False]*num_led_strips
        
        current_hour = 24
        
        for i in range(num_led_strips):
            f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_Led_Strip_'+str(i)+'_On','r')
            value = f.readline()
            f.close()
            if 'true' in value:
                led_strip_power[i] = True
            else:
                led_strip_power[i] = False
        
        night_time = False
        morning = False
        if path.isfile(r'/var/lib/homebridge/input_control/going_to_bed_nv'):
            going_to_bed = True
        else:
            going_to_bed = False

        if path.isfile(r'/var/lib/homebridge/input_control/left_house_nv'):
            left_house = True
            sock.sendto('write:input_control/:left_house:', (UDP_IP, UDP_PORT))
        else:
            left_house = False
            sock.sendto('delete:input_control/:left_house:', (UDP_IP, UDP_PORT))

        left_house_hold_off = 0
        welcome_home = False
        welcome_sitting = False
        welcome_kitchen = False
        welcome_landing = False
        refresh_all_indicators = False

        bedroom_ultra_dark = False
        bedroom_ultra_dark_not_actioned_yet = True
        bedroom_ultra_dark_time = 6 # must be greater than 2. Else adjust time that bathroom goes off below
        bedroom_ultra_dark_timer = bedroom_ultra_dark_time
        
        #print 'test'
        #print num_dimmers
        shower_temp_not_reached = True
        shower_change_to_pink = False
        shower_temp_last_2 = 99
        shower_temp_last = 99
        shower_temp = 99
        after_shower_bedroom_lights = False
        after_shower = False

        if len(post_box):
            set_i2c_mux(post_box[0])
            post_readback = read_byte_reg(extra_8bit_adr, GPIO_REGISTER_8)
            last_post_flag = (post_readback >> (post_box[1]+post_box[2])) & 0b1
            #print 'last_post_flag on power up:',last_post_flag
            deassert_post_box = False

        board_3_timer = 0
                
        for i in range(num_board_3):
            refresh_board_3_config(board_3[i])
            initial_states_board_3(board_3[i])

        # sleep(0.1)
        # custom_states_board_3(board_3[0])
        # sleep(0.1)
        # initial_states_board_3(board_3[0])
        
        if num_blinds:
            locate_1_blind_ctrls(blinds[0])
            sv = [0]
            pause = [False]
            pause_counter = [0]
            movingleft = [False]
            test_led_or_reduce = [False]
            test_led2_or_reduce = [False]
            numpresses = [0]
            returnpresses = [0]
            old_blind_number_store = 1

        blind_update_not_found = True
        blind_busy = False
        #blind_timeout_after = False
        #blind_timeout = 120
        #blind_timeout_after_counter = blind_timeout
        #btc_enable = True
        #f = open(r'/var/lib/homebridge/input_control/btc_enable','w')
        #f.close()

        if garage_control:
            set_i2c_mux(IOmux[garage_io[0][0]])
                        
            garage_pulse = 0b1 << garage_io[0][1]
            write_byte_reg(io_adr, 0x1, 0x0)                    # output port
            write_byte_reg(io_adr, 0x3, (garage_pulse ^ 0xF))   # config (dir)

        for i in range(num_air_qual):
            set_i2c_mux(air_qual[i][0])
            write_byte_retry(air_qual_adr, 0xF4)              # APP_START
            write_byte_reg_retry(air_qual_adr, 0x01, 0x00)    # set air quality sensor into mode 0 - needs to stay here for 10 mins before entering mode 3

        block_air_qual_reading = False
        alarm_reminder_not_given = False
        reset_alarm_reminder_not_given = True

        turn_on_active_nightlights = False

        extractor_on = STATUS[extractor[0]][extractor[1]]
        if extractor_on:
            extractor_timer = 20

        set_i2c_mux(-1) # reset i2c mux
        
        while True:
            # CHECK INPUTS FROM PHYSICAL SWITCHES
            for i in range(num_boards):
                if not(GPIO.input(interrupt_pins[i])) or refresh_all_indicators: # bring in periodic checking, careful that not only first board gets checked by periodic checker
                    read_status(i)
                    for j in range(8):
                        if (LAST_STATUS[i][j] != STATUS[i][j]) or refresh_all_indicators:
                            non_scene_button = True
                            for k in range(num_buttons):
                                if (button_led_ind[k][0] == i) and (button_led_ind[k][1] == j):
                                    non_scene_button = False
                            for k in range(num_special_buttons):
                                if (special_button_led[k][0] == i) and (special_button_led[k][1] == j):
                                    non_scene_button = False
                            if STATUS[i][j]:    # if ON
                                if (not(i == FAN[0] and j == FAN[1])) and non_scene_button:
                                    if bed:
                                        set_one_led(i, j, IND_SETTING[1][INDICATOR_TYPE[i][j]][1])
                                    else:
                                        set_one_led(i, j, IND_SETTING[0][INDICATOR_TYPE[i][j]][1])
                                if (not path.isfile(r'/var/lib/homebridge/state_'+str(i)+'/'+str(j))):
                                    f = open(r'/var/lib/homebridge/state_'+str(i)+'/'+str(j),'w')
                                    f.close()
                                if TRANSFER_STATUS[i][j] != -1:
                                    sock.sendto('write:input_control/:'+str(TRANSFER_STATUS[i][j])+':', (UDP_IP, UDP_PORT)) # pass on channel status to other board

                                # if is_master and i==0 and j==2: # DS bathroom light
                                #     if ACTIVATED_AS_NIGHTLIGHT[0][2] and (not PIR[4][0]):   # if no motion detected and is currently activated as night light
                                #         ACTIVATED_AS_NIGHTLIGHT[0][2] = False   # remove night light status - way to cancel night light operation (by flicking on and off switch)

                            else:               # if OFF
                                if (not(i == FAN[0] and j == FAN[1])) and non_scene_button:
                                    if bed:
                                        set_one_led(i, j, IND_SETTING[1][INDICATOR_TYPE[i][j]][0])
                                    else:
                                        set_one_led(i, j, IND_SETTING[0][INDICATOR_TYPE[i][j]][0])
                                if path.isfile(r'/var/lib/homebridge/state_'+str(i)+'/'+str(j)):
                                    remove(r'/var/lib/homebridge/state_'+str(i)+'/'+str(j))
                                if TRANSFER_STATUS[i][j] != -1:
                                    sock.sendto('delete:input_control/:'+str(TRANSFER_STATUS[i][j])+':', (UDP_IP, UDP_PORT)) # pass on channel status to other board
                    #print 'Board',i,'status:', STATUS[i]
            
            refresh_all_indicators = False
            # CHECK INPUTS FROM HOMEBRIDGE SWITCHES
            for i in range(num_boards):
                last_ts_switch[i] = new_ts_switch[i]
                new_ts_switch[i] = stat(r'/var/lib/homebridge/input_'+str(i)).st_mtime
                if (last_ts_switch[i] != new_ts_switch[i]): # or (counter > 40):    # bring in periodic checking
                    # take action
                    read_status(i)
                    for j in range(8):
                        non_dimmer_or_socket = True   
                        for k in range(num_dimmers):
                            if (DIMMER_SWITCH[k][0] == i) and (DIMMER_SWITCH[k][1] == j):
                                non_dimmer_or_socket = False

                            if k < num_sockets:
                                if (powersocket[k][0] == i) and (powersocket[k][1] == j):
                                    #print 'switch ['+str(i)+']['+str(j)+'] is a socket'
                                    non_dimmer_or_socket = False
                                
                        if non_dimmer_or_socket:
                            if path.isfile(r'/var/lib/homebridge/input_'+str(i)+'/'+str(j)):
                                ### trying to remove night light status of ds bathroom if turned on by siri
                                ## Won't work at present:
                                # 1) This code will disable the night light immediately - but doesn't seem to work, not sure why
                                # 2) More critically - siri does not update file when you ask to turn on light that is already on
                                #
                                # print i,j,'file active'
                                # if ACTIVATED_AS_NIGHTLIGHT[i][j]:
                                #     print i,j,'nightlight active'
                                #     print stat(r'/var/lib/homebridge/input_'+str(i)+'/'+str(j)).st_mtime 
                                #     print last_ts_switch[i]
                                #     if stat(r'/var/lib/homebridge/input_'+str(i)+'/'+str(j)).st_mtime > last_ts_switch[i]:
                                #         print 'turning off nightlight coord',i,j
                                #         ACTIVATED_AS_NIGHTLIGHT[i][j] = False # remove night light status
                                #         for h in range(num_night_lights):
                                #             if (i == NIGHT_LIGHTS[h][2]) and (j == NIGHT_LIGHTS[h][3]):
                                #                 print 'turning off nightlight index',h
                                #                 night_light_activated[h] = False
                                #                 night_light_timer[h] = 0
                                ###
                                if not STATUS[i][j]:
                                    if (not RELAY_QUEUE[i][j][0]):  # only increment queue size if the relay is not already on the queue
                                        QUEUED_RELAYS += 1
                                    RELAY_QUEUE[i][j][0] = True # Relay action queued
                                    RELAY_QUEUE[i][j][1] = True # power ON

                                    ###########################################
                                    # if (not is_master) and (i==0) and (j==2):
                                    #     f = open('/var/lib/homebridge/zen_den.log','a')
                                    #     f.write('Zen den homebridge file written at ')
                                    #     now = datetime.now()
                                    #     f.write(now.strftime("%d/%m/%Y %H:%M:%S\n"))
                                    #     f.close()
                                    ###########################################

                            else:
                                if STATUS[i][j]:
                                    if (not RELAY_QUEUE[i][j][0]):
                                        QUEUED_RELAYS += 1
                                    RELAY_QUEUE[i][j][0] = True # Relay action queued
                                    RELAY_QUEUE[i][j][1] = False # power OFF

            if board_3_timer:
                if board_3_timer == 1:
                    for i in range(num_board_3):
                        set_i2c_mux(board_3[i])
                        write_byte_reg(extra_8bit_adr, GPIO_REGISTER_8, 0x0)
                    board_3_timer = 0
                    #print 'board 3 relays reset'
                else:
                    board_3_timer -= 1
            if num_board_3:
                last_ts_switch[3] = new_ts_switch[3]
                new_ts_switch[3] = stat(r'/var/lib/homebridge/input_3').st_mtime
                if (last_ts_switch[3] != new_ts_switch[3]):
                    for i in range(num_board_3):
                        val_board_3 = 0
                        for h in range(4):
                            j = h+(i*4)
                            if path.isfile(r'/var/lib/homebridge/input_3/'+str(j)):
                                if not RELAY_STATE[3][j]:
                                    #print 'turn on board 3 relay '+str(j)
                                    val_board_3 += (0b1 << (h*2))

                                    RELAY_STATE[3][j] = True
                                    system(r'touch /var/lib/homebridge/relay_3/'+str(j))
                            else:
                                if RELAY_STATE[3][j]:
                                    #print 'turn off board 3 relay '+str(j)
                                    val_board_3 += (0b10 << (h*2))

                                    RELAY_STATE[3][j] = False
                                    if path.isfile(r'/var/lib/homebridge/relay_3/'+str(j)):
                                        remove(r'/var/lib/homebridge/relay_3/'+str(j))

                        #print 'val to write is '+hex(val_board_3)
                        if val_board_3:
                            set_i2c_mux(board_3[i])
                            write_byte_reg(extra_8bit_adr, GPIO_REGISTER_8, val_board_3)
                            board_3_timer = 3

            # CHECK INPUTS FROM HOMEBRIDGE SOCKETS
            for i in range(num_sockets):
                last_ts_socket[i] = new_ts_socket[i]
                new_ts_socket[i] = stat(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_Outlet_'+str(i)+'_On').st_mtime
                if (last_ts_socket[i] != new_ts_socket[i]):
                    f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_Outlet_'+str(i)+'_On','r')
                    value = f.readline()
                    f.close()
                    if 'true' in value:
                        if (not RELAY_QUEUE[powersocket[i][0]][powersocket[i][1]][0]):
                            QUEUED_RELAYS += 1
                        RELAY_QUEUE[powersocket[i][0]][powersocket[i][1]][0] = True # Relay action queued
                        RELAY_QUEUE[powersocket[i][0]][powersocket[i][1]][1] = True # power ON

                    else:
                        if (not RELAY_QUEUE[powersocket[i][0]][powersocket[i][1]][0]):
                            QUEUED_RELAYS += 1
                        RELAY_QUEUE[powersocket[i][0]][powersocket[i][1]][0] = True  # Relay action queued
                        RELAY_QUEUE[powersocket[i][0]][powersocket[i][1]][1] = False # power OFF

            # CHECK INPUTS FROM HOMEBRIDGE DIMMERS
            for i in range(num_dimmers):
                last_ts_dimmer[i] = new_ts_dimmer[i]
                new_ts_dimmer[i] = stat(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_Dimmer_'+str(i)+'_On').st_mtime
                if (last_ts_dimmer[i] != new_ts_dimmer[i]) or turn_off_nightlight_dimmer[i]:
                    f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_Dimmer_'+str(i)+'_On','r')
                    value = f.readline()
                    f.close()
                    if 'true' in value:
                        if (not RELAY_QUEUE[DIMMER_SWITCH[i][0]][DIMMER_SWITCH[i][1]][0]):
                            QUEUED_RELAYS += 1
                        RELAY_QUEUE[DIMMER_SWITCH[i][0]][DIMMER_SWITCH[i][1]][0] = True # Relay action queued
                        RELAY_QUEUE[DIMMER_SWITCH[i][0]][DIMMER_SWITCH[i][1]][1] = True # power ON

                        f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_Dimmer_'+str(i)+'_Brightness','r')
                        value = f.readline()
                        f.close()
                        try:
                            DIMMER_SET_BRIGHTNESS[i] = float(value)/100.0
                            #print 'Dimmer brightness set to '+value+'%'
                        except:
                            new_ts_brightness[i] = 0
                            print 're-reading dimmer brightness inside ON loop...'
                    else:
                        DIMMER_SET_BRIGHTNESS[i] = 0    # fade out rather than turn off
                        
                last_ts_brightness[i] = new_ts_brightness[i]
                new_ts_brightness[i] = stat(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_Dimmer_'+str(i)+'_Brightness').st_mtime
                if (last_ts_brightness[i] != new_ts_brightness[i]) and STATUS[DIMMER_SWITCH[i][0]][DIMMER_SWITCH[i][1]] and not(turn_off_nightlight_dimmer[i]):
                    f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_Dimmer_'+str(i)+'_Brightness','r')
                    value = f.readline()
                    f.close()
                    try:
                        DIMMER_SET_BRIGHTNESS[i] = float(value)/100.0
                        #print 'Dimmer brightness set to '+value+'%'
                    except:
                        print 're-reading dimmer brightness...'
                        new_ts_brightness[i] = 0
                        #DIMMER_SET_BRIGHTNESS[i] = float(value[:-1])/100.0
                    
                if turn_off_nightlight_dimmer[i]:
                    turn_off_nightlight_dimmer[i] = False
            
            #HANDLE DIMMER FADES
            for i in range(num_dimmers):
                if (DIMMER_SET_BRIGHTNESS[i] != DIMMER_CURRENT_BRIGHTNESS[i]):
                    if DIMMER_CURRENT_BRIGHTNESS[i] == 0.0 and DIM_PROFILE[i] == 1:
                        set_wait_power_up = True
                        #print 'wait power up SET'
                    else:
                        set_wait_power_up = False
                    
                    if wait_power_up[i] == 0:
                        if DIMMER_CURRENT_BRIGHTNESS[i] < DIMMER_SET_BRIGHTNESS[i]:
                            inc = float(UP_DOWN_SPEED[i][0]) / 100.0
                            if inc < (DIMMER_SET_BRIGHTNESS[i] - DIMMER_CURRENT_BRIGHTNESS[i]):
                                DIMMER_CURRENT_BRIGHTNESS[i] += inc
                            else:
                                DIMMER_CURRENT_BRIGHTNESS[i] = DIMMER_SET_BRIGHTNESS[i]
                        else:
                            inc = float(UP_DOWN_SPEED[i][1]) / 100.0
                            if inc < (DIMMER_CURRENT_BRIGHTNESS[i] - DIMMER_SET_BRIGHTNESS[i]):
                                DIMMER_CURRENT_BRIGHTNESS[i] -= inc
                            else:
                                DIMMER_CURRENT_BRIGHTNESS[i] = DIMMER_SET_BRIGHTNESS[i]
                        
                        #print 'Current brightness:', DIMMER_CURRENT_BRIGHTNESS[i]
                        if DIMMER_CURRENT_BRIGHTNESS[i] == 0:
                            #print 'turning off relay beacuse brightness set to 0'
                            if (not RELAY_QUEUE[DIMMER_SWITCH[i][0]][DIMMER_SWITCH[i][1]][0]):
                                QUEUED_RELAYS += 1
                            RELAY_QUEUE[DIMMER_SWITCH[i][0]][DIMMER_SWITCH[i][1]][0] = True # Relay action queued
                            RELAY_QUEUE[DIMMER_SWITCH[i][0]][DIMMER_SWITCH[i][1]][1] = False # power OFF
                        
                        if DIMMER_EN[i]:
                            set_i2c_mux(dimmer_mux[i])
                            LAST_DIMMER_WRITE[i] = setDimmer(0, DIM_PROFILE[i], DIMMER_CURRENT_BRIGHTNESS[i], LAST_DIMMER_WRITE[i])

                    else:
                        wait_power_up[i] -= 1
                        
                    if set_wait_power_up:
                        wait_power_up[i] = 15
            
            # CLEAR ENERGISED RELAYS AND ADVANCE TIMERS
            for i in range(num_boards):
                for j in range(8):
                    if RELAY_CLR_TIMER[i][j] == 1:
                        clr_relay(i, j)
                    if RELAY_CLR_TIMER[i][j]:
                        RELAY_CLR_TIMER[i][j] -= 1
                        
                    if STATUS_SETTLE_TIMER[i][j] > 0:
                        STATUS_SETTLE_TIMER[i][j] -= 1
            
            # ACTION RELAY QUEUE
            if (QUEUED_RELAYS > 0) and (NUM_RELAYS_ON[0] < MAX_RELAYS_ON):
                for i in range(num_boards):
                    for j in range(8):
                        if RELAY_QUEUE[i][j][0] and (RELAY_CLR_TIMER[i][j] == 0) and (STATUS_SETTLE_TIMER[i][j] == 0):  # if relay waiting in queue and not currently energised
                            #print 'queue actioned - board:',i,', chan:',j,', val:',RELAY_QUEUE[i][j][1]
                            power(i, j, RELAY_QUEUE[i][j][1])
                            RELAY_QUEUE[i][j][0] = False
                            QUEUED_RELAYS -= 1
                            
            # CHECK INDICATOR CONTROLS
            for i in range(num_boards):     # maybe don't check every time - very low priority
                last_ts_ind[i] = new_ts_ind[i]
                new_ts_ind[i] = stat(r'/var/lib/homebridge/ind_'+str(i)).st_mtime
                if (last_ts_ind[i] != new_ts_ind[i]):
                    check_ind_status(i)
                    update_ind(i)

            # CHECK CONTROL SIGNALS FROM HOMEBRIDGE            
            last_ts_control = new_ts_control
            new_ts_control = stat(r'/var/lib/homebridge/input_control').st_mtime
            if (last_ts_control != new_ts_control):
                if path.isfile(r'/var/lib/homebridge/input_control/night') and (not night_time):
                    for i in range(num_buttons):
                        button_scene[i] = 0 # reset all button scenes so the first time the button is pressed if light already on, it goes to the first scene
                    night_time = True
                    eightAM = False     #reset 8 am single entry sentinel
                    #print 'Night Time'
                    if is_master:
                        sock.sendto('write:input_control/:night:', (UDP_IP, UDP_PORT)) # pass on night time status to slaves
                        #accesspointLED(access_points, '0') # turn off leds on access points
                        if (not left_house) and current_hour <= 21 and current_hour > 14: # turn on hall lights if at home and time earlier than 21:59
                            f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_Dimmer_4_Brightness','w')
                            f.write('100')
                            f.close()
                            f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_Dimmer_4_On','w')
                            f.write('true')
                            f.close()
                            night_light_timer[1] = NIGHT_LIGHTS[1][11] #night_light_on_time  # will prevent hall lamp from going into night light mode
                elif (not path.isfile(r'/var/lib/homebridge/input_control/night')) and night_time:
                    night_time = False
                    evening_lights_not_activated = True
                    #going_to_bed = False
                    if is_master:   # downstairs going to bed dismissed by morning, upstairs going to bed dismissed by falling edge of bed
                        going_to_bed = False
                        if path.isfile(r'/var/lib/homebridge/input_control/going_to_bed_nv'):
                            remove(r'/var/lib/homebridge/input_control/going_to_bed_nv')
                    
                    # turn back on indicators that were turned off by bed if they are not in bedroom
                    for i in range(len(zone_indicators)):
                        system(r'touch /var/lib/homebridge/ind_'+str(zone_indicators[i][0])+'/'+str(zone_indicators[i][1]))

                    #print 'Day Time'
                    if is_master:
                        sock.sendto('delete:input_control/:night:', (UDP_IP, UDP_PORT)) # pass on day time status to slaves
                        if disarm_security_lights_on_sunrise:
                            if path.isfile(r'/var/lib/homebridge/input_control/security_lights'):
                                remove(r'/var/lib/homebridge/input_control/security_lights')
                            disarm_security_lights_on_sunrise = False

                        accesspointLED(access_points, '1') # turn back on leds on access points
                    else:
                        # Set office LED strip to default setup
                        f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_Led_Strip_1_Hue','w')
                        f.write('188')
                        f.close()
                        f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_Led_Strip_1_Saturation','w')
                        f.write('58')
                        f.close()
                        f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_Led_Strip_1_Brightness','w')
                        f.write('55')
                        f.close()

                        bedroom_ultra_dark = False
                        bedroom_ultra_dark_not_actioned_yet = True

                    system(r'touch /var/lib/homebridge/input_control/extractor_en')
                    extractor_en = True
                        
                if path.isfile(r'/var/lib/homebridge/input_control/evening_lights'):
                    if evening_lights_not_activated:
                        evening_lights_not_activated = False
                        if is_master:
                            if (not left_house):
                                if PIR[2][2]:   # Sitting Room PIR, last 10 mins
                                    if not(STATUS[2][6] or STATUS[2][7] or (STATUS[1][0] and (not ACTIVATED_AS_NIGHTLIGHT[1][0])) or STATUS[1][1]):   # if all lights off -- except for side lights as they may be on as night light
                                        #button[1] = 1   # "press" the sitting room button
                                        if night_time:
                                            set_scene(1,2, bed, is_master)  #sitting room dark
                                        else:
                                            set_scene(1,1, bed, is_master)  #sitting room medium
                                        button_scene[1] = 1
                                    #if not(STATUS[1][4] or STATUS[1][5] or STATUS[0][7]):   # if all dining room lights off
                                        #button[2] = 1   # "press" the dining room button
                                    if night_time:
                                        set_scene(2,2, bed, is_master)  #dining room dark
                                    else:
                                        set_scene(2,1, bed, is_master)  #dining room medium
                                    button_scene[2] = 1
                                
                                if PIR[4][2]:   # Kitchen PIR, last 10 mins
                                    if not(STATUS[2][0] or STATUS[2][1] or STATUS[2][3]):   # if all lights off
                                        #if STATUS[2][2]:    # counter
                                            #button[0] = 2   # "double press" the kitchen button to turn on lights + counter
                                        set_scene(0,1, bed, is_master)  #always kitchen medium
                                        button_scene[0] = 1
                                        #else:
                                        #    button[0] = 1   # "press" the kitchen button
                                    #if not(STATUS[1][4] or STATUS[1][5] or STATUS[0][7]):   # if all dining room lights off
                                        #button[2] = 1   # "press" the dining room button
                                    if night_time:
                                        set_scene(2,2, bed, is_master)  #dining room dark
                                    else:
                                        set_scene(2,1, bed, is_master)  #dining room medium
                                    button_scene[2] = 1
                    remove(r'/var/lib/homebridge/input_control/evening_lights')

                else:
                    evening_lights_not_activated = True

                if path.isfile(r'/var/lib/homebridge/input_control/guest'):
                    night_light_on_time_ext = 6000 # 5min when guest mode on
                    if is_master:
                        sock.sendto('write:input_control/:guest:', (UDP_IP, UDP_PORT))
                        if STATUS[0][2] and (night_light_timer[4] > 0) and (not guest): # if DS bathroom night light is on already and rising edge of guest
                            night_light_timer[4] = 6000
                    guest = True
                else:
                    guest = False
                    night_light_on_time_ext = 1200 # 1min when guest mode off
                    if is_master:
                        sock.sendto('delete:input_control/:guest:', (UDP_IP, UDP_PORT))
                        
                if path.isfile(r'/var/lib/homebridge/input_control/bed') and (not bed):
                    bed = True
                    if (not is_master):
                        sock.sendto('write:input_control/:bed:', (UDP_IP, UDP_PORT)) # pass on bed status to master
                        # dim the bedside indicator and all other indicators when they come on
                        PWM_0   = 0xFE  # 0.39% brightness (dim state when bed)
                        PWM_1   = 0xE7  # 9.37% brightness (bright state when bed)
                        if num_special_buttons:
                            set_one_led(special_button_led[0][0], special_button_led[0][1], 2) # set special button to dimmest setting
                            
                            # add series 1Mohm resistor for extreme dim
                            set_i2c_mux(IOmux[special_button_led[0][2]])
                            
                            special_button_resistor = 0b1 << special_button_led[0][3]
                            #print 'val to write to output:',special_button_resistor
                            #print 'val to write to dir:',(special_button_resistor ^ 0xF)
                            
                            write_byte_reg(io_adr, 0x1, 0x0)                               # output port
                            write_byte_reg(io_adr, 0x3, (special_button_resistor ^ 0xF))   # config (dir)
                        
                    # if path.isfile(r'/var/lib/homebridge/input_control/evening_lights'):    # bed removes evening lights
                    #     remove(r'/var/lib/homebridge/input_control/evening_lights')
                    system(r'touch /var/lib/homebridge/input_control/extractor_en')
                    extractor_en = True
                        
                elif (not path.isfile(r'/var/lib/homebridge/input_control/bed')) and bed:
                    bed = False

                    for i in range(num_buttons):
                        button_scene[i] = 0 # reset all button scenes so the first time the button is pressed if light already on, it goes to the first scene

                    if (not is_master): # downstairs going to bed dismissed by morning, upstairs going to bed dismissed by falling edge of bed
                        going_to_bed = False
                        if path.isfile(r'/var/lib/homebridge/input_control/going_to_bed_nv'):
                            remove(r'/var/lib/homebridge/input_control/going_to_bed_nv')

                        sock.sendto('write:input_control/:SFDS:', (UDP_IP, UDP_PORT)) # if not bed, supress first downstairs so upstairs music doesn't stop
                    
                        sock.sendto('delete:input_control/:bed:', (UDP_IP, UDP_PORT)) # pass on bed status to master

                        PWM_0   = 0xF0  # 6.25% brightness  (dim state when not bed)
                        PWM_1   = 0x90  # 43% for low speed fan
                        if num_special_buttons:
                            set_one_led(special_button_led[0][0], special_button_led[0][1], 1) # set special button to normal on
                            
                            # bypass series 1Mohm resistor for normal brightness
                            set_i2c_mux(IOmux[special_button_led[0][2]])
                            
                            special_button_resistor = 0b1 << special_button_led[0][3]
                            #print 'val to write to output:',special_button_resistor
                            #print 'val to write to dir:',(special_button_resistor ^ 0xF)
                            
                            write_byte_reg(io_adr, 0x1, special_button_resistor)           # output port
                            write_byte_reg(io_adr, 0x3, (special_button_resistor ^ 0xF))   # config (dir)

                if path.isfile(r'/var/lib/homebridge/input_control/security_lights'):
                    security_enabled = True
                    #print 'Security lights enabled'
                    if is_master:
                        sock.sendto('write:input_control/:security_lights:', (UDP_IP, UDP_PORT)) # pass on security status to slave
                else:
                    security_enabled = False
                    #print 'Security lights disabled'
                    for i in range(num_security_lights):
                        security_light_activated[i] = False

                    if is_master:
                        sock.sendto('delete:input_control/:security_lights:', (UDP_IP, UDP_PORT)) # pass on security status to slave
                        
                if path.isfile(r'/var/lib/homebridge/input_control/reset_fire_lights'):
                    if is_master:
                        sock.sendto('write:input_control/:reset_fire_lights:', (UDP_IP, UDP_PORT)) # pass on reset to slaves
                    for i in range(num_fire_lights):
                        if not fire_lights_prev_status[i]:
                            #print 'turning off fire light',FIRE_LIGHTS[i][0],FIRE_LIGHTS[i][1]
                            if path.isfile(r'/var/lib/homebridge/input_'+str(FIRE_LIGHTS[i][0])+'/'+str(FIRE_LIGHTS[i][1])):
                                remove(r'/var/lib/homebridge/input_'+str(FIRE_LIGHTS[i][0])+'/'+str(FIRE_LIGHTS[i][1]))
                    system(r'sudo rm /var/lib/homebridge/input_control/reset_fire_lights')

                if path.isfile(r'/var/lib/homebridge/input_control/gtb'): # going to bed
                    remove(r'/var/lib/homebridge/input_control/gtb')
                    if is_master:
                        button[1] = 3 # emulate triple press of sitting room button
                    else:
                        bedroom_ultra_dark_not_actioned_yet = True
                        going_to_bed = True
                        system(r'touch /var/lib/homebridge/input_control/going_to_bed_nv')

                if path.isfile(r'/var/lib/homebridge/input_control/wd_powercycle'): # request from other pi for power cycle
                    remove(r'/var/lib/homebridge/input_control/wd_powercycle')
                    powercycle_req = True
                    powercycle_timer = 3

                if is_master:
                    if path.isfile(r'/var/lib/homebridge/input_control/turn_on_active_nightlights'): # and (not do_not_disturb):
                        turn_on_active_nightlights = True
                        remove(r'/var/lib/homebridge/input_control/turn_on_active_nightlights')

                    if path.isfile(r'/var/lib/homebridge/input_control/package_garage') and (not package_garage_last):
                        package_garage = True
                        package_garage_last = True
                        if not(doorbell):
                            packageGarageMessage(doorbell_ip_adr, 1)
                    elif (not path.isfile(r'/var/lib/homebridge/input_control/package_garage')) and package_garage_last:
                        package_garage_last = False
                        if not(doorbell):
                            package_garage = False
                            packageGarageMessage(doorbell_ip_adr, 0)

                    if path.isfile(r'/var/lib/homebridge/input_control/do_not_disturb'): # and (not do_not_disturb):
                        do_not_disturb = True
                        system(r'touch /var/lib/homebridge/input_3/2')
                        sock.sendto('write:input_control/:do_not_disturb:', (UDP_IP, UDP_PORT))
                    #elif (not path.isfile(r'/var/lib/homebridge/input_control/do_not_disturb')) and do_not_disturb:
                    else:
                        do_not_disturb = False
                        if path.isfile(r'/var/lib/homebridge/input_3/2'):
                            remove(r'/var/lib/homebridge/input_3/2')
                        sock.sendto('delete:input_control/:do_not_disturb:', (UDP_IP, UDP_PORT))

                    if path.isfile(r'/var/lib/homebridge/input_control/dnd_suppress_doorbell_msg'):
                        dnd_suppress_doorbell_msg = True
                        sock.sendto('write:input_control/:dnd_suppress_doorbell_msg:', (UDP_IP, UDP_PORT))
                    else:
                        dnd_suppress_doorbell_msg = False
                        sock.sendto('delete:input_control/:dnd_suppress_doorbell_msg:', (UDP_IP, UDP_PORT))                      

                    if path.isfile(r'/var/lib/homebridge/input_control/lth'): # leave the house
                        remove(r'/var/lib/homebridge/input_control/lth')
                        button[3] = 3 # emulate triple press of front door button
                            
                else:

                    if path.isfile(r'/var/lib/homebridge/input_control/shower_blinds_EN'): # and (not do_not_disturb):
                        shower_blinds_EN = True
                    else:
                        shower_blinds_EN = False

                    if path.isfile(r'/var/lib/homebridge/input_control/turn_on_active_nightlights'): # and (not do_not_disturb):
                        turn_on_active_nightlights = True
                        sock.sendto('write:input_control/:turn_on_active_nightlights:', (UDP_IP, UDP_PORT))
                        remove(r'/var/lib/homebridge/input_control/turn_on_active_nightlights')

                    if path.isfile(r'/var/lib/homebridge/input_control/do_not_disturb'): # and (not do_not_disturb):
                        do_not_disturb = True
                    else:
                        do_not_disturb = False

                    if path.isfile(r'/var/lib/homebridge/input_control/left_house'):
                        left_house = True
                    else:
                        left_house = False

                    if path.isfile(r'/var/lib/homebridge/input_control/dnd_suppress_doorbell_msg'):
                        dnd_suppress_doorbell_msg = True
                    else:
                        dnd_suppress_doorbell_msg = False

                if path.isfile(r'/var/lib/homebridge/input_control/SFDS'):
                    suppress_first_downstairs = True
                else:
                    suppress_first_downstairs = False
                    
                if path.isfile(r'/var/lib/homebridge/input_control/debug'):
                    debug_press = True
                    remove(r'/var/lib/homebridge/input_control/debug')
                else:
                    debug_press = False

                if path.isfile(r'/var/lib/homebridge/input_control/extractor_en'):
                    extractor_en = True
                else:
                    extractor_en = False

                # if path.isfile(r'/var/lib/homebridge/input_control/btc_enable'):
                #     btc_enable = True
                # else:
                #     btc_enable = False
                        
                if not is_master: # fire alarm/door bell status transferred by UDP
                    if path.isfile(r'/var/lib/homebridge/input_control/fire_alarm'):
                        fire_alarm = True
                    else:
                        fire_alarm = False
                        
                    if path.isfile(r'/var/lib/homebridge/input_control/door_bell'):
                        doorbell_press = True
                        system(r'sudo rm /var/lib/homebridge/input_control/door_bell')
                
                for i in range(8):
                    if path.isfile(r'/var/lib/homebridge/input_control/'+str(i)):
                        STATUS[4][i] = True
                        if is_master and i == 2:
                            if reset_alarm_reminder_not_given:
                                reset_alarm_reminder_not_given = False
                                alarm_reminder_not_given = True
                            if path.isfile(r'/var/lib/homebridge/input_3/3'):   # set up doorbell ring in morning reminder
                                remove(r'/var/lib/homebridge/input_3/3')
                    else:
                        STATUS[4][i] = False
                        if is_master and i == 2:
                            reset_alarm_reminder_not_given = True

                    # MASTER
                    # 0: Landing Light
                    # 1: Sitting Room Blind
                    # 2: PhoneWatch Alarm enabled to Home or Away
                    # 3: Phonewatch Alarm set to Away

                    # SLAVE
                    # 0: Outside Temperature >= 23deg (outdoor_temp_thresh)
                      
            # READ TEMP/HUMIDITY and other slow update items (once every 5 seconds)
            if counter == 1:    # set up reading
                last_hour = current_hour
                current_hour = datetime.now().hour
                current_month = datetime.now().month
                if (current_hour >= 6) and (current_hour <= 9): # Morning between 06:00 and 09:59
                    morning = True
                else:
                    morning = False

                if not(is_master):
                    if current_hour == 8 and (not eightAM):
                        eightAM = True
                        if (not guest):
                            f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_WindowCovering_3_TargetPosition','w')
                            f.write('100')
                            f.close()
                            f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_WindowCovering_3_CurrentPosition','w')
                            f.write('100')
                            f.close()

                        if left_house:   # open bedroom blind at 8am if left_house
                            f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_WindowCovering_1_TargetPosition','w')
                            f.write('100')
                            f.close()
                            f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_WindowCovering_1_CurrentPosition','w')
                            f.write('100')
                            f.close()
                    
                if (current_hour >= 20) or (current_hour <= 3): # Bedtime between 20:00 and 03:59
                    bedtime = True
                else:
                    bedtime = False

                # if not(is_master):
                #     if (current_hour == 8) and (last_hour == 7) and left_house:   # open bedroom blind at 8am if left_house
                #         f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_WindowCovering_1_TargetPosition','w')
                #         f.write('100')
                #         f.close()
                #         f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_WindowCovering_1_CurrentPosition','w')
                #         f.write('100')
                #         f.close()
                    
                for i in range(numtemp):
                    if tempmux[i] != -1:
                        set_i2c_mux(tempmux[i])
                        if i == 1 and not is_master:
                            ok_to_have_error = STATUS[1][1] # bed side lamp, if it's on, get regular errors on temp/humidity sensor due to noise
                        else:
                            ok_to_have_error = False
                        write_byte(hum_temp_adr, 0x00, ok_to_have_error = ok_to_have_error) # get temp/humidity sensor to start a conversion

                f = open(r'/var/lib/homebridge/heartbeat','w')  # heartbeat
                f.close()
                if core_counter == 1:
                    system(r'/opt/vc/bin/vcgencmd measure_temp > core_temp.log')
                    f = open('core_temp.log','r')
                    core_temp = (f.readline().split('=')[1]).split('.')[0]
                    f.close()
                    if core_temp != last_core_temp:
                        # activate fan if required
                        core_temp_int = int(core_temp)
                        if (core_temp_int > fan_temps[1]+fan_hyst) and (fan_speed != 2):    # max temp test
                            set_one_led(FAN[0], FAN[1], 1) # speed order = [0,3,1]
                            fan_speed = 2
                            print 'Set fan to speed 2 because temp is',core_temp,'degC'
                        elif (core_temp_int < fan_temps[0]-fan_hyst) and (fan_speed != 0):  # min temp test
                            set_one_led(FAN[0], FAN[1], 0) # speed order = [0,3,1]
                            fan_speed = 0
                            print 'Set fan to speed 0 because temp is',core_temp,'degC'
                        elif (core_temp_int > fan_temps[0]+fan_hyst) and (fan_speed == 0):  # med temp test 1
                            if bed:
                                set_one_led(FAN[0], FAN[1], 1) # speed order = [0,3,1] - 3 (medium) is unusable when in bed because its used for indicators, have to use 1 (fully on)
                            else:
                                set_one_led(FAN[0], FAN[1], 3) # speed order = [0,3,1]
                            fan_speed = 1
                            print 'Set fan to speed 1 because temp is',core_temp,'degC'
                        elif (core_temp_int < fan_temps[1]-fan_hyst) and (fan_speed == 2):  # med temp test 2
                            if bed:
                                set_one_led(FAN[0], FAN[1], 1) # speed order = [0,3,1]  - 3 (medium) is unusable when in bed because its used for indicators, have to use 1 (fully on)
                            else:
                                set_one_led(FAN[0], FAN[1], 3) # speed order = [0,3,1]
                            fan_speed = 1
                            print 'Set fan to speed 1 because temp is',core_temp,'degC'
                            
                        # print 'Core temperature = '+core_temp+'degC'
                        f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_Core_'+str(cfg.core_id)+'_CurrentTemperature','w')
                        f.write(core_temp+'\n')
                        f.close()
                    last_core_temp = core_temp
                elif core_counter == 4:
                    core_counter = 0
                core_counter += 1

                if is_master:
                    if clear_dnd_msg:
                        clear_dnd_msg2 = True
                        clear_dnd_msg = False

                    if clear_dnd_msg2:
                        clear_dnd_msg2 = False
                        if path.isfile(r'/var/lib/homebridge/input_control/DND_Msg'):
                            remove(r'/var/lib/homebridge/input_control/DND_Msg')

                    if enable_doorbell_timeout and do_not_disturb:
                        if enable_doorbell_timeout == 1:
                            system(r'touch /var/lib/homebridge/input_3/2')
                        enable_doorbell_timeout -= 1

                    if temporarily_enable_doorbell and (not doorbell_press):
                        temporarily_enable_doorbell = False
                        enable_doorbell_timeout = 6
                        if path.isfile(r'/var/lib/homebridge/input_3/2'):
                            remove(r'/var/lib/homebridge/input_3/2')

                elif bedroom_ultra_dark and bedroom_ultra_dark_not_actioned_yet:
                    #print bedroom_ultra_dark_timer
                    bedroom_ultra_dark_timer -= 1
                    if (not bedroom_ultra_dark_timer):
                        if STATUS[1][2]:    # if big lamp in bedroom is on, dim lights down one stage
                            f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_Dimmer_1_On','w')
                            f.write('false\n')
                            f.close()
                            f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_Dimmer_0_Brightness','w')
                            f.write('70\n')
                            f.close()
                            f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_Led_Strip_2_Brightness','w')
                            f.write('55\n')
                            f.close()
                            f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_Led_Strip_2_Hue','w')
                            f.write('33\n')
                            f.close()
                            f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_Led_Strip_2_Saturation','w')
                            f.write('73\n')
                            f.close()
                            f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_Led_Strip_3_Brightness','w')
                            f.write('30\n')
                            f.close()
                            f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_Led_Strip_3_Hue','w')
                            f.write('162\n')
                            f.close()
                            f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_Led_Strip_3_Saturation','w')
                            f.write('100\n')
                            f.close()
                            bedroom_ultra_dark_timer = bedroom_ultra_dark_time
                        else:
                            # dim down bedroom lights even further
                            f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_Dimmer_1_On','w')
                            f.write('false\n')
                            f.close()
                            f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_Dimmer_0_Brightness','w')
                            f.write('17\n')
                            f.close()
                            f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_Led_Strip_2_Brightness','w')
                            f.write('10\n')
                            f.close()
                            f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_Led_Strip_2_Hue','w')
                            f.write('35\n')
                            f.close()
                            f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_Led_Strip_2_Saturation','w')
                            f.write('95\n')
                            f.close()
                            f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_Led_Strip_3_Brightness','w')
                            f.write('20\n')
                            f.close()
                            f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_Led_Strip_3_Hue','w')
                            f.write('162\n')
                            f.close()
                            f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_Led_Strip_3_Saturation','w')
                            f.write('100\n')
                            f.close()
                            if path.isfile(r'/var/lib/homebridge/ind_1/0'):
                                remove(r'/var/lib/homebridge/ind_1/0')
                            if path.isfile(r'/var/lib/homebridge/ind_0/3'):
                                remove(r'/var/lib/homebridge/ind_0/3')
                            if path.isfile(r'/var/lib/homebridge/ind_0/4'):
                                remove(r'/var/lib/homebridge/ind_0/4')

                            bedroom_ultra_dark = False
                            bedroom_ultra_dark_not_actioned_yet = False
                            bedroom_ultra_dark_timer = bedroom_ultra_dark_time

                    elif bedroom_ultra_dark_timer == 2:
                        # turn off bathroom lights
                        set_scene_off(1)

            elif counter == 3:  # read
                for i in range(numtemp):
                    if tempmux[i] != -1:
                        set_i2c_mux(tempmux[i])
                        if i == 1 and not is_master:
                            ok_to_have_error = STATUS[1][1] # bed side lamp, if it's on, get regular errors on temp/humidity sensor due to noise
                        else:
                            ok_to_have_error = False
                        temperature[i], humidity[i], temp_prec[i], hum_prec[i] = read_temp_hum(hum_temp_adr, ok_to_have_error = ok_to_have_error) #bus.read_byte(hum_temp_adr)

                        if is_master and (i==1):   # temp sensor in sitting room reads high
                            temperature[1] = temperature[1] - 1.0
                            temp_prec[1] = temp_prec[1] - 1.0

                        if humidity[i] != -100: # if there was an error reading, -100 returned
                            if temperature[i] != last_temperature[i]:
                                #sock.sendto('write:Cmd4Scripts/Cmd4States/:Status_Temperature_'+str(i)+'_CurrentTemperature:'+str(temperature[i])+'\n', (UDP_IP, UDP_PORT))
                                #print 'temperature '+str(i)+' packet sent to '+UDP_IP+' = '+str(temperature[i])+'degC'
                                f = open('/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_Temperature_'+str(i)+'_CurrentTemperature','w')
                                f.write(str(temperature[i])+'\n')
                                f.close()
                                last_temperature[i] = temperature[i]
                            if humidity[i] != last_humidity[i]:
                                #sock.sendto('write:Cmd4Scripts/Cmd4States/:Status_Humidity_'+str(i)+'_CurrentRelativeHumidity:'+str(humidity[i])+'\n', (UDP_IP, UDP_PORT))
                                #print 'humidity '+str(i)+' packet sent to '+UDP_IP+' = '+str(humidity[i])+'% RH'
                                f = open('/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_Humidity_'+str(i)+'_CurrentRelativeHumidity','w')
                                f.write(str(humidity[i])+'\n')
                                f.close()
                                last_humidity[i] = humidity[i]
                        
                if package_garage_timer == 0 and garage_door_open_package:  # need to add PIR at garage to this condition also
                    f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_GarageDoorOpener_TargetDoorState','w')
                    f.write('1')
                    f.close()
                    garage_door_open_package = False
                    if path.isfile(r'/var/lib/homebridge/input_control/package_garage'):
                        remove(r'/var/lib/homebridge/input_control/package_garage') # remove it here to keep message up on screen of doorbell for 1 min after ring
                    else:
                        packageGarageMessage(doorbell_ip_adr, 0)
                elif package_garage_timer == 7:
                    system(r'touch /var/lib/homebridge/input_control/package_garage')
                    
                if package_garage_timer:
                    package_garage_timer -= 1

                if powercycle_req:
                    print 'powercycle_timer:',powercycle_timer
                    if powercycle_timer == 0:
                        set_i2c_mux(wd_powercycle)
                        write_byte_reg(extra_8bit_adr, GPIO_REGISTER_8, 0x01)   # output port
                        write_byte_reg(extra_8bit_adr, 0x0, 0xFE)               # config (dir)
                        powercycle_timer -= 1
                        powercycle_req = False               
                    else:
                        powercycle_timer -= 1
                else:
                    set_i2c_mux(wd_powercycle)
                    write_byte_reg(extra_8bit_adr, GPIO_REGISTER_8, 0x00)   # output port
                    write_byte_reg(extra_8bit_adr, 0x0, 0xFF)               # config (dir)

                if len(post_box):
                    if deassert_post_box:
                        f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_Post_Box_MotionDetected','w')
                        f.write('0')
                        f.close()
                        deassert_post_box = False
                    else:
                        set_i2c_mux(post_box[0])
                        post_readback = read_byte_reg(extra_8bit_adr, GPIO_REGISTER_8)
                        this_post_flag = (post_readback >> (post_box[1]+post_box[2])) & 0b1
                        #print 'post_readback:',bin(post_readback)
                        if this_post_flag != last_post_flag:
                            #print 'Post detected!'
                            f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_Post_Box_MotionDetected','w')
                            f.write('1')
                            f.close()
                            deassert_post_box = True
                            post_battery = (post_readback >> (post_box[1]+post_box[2]+4)) & 0b1
                            #print 'Battery status:',post_battery
                            f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_Post_Box_StatusLowBattery','w')
                            if post_battery:
                                f.write('0')
                            else:
                                f.write('1')
                            f.close()

                        last_post_flag = this_post_flag
                        
            elif counter == 5:
                if is_master and (morning or (not night_time)) and (PIR[2][2] or PIR[4][2]):    # if motion detected in sitting room or kitchen in morning, turn off BED downstairs
                    if path.isfile(r'/var/lib/homebridge/input_control/bed'):
                        remove(r'/var/lib/homebridge/input_control/bed')
                        
                # if is_master and left_house and (left_house_hold_off == 0):
                #     if PIR[2][1] and not(STATUS[4][3]):     #STATUS[4][3] = Security Alarm set to Away # motion in sitting room removes left house status if alarm not set to away
                #         left_house = False
                #     if PIR[4][1]:  # motion in kitchen removes left house status
                #         left_house = False
                #         # if path.isfile(r'/var/lib/homebridge/input_control/security_lights'):
                #         #     remove(r'/var/lib/homebridge/input_control/security_lights')

                        
                if left_house_hold_off:
                    left_house_hold_off -= 1
                
                # Refresh button LED to reflect status of lights if have been controlled by app/automation              
                for i in range(num_buttons):
                    # Check if any lights the button controls are on
                    if not button_flashing[i]:
                        num_lights_button = len(lights_under_button_control[i])
                        any_button_lights_on = False
                        for j in range(num_lights_button): 
                            if lights_under_button_control[i][j][0] == 0: #  switch
                                if STATUS[lights_under_button_control[i][j][1]][lights_under_button_control[i][j][2]]:
                                    any_button_lights_on = True
                            elif lights_under_button_control[i][j][0] == 1: # dimmer
                                if STATUS[DIMMER_SWITCH[lights_under_button_control[i][j][1]][0]][DIMMER_SWITCH[lights_under_button_control[i][j][1]][1]]:
                                    any_button_lights_on = True
                            elif lights_under_button_control[i][j][0] == 2: # led
                                if led_strip_power[lights_under_button_control[i][j][1]]:
                                    any_button_lights_on = True
                        if any_button_lights_on:
                            set_one_led(button_led_ind[i][0], button_led_ind[i][1], 2)
                        else:
                            if bed:
                                set_one_led(button_led_ind[i][0], button_led_ind[i][1], 3)
                            else:
                                set_one_led(button_led_ind[i][0], button_led_ind[i][1], 1)

                if num_air_qual:
                    # for i in range(num_air_qual):
                    #     set_i2c_mux(air_qual[i][0])
                    #     air_qual_sts = read_byte_reg(air_qual_adr, 0x00)
                    #     air_qual_mode = read_byte_reg(air_qual_adr, 0x01)
                    #     #air_qual_HW_ID = read_byte_reg(air_qual_adr, 0x20)
                    #     air_qual_ER_ID = read_byte_reg(air_qual_adr, 0xE0)
                    #     air_qual_raw1, air_qual_raw0 = read_two_bytes_reg(air_qual_adr, 0x03)

                    #     print '\t\tAir quality sensor #'+str(i)+' status: '+hex(air_qual_sts)
                    #     print '\t\tAir quality sensor #'+str(i)+' mode: '+hex(air_qual_mode)
                    #     #print 'Air quality sensor #'+str(i)+' HW_ID: '+hex(air_qual_HW_ID)
                    #     print '\t\tAir quality sensor #'+str(i)+' Error code: '+hex(air_qual_ER_ID)
                    #     print
                    #     print '\t\tAir Quality RAW: '+hex((air_qual_raw1<<8)+air_qual_raw0)
                    #     print

                    if air_quality_config_delay == 1:
                        air_quality_config_delay = 0
                        for i in range(num_air_qual):
                            set_i2c_mux(air_qual[i][0])
                            write_byte_reg_retry(air_qual_adr, 0x01, 0x30)    # set air quality sensor into mode 3
                            #print 'Air quality sensor #'+str(i)+' set to mode 3'
                    elif air_quality_config_delay:
                        air_quality_config_delay -= 1
                    else:
                        #print 'Reading air quality...'
                        for i in range(num_air_qual):
                            # if (not is_master) and i==0:
                            #     ok_to_have_error = STATUS[1][1]
                            # elif(i==0):
                            if(i==0):
                                ok_to_have_error = True
                            else:
                                ok_to_have_error = False

                            set_i2c_mux(air_qual[i][0])
                            air_qual_sts = read_byte_reg(air_qual_adr, 0x00, ok_to_have_error)
                            if ((air_qual_sts & 0x08) == 0x08): # sample ready
                                air_qual_eco2[i], air_qual_etvoc[i] = read_air_qual(air_qual_adr, 0x02, ok_to_have_error)   # , air_qual_sts, air_qual_err_id, air_qual_raw 
                                #print 'eCO2: '+str(air_qual_eco2[i])
                                #print 'eTVOC: '+str(air_qual_etvoc[i])

                                if (air_qual_eco2[i] >= 32767) and (last_eco2[i] < 20000):
                                    block_air_qual_reading = True
                                elif (air_qual_eco2[i] != last_eco2[i]) and (air_qual_eco2[i] != -100) and (air_qual_etvoc[i] < 5000):
                                    block_air_qual_reading = False
                                    f = open('/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_CO2_Sensor_'+str(i)+'_CarbonDioxideLevel','w')
                                    f.write(str(air_qual_eco2[i])+'\n')
                                    f.close()
                                    last_eco2[i] = air_qual_eco2[i]

                                    f = open('/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_CO2_Sensor_'+str(i)+'_CarbonDioxideDetected','w')
                                    if air_qual_eco2[i] < 5000: # 5000 = high levels of CO2
                                        f.write('0\n')
                                    else:
                                        f.write('1\n')
                                    f.close()

                                    if air_qual_eco2[i] > peak_eco2[i]:
                                        peak_eco2[i] = air_qual_eco2[i]
                                        f = open('/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_CO2_Sensor_'+str(i)+'_CarbonDioxidePeakLevel','w')
                                        f.write(str(peak_eco2[i])+'\n')
                                        f.close()
                                else:
                                    block_air_qual_reading = False
                                        
                                if (air_qual_etvoc[i] != last_etvoc[i]) and (air_qual_etvoc[i] != -100) and (not block_air_qual_reading) and (air_qual_etvoc[i] < 5000):
                                    f = open('/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_AirQualitySensor_'+str(i)+'_VOCDensity','w')
                                    f.write(str(air_qual_etvoc[i]*2)+'\n')  # x2 = ppb -> ug/m^3
                                    f.close()
                                    last_etvoc[i] = air_qual_etvoc[i]

                                    f = open('/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_AirQualitySensor_'+str(i)+'_AirQuality','w')
                                    #if air_qual_etvoc[i] == 0:
                                    #    f.write('0\n')  # unknown
                                    #elif air_qual_etvoc[i] < 150:         # less than 0.3 mg/m^3 = less than 150 ppb - excellent
                                    if air_qual_etvoc[i] < 150:         # less than 0.3 mg/m^3 = less than 150 ppb - excellent
                                        f.write('1\n')
                                    elif air_qual_etvoc[i] < 250:       # less than 0.5 mg/m^3 = less than 250 ppb - good
                                        f.write('2\n')
                                    elif air_qual_etvoc[i] < 500:       # less than 1 mg/m^3 = less than 500 ppb - fair
                                        f.write('3\n')
                                    elif air_qual_etvoc[i] < 1500:      # less than 3 mg/m^3 = less than 1500 ppb - inferior
                                        f.write('4\n')
                                    else:                               # poor
                                        f.write('5\n')
                                    f.close()

                                # print 'sts: '+hex(air_qual_sts)
                                # print 'err_id: '+hex(air_qual_err_id)
                                # print 'raw: '+hex(air_qual_raw)
                            # else:
                            #     print 'no sample ready'

                                ### Commented out writing humidity and temp to air quality sensor
                                # if humidity[air_qual[i][1]] != -100 and (is_master or (not (STATUS[1][1] and (i==0)))): # only write the hum/temp data into bedroom sensor if the side lamp is off (interference):    # if valid humidity/temp values present
                                #     #print 'sending temp/hum values to air quality sensor'
                                #     set_i2c_mux(air_qual[i][0])
                                #     # print 'humidity: '+str(hum_prec[air_qual[i][1]])
                                #     # print 'temperature: '+str(temp_prec[air_qual[i][1]])
                                #     humidity_formatted_upper = int(floor(hum_prec[air_qual[i][1]] * 2))
                                #     humidity_formatted_lower = int(round(((hum_prec[air_qual[i][1]] * 2) - humidity_formatted_upper) * 256))
                                #     temperature_formatted_upper = int(floor((temp_prec[air_qual[i][1]]+25) * 2))
                                #     temperature_formatted_lower = int(round((((temp_prec[air_qual[i][1]]+25) * 2) - temperature_formatted_upper) * 256))
                                #     # print humidity_formatted_upper
                                #     # print humidity_formatted_lower
                                #     # print temperature_formatted_upper
                                #     # print temperature_formatted_lower
                                #     # print
                                #     if is_master and i==0:
                                #         ok_to_have_error = True
                                #     else:
                                #         ok_to_have_error = False
                                #     write_four_bytes_reg(air_qual_adr, 0x05, humidity_formatted_upper, humidity_formatted_lower, temperature_formatted_upper, temperature_formatted_lower, ok_to_have_error)

            elif counter == 6:
                if led_locate_holdoff:
                    led_locate_holdoff -= 1
                else:
                    led_status_indicator = True
                    for i in range(num_led_strips):
                        if not led_retry[i]:
                            if led_repeat_pwr[i]:
                                if led_repeat_pwr[i] > 1:
                                    led_repeat_pwr[i] -= 1
                                else:
                                    led_repeat_pwr[i] = 0
                                    #print 'Repeating power command to LED',i
                                    setLEDpwr(led_strips[i], i, led_retry, led_retry_pwr, led_retry_counter, led_retry_pwr[i], False, led_confirm, led_retry_delay)

                            elif led_confirm[i]:
                                if led_confirm[i] > 1:
                                    led_confirm[i] -= 1
                                else:
                                    if led_repeat_confirm[i]:
                                        led_confirm[i] = 4
                                        #print 'confirming LED',i,'power has been set correctly for the first time...'
                                        led_repeat_confirm[i] = False
                                    else:
                                        led_confirm[i] = 0
                                        if led_solid_colour[i]:
                                            repeat_led_colour[i] = True
                                        else:
                                            repeat_led_colour[i] = False
                                        #print 'confirming LED',i,'power has been set correctly for a second time...'
                                    #print 'Polling LED Strip',i,'for power status...'
                                    led_not_confirmed = True
                                    led_confirm_attempts = 0

                                    while (led_not_confirmed and (led_confirm_attempts < 3)):
                                        #print led_confirm_attempts
                                        empty_socket(sock)
                                        sock.sendto(lifx_get_light_power, (led_strips[i], led_strip_UDP_port))
                                        try:
                                            data, address = sock.recvfrom(1024)
                                            #sleep(0.001)
                                            if ((address[0] == led_strips[i]) and (ord(data[32]) == 0x76) and (len(data) == 38)):   # 0x76 = StateLightPower - Packet 118
                                                if ord(data[36]) > 0:
                                                    led_sts = True
                                                else:
                                                    led_sts = False

                                                if (led_sts != led_strip_power[i]):
                                                    print 'failed led_confirm - led sts:',ord(data[36])
                                                    led_retry[i] = True
                                                    led_retry_pwr[i] = led_strip_power[i]
                                                    led_retry_counter[i] = 1    # set to 1 so the first thing that is tried is a repeat of pwr command
                                                    led_retry_delay = True
                                                            
                                                led_not_confirmed = False
                                            else:
                                                sleep(0.04)
                                        except:
                                            sleep(0.04)

                                        led_confirm_attempts += 1

                                    if led_not_confirmed:
                                        print 'didn\'t get response to led_confirm 3 times...'
                                        led_retry[i] = True
                                        led_retry_pwr[i] = led_strip_power[i]
                                        led_retry_counter[i] = 1
                                        led_retry_delay = True

                            elif repeat_led_colour[i] and led_strip_power[i]:
                                #print 'repeating solid colour command to LED strip',i
                                response_not_received = True
                                led_retries = 0
                                led_strip_IP = led_strips[i]

                                while response_not_received and (led_retries < 3):
                                    empty_socket(sock)
                                    if num_zones[i] == 0:
                                        setBulbRes(led_strip_IP, int(float(hue_set_f[i])*182.04166666666666666666666666667), int(float(saturation_set_f[i])*655.35), int(master_brightness[i]*65535.0), 3500, 2000)
                                    else:
                                        setMultRes(led_strip_IP, 0, num_zones[i], int(float(hue_set_f[i])*182.04166666666666666666666666667), int(float(saturation_set_f[i])*655.35), int(master_brightness[i]*65535.0), 3500, 2000)
                                    try:
                                        data, address = sock.recvfrom(1024)
                                        if address[0] == led_strip_IP:
                                            response_not_received = False
                                            repeat_led_colour[i] = False
                                            #print 'received reponse from led'
                                    except:
                                        led_retries += 1
                                        print 'LED repeat solid colour command for',led_strip_IP,'took',led_retries,'retries...'

                        if led_reset_ts[i]:
                            last_ts_led_strip[i] = 0
                            last_ts_led_strip_brightness[i] = 0
                            last_ts_led_strip_hue[i] = 0
                            last_ts_led_strip_sat[i] = 0
                            print 'all timestamps reset for LED strip',i
                            led_reset_ts[i] = False

                        if led_retry[i]:
                            led_status_indicator = False
                            if led_retry_delay:
                                led_retry_delay = False
                            else:
                                led_retry_delay = True  # half retry rate so only retry every 10 seconds - 5 seconds is too regular
                                if led_retry_counter[i] <= max_led_retries:
                                    if (led_retry_counter[i] % led_relocate_rate == 0) or first_time_led_locate[i]:
                                        relocateLED(i, led_retry, led_retry_counter, led_strips, led_retry_pwr, led_repeat_pwr, led_strip_confirm, led_confirm, led_repeat_confirm, led_mac, first_time_led_locate)
                                    else:
                                        retryPwrLED(i, led_retry, led_retry_counter, led_strips, led_retry_pwr, led_repeat_pwr, led_strip_confirm, led_confirm, led_repeat_confirm)
                                    led_retry_counter[i] += 1

                                    if not(led_retry[i]):   # moved this up here, was outside of if else (was 6 lines below)
                                        led_reset_ts[i] = True #if relocateLED was successful, reset TS

                                else:
                                    print 'abandoning further attempts to relocate LED strip '+str(i)+'... resetting to try next time'
                                    led_retry_counter[i] = 0    # stop retrying but reset retry counter so it can retry the next time
                                    led_retry[i] = False        # stop retrying... is this correct? - added later - WCA TODO - check - also moved reset_ts inside if
                        #else:
                        #    led_retry_counter[i] = 0

                    if led_status_indicator:
                        GPIO.output(29, GPIO.HIGH)
                    else:
                        GPIO.output(29, GPIO.LOW)

                if (not is_master):
                    if test_rpi2_this_time:
                        last_ts_rpi2 = new_ts_rpi2
                        new_ts_rpi2 = stat(r'/var/lib/homebridge/heartbeat_rpi2').st_mtime
                        if (new_ts_rpi2 > last_ts_rpi2):
                            GPIO.output(31, GPIO.HIGH)
                        else:
                            GPIO.output(31, GPIO.LOW)
                        test_rpi2_this_time = False
                    else:
                        test_rpi2_this_time = True


            elif counter == max_counter:    # reset counter
                counter = 0
                if i2c_error[0]:
                    alert = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_Crash_Alert_MotionDetected','w')
                    alert.write('1')
                    alert.close()
                    i2c_error[0] = False
                    end_error_assert = True
                elif end_error_assert:
                    alert = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_Crash_Alert_MotionDetected','w')
                    alert.write('0')
                    alert.close()
                    end_error_assert = False
                
                # REFRESH ALL I2C
                for i in range(num_boards):
                    refresh_config(i)
                
                #TODO: add refresh of all remote I/O expanders and dimmers and any other remote i2c devices that have a config
                
                if not(is_master):
                    set_i2c_mux(4)
                    #sleep(0.1)
                    shower_temp_last_2 = shower_temp_last
                    shower_temp_last = shower_temp
                    shower_temp_upper, shower_temp_lower = read_two_bytes_reg(0x48, 0x00)
                    shower_temp = (shower_temp_upper << 8) + shower_temp_lower
                    shower_temp = shower_temp >> 7
                    shower_temp = float(shower_temp) / 2.0
                    #print 'Shower temp:',shower_temp,'degC'
                    if shower_change_to_pink:
                        shower_change_to_pink = False
                        #setMult(led_strips[0], 0, 15, 57707, 65535, 64486, 3500, 10000) # pink
                        setMult(led_strips[0], 0, 15, 49333, 30000, 40000, 3500, 10000) # lilac

                    if (((shower_temp >= (shower_temp_last_2 + 2.0))or((shower_temp >= 25.0) and (shower_temp >= (shower_temp_last + 0.5)))) and shower_temp_not_reached):
                        shower_temp_not_reached = False
                        print 'Shower is ready'
                        if led_strip_power[0]:
                            setMult(led_strips[0], 0, 15, 5000, 55000, 65535, 3500, 1000)
                            #led_strip_IP, index, num, hue, saturation, brightness, kelvin, lifx_time)
                            led_strip_timer[0] = 400
                            shower_change_to_pink = True
                        
                        if (shower_blinds_EN or guest) and (not going_to_bed): #current_hour > 13:   # controlled by homekit button now. Shower blinds always happen when guest mode
                            after_shower_bedroom_lights = True
                            after_shower = True
                            for i in range(len(shower_blinds)):
                                f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_WindowCovering_'+str(shower_blinds[i])+'_TargetPosition','w')
                                f.write('0')
                                f.close()
                                f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_WindowCovering_'+str(shower_blinds[i])+'_CurrentPosition','w')
                                f.write('0')
                                f.close()

                        if STATUS[extractor[2]][extractor[3]] or STATUS[0][4]:  # fan main or mirror on
                            #if (extractor_en or bool(extractor[7])):  #extractor[7] = not_gated_by_extractor_en    # shower detection not gated by extractor enable
                            system(r'touch /var/lib/homebridge/input_'+str(extractor[0])+'/'+str(extractor[1]))
                            extractor_on = True
                            # if ((going_to_bed or bed) and bool(extractor[4])):
                            #     extractor_timer = 60    # 5min
                            # else:
                            extractor_timer = 180    # 15min
                            extractor_long = True

                else:
                    if welcome_home:
                        welcome_home_timer -= 1
                        #print welcome_home_timer
                        if welcome_home_timer == 0:
                            welcome_home = False
                            welcome_sitting = False
                            welcome_kitchen = False
                            welcome_landing = False
                            
                    if path.isfile(r'/var/lib/homebridge/input_3/3'):   # set up doorbell ring in morning reminder
                        remove(r'/var/lib/homebridge/input_3/3')

                # EXTRACTOR FANS
                if STATUS[extractor[0]][extractor[1]] and n_last_extractor_status: # fan just turned on manually
                    if (not extractor_on):
                        extractor_on = True
                        if (going_to_bed or bed) and bool(extractor[4]):
                            extractor_timer = extractor[6]   # short time
                            extractor_long = True
                        else:
                            extractor_timer = 60   # 5min
                            #extractor_long = True
                #elif (not(STATUS[extractor[0]][extractor[1]])) and (not(n_last_extractor_status)):
                    #extractor_on = False

                if STATUS[extractor[2]][extractor[3]] and n_last_extractor_light_status: # light just turned on
                    if (not extractor_on):
                        extractor_timer = extractor[5]    # amount of time before extractor comes on

                elif ((not STATUS[extractor[2]][extractor[3]]) and (not n_last_extractor_light_status)): # light just turned off
                    if ((going_to_bed or bed) and bool(extractor[4])):  # if in bed and fan set to not activate when in bed
                        if path.isfile(r'/var/lib/homebridge/input_'+str(extractor[0])+'/'+str(extractor[1])):
                            remove(r'/var/lib/homebridge/input_'+str(extractor[0])+'/'+str(extractor[1]))
                        extractor_on = False
                        extractor_long = False

                if extractor_timer:
                    if extractor_timer == 1:
                        if extractor_on:
                            if extractor_long or (not(STATUS[extractor[2]][extractor[3]])): # if on, and it's been through long timer or if the light is off, turn off
                                if path.isfile(r'/var/lib/homebridge/input_'+str(extractor[0])+'/'+str(extractor[1])):
                                    remove(r'/var/lib/homebridge/input_'+str(extractor[0])+'/'+str(extractor[1]))
                                extractor_on = False
                                extractor_long = False
                            elif STATUS[extractor[2]][extractor[3]] and (not((going_to_bed or bed) and bool(extractor[4]))):    # if it's just been through short time, put on long mode if light still on
                                extractor_timer = 96   # extend by 8min
                                extractor_long = True
                        elif STATUS[extractor[2]][extractor[3]] and (not((going_to_bed or bed) and bool(extractor[4]))):
                            if (extractor_en or bool(extractor[7])):  #extractor[7] = not_gated_by_extractor_en
                                system(r'touch /var/lib/homebridge/input_'+str(extractor[0])+'/'+str(extractor[1]))
                                extractor_on = True
                                extractor_timer = extractor[6]    # extend by short time (from config file)

                    extractor_timer-=1

                #print extractor_timer
                n_last_extractor_status = (not STATUS[extractor[0]][extractor[1]])
                n_last_extractor_light_status = (not STATUS[extractor[2]][extractor[3]])

                if is_master:
                    outside_temp_last = outside_temp
                    outside_temp = temperature[2]
                    if outside_temp >= outdoor_temp_thresh and outside_temp_last < outdoor_temp_thresh:
                        sock.sendto('write:input_control/:0:', (UDP_IP, UDP_PORT))
                    elif outside_temp < outdoor_temp_thresh and outside_temp_last >= outdoor_temp_thresh:
                        sock.sendto('delete:input_control/:0:', (UDP_IP, UDP_PORT))

                else:
                    if STATUS[4][0]:
                        outside_temp = (outdoor_temp_thresh+1)
                    else:
                        outside_temp = (outdoor_temp_thresh-1)

                if btc: # and btc_enable:
                    if (temperature[blinds_to_close[0]] >= blinds_to_close[1]) and (outside_temp >= outdoor_temp_thresh) and (not blinds_closed_mid) and (current_month>=4) and (current_month<=9) and (current_hour <= 17) and (current_hour >= 12):   # threshold for mid point set
                        #print 'closing blinds to mid to cool sitting room'
                        for i in range(len(blinds_to_close)-3):
                            if is_master:
                                sock.sendto('write:Cmd4Scripts/Cmd4States/:Status_WindowCovering_'+str(blinds_to_close[i+3])+'_TargetPosition:50', (UDP_IP, UDP_PORT))
                                sock.sendto('write:Cmd4Scripts/Cmd4States/:Status_WindowCovering_'+str(blinds_to_close[i+3])+'_CurrentPosition:50', (UDP_IP, UDP_PORT))
                            else:
                                f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_WindowCovering_'+str(blinds_to_close[i+3])+'_TargetPosition','w')
                                f.write('50')
                                f.close()
                                f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_WindowCovering_'+str(blinds_to_close[i+3])+'_CurrentPosition','w')
                                f.write('50')
                                f.close()
                        blinds_closed_mid = True
                    elif (temperature[blinds_to_close[0]] >= blinds_to_close[2]) and (outside_temp >= outdoor_temp_thresh) and (not blinds_closed_full) and (current_month>=4) and (current_month<=9) and (current_hour <= 17) and (current_hour >= 12) and (not PIR[2][2]):   # threshold for closing blind
                        #print 'closing blinds fully to cool sitting room'
                        for i in range(len(blinds_to_close)-3):
                            if is_master:
                                sock.sendto('write:Cmd4Scripts/Cmd4States/:Status_WindowCovering_'+str(blinds_to_close[i+3])+'_TargetPosition:0', (UDP_IP, UDP_PORT))
                                sock.sendto('write:Cmd4Scripts/Cmd4States/:Status_WindowCovering_'+str(blinds_to_close[i+3])+'_CurrentPosition:0', (UDP_IP, UDP_PORT))
                            else:
                                f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_WindowCovering_'+str(blinds_to_close[i+3])+'_TargetPosition','w')
                                f.write('0')
                                f.close()
                                f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_WindowCovering_'+str(blinds_to_close[i+3])+'_CurrentPosition','w')
                                f.write('0')
                                f.close()
                        blinds_closed_full = True

                    if blinds_closed_full or blinds_closed_mid:
                        if (current_hour >= 18) and (not night_time):
                            #print 'opening blinds as its after 6'
                            for i in range(len(blinds_to_close)-3):
                                if is_master:
                                    sock.sendto('write:Cmd4Scripts/Cmd4States/:Status_WindowCovering_'+str(blinds_to_close[i+3])+'_TargetPosition:100', (UDP_IP, UDP_PORT))
                                    sock.sendto('write:Cmd4Scripts/Cmd4States/:Status_WindowCovering_'+str(blinds_to_close[i+3])+'_CurrentPosition:100', (UDP_IP, UDP_PORT))
                                else:
                                    f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_WindowCovering_'+str(blinds_to_close[i+3])+'_TargetPosition','w')
                                    f.write('100')
                                    f.close()
                                    f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_WindowCovering_'+str(blinds_to_close[i+3])+'_CurrentPosition','w')
                                    f.write('100')
                                    f.close()
                                blinds_closed_mid = False
                                blinds_closed_full = False
                        elif ((temperature[blinds_to_close[0]] < (blinds_to_close[2] - 0.5)) and (not night_time)) and blinds_closed_full: # open blinds again if temperature drops and it's worth it timewise
                            #print 'opening blinds to mid as its cooled down'
                            for i in range(len(blinds_to_close)-3):
                                if is_master:
                                    sock.sendto('write:Cmd4Scripts/Cmd4States/:Status_WindowCovering_'+str(blinds_to_close[i+3])+'_TargetPosition:50', (UDP_IP, UDP_PORT))
                                    sock.sendto('write:Cmd4Scripts/Cmd4States/:Status_WindowCovering_'+str(blinds_to_close[i+3])+'_CurrentPosition:50', (UDP_IP, UDP_PORT))
                                else:
                                    f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_WindowCovering_'+str(blinds_to_close[i+3])+'_TargetPosition','w')
                                    f.write('50')
                                    f.close()
                                    f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_WindowCovering_'+str(blinds_to_close[i+3])+'_CurrentPosition','w')
                                    f.write('50')
                                    f.close()
                                blinds_closed_full = False
                        elif ((temperature[blinds_to_close[0]] < (blinds_to_close[1] - 0.5)) and (not night_time)) and blinds_closed_mid: # open blinds again if temperature drops and it's worth it timewise
                            #print 'opening blinds fully as its cooled down'
                            for i in range(len(blinds_to_close)-3):
                                if is_master:
                                    sock.sendto('write:Cmd4Scripts/Cmd4States/:Status_WindowCovering_'+str(blinds_to_close[i+3])+'_TargetPosition:100', (UDP_IP, UDP_PORT))
                                    sock.sendto('write:Cmd4Scripts/Cmd4States/:Status_WindowCovering_'+str(blinds_to_close[i+3])+'_CurrentPosition:100', (UDP_IP, UDP_PORT))
                                else:
                                    f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_WindowCovering_'+str(blinds_to_close[i+3])+'_TargetPosition','w')
                                    f.write('100')
                                    f.close()
                                    f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_WindowCovering_'+str(blinds_to_close[i+3])+'_CurrentPosition','w')
                                    f.write('100')
                                    f.close()
                                blinds_closed_mid = False
                                blinds_closed_full = False

            # READ REMOTE I/O EXPANDERS
            for i in range(num_IO):
                set_i2c_mux(IOmux[i])
                IO[i] = read_byte_reg_remote_io(io_adr, 0x00) & 0xF   # only interested in lower 4 bits
            
            set_i2c_mux(-1) # reset all i2c mux channels
                
            # CHECK FIREALARM/DOORBELL ## NB!!! fire alarm detector needs to force all timers to 0 and turn on LED strip
            if doorbell_timer > 0:
                doorbell_timer -= 1
                if package_garage and is_master and (doorbell_timer == 20):
                    #system('/var/lib/homebridge/package-garage/package_garage_doorbell_3.sh '+doorbell_ip_adr)  # restart process
                    if path.isfile(r'/var/lib/homebridge/input_control/package_garage'):
                        remove(r'/var/lib/homebridge/input_control/package_garage')
                #if package_garage and is_master and (doorbell_timer == 10):
                #    system(r'touch /var/lib/homebridge/input_control/package_garage')
            else:
                doorbell = False
                
            if is_master:
                #print "IO:",bin(IO[3])
                mask = 0b1 << cfg_firealarm[1]
                fire_alarm = not((IO[cfg_firealarm[0]]) & mask == mask)
                mask = 0b1 << cfg_doorbell[1]
                doorbell_press = not((IO[cfg_doorbell[0]]) & mask == mask)

                # if debug:
                #     doorbell_press = True
                
                if fire_alarm and not(fire_alarm_last):
                    sock.sendto('write:input_control/:fire_alarm:', (UDP_IP, UDP_PORT)) # pass on fire alarm status to slaves
                    sock.sendto('write:input_control/:fire_alarm:', (UDP_IP2, UDP_PORT2))
                elif not(fire_alarm) and (fire_alarm_last or first_time):
                    sock.sendto('delete:input_control/:fire_alarm:', (UDP_IP, UDP_PORT)) # deassert fire alarm status/remove from slave on master restart if not active
                    
                if doorbell_press and not(doorbell_last):
                    if package_garage:    # open garage door to receive package
                        f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_GarageDoorOpener_TargetDoorState','w')
                        f.write('0')
                        f.close()
                        package_garage_timer = 14
                        garage_door_open_package = True
                    else:
                        #if(not do_not_disturb):
                        sock.sendto('write:input_control/:door_bell:', (UDP_IP, UDP_PORT)) # pass on doorbell status to slaves. No deassertion required
                
            if (fire_alarm and not(fire_alarm_last)) or (doorbell_press and (not doorbell_last) and (not package_garage)): # and (not do_not_disturb)):
                for i in range(num_led_strips):
                    if not(led_strip_power[i]) and (((led_strip_not_in_bedroom[i] or (not bed)) and ((not do_not_disturb) or (led_strip_dnd_suppress_allowed[i] and dnd_suppress_doorbell_msg))) or fire_alarm):
                        #print 'led strip',i,'powered on'
                        setLEDpwr(led_strips[i], i, led_retry, led_retry_pwr, led_retry_counter, True, False, led_confirm, led_retry_delay, timeout=1)
                    led_strip_timer[i] = 0
                if not fire_alarm: # if doorbell
                    doorbell_timer = 100
                    doorbell = True
                    
            if (fire_alarm and not(fire_alarm_last)):
                for i in range(num_fire_lights):
                    fire_lights_prev_status[i] = STATUS[FIRE_LIGHTS[i][0]][FIRE_LIGHTS[i][1]]
                    if not STATUS[FIRE_LIGHTS[i][0]][FIRE_LIGHTS[i][1]]:
                        #print 'turning on fire light',FIRE_LIGHTS[i][0],FIRE_LIGHTS[i][1]
                        system(r'touch /var/lib/homebridge/input_'+str(FIRE_LIGHTS[i][0])+'/'+str(FIRE_LIGHTS[i][1]))
                #print 'prev status:',fire_lights_prev_status
                
            fire_alarm_last = fire_alarm
            doorbell_last = doorbell_press
            
            if not is_master:
                doorbell_press = False
                
            # if doorbell and not(doorbell_last):
                # #eventual control needs for loop to go through all strips
                # for i in range(num_led_strips):
                    # if not(led_strip_power[i]) and led_strip_not_in_bedroom[i]:
                        # setLEDpwr(led_strips[i], i, led_retry, led_retry_pwr, led_retry_counter, true, false, led_confirm, led_retry_delay, timeout=1)
                    # #sock.sendto(lifx_power_on, (led_strip_IP, led_strip_UDP_port))
                    # led_strip_timer[i] = 0

            # DO NOT DISTURB
            if do_not_disturb and is_master:
                if (not dnd_suppress_doorbell_msg):
                    motion_detected = ((IO[5] & 0b0001) == 0b0001)
                    if motion_detected:
                        system(r'touch /var/lib/homebridge/input_control/DND_Msg')
                        clear_dnd_msg = True

                if doorbell_press:
                    temporarily_enable_doorbell = True
            
            # CHECK INPUT FROM PHYSICAL BUTTONS
            for i in range(num_buttons_p_num_special_buttons):
                if i == num_buttons:    # special button
                    mask = 0b1 << special_button[0][1]
                    button_input[i] = not((IO[special_button[0][0]]) & mask == mask)
                else:
                    mask = 0b1 << SceneButton[i][1]
                    button_input[i] = not((IO[SceneButton[i][0]]) & mask == mask)
                
                if button_state[i] == 0: # state = 0: waiting for first press
                    if button_input[i]: 
                        button_state[i] = 1 # state = 1: received first press
                        button_timer[i] = 1 # debouncing
                        button_long_timer[i] = 10
                else:
                    if button_input[i] and button_state[i] == 1:
                        button_long_timer[i] -= 1
                        if button_long_timer[i] == 0:
                            button[i] = 4 # long press recorded
                            button_state[i] = 6 # state = 6: received long press, go here to wait for button to be released
                            #print 'Long press recorded from button',i
                    elif not(button_input[i]) and button_state[i] == 1 and button_timer[i] == 0:
                        button_state[i] = 2 # state = 2: waiting for second press
                        button_timer[i] = 1 # debouncing
                        button_timeout[i] = 4   ### dictates speed that double/triple press must happen at
                    elif button_state[i] == 2 and button_timer[i] == 0:
                        if button_input[i]:
                            button_state[i] = 3 # state = 3: received second press
                            button_timer[i] = 1 # debouncing
                        elif button_timeout[i] == 0:
                            button[i] = 1 # one press recorded
                            button_state[i] = 0
                            #print 'Single press recorded from button',i
                        button_timeout[i] -= 1
                    elif not(button_input[i]) and button_state[i] == 3 and button_timer[i] == 0:
                        button_state[i] = 4 # state = 4: waiting for third press
                        button_timer[i] = 1 # debouncing
                        button_timeout[i] = 4   ### dictates speed that double/triple press must happen at
                    elif button_state[i] == 4 and button_timer[i] == 0:
                        if button_input[i]:
                            button[i] = 3 # triple press recorded
                            button_state[i] = 5 # just to add timeout
                            button_timeout[i] = 4
                            #print 'Triple press recorded from button',i
                        elif button_timeout[i] == 0:
                            button[i] = 2 # double press recorded
                            button_state[i] = 0
                            #print 'Double press recorded from button',i
                        button_timeout[i] -= 1
                    elif button_state[i] == 5:
                        if button_timeout[i] == 0:
                            button_state[i] = 0
                        button_timeout[i] -= 1
                    elif button_state[i] == 6:
                        if not(button_input[i]):
                            button_state[i] = 0
                        
                    if button_timer[i] > 0:
                        button_timer[i] -= 1

            # Clean up bug where bedroom, zen den and bathroom buttons all phantom pressed together
            if not is_master:
                if button[0] == 1 and button[1] == 1 and button[4] == 1:
                    button[0] = 0
                    button[1] = 0
                    button[4] = 0
                    button[5] = 0   # bedside special button

            # ACT ON BUTTON
            for i in range(num_buttons):
                if button[i] != 0:
                    # Check if any lights the button controls are on first
                    num_lights_button = len(lights_under_button_control_off[i])
                    any_button_lights_on = False
                    for j in range(num_lights_button): 
                        if lights_under_button_control_off[i][j][0] == 0: #  switch
                            if STATUS[lights_under_button_control_off[i][j][1]][lights_under_button_control_off[i][j][2]] and (not ACTIVATED_AS_NIGHTLIGHT[lights_under_button_control_off[i][j][1]][lights_under_button_control_off[i][j][2]]):
                                any_button_lights_on = True
                        elif lights_under_button_control_off[i][j][0] == 1: # dimmer
                            if STATUS[DIMMER_SWITCH[lights_under_button_control_off[i][j][1]][0]][DIMMER_SWITCH[lights_under_button_control_off[i][j][1]][1]] and (not ACTIVATED_AS_NIGHTLIGHT[DIMMER_SWITCH[lights_under_button_control_off[i][j][1]][0]][DIMMER_SWITCH[lights_under_button_control_off[i][j][1]][1]]):
                                any_button_lights_on = True
                        elif lights_under_button_control_off[i][j][0] == 2: # led
                            if led_strip_power[lights_under_button_control_off[i][j][1]]:
                                any_button_lights_on = True
                                
                    #print 'any_button_lights_on =',any_button_lights_on
                    
                    # Decide what to do based on which button command received
                    if button[i] == 1:      # Single Press action
                        if button_flashing[i]: # if button flashing, proceed to next scene
                            #print 'button flashing: proceed to next scene'
                            if button_scene[i] == 2:
                                button_scene[i] = 0
                            else:
                                button_scene[i] += 1

                            if (night_time and (((current_hour > 20) or (current_hour < 6)) or bool(ReorderSceneNight[i][4])) and bool(ReorderSceneNight[i][0])):
                                set_scene(i,ReorderSceneNight[i][button_scene[i]+1], bed, is_master)
                            else:
                                set_scene(i,button_scene[i], bed, is_master)
                            button_flashing_timer[i] = button_flashing_timeout
                        elif any_button_lights_on: # if any lights on, turn all off
                            #print 'lights on: turn all off'
                            button_flashing[i] = False
                            led_flashing[button_led_ind[i][0]][button_led_ind[i][1]] = False
                            set_scene_off(i)
                            set_one_led(button_led_ind[i][0], button_led_ind[i][1], 1)
                        else: # if lights off, turn on scene 1 (medium brightness), enter flashing state
                            #print 'lights off: turn on scene 0, enter flashing state'
                            button_scene[i] = 1
                            button_flashing[i] = True
                            button_flashing_timer[i] = button_flashing_timeout
                            set_one_led(button_led_ind[i][0], button_led_ind[i][1], 0)
                            led_flashing[button_led_ind[i][0]][button_led_ind[i][1]] = True
                            if (night_time and (((current_hour > 20) or (current_hour < 6)) or bool(ReorderSceneNight[i][4])) and bool(ReorderSceneNight[i][0])):
                                set_scene(i,ReorderSceneNight[i][button_scene[i]+1], bed, is_master)
                            else:
                                set_scene(i,button_scene[i], bed, is_master)
                        
                        if is_master:
                            if (i == 3): # hall button
                                welcome_landing = False #True # welcome landing dismissed by hall button press
                                if left_house:  # if arriving home and pressed hall button
                                    for i in range(num_buttons):
                                        button_scene[i] = 0 # reset all button scenes so the first time the button is pressed if light already on, it goes to the first scene
                                    welcome_home = True
                                    welcome_sitting = True
                                    welcome_kitchen = True
                                    welcome_home_timer = 60
                                    left_house = False
                                    sock.sendto('delete:input_control/:left_house:', (UDP_IP, UDP_PORT))
                                    if path.isfile(r'/var/lib/homebridge/input_control/left_house_nv'):
                                        remove(r'/var/lib/homebridge/input_control/left_house_nv')
                                    if path.isfile(r'/var/lib/homebridge/input_control/package_garage'):
                                        remove(r'/var/lib/homebridge/input_control/package_garage')
                                    if path.isfile(r'/var/lib/homebridge/input_control/security_lights'):
                                        remove(r'/var/lib/homebridge/input_control/security_lights')

                            elif left_house:
                                for i in range(num_buttons):
                                    button_scene[i] = 0 # reset all button scenes so the first time the button is pressed if light already on, it goes to the first scene
                                left_house = False
                                sock.sendto('delete:input_control/:left_house:', (UDP_IP, UDP_PORT))
                                if path.isfile(r'/var/lib/homebridge/input_control/left_house_nv'):
                                    remove(r'/var/lib/homebridge/input_control/left_house_nv')
                                if path.isfile(r'/var/lib/homebridge/input_control/package_garage'):
                                    remove(r'/var/lib/homebridge/input_control/package_garage')
                                if path.isfile(r'/var/lib/homebridge/input_control/security_lights'):
                                    remove(r'/var/lib/homebridge/input_control/security_lights')

                        ###########################################
                        # if (not is_master) and (i==4):
                        #     f = open('/var/lib/homebridge/zen_den.log','a')
                        #     f.write('Zen den button pressed at ')
                        #     now = datetime.now()
                        #     f.write(now.strftime("%d/%m/%Y %H:%M:%S\n"))
                        #     f.close()
                        ###########################################
                            
                    elif button[i] == 2:    # Double Press action
                        if button_flashing[i]: # if button flashing, turn all lights off
                            #print 'button flashing: turn all lights off'
                            button_flashing[i] = False
                            led_flashing[button_led_ind[i][0]][button_led_ind[i][1]] = False
                            set_scene_off(i)
                            set_one_led(button_led_ind[i][0], button_led_ind[i][1], 1)
                        elif any_button_lights_on: # if any lights on, proceed to next scene, enter flashing state
                            #print 'lights are on: proceed to next scene, enter flashing state'
                            button_flashing[i] = True
                            button_flashing_timer[i] = button_flashing_timeout
                            set_one_led(button_led_ind[i][0], button_led_ind[i][1], 0)
                            led_flashing[button_led_ind[i][0]][button_led_ind[i][1]] = True
                            if button_scene[i] == 2:
                                button_scene[i] = 0
                            else:
                                button_scene[i] += 1
                            #if (night_time and (current_hour > 20)) and ReorderSceneNight[i][0]:
                            if (night_time and (((current_hour > 20) or (current_hour < 6)) or bool(ReorderSceneNight[i][4])) and bool(ReorderSceneNight[i][0])):
                                set_scene(i,ReorderSceneNight[i][button_scene[i]+1], bed, is_master)
                            else:
                                set_scene(i,button_scene[i], bed, is_master)
                        else: # if lights off, turn on scene 0 (max brightness), enter flashing state
                            #print 'lights are off: turn on scene 1, enter flashing state'
                            button_scene[i] = 0
                            button_flashing[i] = True
                            button_flashing_timer[i] = button_flashing_timeout
                            if (night_time and (current_hour > 20)) and ReorderSceneNight[i][0]:
                                set_scene(i,ReorderSceneNight[i][button_scene[i]+1], bed, is_master)
                            else:
                                set_scene(i,button_scene[i], bed, is_master)
                            set_one_led(button_led_ind[i][0], button_led_ind[i][1], 0)
                            led_flashing[button_led_ind[i][0]][button_led_ind[i][1]] = True
                        
                    elif button[i] == 3:    # Triple Press action
                        button_fast_flash_counter[i] = 3
                        if is_master:
                            if((i == 0) or (i == 1)):   # kitchen or sitting room button
                                if (STATUS[1][0] and STATUS[2][2]): # if kitchen and sitting nightlight on
                                    ACTIVATED_AS_NIGHTLIGHT[1][0] = True    # put it in night light mode
                                    night_light_activated[2] = True
                                    night_light_timer[2] = 1800 #NIGHT_LIGHTS[2][11] #night_light_on_time   # x3 longer time needed
                                    ACTIVATED_AS_NIGHTLIGHT[2][2] = True    # put it in night light mode
                                    night_light_activated[3] = True
                                    night_light_timer[3] = NIGHT_LIGHTS[3][11] #night_light_on_time

                                    switches_to_turn_off = [[2,0],[2,4],[2,6],[1,4],[1,6],[1,7],[0,2],[0,3],[0,4],[0,5],[0,7]] #,[0,1],[1,2],[1,3]
                                elif STATUS[1][0]:    # if sitting room side light on
                                    ACTIVATED_AS_NIGHTLIGHT[1][0] = True    # put it in night light mode
                                    night_light_activated[2] = True
                                    night_light_timer[2] = 1800 #NIGHT_LIGHTS[2][11] #night_light_on_time # x3 longer time needed

                                    switches_to_turn_off = [[2,0],[2,2],[2,4],[2,6],[1,4],[1,6],[1,7],[0,2],[0,3],[0,4],[0,5],[0,7]] #,[0,1],[1,2],[1,3]
                                elif STATUS[2][2]:    # if kitchen counter light on
                                    ACTIVATED_AS_NIGHTLIGHT[2][2] = True    # put it in night light mode
                                    night_light_activated[3] = True
                                    night_light_timer[3] = NIGHT_LIGHTS[3][11] #night_light_on_time

                                    switches_to_turn_off = [[2,0],[2,4],[2,6],[1,4],[1,6],[1,7],[0,2],[0,3],[0,4],[0,5],[0,7]] #,[0,1],[1,2],[1,3]
                                else:
                                    switches_to_turn_off = [[2,0],[2,2],[2,4],[2,6],[1,4],[1,6],[1,7],[0,2],[0,3],[0,4],[0,5],[0,7]] #[1,1], ,[0,1],[1,2],[1,3]
                                led_strips_to_turn_off = [0,1,2,3]
                                switches_to_turn_on = []
                                dimmers_to_turn_on = []
                                dimmers_brightness = []
                                led_strips_to_turn_on = []
                                led_strips_brightness = []
                                led_strips_hue = []
                                led_strips_saturation = []
                                off_board_switches_to_turn_off = [[1,0],[1,6],[0,7],[0,5]] #,[1,7]
                                off_board_dimmers_to_turn_off = []
                                off_board_led_strips_to_turn_off = []
                                sockets_to_turn_off = [1,2]
                                off_board_sockets_to_turn_off = []

                                if (not morning):
                                    sock.sendto('write:input_control/:gtb:', (UDP_IP, UDP_PORT)) 
                                    going_to_bed = True
                                    system(r'touch /var/lib/homebridge/input_control/going_to_bed_nv')
                                    
                                    system(r'touch /var/lib/homebridge/input_control/do_not_disturb')
                                    if bedtime:   
                                        if path.isfile(r'/var/lib/homebridge/input_control/dnd_suppress_doorbell_msg'):
                                            remove(r'/var/lib/homebridge/input_control/dnd_suppress_doorbell_msg')
                                    else: # don't display the DND message if going to bed during the day
                                        system(r'touch /var/lib/homebridge/input_control/dnd_suppress_doorbell_msg')
                                    if (i == 0):
                                        off_board_switches_to_turn_on = [[0,6]]   # bathroom nightlight
                                        off_board_led_strips_to_turn_on = [0]
                                        off_board_led_strips_brightness = [60]
                                        off_board_led_strips_hue = [33]
                                        off_board_led_strips_saturation = [73]
                                        off_board_dimmers_to_turn_on = []
                                        off_board_dimmers_brightness = []
                                    elif (i == 1):
                                        if DIMMER_SET_BRIGHTNESS[3] <= 0.5: # if sitting room side lights dimmer than 50%, set bedroom ultra dark
                                            off_board_switches_to_turn_on = [[0,6]]   # bathroom nightlight
                                            off_board_dimmers_to_turn_on = [0,2]
                                            off_board_dimmers_brightness = [70,10]
                                            off_board_led_strips_to_turn_on = [0, 2, 3]
                                            off_board_led_strips_brightness = [60, 55, 30]
                                            off_board_led_strips_hue = [33, 33, 162]
                                            off_board_led_strips_saturation = [73, 73, 100]
                                        else:
                                            off_board_switches_to_turn_on = [[0,4],[0,6]]   # bathroom mirror/nightlight
                                            off_board_dimmers_to_turn_on = [0,1]
                                            off_board_dimmers_brightness = [70,30]
                                            off_board_led_strips_to_turn_on = [0, 2, 3]
                                            off_board_led_strips_brightness = [70, 100, 30]
                                            off_board_led_strips_hue = [284, 33, 180]
                                            off_board_led_strips_saturation = [100, 73, 88]

                                        sock.sendto('write:Cmd4Scripts/Cmd4States/:Status_WindowCovering_1_TargetPosition:0', (UDP_IP, UDP_PORT))
                                        sock.sendto('write:Cmd4Scripts/Cmd4States/:Status_WindowCovering_1_CurrentPosition:0', (UDP_IP, UDP_PORT))

                                        sock.sendto('write:input_control/:HP2_S:', (UDP_IP2, UDP_PORT2))    # start sleep music

                                else:
                                    off_board_switches_to_turn_on = []
                                    off_board_led_strips_to_turn_on = []
                                    off_board_led_strips_brightness = []
                                    off_board_led_strips_hue = []
                                    off_board_led_strips_saturation = []
                                    off_board_dimmers_to_turn_on = []
                                    off_board_dimmers_brightness = []
                                        
                                if night_time:
                                    dimmers_to_turn_off = [0,1,2,5,6]
                                    f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_Dimmer_4_Brightness','r')
                                    night_light_store_val[1] = f.readline()
                                    f.close()
                                    f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_Dimmer_4_Brightness','w')
                                    f.write('60')
                                    f.close()
                                    f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_Dimmer_4_On','w')
                                    f.write('true')
                                    f.close()
                                    night_light_activated[1] = True
                                    ACTIVATED_AS_NIGHTLIGHT[NIGHT_LIGHTS[1][2]][NIGHT_LIGHTS[1][3]] = True
                                    night_light_timer[1] = NIGHT_LIGHTS[1][11] #night_light_on_time
                                    
                                    STATUS[0][0] = False    # Force Hall Lamp status to False, so NL timer isn't reloaded
                                    STATUS[1][7] = False    # Force Hall Main status to False, so NL timer isn't reloaded
                                    STATUS[4][0] = False    # Force Landing status to False, so NL timer isn't reloaded
                                    
                                    night_light_timer[0] = 0    # Stairs NL timer
                                    
                                else:
                                    dimmers_to_turn_off = [0,1,2,3,4,5,6]

                                if (current_hour >= 6) and (current_hour < 8) and night_time and (i == 0):    # if kitchen triple press in morning when still dark
                                    #print 'front light turned on'
                                    system(r'touch /var/lib/homebridge/input_0/1')
                                    security_light_timer[0] = 6000
                                    security_light_activated[0] = True
                                    security_light_timer[3] = 6000 # hold off front security light
                                else:
                                    if path.isfile(r'/var/lib/homebridge/input_0/1'):   # this is what turns off outdoor front normally - it's taken out of list above
                                        remove(r'/var/lib/homebridge/input_0/1')

                                sock.sendto('delete:input_control/:HP0:', (UDP_IP2, UDP_PORT2))
                                sock.sendto('delete:input_control/:HP1:', (UDP_IP2, UDP_PORT2))

                                if bedtime:
                                    sock.sendto('write:Cmd4Scripts/Cmd4States/:Status_Alarm_SecuritySystemTargetState:2', (UDP_IP2, UDP_PORT2)) # set alarm to night mode (2)

                            elif (i == 3):  # front door button
                                left_house = True
                                sock.sendto('write:input_control/:left_house:', (UDP_IP, UDP_PORT))
                                system(r'touch /var/lib/homebridge/input_control/left_house_nv')
                                left_house_hold_off = 12    # 1 minute before can be removed by motion
                                night_light_timer[1] = NIGHT_LIGHTS[1][11] #night_light_on_time # delay hall lamp NL

                                switches_to_turn_off = [[2,0],[2,2],[2,4],[2,6],[1,4],[1,6],[1,7],[0,2],[0,4],[0,5],[0,7]] #,[0,3] - DS bathroom fan ,[1,2],[1,3]
                                dimmers_to_turn_off = [0,1,2,3,4,5,6]
                                led_strips_to_turn_off = [0,1,2,3]
                                switches_to_turn_on = []
                                dimmers_to_turn_on = []
                                dimmers_brightness = []
                                led_strips_to_turn_on = []
                                led_strips_brightness = []
                                led_strips_hue = []
                                led_strips_saturation = []
                                off_board_switches_to_turn_off = [[1,0],[1,4],[1,5],[1,6],[1,7],[0,0],[0,1],[0,2],[0,4],[0,6]]  # ,[0,7] - tree, ,[0,5] - US bathroom fan ,[1,3]
                                off_board_dimmers_to_turn_off = [0,1,2]
                                off_board_led_strips_to_turn_off = [0,1,2,3,4,5]
                                off_board_switches_to_turn_on = []     
                                off_board_dimmers_to_turn_on = []
                                off_board_dimmers_brightness = []
                                off_board_led_strips_to_turn_on = []
                                off_board_led_strips_brightness = []
                                off_board_led_strips_hue = []
                                off_board_led_strips_saturation = []
                                sockets_to_turn_off = [1]   #,2
                                off_board_sockets_to_turn_off = [0]

                                sock.sendto('delete:input_control/:HP0:', (UDP_IP2, UDP_PORT2))
                                sock.sendto('delete:input_control/:HP1:', (UDP_IP2, UDP_PORT2))
                                sock.sendto('delete:input_control/:HP2:', (UDP_IP2, UDP_PORT2))

                                sock.sendto('write:Cmd4Scripts/Cmd4States/:Status_Alarm_SecuritySystemTargetState:1', (UDP_IP2, UDP_PORT2)) # set alarm to away mode (1)

                            else:
                                switches_to_turn_off = []
                                dimmers_to_turn_off = []
                                led_strips_to_turn_off = []
                                switches_to_turn_on = []
                                dimmers_to_turn_on = []
                                dimmers_brightness = []
                                led_strips_to_turn_on = []
                                led_strips_brightness = []
                                led_strips_hue = []
                                led_strips_saturation = []
                                off_board_switches_to_turn_off = []
                                off_board_dimmers_to_turn_off = []
                                off_board_led_strips_to_turn_off = []
                                off_board_switches_to_turn_on = []     
                                off_board_dimmers_to_turn_on = []
                                off_board_dimmers_brightness = []
                                off_board_led_strips_to_turn_on = []
                                off_board_led_strips_brightness = []
                                off_board_led_strips_hue = []
                                off_board_led_strips_saturation = []
                                sockets_to_turn_off = []
                                off_board_sockets_to_turn_off = []

                            # Garage Door - Close if any triple press received
                            f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_GarageDoorOpener_TargetDoorState','w')
                            f.write('1')
                            f.close()
                            
                            # Turn off TV if any triple press received
                            if path.isfile(r'/var/lib/homebridge/input_control/tv'):
                                remove(r'/var/lib/homebridge/input_control/tv')

                            # Arm Security Lights if any triple button pressed
                            f = open(r'/var/lib/homebridge/input_control/security_lights','w')
                            f.close()

                        else:
                            if i == 0:
                                switches_to_turn_off = [[1,6],[1,7],[0,0],[0,1],[0,4],[0,5],[0,6],[0,7]]
                                dimmers_to_turn_off = [2]
                                led_strips_to_turn_off = [0,1,4,5]
                                switches_to_turn_on = []
                                dimmers_to_turn_on = []
                                dimmers_brightness = []
                                led_strips_to_turn_on = []
                                led_strips_brightness = []
                                led_strips_hue = []
                                led_strips_saturation = []
                                off_board_switches_to_turn_off = [[2,0],[2,2],[2,4],[2,6],[1,4],[1,6],[1,7],[0,1],[0,2],[0,3],[0,4],[0,5],[0,7]] #,[1,1],[1,2],[1,3]
                                off_board_dimmers_to_turn_off = [0,1,2,3,4,5,6]
                                off_board_led_strips_to_turn_off = [0,1,2,3]
                                off_board_switches_to_turn_on = []     
                                off_board_dimmers_to_turn_on = []
                                off_board_dimmers_brightness = []
                                off_board_led_strips_to_turn_on = []
                                off_board_led_strips_brightness = []
                                off_board_led_strips_hue = []
                                off_board_led_strips_saturation = []
                                sockets_to_turn_off = []
                                off_board_sockets_to_turn_off = [1,2]

                                sock.sendto('write:input_control:do_not_disturb:', (UDP_IP, UDP_PORT))

                                if bedtime:
                                    sock.sendto('write:Cmd4Scripts/Cmd4States/:Status_Alarm_SecuritySystemTargetState:2', (UDP_IP2, UDP_PORT2)) # set alarm to night mode (2)
                                    sock.sendto('delete:input_control:dnd_suppress_doorbell_msg:', (UDP_IP, UDP_PORT))
                                else: # don't display the DND message if going to bed during the day
                                    sock.sendto('write:input_control:dnd_suppress_doorbell_msg:', (UDP_IP, UDP_PORT))

                                # Arm Security Lights if bedroom triple button pressed
                                sock.sendto('write:input_control:security_lights:', (UDP_IP, UDP_PORT))

                            elif i == 2:    # Office - turn off downstairs lights
                                switches_to_turn_off = []
                                dimmers_to_turn_off = []
                                led_strips_to_turn_off = [1]
                                switches_to_turn_on = []
                                dimmers_to_turn_on = []
                                dimmers_brightness = []
                                led_strips_to_turn_on = []
                                led_strips_brightness = []
                                led_strips_hue = []
                                led_strips_saturation = []
                                off_board_switches_to_turn_off = [[2,0],[2,2],[2,4],[2,6],[1,4],[1,6],[1,7],[0,2],[0,3],[0,4],[0,5],[0,7]] #[1,1],,[1,2],[1,3],[0,1]
                                off_board_dimmers_to_turn_off = [0,1,2,3,4,5,6]
                                off_board_led_strips_to_turn_off = [0,1,2,3]
                                off_board_switches_to_turn_on = []     
                                off_board_dimmers_to_turn_on = []
                                off_board_dimmers_brightness = []
                                off_board_led_strips_to_turn_on = []
                                off_board_led_strips_brightness = []
                                off_board_led_strips_hue = []
                                off_board_led_strips_saturation = []
                                sockets_to_turn_off = []
                                off_board_sockets_to_turn_off = [1,2]
                            else:
                                switches_to_turn_off = []
                                dimmers_to_turn_off = []
                                led_strips_to_turn_off = []
                                switches_to_turn_on = []
                                dimmers_to_turn_on = []
                                dimmers_brightness = []
                                led_strips_to_turn_on = []
                                led_strips_brightness = []
                                led_strips_hue = []
                                led_strips_saturation = []
                                off_board_switches_to_turn_off = []
                                off_board_dimmers_to_turn_off = []
                                off_board_led_strips_to_turn_off = []
                                off_board_switches_to_turn_on = []     
                                off_board_dimmers_to_turn_on = []
                                off_board_dimmers_brightness = []
                                off_board_led_strips_to_turn_on = []
                                off_board_led_strips_brightness = []
                                off_board_led_strips_hue = []
                                off_board_led_strips_saturation = []
                                sockets_to_turn_off = []
                                off_board_sockets_to_turn_off = []

                            # Garage Door - Close if any triple press received
                            sock.sendto('write:Cmd4Scripts/Cmd4States/:Status_GarageDoorOpener_TargetDoorState:1', (UDP_IP, UDP_PORT))
                            
                            # Turn off TV if any triple press received
                            sock.sendto('delete:input_control/:tv:', (UDP_IP, UDP_PORT))

                        # TEMPLATE        
                            # switches_to_turn_off = []
                            # dimmers_to_turn_off = []
                            # led_strips_to_turn_off = []
                            # switches_to_turn_on = []
                            # dimmers_to_turn_on = []
                            # dimmers_brightness = []
                            # led_strips_to_turn_on = []
                            # led_strips_brightness = []
                            # led_strips_hue = []
                            # led_strips_saturation = []
                            # off_board_switches_to_turn_off = []
                            # off_board_dimmers_to_turn_off = []
                            # off_board_led_strips_to_turn_off = []
                            # off_board_switches_to_turn_on = []     
                            # off_board_dimmers_to_turn_on = []
                            # off_board_dimmers_brightness = []
                            # off_board_led_strips_to_turn_on = []
                            # off_board_led_strips_brightness = []
                            # off_board_led_strips_hue = []
                            # off_board_led_strips_saturation = []

                        # On board OFF
                        for switch_to_turn_off in switches_to_turn_off:
                            if path.isfile(r'/var/lib/homebridge/input_'+str(switch_to_turn_off[0])+'/'+str(switch_to_turn_off[1])):
                                remove(r'/var/lib/homebridge/input_'+str(switch_to_turn_off[0])+'/'+str(switch_to_turn_off[1]))
                                
                        for dimmer_to_turn_off in dimmers_to_turn_off:
                            f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_Dimmer_'+str(dimmer_to_turn_off)+'_On','w')
                            f.write('false')
                            f.close()
                            
                        for led_strip_to_turn_off in led_strips_to_turn_off:
                            f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_Led_Strip_'+str(led_strip_to_turn_off)+'_On','w')
                            f.write('false')
                            f.close()
                        
                        # On board ON
                        for switch_to_turn_on in switches_to_turn_on:
                            system(r'touch /var/lib/homebridge/input_'+str(switch_to_turn_on[0])+'/'+str(switch_to_turn_on[1]))

                        j = 0
                        for dimmer_brightness in dimmers_brightness:
                            f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_Dimmer_'+str(dimmers_to_turn_on[j])+'_Brightness','w')
                            f.write(str(dimmer_brightness))
                            f.close()
                            j += 1
                            
                        for dimmer_to_turn_on in dimmers_to_turn_on:
                            f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_Dimmer_'+str(dimmer_to_turn_on)+'_On','w')
                            f.write('true')
                            f.close()

                        j = 0
                        for led_strip_brightness in led_strips_brightness:
                            f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_Led_Strip_'+str(led_strips_to_turn_on[j])+'_Brightness','w')
                            f.write(str(led_strip_brightness))
                            f.close()
                            j += 1

                        j = 0
                        for led_strip_hue in led_strips_hue:
                            f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_Led_Strip_'+str(led_strips_to_turn_on[j])+'_Hue','w')
                            f.write(str(led_strip_hue))
                            f.close()
                            j += 1

                        j = 0
                        for led_strip_saturation in led_strips_saturation:
                            f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_Led_Strip_'+str(led_strips_to_turn_on[j])+'_Saturation','w')
                            f.write(str(led_strip_saturation))
                            f.close()
                            j += 1

                        for led_strip_to_turn_on in led_strips_to_turn_on:
                            f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_Led_Strip_'+str(led_strip_to_turn_on)+'_On','w')
                            f.write('true')
                            f.close()

                        for socket_to_turn_off in sockets_to_turn_off:
                            f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_Outlet_'+str(socket_to_turn_off)+'_On','w')
                            f.write('false')
                            f.close()

                        # Off board OFF
                        for switch_to_turn_off in off_board_switches_to_turn_off:
                            sock.sendto('delete:input_'+str(switch_to_turn_off[0])+':'+str(switch_to_turn_off[1])+':', (UDP_IP, UDP_PORT))

                        for dimmer_to_turn_off in off_board_dimmers_to_turn_off:
                            sock.sendto('write:Cmd4Scripts/Cmd4States:Status_Dimmer_'+str(dimmer_to_turn_off)+'_On:false\n', (UDP_IP, UDP_PORT))

                        for led_strip_to_turn_off in off_board_led_strips_to_turn_off:
                            sock.sendto('write:Cmd4Scripts/Cmd4States:Status_Led_Strip_'+str(led_strip_to_turn_off)+'_On:false\n', (UDP_IP, UDP_PORT))

                        for socket_to_turn_off in off_board_sockets_to_turn_off:
                            sock.sendto('write:Cmd4Scripts/Cmd4States:Status_Outlet_'+str(socket_to_turn_off)+'_On:false\n', (UDP_IP, UDP_PORT))

                        # Off board ON
                        for switch_to_turn_on in off_board_switches_to_turn_on:
                            sock.sendto('write:input_'+str(switch_to_turn_on[0])+':'+str(switch_to_turn_on[1])+':', (UDP_IP, UDP_PORT))

                        j = 0
                        for dimmer_brightness in off_board_dimmers_brightness:
                            sock.sendto('write:Cmd4Scripts/Cmd4States:Status_Dimmer_'+str(off_board_dimmers_to_turn_on[j])+'_Brightness:'+str(dimmer_brightness)+'\n', (UDP_IP, UDP_PORT))
                            j += 1
                            
                        for dimmer_to_turn_on in off_board_dimmers_to_turn_on:
                            sock.sendto('write:Cmd4Scripts/Cmd4States:Status_Dimmer_'+str(dimmer_to_turn_on)+'_On:true\n', (UDP_IP, UDP_PORT))

                        j = 0
                        for led_strip_brightness in off_board_led_strips_brightness:
                            sock.sendto('write:Cmd4Scripts/Cmd4States:Status_Led_Strip_'+str(off_board_led_strips_to_turn_on[j])+'_Brightness:'+str(led_strip_brightness)+'\n', (UDP_IP, UDP_PORT))
                            j += 1

                        j = 0
                        for led_strip_hue in off_board_led_strips_hue:
                            sock.sendto('write:Cmd4Scripts/Cmd4States:Status_Led_Strip_'+str(off_board_led_strips_to_turn_on[j])+'_Hue:'+str(led_strip_hue)+'\n', (UDP_IP, UDP_PORT))
                            j += 1

                        j = 0
                        for led_strip_saturation in off_board_led_strips_saturation:
                            sock.sendto('write:Cmd4Scripts/Cmd4States:Status_Led_Strip_'+str(off_board_led_strips_to_turn_on[j])+'_Saturation:'+str(led_strip_saturation)+'\n', (UDP_IP, UDP_PORT))
                            j += 1

                        for led_strip_to_turn_on in off_board_led_strips_to_turn_on:
                            sock.sendto('write:Cmd4Scripts/Cmd4States:Status_Led_Strip_'+str(led_strip_to_turn_on)+'_On:true\n', (UDP_IP, UDP_PORT))

                            
                    elif button[i] == 4:    # Long Press action
                        if is_master:
                            if (i == 0):
                                if STATUS[2][2]:    # STATUS[2][2] = counter
                                    if path.isfile(r'/var/lib/homebridge/input_2/2'):
                                        remove(r'/var/lib/homebridge/input_2/2')
                                else:
                                    system(r'touch /var/lib/homebridge/input_2/2')
                                button_fast_flash_counter[i] = 4
                            if (i == 1):
                                if STATUS[4][1]:    # STATUS[4][1] = sitting room blind
                                    sock.sendto('write:Cmd4Scripts/Cmd4States/:Status_WindowCovering_0_TargetPosition:0', (UDP_IP, UDP_PORT))
                                    sock.sendto('write:Cmd4Scripts/Cmd4States/:Status_WindowCovering_0_CurrentPosition:0', (UDP_IP, UDP_PORT))
                                else:
                                    sock.sendto('write:Cmd4Scripts/Cmd4States/:Status_WindowCovering_0_TargetPosition:100', (UDP_IP, UDP_PORT))
                                    sock.sendto('write:Cmd4Scripts/Cmd4States/:Status_WindowCovering_0_CurrentPosition:100', (UDP_IP, UDP_PORT))
                                button_fast_flash_counter[i] = 4
                            if(i == 3):   # Hall
                                # if STATUS[4][0]:    # Landing Light
                                #     sock.sendto('delete:input_1/:6:', (UDP_IP, UDP_PORT))
                                # else:
                                #     sock.sendto('write:input_1/:6:', (UDP_IP, UDP_PORT))
                                f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_GarageDoorOpener_CurrentDoorState','r')
                                garage_position = f.readline()
                                if "1" in garage_position:
                                    f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_GarageDoorOpener_TargetDoorState','w')
                                    f.write('0')
                                    f.close()
                                    f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_GarageDoorOpener_CurrentDoorState','w')
                                    f.write('0')
                                    f.close()

                                else:
                                    f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_GarageDoorOpener_TargetDoorState','w')
                                    f.write('1')
                                    f.close()
                                    f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_GarageDoorOpener_CurrentDoorState','w')
                                    f.write('1')
                                    f.close()
                                button_fast_flash_counter[i] = 4
                        else:
                            if i == 0:  # bedroom
                                if bed:
                                    if path.isfile(r'/var/lib/homebridge/input_control/bed'):
                                        remove(r'/var/lib/homebridge/input_control/bed')
                                    f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_WindowCovering_1_TargetPosition','w')
                                    f.write('100')
                                    f.close()
                                    f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_WindowCovering_1_CurrentPosition','w')
                                    f.write('100')
                                    f.close()

                                    #sock.sendto('write:Cmd4Scripts/Cmd4States/:Status_WindowCovering_1_TargetPosition:100\n', (UDP_IP, UDP_PORT))
                                    #sock.sendto('write:Cmd4Scripts/Cmd4States/:Status_WindowCovering_1_CurrentPosition:100\n', (UDP_IP, UDP_PORT))

                                    sock.sendto('delete:input_control:do_not_disturb:', (UDP_IP, UDP_PORT))
                                    sock.sendto('delete:input_control:dnd_suppress_doorbell_msg:', (UDP_IP, UDP_PORT))

                                    if morning:
                                        sock.sendto('write:Cmd4Scripts/Cmd4States/:Status_Alarm_SecuritySystemTargetState:3', (UDP_IP2, UDP_PORT2)) # disarm alarm (3)

                                        f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_WindowCovering_2_TargetPosition','w')
                                        f.write('100')
                                        f.close()
                                        f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_WindowCovering_2_CurrentPosition','w')
                                        f.write('100')
                                        f.close()
                                        f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_WindowCovering_4_TargetPosition','w')
                                        f.write('100')
                                        f.close()
                                        f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_WindowCovering_4_CurrentPosition','w')
                                        f.write('100')
                                        f.close()
                                else:
                                    f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_WindowCovering_1_CurrentPosition','r')
                                    blind_position = f.readline()
                                    if "100" in blind_position: # blind is open
                                        f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_WindowCovering_1_TargetPosition','w')
                                        f.write('0')
                                        f.close()
                                        f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_WindowCovering_1_CurrentPosition','w')
                                        f.write('0')
                                        f.close()

                                    else:
                                        if after_shower:
                                            set_scene_off(0)
                                            if (not night_time):
                                                for j in range(len(shower_blinds)):
                                                    f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_WindowCovering_'+str(shower_blinds[j])+'_TargetPosition','w')
                                                    f.write('100')
                                                    f.close()
                                                    f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_WindowCovering_'+str(shower_blinds[j])+'_CurrentPosition','w')
                                                    f.write('100')
                                                    f.close()
                                        else:
                                            f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_WindowCovering_1_TargetPosition','w')
                                            f.write('100')
                                            f.close()
                                            f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_WindowCovering_1_CurrentPosition','w')
                                            f.write('100')
                                            f.close()
                                    after_shower = False

                                button_fast_flash_counter[i] = 4

                            elif i == 2:    # office
                                f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_WindowCovering_2_CurrentPosition','r')
                                blind_position = f.readline()
                                if "100" in blind_position:
                                    f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_WindowCovering_2_TargetPosition','w')
                                    f.write('0')
                                    f.close()
                                    f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_WindowCovering_2_CurrentPosition','w')
                                    f.write('0')
                                    f.close()

                                else:
                                    f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_WindowCovering_2_TargetPosition','w')
                                    f.write('100')
                                    f.close()
                                    f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_WindowCovering_2_CurrentPosition','w')
                                    f.write('100')
                                    f.close()
                                button_fast_flash_counter[i] = 4

                            elif i == 3:    # front bedroom
                                f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_WindowCovering_3_CurrentPosition','r')
                                blind_position = f.readline()
                                if "100" in blind_position:
                                    f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_WindowCovering_3_TargetPosition','w')
                                    f.write('0')
                                    f.close()
                                    f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_WindowCovering_3_CurrentPosition','w')
                                    f.write('0')
                                    f.close()

                                else:
                                    f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_WindowCovering_3_TargetPosition','w')
                                    f.write('100')
                                    f.close()
                                    f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_WindowCovering_3_CurrentPosition','w')
                                    f.write('100')
                                    f.close()
                                button_fast_flash_counter[i] = 4

                            elif i == 4:    # zen den
                                f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_WindowCovering_4_CurrentPosition','r')
                                blind_position = f.readline()
                                if "100" in blind_position:
                                    f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_WindowCovering_4_TargetPosition','w')
                                    f.write('0')
                                    f.close()
                                    f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_WindowCovering_4_CurrentPosition','w')
                                    f.write('0')
                                    f.close()

                                else:
                                    f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_WindowCovering_4_TargetPosition','w')
                                    f.write('100')
                                    f.close()
                                    f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_WindowCovering_4_CurrentPosition','w')
                                    f.write('100')
                                    f.close()
                                button_fast_flash_counter[i] = 4
                                    
                    button[i] = 0 # reset button state
                    
                if not button_flashing[i]:
                    pass
                elif button_flashing_timer[i] > 1:
                    button_flashing_timer[i] -= 1
                else:
                    button_flashing[i] = False
                    led_flashing[button_led_ind[i][0]][button_led_ind[i][1]] = False
                    set_one_led(button_led_ind[i][0], button_led_ind[i][1], 2)
                    button_flashing_timer[i] = 0
                    
                if button_fast_flash_counter[i] > 0:
                    if button_fast_flash_state[i]:
                        set_one_led(button_led_ind[i][0], button_led_ind[i][1], 0)
                        button_fast_flash_state[i] = False
                    else:
                        set_one_led(button_led_ind[i][0], button_led_ind[i][1], 1)
                        button_fast_flash_state[i] = True
                        button_fast_flash_counter[i] -= 1
                        
            # ACT ON SPECIAL BUTTON
            if num_special_buttons:
                i = num_buttons     # special button is always last button in list
                if button[i] != 0:
                    if button[i] == 1:
                        button_fast_flash_counter[i] = 1
                        if not is_master:
                            f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_Led_Strip_2_On','w')
                            f.write('false')
                            f.close()
                            f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_Led_Strip_3_On','w')
                            f.write('false')
                            f.close()
                            if bed:
                                if STATUS[1][0] or STATUS[1][2]:    # if main or tall lamp on
                                    switches_to_turn_off = [[1,0]]
                                    for switch_to_turn_off in switches_to_turn_off:
                                        if path.isfile(r'/var/lib/homebridge/input_'+str(switch_to_turn_off[0])+'/'+str(switch_to_turn_off[1])):
                                            remove(r'/var/lib/homebridge/input_'+str(switch_to_turn_off[0])+'/'+str(switch_to_turn_off[1]))
                                    f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_Dimmer_1_On','w')
                                    f.write('false')
                                    f.close()
                                    f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_Dimmer_0_On','w')
                                    f.write('true')
                                    f.close()
                                elif STATUS[1][1]:  # if only bedside lamps on
                                    f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_Dimmer_0_On','w')
                                    f.write('false')
                                    f.close()
                                else:
                                    f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_Dimmer_0_Brightness','w')
                                    f.write('70')
                                    f.close()
                                    f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_Dimmer_0_On','w')
                                    f.write('true')
                                    f.close()
                            else:
                                if STATUS[1][0] or STATUS[1][2]:    # if main or tall lamp on
                                    switches_to_turn_off = [[1,0]]
                                    for switch_to_turn_off in switches_to_turn_off:
                                        if path.isfile(r'/var/lib/homebridge/input_'+str(switch_to_turn_off[0])+'/'+str(switch_to_turn_off[1])):
                                            remove(r'/var/lib/homebridge/input_'+str(switch_to_turn_off[0])+'/'+str(switch_to_turn_off[1]))
                                    f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_Dimmer_1_On','w')
                                    f.write('false')
                                    f.close()
                                elif STATUS[1][1]:  # if only bedside lamps on
                                    f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_Dimmer_0_On','w')
                                    f.write('false')
                                    f.close()
                                else:
                                    f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_Dimmer_0_Brightness','w')
                                    f.write('100')
                                    f.close()
                                    f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_Dimmer_0_On','w')
                                    f.write('true')
                                    f.close()
                                    
                    elif button[i] == 2:
                        button_fast_flash_counter[i] = 2
                        if morning:
                            sock.sendto('write:Cmd4Scripts/Cmd4States/:Status_Alarm_SecuritySystemTargetState:3', (UDP_IP2, UDP_PORT2)) # disarm alarm (3)

                    elif button[i] == 3:
                        button_fast_flash_counter[i] = 3
                        if not is_master:
                            # replicate main button in bedroom triple press
                            button[0] = 3
                    elif button[i] == 4:
                        button_fast_flash_counter[i] = 4
                        if not is_master:
                            if bed:
                                if path.isfile(r'/var/lib/homebridge/input_control/bed'):
                                    remove(r'/var/lib/homebridge/input_control/bed')
                                f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_WindowCovering_1_TargetPosition','w')
                                f.write('100')
                                f.close()
                                f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_WindowCovering_1_CurrentPosition','w')
                                f.write('100')
                                f.close()

                                #sock.sendto('write:Cmd4Scripts/Cmd4States/:Status_WindowCovering_1_TargetPosition:100\n', (UDP_IP, UDP_PORT))
                                #sock.sendto('write:Cmd4Scripts/Cmd4States/:Status_WindowCovering_1_CurrentPosition:100\n', (UDP_IP, UDP_PORT))

                                sock.sendto('delete:input_control:do_not_disturb:', (UDP_IP, UDP_PORT))
                                sock.sendto('delete:input_control:dnd_suppress_doorbell_msg:', (UDP_IP, UDP_PORT))

                                if morning:
                                    sock.sendto('write:Cmd4Scripts/Cmd4States/:Status_Alarm_SecuritySystemTargetState:3', (UDP_IP2, UDP_PORT2)) # disarm alarm (3)

                                    f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_WindowCovering_2_TargetPosition','w')
                                    f.write('100')
                                    f.close()
                                    f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_WindowCovering_2_CurrentPosition','w')
                                    f.write('100')
                                    f.close()
                                    f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_WindowCovering_4_TargetPosition','w')
                                    f.write('100')
                                    f.close()
                                    f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_WindowCovering_4_CurrentPosition','w')
                                    f.write('100')
                                    f.close()
                                    
                            else: #if bedtime and (not bed):    # set good night
                                system(r'touch /var/lib/homebridge/input_control/bed')
                                switches_to_turn_off = [[1,0]]
                                dimmers_to_turn_off = [0,1]
                                led_strips_to_turn_off = [2,3]

                                for switch_to_turn_off in switches_to_turn_off:
                                    if path.isfile(r'/var/lib/homebridge/input_'+str(switch_to_turn_off[0])+'/'+str(switch_to_turn_off[1])):
                                        remove(r'/var/lib/homebridge/input_'+str(switch_to_turn_off[0])+'/'+str(switch_to_turn_off[1]))
                         
                                for dimmer_to_turn_off in dimmers_to_turn_off:
                                    f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_Dimmer_'+str(dimmer_to_turn_off)+'_On','w')
                                    f.write('false')
                                    f.close()

                                for led_strip_to_turn_off in led_strips_to_turn_off:
                                    f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_Led_Strip_'+str(led_strip_to_turn_off)+'_On','w')
                                    f.write('false')
                                    f.close()

                                f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_WindowCovering_1_TargetPosition','w')
                                f.write('0')
                                f.close()
                                f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_WindowCovering_1_CurrentPosition','w')
                                f.write('0')
                                f.close()

                                sock.sendto('write:input_control:do_not_disturb:', (UDP_IP, UDP_PORT))
                                if bedtime:
                                    sock.sendto('delete:input_control:dnd_suppress_doorbell_msg:', (UDP_IP, UDP_PORT))
                                else:
                                    sock.sendto('write:input_control:dnd_suppress_doorbell_msg:', (UDP_IP, UDP_PORT))

                                #sock.sendto('write:Cmd4Scripts/Cmd4States/:Status_WindowCovering_1_TargetPosition:0\n', (UDP_IP, UDP_PORT))
                                #sock.sendto('write:Cmd4Scripts/Cmd4States/:Status_WindowCovering_1_CurrentPosition:0\n', (UDP_IP, UDP_PORT))
                        
                    button[i] = 0
                    
                if button_fast_flash_counter[i] > 0:
                    if button_fast_flash_state[i]:
                        set_one_led(special_button_led[0][0], special_button_led[0][1], 0)
                        button_fast_flash_state[i] = False
                    else:
                        if bed:
                            set_one_led(special_button_led[0][0], special_button_led[0][1], 2)
                        else:
                            set_one_led(special_button_led[0][0], special_button_led[0][1], 1)
                        button_fast_flash_state[i] = True
                        button_fast_flash_counter[i] -= 1
            
            # TOGGLE BUTTON
            for i in range(num_toggle_buttons):
                mask = 0b1 << toggle_button[i][1]
                current_toggle_val = (IO[toggle_button[i][0]] & mask == mask)
                if toggle_button_last[i] != current_toggle_val:
                    if i == 0:  # Cooker hood light button
                        if STATUS[2][2]:
                            if path.isfile(r'/var/lib/homebridge/input_2/2'):
                                remove(r'/var/lib/homebridge/input_2/2')
                        else:
                            system(r'touch /var/lib/homebridge/input_2/2')
                            
                toggle_button_last[i] = current_toggle_val
                
            # UPDATE PIR STATES
            for i in range(num_PIR):
                mask = 0b1 << PIRsens[i][1]
                PIR[i][0] = not((IO[PIRsens[i][0]]) & mask == mask)
                if PIR[i][0]:
                    PIR[i][1] = True
                    PIR[i][2] = True
                    PIRtimer[i][0] = PIR30s
                    PIRtimer[i][1] = PIR10m
                    #sock.sendto('write:Cmd4Scripts/Cmd4States/:Status_OccupancySensor_'+str(i)+'_OccupancyDetected:true\n', (UDP_IP, UDP_PORT))
                    if is_master:
                        if i == 0:  # Stairs PIR
                            if welcome_landing:
                                sock.sendto('write:input_1/:6:', (UDP_IP, UDP_PORT))
                                STATUS[4][0] = True # to hold off nightlight
                                welcome_landing = False
                            elif left_house:
                                left_house = False
                                sock.sendto('delete:input_control/:left_house:', (UDP_IP, UDP_PORT))
                                if path.isfile(r'/var/lib/homebridge/input_control/left_house_nv'):
                                    remove(r'/var/lib/homebridge/input_control/left_house_nv')
                        elif i == 1:    # Hall PIR
                            if alarm_reminder_not_given and STATUS[4][2] and morning:   #STATUS[4][2] = alarm status
                                if left_house:
                                    alarm_reminder_not_given = False
                                elif left_house_hold_off == 0:  # reminder was getting sent when leaving house in morning and if motion detected in hallway on way out
                                    #print 'sending alarm on reminder'
                                    system(r'touch /var/lib/homebridge/input_3/3')
                                    alarm_reminder_not_given = False
                            if (not suppress_first_downstairs) and (not first_downstairs) and morning:# and bed:  # and bed added to stop silencing upstairs homepod if everyone up - didn't work as Luna moves in morning and dismisses bed downstairs
                                f = open(r'/var/lib/homebridge/input_control/FDS','w')
                                f.close()
                                first_downstairs = True

                            if left_house and (left_house_hold_off == 0): # if arriving home
                                if path.isfile(r'/var/lib/homebridge/input_control/package_garage'):
                                    remove(r'/var/lib/homebridge/input_control/package_garage')
                                if path.isfile(r'/var/lib/homebridge/input_control/security_lights'):
                                    remove(r'/var/lib/homebridge/input_control/security_lights')

                                for i in range(num_buttons):
                                    button_scene[i] = 0 # reset all button scenes so the first time the button is pressed if light already on, it goes to the first scene

                                if night_time: # if arriving home at night
                                    welcome_home = True
                                    welcome_sitting = True
                                    welcome_kitchen = True
                                    welcome_landing = True
                                    welcome_home_timer = 60

                                left_house = False
                                sock.sendto('delete:input_control/:left_house:', (UDP_IP, UDP_PORT))
                                if path.isfile(r'/var/lib/homebridge/input_control/left_house_nv'):
                                    remove(r'/var/lib/homebridge/input_control/left_house_nv')

                        elif i == 2:    # Sitting Room PIR
                            if welcome_sitting:
                                #print 'press sitting room'
                                button[1] = 1   # "Press" sitting room button
                                welcome_sitting = False
                            #elif left_house:
                                #left_house = False
                            
                        elif i == 4:    # Kitchen PIR
                            if welcome_kitchen:
                                #button[0] = 1   # "Press" kitchen button
                                set_scene(0,1, bed, is_master)
                                welcome_kitchen = False
                                #night_light_timer[3] == 100 # to hold off night light
                                STATUS[2][2] = True # to hold off nightlight
                            #elif left_house:
                                #left_house = False
                    else:
                        if i == 2:
                            if after_shower_bedroom_lights:
                                if (not bed):
                                    if (not(STATUS[1][0] or STATUS[1][1] or STATUS[1][2])): # only if no lights on already
                                        if night_time:
                                            f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_Dimmer_0_Brightness','w')
                                            f.write('100')
                                            f.close()
                                            f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_Dimmer_0_On','w')
                                            f.write('true')
                                            f.close()
                                            f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_Dimmer_1_Brightness','w')
                                            f.write('70')
                                            f.close()
                                            f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_Dimmer_1_On','w')
                                            f.write('true')
                                            f.close()
                                        else:
                                            f = open(r'/var/lib/homebridge/input_1/0','w')
                                            f.close()

                                            f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_Dimmer_1_Brightness','w')
                                            f.write('100')
                                            f.close()

                                            f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_Dimmer_1_On','w')
                                            f.write('true')
                                            f.close()
                                if night_time:
                                    after_shower = False    # no open blinds if night
                                after_shower_bedroom_lights = False
                
                if PIRtimer[i][0] > 0:
                    PIRtimer[i][0] -= 1
                else:
                    PIR[i][1] = False
                    #sock.sendto('write:Cmd4Scripts/Cmd4States/:Status_OccupancySensor_'+str(i)+'_OccupancyDetected:false\n', (UDP_IP, UDP_PORT))
                    #^^^ sends a lot of packets!!! ^^^
                if PIRtimer[i][1] > 0:
                    PIRtimer[i][1] -= 1
                else:
                    PIR[i][2] = False
                    
            # CONTROL INDICATORS
            if bed:
                if (not bed_last):
                    # turn off all indicators
                    if night_time:
                        for i in range(len(zone_indicators)):
                            if path.isfile(r'/var/lib/homebridge/ind_'+str(zone_indicators[i][0])+'/'+str(zone_indicators[i][1])):
                                remove(r'/var/lib/homebridge/ind_'+str(zone_indicators[i][0])+'/'+str(zone_indicators[i][1]))
                    for i in range(len(bedroom_indicators)):
                        if path.isfile(r'/var/lib/homebridge/ind_'+str(bedroom_indicators[i][0])+'/'+str(bedroom_indicators[i][1])):
                            remove(r'/var/lib/homebridge/ind_'+str(bedroom_indicators[i][0])+'/'+str(bedroom_indicators[i][1]))
                    if special_button:
                        for i in range(len(special_button_led)):
                            if path.isfile(r'/var/lib/homebridge/ind_'+str(special_button_led[i][0])+'/'+str(special_button_led[i][1])):
                                remove(r'/var/lib/homebridge/ind_'+str(special_button_led[i][0])+'/'+str(special_button_led[i][1]))

                    # turn off landing access point LED
                    if is_master:
                        accesspointLED(access_points, '0') # turn off leds on access points. Turened back on at sunrise

                    # reset first downstairs
                    if first_downstairs:
                        if path.isfile(r'/var/lib/homebridge/input_control/FDS'):
                            remove(r'/var/lib/homebridge/input_control/FDS')
                            first_downstairs = False

                    #suppress first downstairs
                    if is_master:
                        f = open(r'/var/lib/homebridge/input_control/SFDS','w')
                        f.close()
                        suppress_first_downstairs = True

                    refresh_all_indicators = True
                            
                PIR_activity = False
                if special_button:
                    PIR_range = num_PIR-1
                else:
                    PIR_range = num_PIR
                for i in range(PIR_range):
                    if PIR[i][1]:
                        PIR_activity = True
                
                if night_time:
                    if PIR_activity and (not PIR_activity_last):    # turn on zone indicators
                        for i in range(len(zone_indicators)):
                            system(r'touch /var/lib/homebridge/ind_'+str(zone_indicators[i][0])+'/'+str(zone_indicators[i][1]))
                            
                    if (not PIR_activity) and PIR_activity_last:    # turn off zone indicators
                        for i in range(len(zone_indicators)):
                            if path.isfile(r'/var/lib/homebridge/ind_'+str(zone_indicators[i][0])+'/'+str(zone_indicators[i][1])):
                                remove(r'/var/lib/homebridge/ind_'+str(zone_indicators[i][0])+'/'+str(zone_indicators[i][1]))
                            
                if special_button:
                    if PIR[num_PIR-1][1]:
                        special_PIR_activity = True
                    else:
                        special_PIR_activity = False
						
                    if special_PIR_activity and (not special_PIR_activity_last):    # turn on special indicators
                        for i in range(len(special_button_led)):
                            system(r'touch /var/lib/homebridge/ind_'+str(special_button_led[i][0])+'/'+str(special_button_led[i][1]))
							
                    if (not special_PIR_activity) and special_PIR_activity_last:    # turn off special indicators
                        for i in range(len(special_button_led)):
                            if path.isfile(r'/var/lib/homebridge/ind_'+str(special_button_led[i][0])+'/'+str(special_button_led[i][1])):
                                remove(r'/var/lib/homebridge/ind_'+str(special_button_led[i][0])+'/'+str(special_button_led[i][1]))
								
                    special_PIR_activity_last = special_PIR_activity
                            
                PIR_activity_last = PIR_activity
            
            if bed_last and (not bed):  # turn all indicators back on
                for i in range(len(zone_indicators)):
                    system(r'touch /var/lib/homebridge/ind_'+str(zone_indicators[i][0])+'/'+str(zone_indicators[i][1]))
                for i in range(len(bedroom_indicators)):
                    system(r'touch /var/lib/homebridge/ind_'+str(bedroom_indicators[i][0])+'/'+str(bedroom_indicators[i][1]))
                if special_button:
                    for i in range(len(special_button_led)):
                        system(r'touch /var/lib/homebridge/ind_'+str(special_button_led[i][0])+'/'+str(special_button_led[i][1]))

                if is_master:
                    # Disarm Security Lights
                    if night_time:
                        disarm_security_lights_on_sunrise = True
                    else:
                        if path.isfile(r'/var/lib/homebridge/input_control/security_lights'):
                            remove(r'/var/lib/homebridge/input_control/security_lights')

                if btc:
                    blinds_closed_mid = False
                    blinds_closed_full = False
                    # btc_enable = True
                    # f = open(r'/var/lib/homebridge/input_control/btc_enable','w')
                    # f.close()

                refresh_all_indicators = True

            bed_last = bed
            
            # CONTROL NIGHT LIGHTS
            if bed and (not is_master):
                night_light_range = num_night_lights - 1
            else:
                night_light_range = num_night_lights

            if turn_on_active_nightlights:
                for i in range(night_light_range):
                    if NIGHT_LIGHTS[i][12]:
                        if STATUS[NIGHT_LIGHTS[i][2]][NIGHT_LIGHTS[i][3]]:
                            night_light_activated[i] = False
                            ACTIVATED_AS_NIGHTLIGHT[NIGHT_LIGHTS[i][2]][NIGHT_LIGHTS[i][3]] = False
                            night_light_timer[i] = 0
                            #print 'nightlight',i,'permanently turned on'

                if (not security_enabled):
                    for i in range(num_security_lights):
                        if SECURITY_LIGHTS[i][9]:
                            if STATUS[SECURITY_LIGHTS[i][5]][SECURITY_LIGHTS[i][6]]:    # if secondary security light on (back/side bronx lights)
                                security_light_activated[i] = False
                                security_light_timer[i] = 0
                                #print 'backup security light',i,'permanently turned on'

                turn_on_active_nightlights = False
                
            for i in range(night_light_range):
                mains_off = True

                ##first part
                if NIGHT_LIGHT_MAINS[0][0][0] == -1:
                    pass
                else:
                    for j in range(len(NIGHT_LIGHT_MAINS[i])):
                        if STATUS[NIGHT_LIGHT_MAINS[i][j][0]][NIGHT_LIGHT_MAINS[i][j][1]] and (not ACTIVATED_AS_NIGHTLIGHT[NIGHT_LIGHT_MAINS[i][j][0]][NIGHT_LIGHT_MAINS[i][j][1]]):
                            mains_off = False
                ##

                if night_time or NIGHT_LIGHTS[i][6]:    # NIGHT_LIGHTS[i][6] = daytime operation

                    ## the following code was broken into two - first part moved up outside "if night_time or NIGHT_LIGHTS[i][6]:", second part moved down
                    # if NIGHT_LIGHT_MAINS[0][0][0] == -1:
                    #     pass
                    # else:
                    #     for j in range(len(NIGHT_LIGHT_MAINS[i])):
                    #         if STATUS[NIGHT_LIGHT_MAINS[i][j][0]][NIGHT_LIGHT_MAINS[i][j][1]] and (not ACTIVATED_AS_NIGHTLIGHT[NIGHT_LIGHT_MAINS[i][j][0]][NIGHT_LIGHT_MAINS[i][j][1]]):
                    #             mains_off = False
 
                    #     if (is_master and (i==0) and (not guest) and (not going_to_bed)):  # if not guest mode and not going to bed, hall lamp is a main light for stairs NL also
                    #         if STATUS[0][0]:
                    #             mains_off = False
                    ##

                    ##second part
                    if (is_master and (i==0) and (not guest) and (not going_to_bed)):  # if not guest mode and not going to bed, hall lamp is a main light for stairs NL also
                        if STATUS[0][0]:
                            mains_off = False
                    ##

                    #print 'nightlight',i,'timer:',night_light_timer[i],mains_off,ACTIVATED_AS_NIGHTLIGHT[NIGHT_LIGHTS[i][2]][NIGHT_LIGHTS[i][3]]
                    if (not mains_off) and (not ACTIVATED_AS_NIGHTLIGHT[NIGHT_LIGHTS[i][2]][NIGHT_LIGHTS[i][3]]):
                        #print 'entered timer hold off'
                        night_light_timer[i] = 200 # 10 seconds #night_light_on_time
                        night_light_activated[i] = False
                        
                    if PIR[NIGHT_LIGHTS[i][0]][0]: # if motion detected
                        if mains_off and (not((going_to_bed or left_house) and NIGHT_LIGHTS[i][9])):   # if all main lights off and night light isn't to be surpressed by gtb/left_house
                            if NIGHT_LIGHTS[i][1] == 0: # nightlight is switch, not dimmer
                                if not STATUS[NIGHT_LIGHTS[i][2]][NIGHT_LIGHTS[i][3]] and ((night_light_timer[i] == 0) or guest):   # guest mode doesn't need timer = 0 to activate NL
                                    # if (not RELAY_QUEUE[NIGHT_LIGHTS[i][2]][NIGHT_LIGHTS[i][3]][0]):  # only increment queue size if the relay is not already on the queue
                                        # QUEUED_RELAYS += 1
                                    # RELAY_QUEUE[NIGHT_LIGHTS[i][2]][NIGHT_LIGHTS[i][3]][0] = True # Relay action queued
                                    # RELAY_QUEUE[NIGHT_LIGHTS[i][2]][NIGHT_LIGHTS[i][3]][1] = True   # power ON
                                    system(r'touch /var/lib/homebridge/input_'+str(NIGHT_LIGHTS[i][2])+'/'+str(NIGHT_LIGHTS[i][3]))
                                    night_light_activated[i] = True
                                    ACTIVATED_AS_NIGHTLIGHT[NIGHT_LIGHTS[i][2]][NIGHT_LIGHTS[i][3]] = True
                                    if NIGHT_LIGHTS[i][6]:
                                        night_light_timer[i] = night_light_on_time_ext
                                    else:
                                        night_light_timer[i] = NIGHT_LIGHTS[i][11] #night_light_on_time
                                elif night_light_activated[i]:
                                    if NIGHT_LIGHTS[i][6]:
                                        night_light_timer[i] = night_light_on_time_ext
                                    else:
                                        if (not is_master) and (i == 0) and (not bed):  # hack to double length of landing night lights when not in bed
                                            night_light_timer[i] = NIGHT_LIGHTS[i][11] * 2
                                        else:
                                            night_light_timer[i] = NIGHT_LIGHTS[i][11] #night_light_on_time
                            else:
                                if not STATUS[DIMMER_SWITCH[NIGHT_LIGHTS[i][4]][0]][DIMMER_SWITCH[NIGHT_LIGHTS[i][4]][1]] and (night_light_timer[i] == 0):
                                    f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_Dimmer_'+str(NIGHT_LIGHTS[i][4])+'_Brightness','r')
                                    night_light_store_val[i] = f.readline()
                                    f.close()
                                    night_light_brightness = str(int(NIGHT_LIGHTS[i][7]))
                                    f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_Dimmer_'+str(NIGHT_LIGHTS[i][4])+'_Brightness','w')
                                    f.write(night_light_brightness+'\n')
                                    f.close()
                                    f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_Dimmer_'+str(NIGHT_LIGHTS[i][4])+'_On','w')
                                    f.write('true\n')
                                    f.close()
                                    night_light_activated[i] = True
                                    ACTIVATED_AS_NIGHTLIGHT[DIMMER_SWITCH[NIGHT_LIGHTS[i][4]][0]][DIMMER_SWITCH[NIGHT_LIGHTS[i][4]][1]] = True
                                    night_light_timer[i] = NIGHT_LIGHTS[i][11] #night_light_on_time
                                elif night_light_activated[i]:
                                    night_light_timer[i] = NIGHT_LIGHTS[i][11] #night_light_on_time
                        
                        if (not is_master) and i==0:
                            if bedroom_ultra_dark:
                                bedroom_ultra_dark_timer = bedroom_ultra_dark_time  # reset timer
                        
                    if NIGHT_LIGHTS[i][5] != -1:    # if a valid secodary PIR is specified
                        if PIR[NIGHT_LIGHTS[i][5]][0]:  # if motion detected on secondary PIR
                            if ACTIVATED_AS_NIGHTLIGHT[NIGHT_LIGHTS[i][2]][NIGHT_LIGHTS[i][3]] and mains_off: # if nightlight currently activated and main light isn't on
                                night_light_timer[i] = NIGHT_LIGHTS[i][11] #night_light_on_time  # reset timer
                            if (not is_master) and i==0:
                                if bedroom_ultra_dark:
                                    bedroom_ultra_dark_timer = bedroom_ultra_dark_time  # reset timer

                        if NIGHT_LIGHTS[i][10] != -1:    # if a valid tertiary PIR is specified
                            if(is_master or (not going_to_bed)):    # tertiary PIR disabled upstairs when going to bed
                                if PIR[NIGHT_LIGHTS[i][10]][0]:  # if motion detected on tertiary PIR
                                    if ACTIVATED_AS_NIGHTLIGHT[NIGHT_LIGHTS[i][2]][NIGHT_LIGHTS[i][3]] and mains_off: # if nightlight currently activated and main light isn't on
                                        night_light_timer[i] = NIGHT_LIGHTS[i][11] #night_light_on_time  # reset timer
                
                if night_light_timer[i] > 0:
                    if night_light_timer[i] == 10:
                        if NIGHT_LIGHTS[i][1] == 0 and ACTIVATED_AS_NIGHTLIGHT[NIGHT_LIGHTS[i][2]][NIGHT_LIGHTS[i][3]]: # nightlight is switch, not dimmer
                            if STATUS[NIGHT_LIGHTS[i][2]][NIGHT_LIGHTS[i][3]]:
                                if path.isfile(r'/var/lib/homebridge/input_'+str(NIGHT_LIGHTS[i][2])+'/'+str(NIGHT_LIGHTS[i][3])):
                                    remove(r'/var/lib/homebridge/input_'+str(NIGHT_LIGHTS[i][2])+'/'+str(NIGHT_LIGHTS[i][3]))
                                #ACTIVATED_AS_NIGHTLIGHT[NIGHT_LIGHTS[i][2]][NIGHT_LIGHTS[i][3]] = False
                                if (not is_master) and i==0:    # if landing night light turing off
                                    if going_to_bed and bedtime:   #was previously if security lights on - now going_to_bed and bathroom nightlights off (detection method for "last person getting into bed")    #and (not STATUS[NIGHT_LIGHTS[1][2]][NIGHT_LIGHTS[1][3]])
                                        bedroom_ultra_dark = True
                                        bedroom_ultra_dark_timer = bedroom_ultra_dark_time
                                        # dim down bedroom lights even further
                                        # f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_Dimmer_1_On','w')
                                        # f.write('false\n')
                                        # f.close()
                                        # f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_Dimmer_0_Brightness','w')
                                        # f.write('50\n')
                                        # f.close()
                                        # f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_Led_Strip_2_Brightness','w')
                                        # f.write('30\n')
                                        # f.close()
                                        # f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_Led_Strip_3_Brightness','w')
                                        # f.write('20\n')
                                        # f.close()

                                # if (not RELAY_QUEUE[NIGHT_LIGHTS[i][2]][NIGHT_LIGHTS[i][3]][0]):
                                    # QUEUED_RELAYS += 1
                                # RELAY_QUEUE[NIGHT_LIGHTS[i][2]][NIGHT_LIGHTS[i][3]][0] = True # Relay action queued
                                # RELAY_QUEUE[NIGHT_LIGHTS[i][2]][NIGHT_LIGHTS[i][3]][1] = False  # power OFF
                        else: 
                            if STATUS[DIMMER_SWITCH[NIGHT_LIGHTS[i][4]][0]][DIMMER_SWITCH[NIGHT_LIGHTS[i][4]][1]] and ACTIVATED_AS_NIGHTLIGHT[DIMMER_SWITCH[NIGHT_LIGHTS[i][4]][0]][DIMMER_SWITCH[NIGHT_LIGHTS[i][4]][1]]:
                                f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_Dimmer_'+str(NIGHT_LIGHTS[i][4])+'_Brightness','w')
                                f.write(night_light_store_val[i]+'\n')
                                f.close()
                                f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_Dimmer_'+str(NIGHT_LIGHTS[i][4])+'_On','w')
                                f.write('false\n')
                                f.close()
                                turn_off_nightlight_dimmer[NIGHT_LIGHTS[i][4]] = True
                                #ACTIVATED_AS_NIGHTLIGHT[DIMMER_SWITCH[NIGHT_LIGHTS[i][4]][0]][DIMMER_SWITCH[NIGHT_LIGHTS[i][4]][1]] = False
                        night_light_activated[i] = False
                    elif night_light_timer[i] == 1:
                        ACTIVATED_AS_NIGHTLIGHT[NIGHT_LIGHTS[i][2]][NIGHT_LIGHTS[i][3]] = False

                    if (mains_off or bool(NIGHT_LIGHTS[i][8])):   #NIGHT_LIGHTS[i][8] = don't pause timer when main turned on  
                        night_light_timer[i] -= 1

            # if debug:
            #     blind_RIGHT   = 0b00010000
            #     blind_CLEAR   = 0b00000000
            #     set_up_blind_IOexp(blinds[0])             
            #     write_byte_reg(extra_8bit_adr, GPIO_REGISTER_8, blind_RIGHT)
            #     sleep(0.1)
            #     write_byte_reg(extra_8bit_adr, GPIO_REGISTER_8, blind_CLEAR)

            # SECURITY LIGHTS
            for i in range(num_security_lights):
                if (security_enabled or bool(SECURITY_LIGHTS[i][4])) and night_time:        #SECURITY_LIGHTS[i][4] = bypass arm_security_lights
                    mask = 0b1 << SECURITY_LIGHTS[i][1]
                    motion_detected = (IO[SECURITY_LIGHTS[i][0]]) & mask == mask
                    if motion_detected:
                        if bool(SECURITY_LIGHTS[i][4]) and (not security_enabled):
                            if not STATUS[SECURITY_LIGHTS[i][5]][SECURITY_LIGHTS[i][6]] and (security_light_timer[i] == 0):
                                system(r'touch /var/lib/homebridge/input_'+str(SECURITY_LIGHTS[i][5])+'/'+str(SECURITY_LIGHTS[i][6]))
                                security_light_activated[i] = True
                        else:
                            if not STATUS[SECURITY_LIGHTS[i][2]][SECURITY_LIGHTS[i][3]] and (security_light_timer[i] == 0):
                                # if (not RELAY_QUEUE[SECURITY_LIGHTS[i][2]][SECURITY_LIGHTS[i][3]][0]):    # only increment queue size if the relay is not already on the queue
                                    # QUEUED_RELAYS += 1
                                # RELAY_QUEUE[SECURITY_LIGHTS[i][2]][SECURITY_LIGHTS[i][3]][0] = True   # Relay action queued
                                # RELAY_QUEUE[SECURITY_LIGHTS[i][2]][SECURITY_LIGHTS[i][3]][1] = True   # power ON
                                system(r'touch /var/lib/homebridge/input_'+str(SECURITY_LIGHTS[i][2])+'/'+str(SECURITY_LIGHTS[i][3]))
                                #security_light_timer[i] = security_light_on_time
                                security_light_activated[i] = True
                                #print 'Security light',i,'activated for the first time'
                        
                        if security_light_activated[i]:
                            if bool(SECURITY_LIGHTS[i][4]) and (not security_enabled):
                                security_light_timer[i] = SECURITY_LIGHTS[i][8]
                            else:
                                security_light_timer[i] = SECURITY_LIGHTS[i][7]
                            #print 'Security light',i,'timer topped up'
                if security_light_timer[i] > 0:
                    #print security_light_timer[i]
                    if security_light_timer[i] == 1:
                        if path.isfile(r'/var/lib/homebridge/input_'+str(SECURITY_LIGHTS[i][2])+'/'+str(SECURITY_LIGHTS[i][3])):
                            remove(r'/var/lib/homebridge/input_'+str(SECURITY_LIGHTS[i][2])+'/'+str(SECURITY_LIGHTS[i][3]))
                        # if STATUS[SECURITY_LIGHTS[i][2]][SECURITY_LIGHTS[i][3]]:
                            # if (not RELAY_QUEUE[SECURITY_LIGHTS[i][2]][SECURITY_LIGHTS[i][3]][0]):
                                # QUEUED_RELAYS += 1
                            # RELAY_QUEUE[SECURITY_LIGHTS[i][2]][SECURITY_LIGHTS[i][3]][0] = True   # Relay action queued
                            # RELAY_QUEUE[SECURITY_LIGHTS[i][2]][SECURITY_LIGHTS[i][3]][1] = False  # power OFF
                        if bool(SECURITY_LIGHTS[i][4]):
                            if path.isfile(r'/var/lib/homebridge/input_'+str(SECURITY_LIGHTS[i][5])+'/'+str(SECURITY_LIGHTS[i][6])):
                                remove(r'/var/lib/homebridge/input_'+str(SECURITY_LIGHTS[i][5])+'/'+str(SECURITY_LIGHTS[i][6]))
                        security_light_activated[i] = False
                    security_light_timer[i] -= 1
            
            # GARAGE DOOR
            if garage_control:
                mask = 0b1 << garage_io[1][1]
                garage_open = not (IO[garage_io[1][0]] & mask)
                mask = 0b1 << garage_io[2][1]
                garage_closed = not (IO[garage_io[2][0]] & mask)
                #print 'garage_open:',garage_open
                #print 'garage_closed:',garage_closed
                if first_time:
                    if garage_open:
                        garage_state = True
                    elif garage_closed:
                        garage_state = False
                    else:
                        f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_GarageDoorOpener_CurrentDoorState','r')
                        value = f.readline()
                        f.close()
                        if '0' in value:
                            garage_state = True
                        else:
                            garage_state = False
                            
                if clear_garage_pulse:
                    sleep(0.02)
                    set_i2c_mux(IOmux[garage_io[0][0]])
                    #write_byte_reg(io_adr, 0x3, 0xF)
                    write_byte_reg(io_adr, 0x1, 0x0)    # set output port to 0, rather than to stop driving
                    clear_garage_pulse = False
                            
                garage_ts_last = garage_ts
                garage_ts = stat(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_GarageDoorOpener_TargetDoorState').st_mtime
                if (garage_ts_last != garage_ts):
                    #print 'garage activation'
                    f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_GarageDoorOpener_TargetDoorState','r')
                    value = f.readline()
                    f.close()
                    
                    if ('0' in value and (not garage_state)) or ('1' in value and garage_state):
                        # send pulse
                        set_i2c_mux(IOmux[garage_io[0][0]])
                        
                        garage_pulse = 0b1 << garage_io[0][1]
                        #print garage_pulse
                        #print 'not garage_pulse:',(garage_pulse ^ 0xF)
                        write_byte_reg(io_adr, 0x1, garage_pulse)           # output port
                        write_byte_reg(io_adr, 0x3, (garage_pulse ^ 0xF))   # config (dir)
                        clear_garage_pulse = True
                        
                        #garage_state = not garage_state #? not needed maybe

                if garage_open and (not garage_open_last):  # garage just finished opening
                    #print 'garage open'
                    garage_state = True
                    f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_GarageDoorOpener_CurrentDoorState','w')
                    f.write('0')
                    f.close()
                    garage_keepout = True
                    garage_keepout_timer = 5
                elif garage_closed and (not garage_closed_last):    # garage just finished closing
                    #print 'garage closed'
                    garage_state = False
                    f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_GarageDoorOpener_CurrentDoorState','w')
                    f.write('1')
                    f.close()
                    garage_keepout = True
                    garage_keepout_timer = 5
                elif garage_keepout:    # to ignore bouncing on reed switches
                    if garage_keepout_timer > 0:
                        garage_keepout_timer -= 1
                    else:
                        garage_keepout = False
                elif (not garage_open) and garage_open_last:    # garage just started closing
                    #print 'garage started closing'
                    #print 'Status_GarageDoorOpener_TargetDoorState modified to 1'
                    garage_state = False
                    f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_GarageDoorOpener_TargetDoorState','w')
                    f.write('1')
                    f.close()
                    garage_keepout = True
                    garage_keepout_timer = 2
                elif (not garage_closed) and garage_closed_last:    # garage just started opening
                    #print 'garage started opening'
                    #print 'Status_GarageDoorOpener_TargetDoorState modified to 0'
                    garage_state = True
                    f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_GarageDoorOpener_TargetDoorState','w')
                    f.write('0')
                    f.close()
                    garage_keepout = True
                    garage_keepout_timer = 2
                    
                garage_open_last = garage_open
                garage_closed_last = garage_closed
                
            # BLINDS
            if num_blinds:
                # if sv[0] != 8: # and (not pause[0]):
                #     print sv[0]

                for i in range(num_blinds):
                    if blind_update_not_found:
                        blind_ts_last[i] = blind_ts[i]
                        blind_ts[i] = stat(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_WindowCovering_'+str(i)+'_TargetPosition').st_mtime
                        
                        if (blind_ts_last[i] != blind_ts[i]): # and (not first_time):   can't remember why not first_time was needed... was used a few lines below also
                            blind_update_not_found = False
                            blind_to_action = i
                            #print 'blind',i,'control file modified - found during initial search'
                
                # if blind_timeout_after:
                #     #print blind_timeout_after_counter
                #     if blind_timeout_after_counter == 0:
                #         blind_timeout_after = False
                #         blind_update_not_found = True
                #     blind_timeout_after_counter -= 1
                # elif blind_busy:
                if blind_busy:
                    #print 'inside blind busy'
                    if sv[0] == 8:
                        #print 'blind complete'
                        #blind_timeout_after = False
                        blind_update_not_found = True
                        #blind_timeout_after_counter = blind_timeout
                        blind_busy = False
                    elif ((sv[0] == 10) or (sv[0] == 9)) and pause[0] and (pause_counter[0] == 1):
                        #print 'new test'
                        block_further_blind_reads = False
                        new_blind_found = False
                        old_blind_number_store = 1
                        for j in range(num_blinds):
                            if (not block_further_blind_reads):
                                blind_ts_last[j] = blind_ts[j]
                                blind_ts[j] = stat(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_WindowCovering_'+str(j)+'_TargetPosition').st_mtime
                                
                                if (blind_ts_last[j] != blind_ts[j]):
                                    new_blind_to_action = j
                                    # print
                                    # print
                                    # print 'blind',j,'control file modified - found immediately after previous blind actioned'
                                    # print 'Current variables:'
                                    # print 'blind_number_store:',blind_number_store
                                    # print 'blind_action:',blind_action
                                    # print 'sv:',sv
                                    # print 'movingleft:',movingleft
                                    # print 'numpresses:',numpresses
                                    # print 'returnpresses:',returnpresses

                                    block_further_blind_reads = True
                                    new_blind_found = True

                        #new_blind_found = False     # remove eventually
                        if new_blind_found:
                            old_blind_number_store = blind_number_store
                            f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_WindowCovering_'+str(new_blind_to_action)+'_TargetPosition','r')
                            value = int(f.readline())
                            f.close()
                            blind_busy = True
                            sv[0] = 0
                            blind_number_store = new_blind_to_action+1
                            if value == 0:
                                blind_action = 0
                                blind_set_to_middle[new_blind_to_action] = False
                            elif value == 100:
                                blind_action = 2
                                blind_set_to_middle[new_blind_to_action] = False
                            elif (value >= 1) and (value <= 99) and (not blind_set_to_middle[new_blind_to_action]):
                                blind_action = 1
                                blind_set_to_middle[new_blind_to_action] = True
                            else:
                                blind_action = 0
                                blind_set_to_middle[new_blind_to_action] = False


                        #if (sv[0] == 9)

                        activate_blind(blinds[0], blind_number_store, blind_action, sv, pause, pause_counter, movingleft, numpresses, returnpresses, old_blind_number_store, blind_ts, test_led_or_reduce, test_led2_or_reduce)

                    else:
                        #print 'blind remaining actions'
                        activate_blind(blinds[0], blind_number_store, blind_action, sv, pause, pause_counter, movingleft, numpresses, returnpresses, old_blind_number_store, blind_ts, test_led_or_reduce, test_led2_or_reduce)
                        
                elif (not blind_update_not_found): # and (not first_time):
                    #print 'blind_update_not_found',blind_update_not_found,'first_time:',first_time,'blind_busy:',blind_busy
                    #print 'blind first action'
                    #for i in range(num_blinds):
                        #if (blind_ts_last[i] != blind_ts[i]):
                    i = blind_to_action
                    blind_ts_last[i] = blind_ts[i]
                    #print 'blind',i,'activated'
                    try:
                        f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_WindowCovering_'+str(i)+'_TargetPosition','r')
                        value = int(f.readline())
                        f.close()
                        #print 'value read from blind',i,'control file:',value
                        blind_busy = True
                        sv[0] = 0
                        blind_number_store = i+1
                        if value == 0:
                            #activate_blind_with_delay(blinds[0], i+1, 0)
                            blind_action = 0
                            blind_set_to_middle[i] = False
                            # if blind_to_action == 0:    # if closing sitting room blind
                            #     sock.sendto('delete:input_control:btc_enable:', (UDP_IP, UDP_PORT)) # disable temperature action of blinds
                        elif value == 100:
                            #activate_blind_with_delay(blinds[0], i+1, 2)
                            blind_action = 2
                            blind_set_to_middle[i] = False
                            # if blind_to_action == 0:    # if opening sitting room blind
                            #     sock.sendto('write:input_control:btc_enable:', (UDP_IP, UDP_PORT)) # re-enable temperature action of blinds
                        elif (value >= 1) and (value <= 99) and (not blind_set_to_middle[i]):
                            #activate_blind_with_delay(blinds[0], i+1, 1)
                            blind_action = 1
                            blind_set_to_middle[i] = True
                        else:
                            #activate_blind_with_delay(blinds[0], i+1, 0)
                            blind_action = 0
                            blind_set_to_middle[i] = False

                        if i == 0:  # sitting room blind
                            if blind_action == 2:
                                sock.sendto('write:input_control/:1:', (UDP_IP, UDP_PORT))
                            else:
                                sock.sendto('delete:input_control/:1:', (UDP_IP, UDP_PORT))
                            
                        activate_blind(blinds[0], blind_number_store, blind_action, sv, pause, pause_counter, movingleft, numpresses, returnpresses, 1, blind_ts, test_led_or_reduce, test_led2_or_reduce)
                    except:
                        blind_ts[i] = 0
                        #log_error('error reading blind, trying again on next loop')
                            
                    #print 'blind_busy:',blind_busy
            
            # CONTROL LED STRIPS
            if num_led_strips > 0:
                for i in range(num_led_strips):
                    #led_strip_power_on = False
                    led_strip_update = False
                    if fire_alarm:
                        if led_strip_timer[i] == 0: ## NB!!! fire alarm detector needs to force all timers to 0 and turn on LED strip
                            led_strip_IP = led_strips[i]
                            #sock.sendto(lifx_power_on, (led_strip_IP, led_strip_UDP_port))
                            if alert_state:
                                if num_zones[i] == 0:
                                    setBulb(led_strip_IP, 0, 65535, 0, 3500, 10)
                                else:
                                    setMult(led_strip_IP, 0, num_zones[i], 0, 65535, 0, 3500, 10)
                                if i == (num_led_strips - 1):
                                    alert_state = False
                            else:
                                if num_zones[i] == 0:
                                    setBulb(led_strip_IP, 0, 65535, 65535, 3500, 10)
                                else:
                                    setMult(led_strip_IP, 0, num_zones[i], 0, 65535, 65535, 3500, 10)
                                if i == (num_led_strips - 1):
                                    alert_state = True
                            led_strip_timer[i] = 9
                        alert_ended = True # so that after fire alarm ceases, LED strips will be turned off
                    elif doorbell:
                        if(led_strip_not_in_bedroom[i] or (not(bed))) and (not package_garage) and ((not do_not_disturb) or (led_strip_dnd_suppress_allowed[i] and dnd_suppress_doorbell_msg)):
                            if led_strip_timer[i] == 0: ## NB!!! doorbell detector needs to force all timers to 0 and turn on LED strip
                                led_strip_IP = led_strips[i]
                                #sock.sendto(lifx_power_on, (led_strip_IP, led_strip_UDP_port))
                                if alert_state:
                                    #print 'led strip',i,'flash on'
                                    if num_zones[i] == 0:
                                        setBulb(led_strip_IP, 40959, 40000, 0, 3500, 10)
                                    else:
                                        setMult(led_strip_IP, 0, num_zones[i], 40959, 40000, 0, 3500, 10)
                                    
                                else:
                                    #print 'led strip',i,'flash off'
                                    if night_time:
                                        if num_zones[i] == 0:
                                            setBulb(led_strip_IP, 40959, 40000, 26214, 3500, 10)
                                        else:
                                            setMult(led_strip_IP, 0, num_zones[i], 40959, 40000, 26214, 3500, 10)   # only flash at 40% brightness at night
                                    else:
                                        if num_zones[i] == 0:
                                            setBulb(led_strip_IP, 40959, 40000, 65535, 3500, 10)
                                        else:
                                            setMult(led_strip_IP, 0, num_zones[i], 40959, 40000, 65535, 3500, 10)

                                led_strip_timer[i] = 9
                        alert_ended = True # so that after doorbell alert ceases, LED strips will be turned off
                        if i == (num_led_strips - 1):
                            alert_state = not(alert_state)
                    elif alert_ended:
                        led_strip_IP = led_strips[i]
                        if led_strip_power[i]:
                            if theme_activated[i]: #((saturation_set[i] == 1) and (hue_set[i] < num_themes)):
                                #print 'led strip',i,'set back to theme'
                                if num_zones[i] == 0:
                                    setBulb(led_strip_IP, colours[colour_library[i]][0][0], colours[colour_library[i]][0][1], colours[colour_library[i]][0][2]*master_brightness[i], colours[colour_library[i]][0][3], 2000)
                                else:
                                    setMult(led_strip_IP, 0, num_zones[i], colours[colour_library[i]][0][0], colours[colour_library[i]][0][1], colours[colour_library[i]][0][2]*master_brightness[i], colours[colour_library[i]][0][3], 2000)
                            else:
                                #print 'led strip',i,'set back to static colour'
                                if num_zones[i] == 0:
                                    setBulb(led_strip_IP, int(float(hue_set_f[i])*182.04166666666666666666666666667), int(float(saturation_set_f[i])*655.35), int(master_brightness[i]*65535.0), 3500, 2000)
                                else:
                                    setMult(led_strip_IP, 0, num_zones[i], int(float(hue_set_f[i])*182.04166666666666666666666666667), int(float(saturation_set_f[i])*655.35), int(master_brightness[i]*65535.0), 3500, 2000)
                        else:
                            #sock.sendto(lifx_power_off, (led_strip_IP, led_strip_UDP_port))
                            #print 'led strip',i,'powered off'
                            setLEDpwr(led_strip_IP, i, led_retry, led_retry_pwr, led_retry_counter, False, False, led_confirm, led_retry_delay)
                        alert_state = False
                        if i == (num_led_strips - 1):
                            alert_ended = False

                        #if not(led_strip_power[i]):
                            #sock.sendto(lifx_power_off, (led_strip_IP, led_strip_UDP_port))
                        #    setLEDpwr(led_strip_IP, i, led_retry, led_retry_pwr, led_retry_counter, False, False, led_confirm, led_retry_delay)
                    else:
                        last_ts_led_strip[i] = new_ts_led_strip[i]
                        new_ts_led_strip[i] = stat(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_Led_Strip_'+str(i)+'_On').st_mtime
                        if (last_ts_led_strip[i] != new_ts_led_strip[i]):
                            f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_Led_Strip_'+str(i)+'_On','r')
                            value = f.readline()
                            f.close()
                            if 'true' in value and not(led_strip_power[i]):
                                #print 'LED Strip power on flag read from file'
                                led_strip_update = True
                                led_strip_power_on[i] = True
                                if (not is_master):
                                    if i == 0:  # bathroom
                                        shower_temp_not_reached = True
                                        print 'Reset shower indication'
                                    elif i == 2:    # bed headboard
                                        ACTIVATED_AS_NIGHTLIGHT[1][1] = False #Remove nightlight operation of bedroom night light

                            elif 'false' in value and led_strip_power[i]:
                                led_strip_IP = led_strips[i]
                                led_strip_power[i] = False
                                #sock.sendto(lifx_power_off, (led_strip_IP, led_strip_UDP_port))
                                setLEDpwr(led_strip_IP, i, led_retry, led_retry_pwr, led_retry_counter, False, False, led_confirm, led_retry_delay)
                                #if (not is_master) and  i == 0:
                                    #shower_temp_not_reached = True
                                    #print 'Reset shower indication'
                                #print 'turning off LED strip'
                                #print
                        
                        last_ts_led_strip_brightness[i] = new_ts_led_strip_brightness[i]
                        new_ts_led_strip_brightness[i] = stat(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_Led_Strip_'+str(i)+'_Brightness').st_mtime
                        if (last_ts_led_strip_brightness[i] != new_ts_led_strip_brightness[i]):
                            f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_Led_Strip_'+str(i)+'_Brightness','r')
                            value = f.readline()
                            f.close()
                            try:
                                master_brightness[i] = float(value)/100.0
                                #print 'Brightness of '+value+'% read from file'
                                #print master_brightness[i],'(converted to float)'
                                led_strip_update = True
                            except:
                                print 'reading brightness file again...'
                                new_ts_led_strip_brightness[i] = 0 # try reading again on next loop
                            
                        
                        last_ts_led_strip_hue[i] = new_ts_led_strip_hue[i]
                        new_ts_led_strip_hue[i] = stat(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_Led_Strip_'+str(i)+'_Hue').st_mtime
                        if (last_ts_led_strip_hue[i] != new_ts_led_strip_hue[i]):
                            f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_Led_Strip_'+str(i)+'_Hue','r')
                            value = f.readline()
                            f.close()
                            try:
                                hue_set_f[i] = float(value)
                                hue_set[i] = int(value)
                                #print 'Hue of '+value+' degrees read from file'
                                #print hue_set_f[i],'(converted to float)'
                                theme_activated[i] = False
                                for j in range(num_themes):
                                    if (hue_set[i] == theme_identifier[0][j][0]) and (saturation_set[i] == theme_identifier[0][j][1]): # can change "theme_identifier[0]" back to "theme_identifier[i]" if different settings needed per fixture
                                        colour_library[i] = j
                                        theme_activated[i] = True
                                        
                                led_strip_update = True
                            except:
                                print 'reading hue file for LED strip',i,'again...'
                                new_ts_led_strip_hue[i] = 0 # try reading again on next loop
                            
                        last_ts_led_strip_sat[i] = new_ts_led_strip_sat[i]
                        new_ts_led_strip_sat[i] = stat(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_Led_Strip_'+str(i)+'_Saturation').st_mtime
                        if (last_ts_led_strip_sat[i] != new_ts_led_strip_sat[i]):
                            f = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_Led_Strip_'+str(i)+'_Saturation','r')
                            value = f.readline()
                            f.close()
                            try:
                                saturation_set[i] = int(value)
                                saturation_set_f[i] = float(value)
                                #print 'Saturation of '+value+'% read from file'
                                #print saturation_set_f[i],'(converted to float)'
                                theme_activated[i] = False
                                for j in range(num_themes):
                                    if (hue_set[i] == theme_identifier[0][j][0]) and (saturation_set[i] == theme_identifier[0][j][1]): # can change "theme_identifier[0]" back to "theme_identifier[i]" if different settings needed per fixture
                                        colour_library[i] = j
                                        theme_activated[i] = True
                                        
                                led_strip_update = True
                            except:
                                print 'reading sat file for LED strip',i,'again...'
                                new_ts_led_strip_sat[i] = 0 # try reading again on next loop
                        
                        if led_strip_update:
                            led_strip_IP = led_strips[i]
                            #print 'led_strip_update for',led_strip_IP,' entered'
                            if theme_activated[i]: #((saturation_set[i] == 1) and (hue_set[i] < num_themes)):
                                #print 'LED strip updated while at theme'
                                led_solid_colour[i] = False
                                repeat_led_colour[i] = False
                                if num_zones[i] == 0:
                                    setBulb(led_strip_IP, colours[colour_library[i]][0][0], colours[colour_library[i]][0][1], colours[colour_library[i]][0][2]*master_brightness[i], colours[colour_library[i]][0][3], 2000)
                                else:
                                    setMult(led_strip_IP, 0, num_zones[i], colours[colour_library[i]][0][0], colours[colour_library[i]][0][1], colours[colour_library[i]][0][2]*master_brightness[i], colours[colour_library[i]][0][3], 2000)
                                #last_colour[i] = 0
                                # if colour_library[i] == 3:
                                    # sleep(0.05)
                                    # setMult(led_strip_IP, 8, 7, colours[colour_library[i]][1][0], colours[colour_library[i]][1][1], colours[colour_library[i]][1][2]*master_brightness[i], colours[colour_library[i]][1][3], 2000)
                                    # led_strip_timer[i] = 800 # hold initial look for 40s
                            else:
                                led_solid_colour[i] = True
                                repeat_led_colour[i] = True
                                #print 'LED strip updated while at solid colour'
                                if num_zones[i] == 0:
                                    setBulb(led_strip_IP, int(float(hue_set_f[i])*182.04166666666666666666666666667), int(float(saturation_set_f[i])*655.35), int(master_brightness[i]*65535.0), 3500, 2000)
                                else:
                                    setMult(led_strip_IP, 0, num_zones[i], int(float(hue_set_f[i])*182.04166666666666666666666666667), int(float(saturation_set_f[i])*655.35), int(master_brightness[i]*65535.0), 3500, 2000)
                            #print
                        elif led_strip_power_on[i]:
                            led_strip_IP = led_strips[i]
                            #print 'led_strip_power_on[i] for',led_strip_IP,' entered'
                            led_strip_power_on[i] = False
                            if theme_activated[i]: #((saturation_set[i] == 1) and (hue_set[i] < num_themes)):
                                #print 'LED strip updated and powered on while at theme'
                                #setMult(led_strip_IP, 0, num_zones[i], colours[colour_library[i]][0][0], colours[colour_library[i]][0][1], colours[colour_library[i]][0][2]*master_brightness[i], colours[colour_library[i]][0][3], 10)
                                #if colour_library[i] == 3:
                                #   sleep(0.05)
                                #   setMult(led_strip_IP, 8, 7, colours[colour_library[i]][1][0], colours[colour_library[i]][1][1], colours[colour_library[i]][1][2]*master_brightness[i], colours[colour_library[i]][1][3], 2000)
                                #   led_strip_timer[i] = 800 # hold initial look for 40s
                                #else:
                                led_strip_timer[i] = 120
                                # above line was in else statement
                                #print 'sleeping for 1 second before LED strip power on...'
                                #sleep(1) #sleep(0.05)
                                #sock.sendto(lifx_power_on_slow, (led_strip_IP, led_strip_UDP_port))
                                setLEDpwr(led_strip_IP, i, led_retry, led_retry_pwr, led_retry_counter, True, True, led_confirm, led_retry_delay)
                                #last_colour[i] = 0
                            else:
                                #print 'LED strip updated and powered on while at solid colour'
                                #setMult(led_strip_IP, 0, num_zones[i], int(float(hue_set_f[i])*182.04166666666666666666666666667), int(float(saturation_set_f[i])*655.35), int(master_brightness[i]*65535.0), 3500, 10)
                                #print 'sleeping for 1 second before LED strip power on...'
                                #sleep(1) #sleep(0.05)
                                #sock.sendto(lifx_power_on_slow, (led_strip_IP, led_strip_UDP_port))
                                setLEDpwr(led_strip_IP, i, led_retry, led_retry_pwr, led_retry_counter, True, True, led_confirm, led_retry_delay)
                            led_strip_power[i] = True   
                        elif theme_activated[i] and led_strip_power[i]: ##saturation_set[i] == 1 and hue_set[i] < num_themes and led_strip_power[i]:
                            # if led_strip_timer[i] == 0 and ftb_flag[i]:
                                # led_strip_IP = led_strips[i]
                                # hue = colours[colour_library[i]][next_colour[i]][0]
                                # saturation = colours[colour_library[i]][next_colour[i]][1]
                                # brightness = colours[colour_library[i]][next_colour[i]][2]*master_brightness[i]
                                # setMult(led_strip_IP, next_index[i], next_led_span[i], hue, saturation, 0, colours[colour_library[i]][next_colour[i]][3], 10)
                                # sleep(0.05)
                                # setMult(led_strip_IP, next_index[i], next_led_span[i], hue, saturation, brightness, colours[colour_library[i]][next_colour[i]][3], next_time[i])
                                # ftb_flag[i] = False
                                # led_strip_timer[i] = led_strip_timer_next[i]
                                # #print 'End fade to black'
                            # elif led_strip_timer[i] == 0:
                            if led_strip_timer[i] == 0:
                                led_strip_IP = led_strips[i]
                                colour_select = int(uniform(0,len(colours[colour_library[i]])))
                                #print 'Colour Select:',colour_select
                                index = uniform(0, num_zones[i]+1)
                                led_span = uniform((colours[colour_library[i]][colour_select][5]/23.0)*num_zones[i], (colours[colour_library[i]][colour_select][4]/23.0)*num_zones[i])
                                index -= led_span/2.0
                                index = int(index+0.5)
                                led_span = int(led_span+0.5)
                                if index < 0:
                                    index = 0
                                if index + led_span > num_zones[i]:
                                    led_span = num_zones[i] - index
                                time = int(uniform(time_min, time_max) * 1000)
                                if extra_long_mode[colour_library[i]] or (num_zones[i] == 0):   # single bulbs always do extra long mode
                                    led_strip_timer[i] = int((uniform(time_min_long, time_max_long))*20)
                                else:
                                    led_strip_timer[i] = int((uniform(time_min, time_max))*20)
                            # if fade_through_black[colour_library[i]]:
                                # next_colour[i] = colour_select
                                # setMult(led_strip_IP, index, led_span, colours[colour_library[i]][last_colour[i]][0], 0, 0, colours[colour_library[i]][last_colour[i]][3], 4000)
                                # last_colour[i] = colour_select
                                # ftb_flag[i] = True
                                # next_index[i] = index
                                # next_led_span[i] = led_span
                                # next_time[i] = time
                                # led_strip_timer_next[i] = led_strip_timer[i] + 40
                                # led_strip_timer[i] = 80
                                # #print 'Start fade to black'
                            # else:
                                hue = colours[colour_library[i]][colour_select][0]
                                saturation = colours[colour_library[i]][colour_select][1]
                                brightness = colours[colour_library[i]][colour_select][2]*master_brightness[i]
                                if num_zones[i] == 0:
                                    setBulb(led_strip_IP, hue, saturation, brightness, colours[colour_library[i]][colour_select][3], time)
                                else:
                                    setMult(led_strip_IP, index, led_span, hue, saturation, brightness, colours[colour_library[i]][colour_select][3], time)
                                #print 'Standard Colour'
                                
                    if led_strip_timer[i] > 0:
                        led_strip_timer[i] -= 1
                        
                #alert_ended = False
                
            counter += 1
            led_flash_counter += 1
            if led_flash_counter > led_flash_period:
                led_flash_counter = 0
                led_flash_variable = not led_flash_variable
                for i in range(num_boards):
                    for j in range(8):
                        if led_flashing[i][j]:
                            if led_flash_variable:
                                set_one_led(i, j, 1)
                            else:
                                set_one_led(i, j, 0)
            #GPIO.output(12, GPIO.LOW)  # LOOP LED
            loopLEDval = not(loopLEDval)
            sleep(LOOP_TIME)
            GPIO.output(12, loopLEDval)
            first_time = False
            #print night_light_timer[0], night_light_activated[0], ACTIVATED_AS_NIGHTLIGHT[NIGHT_LIGHTS[0][2]][NIGHT_LIGHTS[0][3]]
            
            if calculate_optimal_sleep_time:
                current_ts = time()
                loop_time_meas = (current_ts - loop_time_start)
                loop_time_start = current_ts

                if led_locate_holdoff == 0:
                    loop_count += 1
                    loop_time_sum += loop_time_meas
                    if (loop_count % 100) == 0:
                        loop_time_average = float(loop_time_sum)/float(loop_count)
                        print loop_count,'loops ... Average Loop time:',loop_time_average,'... Recommended new LOOP_TIME setting:',(LOOP_TIME + (0.050-loop_time_average))
            
            if debug_press:
                if is_master:
                    system(r'touch /var/lib/homebridge/input_3/3')  # doorbell alert from home app
                debug_press = False
                debug_persist = True    # has to be cleared in the main code
                debug = True
            else:
                debug = False
            
    # except Exception as e:
        # exc_type, exc_obj, exc_tb = exc_info()
        # now = datetime.now()
        # errorlog = open(r'/var/lib/homebridge/crash.log','a')
        # errorlog.write(now.strftime("%d/%m/%Y %H:%M:%S - "))
        # errorlog.write(str(e.message))
        # errorlog.write(' - Line number: ')
        # errorlog.write(str(exc_tb.tb_lineno))
        # errorlog.write('\nValue contents: ')
        # try:
            # errorlog.write(value)
        # except:
            # errorlog.write('BLANK - value not used yet')
        # # errorlog.write('\nType: ')
        # # errorlog.write(str(exc_tb.exc_type))
        # # errorlog.write('\nObj: ')
        # # errorlog.write(str(exc_tb.exc_obj))
        # errorlog.write('\n')
        # errorlog.close()
        
        # GPIO.setup(10, GPIO.OUT)  # error LED
        # GPIO.output(10, GPIO.HIGH)
        
        # alert = open(r'/var/lib/homebridge/Cmd4Scripts/Cmd4States/Status_Crash_Alert_MotionDetected','w')
        # alert.write('1\n')
        # alert.close()
        
        # print 'Error encountered, restarting controller.py service...'
        # print str(e.message)
        # print
        # sleep(1)