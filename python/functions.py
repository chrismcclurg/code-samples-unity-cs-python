# ----------------------------------------------------------------------------
# functions.py
# Chris McClurg
# 
# This script defines helper functions for main.py
# -----------------------------------------------------------------------------

import numpy as np
import pandas as pd
import os
from datetime import date, datetime

DXY = 3

def transform(x_raw, y_raw, z_raw):
    '''convert raw Unity xyz to local simulation xyz'''
    
    x0, y0, alpha = 240, 70, np.radians(35.5)

    #transform 1: raw to convenient
    x1 = np.round((1620 - float(z_raw))/3,1)
    y1 = np.round(float(x_raw)/3,1)
    z1 = np.round(float(y_raw)/3,1)

    #transform 2: convenient to local box
    dx = x1 - x0
    dy = y1 - y0
    x2 = np.round(dx * np.cos(alpha) + dy * np.sin(alpha),1)
    y2 = np.round(-dx * np.sin(alpha) + dy * np.cos(alpha),1)
    z2 = z1
    return [x2, y2, z2]

def inverse_transform(x2, y2, z2):
    '''convert local simulation xyz back to raw Unity xyz'''
    
    x0, y0, alpha = 240, 70, np.radians(35.5)

    #transform 1: local box to convenient
    dx = x2 * np.cos(alpha) - y2 * np.sin(alpha)
    dy = x2 * np.sin(alpha) + y2 * np.cos(alpha)
    x1 = dx + x0
    y1 = dy + y0
    z1 = z2

    #transform 2: convenient to raw
    z_raw = np.round((1620 - x1*3),1)
    x_raw = np.round(y1*3,1)
    y_raw = np.round(z1*3,1)
    return x_raw, y_raw, z_raw

def idx(x, y, z):
    '''discretize xyz into grid cell indices'''
    
    if np.isnan(x):
        x_bar = np.nan
        y_bar = np.nan
        z_bar = np.nan
    else:
        x_bar = int(np.floor(x / DXY + 0.5))
        y_bar = int(np.floor(y / DXY + 0.5))
        if z < 10:
            z_bar = 1
        else:
            z_bar = 2
    return x_bar, y_bar, z_bar

def inverse_idx(x_bar, y_bar, z_bar):
    '''grid cell indices to continuous xyz'''
    
    if np.isnan(x_bar):
        x = np.nan
        y = np.nan
        z = np.nan
    else:
        x = np.round(float(x_bar*DXY),1)
        y = np.round(float(y_bar*DXY),1)
        if z_bar == 1:
            z = 0.0
        else:
            z = 14.0
    return x, y, z

def moving_avg(xList, yList, zList, window_size = 7):
    '''smoothing function for noisy positional data'''
    
    xPad = np.pad(xList, (window_size//2, window_size-1-window_size//2), mode='edge')
    yPad = np.pad(yList, (window_size//2, window_size-1-window_size//2), mode='edge')
    zPad = np.pad(zList, (window_size//2, window_size-1-window_size//2), mode='edge')
    xmaList = np.convolve(xPad, np.ones(window_size,)/window_size, mode = 'valid')
    ymaList = np.convolve(yPad, np.ones(window_size,)/window_size, mode = 'valid')
    zmaList = np.convolve(zPad, np.ones(window_size,)/window_size, mode = 'valid')
    return [xmaList, ymaList, zmaList]

def load_layouts():
    '''load binary wall maps for each floor from excel files'''
    
    # read file 1
    file_1 = os.path.join('.', 'dat', 'visual', 'columbine', 'map1.xlsx')
    layout1 = pd.read_excel(file_1, header = None)
    layout1 = layout1.values
    layout1 = np.array(layout1).astype(int)
    layout1[layout1!=1]=0

    # read file 2
    file_2 = os.path.join('.', 'dat', 'visual', 'columbine', 'map2.xlsx')
    layout2 = pd.read_excel(file_2, header = None)
    layout2 = layout2.values
    layout2 = np.array(layout2).astype(int)
    layout2[layout2!=1]=0
    
    ans = dict()
    ans['layout1'] = layout1
    ans['layout2'] = layout2
    return ans

def get_walls(pix, piy, piz, full_layout, wa, num_step):
    '''extract a local 21×21 wall grid centered on the player'''

    # get correct floor
    full = full_layout[f'layout{piz}'].copy()

    grid_size = 21
    ctr = int((grid_size - 1)/2)
    ans = np.zeros((grid_size, grid_size))
    if any([pix < 0, piy < 0, pix > 130, piy > 70]):
        wa.append(ans)

    else:
        full_shape, pos, ans_shape = np.array(full.shape), np.array([piy-ctr, pix-ctr]), np.array(ans.shape)
        end = pos + ans_shape

        #Calculate crop position
        ans_low = np.clip(0 - pos, 0, ans_shape)
        ans_high = ans_shape - np.clip(end-full_shape, 0, ans_shape)
        ans_slices = (slice(low, high) for low, high in zip(ans_low, ans_high))

        # Calculate img slice positions
        pos = np.clip(pos, 0, full_shape)
        end = np.clip(end, 0, full_shape)
        full_slices = (slice(low, high) for low, high in zip(pos, end))
        ans[tuple(ans_slices)] = full[tuple(full_slices)]

        wa.append(ans)

    # limit length of history
    if len(wa) == (num_step + 1):
        wa = wa[1:]
    return wa

def get_steps(px, py, ac_list, px_list, py_list, num_step):
    ''' compute the xy movement deltas per timestep in grid units'''
    px_list.append(px)
    py_list.append(py)

    if len(px_list) == 1:
        dx = 0.0
        dy = 0.0
    else:
        dx = np.round((px_list[-1]-px_list[-2]) / 3,1)  # grid units
        dy = np.round((py_list[-1]-py_list[-2]) / 3,1)  # grid units

    step = np.array([dx,dy])
    ac_list.append(step)

    # limit length of history for memory
    if len(px_list) == (num_step + 1):
        px_list = px_list[1:]
        py_list = py_list[1:]
        ac_list = ac_list[1:]
    return ac_list, px_list, py_list

def get_theta(x,y,px,py):
    ''' compute angle from shooter to object in [0, 2pi]'''
    delta_x = x - px
    delta_y = y - py
    theta = np.arctan2(delta_y, delta_x)
    old = float(theta)
    if old < 0.0:
        new = 2*np.pi + old
    elif old > 2*np.pi :
        new = old - 2*np.pi
    else:
        new = old
    return new

def to_radial_coords(x, y, px, py):
    ''' place object into discrete polar bins (r, theta)'''

    num_theta = 20
    num_radii = 20
    radii_max = 100

    theta_step = 2*np.pi / num_theta
    radii_step = radii_max / num_radii

    radius = np.sqrt((x - px)**2 + (y - py)**2)
    theta = get_theta(x,y,px,py)

    rstep = np.floor(radius / radii_step)
    tstep = np.floor(theta/ theta_step)

    if rstep >= num_radii:
        return (np.nan, np.nan)
    else:
        return (int(rstep),int(tstep))

def get_occupancy(px, py, piz, obj_pos, cv_obj, obj_list, num_step, spec=None, spec_list=None):
    ''' constructs the polar occupancy grid for npcs or doors'''
    
    if spec_list is None:
        spec_list = []  
        
    # resultant grid
    num_theta = 20
    num_radii = 20
    obj = np.zeros((num_radii, num_theta), dtype = int)

    # update current timestep occupancy grid
    for i in range(len(cv_obj)):

        # continue if never seen
        if cv_obj[i] != 1:
            continue

        # continue if not as specified
        if spec is not None:
            if (spec_list[i] != spec) : # not correct state
                continue

        # continue if not on same floor
        x,y,z = transform(obj_pos[3*i], obj_pos[3*i+1], obj_pos[3*i+2])
        xi, yi, zi = idx(x,y,z)
        if zi != piz: # npt same floor
            continue

        # if still here, update occupancy grid
        ri, ti = to_radial_coords(x, y, px, py)
        if not np.isnan(ri):
            obj[ri,ti] = 1

    # add occupancy grid to list
    obj_list.append(obj)

    # limit length of history
    if len(obj_list) == (num_step + 1):
        obj_list = obj_list[1:]

    return obj_list

def load_door_pos():
    '''load Unity door positions (static)'''

    # copied from unity units
    pos_do = '655.5,42.2,999.4,478.1,10,852.9,484.5,10,833,773.1,53,1104.1,784.2,53,1112.2,1280.7,53.5,374.2,595,42.5,507.7,600.4,42.5,718.5,552.5,42.5,582.6,472.2,0,672.6,1047.8,42.5,343.9,666.4,0,730,547.2,42.5,702.8,689.4,42.5,596.7,707,42.5,315.6,908.4,42.5,242.1,1022.5,42.5,584.5,'
    pos_dc = '963.7,52.3,264.9,1249.3,52.3,236.3,678.1,52.3,285,536.2,10,471.7,460.6,10,576.5,423.3,9.6,628.6,629.5,42.2,1063.4,647.1,42.2,1027.5,621.7,42.2,1079.5,638.3,42.2,987.3,635.2,42.5,978.7,1019.4,42.5,824.8,1030.6,42.5,808.6,1142.8,42.5,647.3,1154,42.5,631.1,691.4,-0.5,1167.9,781.6,-0.5,979.1,710.1,-0.5,928.2,661.6,-0.5,894.1,1292.7,53.5,382.7,528.1,42.5,666.8,512.2,42.5,655.4,525.9,42.5,619.8,534.8,42.5,607.4,481.2,42.5,646.2,699.7,42.5,582.6,896.8,42.5,233.8,863.6,42.5,210.2,884.8,42.5,250.4,811.6,42.5,184.6,778.2,42.5,232.2,755.8,42.5,263.4,746,42.5,276.8,785.7,42.5,257.1,794.5,42.5,244.8,754.4,42.5,326.4,765.5,42.5,334.4,804.7,42.5,362.4,805.2,42.5,385.8,755.6,42.5,350.4,743,42.5,341.4,838.7,42.5,573.3,851.2,42.5,582.2,916.3,42.5,628.6,958,42.5,658.3,981.2,42.5,626.1,867.6,42.5,544.8,904.9,42.5,620.4,1205.2,42.5,265.7,1143.1,42.5,222.4,1176.5,42.5,321.5,1111.9,42.5,414.6,1124.2,42.5,397.1,1035.3,42.5,361.8,933.3,42.5,450.8,923.8,42.5,464.3,976.8,42.5,511.5,991.1,42.5,521.2,1056.6,42.5,534.7,1046.9,42.5,549,750.1,42.5,608,759.8,42.5,594.1,715.4,42.5,667.5,483.1,42.5,657,560.7,0,716.3,491.9,0,666.7,469.3,0,650.5,560.2,0,736,709.7,0,666.8,753.4,0,603.6,774.6,0,571.9,595.6,0,665.5,517.4,0,609.5,573.1,0,490.1,614.9,0,520,656.3,0,549.4,697.4,0,578.8,588.5,42.5,732.4,507.6,42.5,609.2,544.6,42.5,557.5,588.1,42.5,533,610.1,42.5,518.5,651.2,42.5,548.2,512.5,0,681.7,547.6,0,727,459.9,0,664,578,0,728.5,612.9,0,677.9,531.1,0,619.1,1117.3,42.5,243.6,'
    
    pos_do      = [float(xi) for xi in pos_do.strip().split(',') if len(xi) > 0]
    pos_dc      = [float(xi) for xi in pos_dc.strip().split(',') if len(xi) > 0]
    return pos_do, pos_dc

def convert_raw_pred(raw_pred, px, py):
    '''convert raw delta index values to Python xy values'''
    dx = [xi*DXY for xi in raw_pred[:,0]]
    dy = [xi*DXY for xi in raw_pred[:,1]]
    cummDx = [np.sum(dx[:ix]) for ix in range(1,len(dx)+1)]
    cummDy = [np.sum(dy[:iy]) for iy in range(1,len(dy)+1)]
    xAns = [(xi + px) for xi in cummDx]
    yAns = [(yi + py) for yi in cummDy]
    return list(zip(xAns, yAns))

def cv_pred(acs, pred_time):
    '''constant-velocity predictor using recent actions.'''
    
    actions = acs.copy()
    if pred_time == 0:
        actions = np.array([0,0])
    elif len(actions) == 0:
        actions = np.array([0,0])
    elif len(actions) > 10:
        actions = actions[-10:]

    dx_total = np.sum(np.array([xi[0] for xi in actions]))
    dy_total = np.sum(np.array([xi[1] for xi in actions]))

    vx_avg = dx_total / len(actions) #avg x per timestep
    vy_avg = dy_total / len(actions) #avg y per timestep

    raw_pred = []
    for i in range(2*pred_time):
        raw_pred.append(np.array([(i+1)*vx_avg, (i+1)*vy_avg]))
    raw_pred = np.array(raw_pred)
    return raw_pred

def sed_pred(model, acs, was, dos, dcs, nas, nds, mSel):
    '''run the LSTM predictor with numerous inputs'''
    
    # truncate copies
    acs_temp = acs.copy()[-(mSel*2):]
    was_temp = was.copy()[-(mSel*2):]
    dos_temp = dos.copy()[-(mSel*2):]
    dcs_temp = dcs.copy()[-(mSel*2):]
    nas_temp = nas.copy()[-(mSel*2):]
    nds_temp = nds.copy()[-(mSel*2):]

    # vectorize elements
    num_theta = 20
    num_radii = 20
    grid_size = 21
    acs_temp = np.array(acs_temp)                                                 # (nTS, 2)
    was_temp = np.array([np.reshape(elem, grid_size**2) for elem in was_temp])    # (nTS, 441)
    dos_temp = np.array([np.reshape(elem, num_radii*num_theta) for elem in dos_temp]) # (nTS, 400)
    dcs_temp = np.array([np.reshape(elem, num_radii*num_theta) for elem in dcs_temp]) # (nTS, 400)
    nas_temp = np.array([np.reshape(elem, num_radii*num_theta) for elem in nas_temp]) # (nTS, 400)
    nds_temp = np.array([np.reshape(elem, num_radii*num_theta) for elem in nds_temp]) # (nTS, 400)

    # expand vectors
    xTest0 = np.expand_dims(acs_temp, 0)   # (None, nTS, 2)
    xTest1 = np.expand_dims(was_temp, 0)   # (None, nTS, 441)
    xTest2 = np.expand_dims(dos_temp, 0)   # (None, nTS, 400)
    xTest3 = np.expand_dims(dcs_temp, 0)   # (None, nTS, 400)
    xTest4 = np.expand_dims(nas_temp, 0)   # (None, nTS, 400)
    xTest5 = np.expand_dims(nds_temp, 0)   # (None, nTS, 400)

    # combine input
    xTest = [xTest0, xTest1, xTest2, xTest3, xTest4, xTest5]

    # make inference
    raw_pred = np.squeeze(model.predict(xTest))
    return raw_pred

def predict(models, px, py, acs, was, dos, dcs, nas, nds, pred_time):
    ''' predict future shooter xy with approriate model'''

    num_dat = len(acs) # int up to 40 timesteps
    num_cap = [xi for xi in [0,5,10,20] if num_dat>=2*xi]
    ix_sel = np.argmin(np.array([np.abs(pred_time - xi) for xi in num_cap]))
    mSel = num_cap[ix_sel]
    
    #raw prediction
    if mSel == 0:      
        raw_pred = cv_pred(acs, pred_time)  # constant velocity
    elif mSel == 5:    
        raw_pred = sed_pred(models[0], acs, was, dos, dcs, nas, nds, 5) # LSTM
    elif mSel == 10:
        raw_pred = sed_pred(models[1], acs, was, dos, dcs, nas, nds, 10) # LSTM
    else:
        raw_pred = sed_pred(models[2], acs, was, dos, dcs, nas, nds, 20) # LSTM
    
    # convert raw prediction
    xy_pred = convert_raw_pred(raw_pred, px, py)
    return xy_pred

def python_to_unity(xy_pred, pz):
    '''convert Python xyz to Unity xyz'''
    
    x_unity = []
    y_unity = []
    z_unity = []
    xPython = [xi[0] for xi in xy_pred]
    yPython = [xi[1] for xi in xy_pred]
    for i in range(len(xPython)):
        xTemp, yTemp, zTemp = inverse_transform(xPython[i], yPython[i], pz)
        x_unity.append(xTemp)
        y_unity.append(yTemp)
        z_unity.append(zTemp)
    return x_unity, y_unity, z_unity

def unity_to_string(t, x_unity, y_unity, z_unity):
    '''format predictions into comma separated string'''
    
    ans = f'{t};'
    for x in x_unity:
        ans += f'{x},'
    ans = ans[:-1]
    ans += ';'
    for y in y_unity:
        ans += f'{y},'
    ans = ans[:-1]
    ans += ';'
    for z in z_unity:
        ans += f'{z},'
    ans = ans[:-1]
    return ans

def make_write_dir():
    '''create results directories for this participant'''

    # results (main)
    path = "D:/chris/projects/shooter-hri/results"
    os.makedirs(path, exist_ok=True)

    # results -> clean
    temp = os.path.join(path, "clean")
    os.makedirs(temp, exist_ok=True)
    
    # results -> video_sim
    temp = os.path.join(path, "video_sim")
    os.makedirs(temp, exist_ok=True)

    # results -> video_real
    temp = os.path.join(path, "video_real")
    os.makedirs(temp, exist_ok=True)
 
    # results -> raw
    dir_raw = os.path.join(path, "raw")
    os.makedirs(dir_raw, exist_ok=True)

    # results -> raw -> date
    today = date.today().strftime("%Y-%m-%d")
    dir_date = os.path.join(dir_raw, today)
    os.makedirs(dir_date, exist_ok=True)

    # results -> raw -> date -> participant no
    nPrev = len(next(os.walk(dir_date))[1])
    dir_pno = os.path.join(dir_date, str(nPrev))
    os.makedirs(dir_pno, exist_ok=True)

    dir_info = os.path.join(dir_pno, "info")
    os.makedirs(dir_info, exist_ok=True)
    
    # results -> raw -> date -> participant no -> info
    filepath = os.path.join(dir_pno, "info", "general.txt")
    currentTime = datetime.now()
    strDate = currentTime.strftime('%m/%d/%y')
    strTime = currentTime.strftime('%I:%M %p')
    pinits = os.environ["PARTICIPANT"]
    info =  f"Participant:\t{pinits}\n"
    info += (f"Date: \t\t{strDate}\n")
    info += (f"Time: \t\t{strTime}\n")
    info += ("Robot Enabled: \t" + os.environ["ROBOT_IS_ENABLED"] + "\n")
    info += ("Distracting: \t" + os.environ["ROBOT_IS_DISTRACTING"] + "\n")
    info += ("Aggressive: \t" + os.environ["ROBOT_IS_AGGRESSIVE"] + "\n")
    info += ("Fog Enabled: \t" + os.environ["ROBOT_FOG_ENABLED"] + "\n")
    with open(filepath, "w") as text_file:
        text_file.write(info)

    return dir_pno

def dump_data(tShoot, path, data_in):
    '''save raw input from Unity to file.'''
    
    if (tShoot > 0):
        print(f"==> DATA DUMPED ({tShoot})")
        nFile = len(next(os.walk(path))[2])
        filepath = os.path.join(path, f'{nFile}.txt')
        with open(filepath, "w") as text_file:
            text_file.write(data_in)
    else:
        print("==> DATA NOT RECORDED.")
    return