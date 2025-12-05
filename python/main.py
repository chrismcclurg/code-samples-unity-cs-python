# ----------------------------------------------------------------------------
# main.py
# Chris McClurg
# 
# This script communicates with Unity to predict the shooter's next positions. 
# ----------------------------------------------------------------------------

import udp
import time
import numpy as np
from functions import (
    transform,
    idx,
    load_layouts,
    load_models,
    load_door_pos,
    make_write_dir,
    dump_data,
    get_steps,
    get_walls,
    get_occupancy,
    predict,
    python_to_unity,
    unity_to_string,
)


# constants (no need to change)
N_NPC = 116             # number of NPCs in the environment
N_DO = 17               # number of open doors in the environment
N_DC = 90               # number of closed doors in the environment
TIMEOUT_WARN1 = 5.0     # wait time before first warning
TIMEOUT_WARN2 = 8.0     # wait tume before second warning
TIMEOUT_END   = 10.0    # wait time before ending script

def run():
    '''This real-time loop exchanges data with Unity to predicting shooter motion'''

    # create socket
    sock = udp.comms(udpIP="127.0.0.1", portTX=8000, portRX=8001, 
                     enableRX=True, suppressWarnings=True)
    print('==> SOCKET STARTED')
    
    # load files
    full_layout = load_layouts()
    print('==> LAYOUTS LOADED')
    
    # load prediction models
    models = load_models()
    print('==> MODELS LOADED')
    
    # load static doors
    pos_do, pos_dc = load_door_pos()
    print('==> STATIC OBJECTS LOADED')
    
    # initialize history buffers
    pxs, pys = [], []  # shooter positions, x and y
    acs, was = [], []  # actions and walls
    nas, nds = [], []  # alive and dead npcs
    dos, dcs = [], []  # open and closed doors
    
    # initialize cumulative visibility
    cv_npc  = np.array([0 for xi in range(N_NPC)])  # npcs
    cv_do   = np.array([0 for xi in range(N_DO)])   # open doors
    cv_dc   = np.array([0 for xi in range(N_DC)])   # closed doors
    
    # initialize flags
    last_msg_time         = time.time()  # time of last message
    _is_running     = True
    _has_started    = False
    _first_warning  = False
    _second_warning = False
    
    # create write directory / wait until signal received
    write_dir = make_write_dir()
    print("==> WAITING FOR UNITY")
    
    # main loop
    while _is_running:
    
        # get input data (from Unity)
        data_in = sock.ReadReceivedData()
        if data_in is not None:
            if not _has_started:
                _has_started = True
    
            # parse input data
            time_info, player_info, npc_info, do_info, dc_info = data_in.split(";")
    
            # parse time data
            time_data   = [float(xi) for xi in time_info.split(',') if len(xi) > 0]
            time_total  = time_data[0]
            time_shoot  = time_data[1]
            time_ahead  = int(time_data[2])
            step_ahead  = 2*time_ahead
    
            # write data to file
            dump_data(time_shoot, write_dir, data_in)
    
            # parse player data
            player_data = [xi for xi in player_info.split(',') if len(xi) > 0]
            eye_diam_l  = float(player_data.pop())
            eye_diam_r  = float(player_data.pop())
            eye_focus_z = int(player_data.pop())
            eye_focus_y = int(player_data.pop())
            eye_focus_x = int(player_data.pop())
            eye_focus_o = player_data.pop()
            num_hits    = int(player_data.pop())
            num_dryfire = int(player_data.pop())
            num_reload  = int(player_data.pop())
            num_shot    = int(player_data.pop())
            
            shooter_data = [float(xi) for xi in player_data]
            shooter_x, shooter_y, shooter_z = shooter_data[0:3]
            shooter_rx, shooter_ry, shooter_rz = shooter_data[3:]
            px, py, pz = transform(shooter_x, shooter_y, shooter_z)
            pix, piy, piz = idx(px, py, pz)
    
            # parse npc data
            pos_npc = []
            vis_npc = []
            sta_npc = []
            if npc_info != "":
                npc_data = [float(xi) for xi in npc_info.split(',') if len(xi) > 0]
                num_seg = int(len(npc_data) / 5)
                for ix in range(num_seg):
                    base = 5 * ix
                    temp = npc_data[base : base + 5]
                    pos_npc.extend(temp[0:3])
                    vis_npc.append(int(temp[3]))
                    sta_npc.append(int(temp[4]))
                vis_npc = np.array(vis_npc)
                sta_npc = np.array(sta_npc)
            
            # parse door data
            do_info = [int(xi) for xi in do_info.split(',') if len(xi) > 0]
            dc_info = [int(xi) for xi in dc_info.split(',') if len(xi) > 0]
            vis_do   = np.array(do_info)
            vis_dc   = np.array(dc_info)
    
            # determine cummulative visability
            if len(vis_npc) > 0:
                cv_npc = vis_npc| cv_npc
                cv_do  = vis_do | cv_do
                cv_dc  = vis_dc | cv_dc
    
            # construct occupancy maps
            acs, pxs, pys = get_steps(px, py, acs, pxs, pys, step_ahead)
            was = get_walls(pix, piy, piz, full_layout, was, step_ahead)
            nas = get_occupancy(px, py, piz, pos_npc, cv_npc, nas, step_ahead, 1, sta_npc)
            nds = get_occupancy(px, py, piz, pos_npc, cv_npc, nds, step_ahead, 0, sta_npc)
            dos = get_occupancy(px, py, piz, pos_do, cv_do, dos, step_ahead)
            dcs = get_occupancy(px, py, piz, pos_dc, cv_dc, dcs, step_ahead)
    
            # predict trajectory from multi-channel LSTM
            xy_pred = predict(models, px, py, acs, was, dos, dcs, nas, nds, time_ahead)
    
            # convert prediction to unity coordinates
            unity_x, unity_y, unity_z = python_to_unity(xy_pred, pz)
    
            # construct output data (to Unity)
            data_out = unity_to_string(time_total, unity_x, unity_y, unity_z)
    
            # send data string
            sock.SendData(data_out)
            last_msg_time = time.time()
    
        # timeout logic
        elif _has_started:
            if (time.time() - last_msg_time) > TIMEOUT_WARN1 and not _first_warning:
                _first_warning = True
                print('==> SIGNAL LOST')
    
            if (time.time() - last_msg_time) > TIMEOUT_WARN2 and not _second_warning:
                _second_warning = True
                print('==> ABOUT TO SHUT DOWN')
    
            if (time.time() - last_msg_time) > TIMEOUT_END:
                _is_running = False
                print('==> PROGRAM ENDED')
                
if __name__ == "__main__":
    run()
    
    
