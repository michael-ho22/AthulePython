# Acoustic Traverse Script
'''  ------------------------------------------------------------------------

This is the original version of the program with no GUI, please refer to 
propeller_no_kill_rOR_GUI.py for a more updated GUI version!

This Python control script interfaces with the Tyto 1780 hardware through
the separate automatic control script "UDP_Netv4.js" in the RCBenchmark
software. This script controls the propeller thrust by adjusting the ESC
throttle and reads propeller performance data from the Tyto 1780
hardware. This script also pulls SPL (LAF) readings from the B&K 2270
sound analyzer, which is read into MATLAB by the NI 9223 DAQ card on the
compact DAQ module. Additionally, the code interfaces with the Velmex
Bi-SLide traverse to move the microphone along the propeller blade radius
in 1/10" increments. This script generates an output log file at the end
% of a successful test.

------------------------------------------------------------------------'''


import json
import time
import socket
import numpy as np
import pandas as pd
from datetime import datetime
from control2Thrust import control2Thrust
import tkinter as tk
from tkinter import messagebox
import serial
import nidaqmx


# Inputs
# Propeller radius "R", [in]
# [in] (radius for 13" nominal diameter blades)
R = 22.25 / 2

# Traverse distance-per-move "X_pm", [in]
X_pm = .5

# Traverse start location "X0", [in]
X0 = 3.8750

# Acoustic measurement duration, [s]
L_sample_default = 5

# Microphone name, {string} (use to retrieve calibration data)
mic_name = 'usr_A'

# DAQ card port ID (where is it on the cDAQ module?) {string}
DAQ_ID = 'cDAQ1Mod8'

# DAQ channel number (which channel is our signal coming in?) {string}
Channel_ID = 'ai0'

# Sample frequency "f_samp", [Hz]
f_sample = 10000

# Gain on 2270 output socket (?) (I've been using 60 dB)
A = 60

# Allows program to grab Host's IP Address
hostname = socket.gethostname()
my_IP = socket.gethostbyname(hostname)

# Send port value
tx_port = 64856

# Specify constant target thrust for test:
target_thrust = float(input("Enter target thrust, [lbf]:"))
# Thrust_tol = ??
main_path = 'C:\\Users\\mykoh\\OneDrive\\Documents\\BIP\\Results\\'
kill = 0
results_table = []

# Set up UDP communication with Tyto JS code
# open a UDP socket
# Might need to be careful that the local port is available AND
# Matches the "send_port" in the Tyto-JS
u = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
u.bind((my_IP, tx_port))
u.close()
u = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
u.bind((my_IP, tx_port))
recv_port = 55047 #this should remain the same across all users
u.sendto(b"hello there RC Benchmark", (my_IP, recv_port)) #should see appear on the right console of the RcBenchmark program

# # define number of moves:
no_of_moves = np.ceil((R - X0) / X_pm)

# VXM setup
# define number of stepper motor steps per-move:
step_resolution = 0.0050 * (1 / 25.4)  # [mm/step] --> [in/step]
nsteps = np.ceil(X_pm / step_resolution)
vxm = serial.Serial('COM5', 9600)  #Serial('COM5', 9600)  # Baud Rate = 9600 for VXM (don't ask me what that means tho)
vxm.write(b'\r')  # ASCII line terminator set to carriage return
time.sleep(1)
# bring VXM controller to "On-Line" mode, with added carriage return
# "<cr>" at line end:
vxm.write(b'G\n')


# Ask user if they want to move the blade to specific location
while True:
    move_blade = input("Do you want to move the blade? (yes/no): ").lower()
    if move_blade in ['yes', 'no']:
        break
    else:
        print("Invalid input. Please enter 'yes' or 'no'.")

if move_blade == 'yes':
    # If user wants to move the blade, allow them to input the specified distance
    while True:
        move_distance = float(input("Enter the distance to move the microphone (in inches, max 15 in): "))
        if 0 <= move_distance <= 15:
            break # if valid input, then break from the loop and contninue through the program
        else:
            print("Invalid input. Please enter a distance between 0 and 8 inches.")
else:
    # If user doesn't want to move the blade, set default traverse distance-per-move
    move_distance = 0.5


# Propeller/Motor Startup
throttle_init = 1120
u.sendto(str(throttle_init).encode(), (my_IP, recv_port))
# time.sleep(3)
# throttle = 1160  # begins to spin blades WITH THE KDE 330 KV MOTOR AND FLAME ESC INSTALLED
# u.sendto(str(throttle).encode(), (my_IP, recv_port))
time.sleep(1)  # wait to spin up
control2Thrust(target_thrust, 0.1, 200, u, my_IP, recv_port, kill)


# Sets new traverse distance-per-move "X_pm" [in] if user inputted anything
X_pm = move_distance


# If the user selects a certain distance for the microphone to move, then this part of the statement will activate
if X_pm != 0.5:
    no_of_moves = 1 # since user only wants to test in one location, there will only be one move
    nsteps = np.ceil(X_pm / step_resolution) # sets new value to nsteps based on new X_pm. steps_revolution remains constant
    # placed this here isntead of end in order to allow the microphone to move to the location at the begging instead of waiting for increments
    vxm_value = f'C,I1M{nsteps},R'
    vxm.write(vxm_value.encode('utf-8'))
    for time_hold in range(1,16):
        X = X_pm + X0
        roR = X / R
        print('Current r/R =', roR)
         # control thrust to target using PID script -------------------------
        control2Thrust(target_thrust, 0.05, 100, u, my_IP, recv_port, kill)
        # take measurements for desired sample length -------------------------
        u.sendto(b"read", (my_IP, recv_port))  # writing the "read" string to the JS requests sensor values
        message, _ = u.recvfrom(10240)  # reading the requested sensor values
        tyto_data = json.loads(message.decode('latin1'))
        t0_meas = tyto_data['time']['displayValue']
        itr_meas = 0
        # collect data while the measurement time is within L_samp
        if True:
            L_sample = L_sample_default  # space where you /could/ change the sample length based on roR...
            # but as we've seen that doesn't really help the
            # standard deviations within one measurement cause the thrust
            # starts to drift up/down the longer it goes uncontrolled
        t_meas = 0
        while t_meas <= L_sample:
            itr_meas += 15
            with nidaqmx.Task() as task:
                task.ai_channels.add_ai_voltage_chan(f'{DAQ_ID}/{Channel_ID}')
                micDATA = task.read(number_of_samples_per_channel=1)
            SPL = (200 / 4) * micDATA[0]  # use output "sensitivity" for 2270 in LAF mode...
            # read Tyto stand data over UDP connection to JS
            u.sendto(b"read", (my_IP, recv_port))  # writing the "read" string to the JS requests sensor values
            message, _ = u.recvfrom(10240)  # reading the requested sensor values
            tytoDATA = json.loads(message.decode('latin1'))
            thrust = tytoDATA['thrust']['displayValue']
            torque = tytoDATA['torque']['displayValue']
            RPM = tytoDATA['motorOpticalSpeed']['displayValue']
            mech_power = tytoDATA['mechanicalPower']['displayValue']
            elec_power = tytoDATA['electricalPower']['displayValue']
            time_tyto = tytoDATA['time']['displayValue']
            t_meas = time_tyto - t0_meas
            # pause? (might be limited enough already by tyto sample rate)
        # compute values to store for this position -----------------------
        SPL_mean = np.mean(SPL)
        print('SPL_mean: ', SPL_mean, 'r/R =', roR)
        SPL_stdev = np.std(SPL)
        THRUST_mean = np.mean(thrust)
        THRUST_stdev = np.std(thrust)
        TORQUE_mean = np.mean(torque)
        TORQUE_stdev = np.std(torque)
        RPM_mean = np.mean(RPM)
        RPM_stdev = np.std(RPM)
        POWER_mean = np.mean(mech_power)
        POWER_stdev = np.std(mech_power)
        ePOWER_mean = np.mean(elec_power)
        ePOWER_stdev = np.std(elec_power)
        TIME = t0_meas
        NSAMP = itr_meas

        results_table.append({'Time, [s]': TIME, 'r/R': roR, 'Mean SPL, [dB]': SPL_mean, 'SD SPL': SPL_stdev,
                            'Mean Thrust, [lbf]': THRUST_mean, 'SD Thrust': THRUST_stdev, 'Mean Torque': TORQUE_mean,
                            'SD Torque': TORQUE_stdev, 'Mean RPM': RPM_mean, 'SD RPM': RPM_stdev,
                            'Mech. Power, [W]': POWER_mean, 'SD Power': POWER_stdev, 'Elec. Power, [W]': ePOWER_mean, 
                            'SD Elec Power': ePOWER_stdev, 'n Samples': NSAMP})
else:
    # Movement/Control/Data-Collection (MCDC) Loop for if user selects no
    for itr_moves in range(1, int(no_of_moves) + 1):
        X = ((itr_moves - 1) * X_pm) + X0
        roR = X / R
        print('Current r/R =', roR)
        # control thrust to target using PID script -------------------------
        control2Thrust(target_thrust, 0.05, 100, u, my_IP, recv_port, kill)
        # take measurements for desired sample length -------------------------
        u.sendto(b"read", (my_IP, recv_port))  # writing the "read" string to the JS requests sensor values
        message, _ = u.recvfrom(10240)  # reading the requested sensor values
        tyto_data = json.loads(message.decode('latin1'))
        t0_meas = tyto_data['time']['displayValue']
        itr_meas = 0
        # collect data while the measurement time is within L_samp
        if True:
            L_sample = L_sample_default  # space where you /could/ change the sample length based on roR...
            # but as we've seen that doesn't really help the
            # standard deviations within one measurement cause the thrust
            # starts to drift up/down the longer it goes uncontrolled
        t_meas = 0
        while t_meas <= L_sample:
            itr_meas += 15
            with nidaqmx.Task() as task:
                task.ai_channels.add_ai_voltage_chan(f'{DAQ_ID}/{Channel_ID}')
                micDATA = task.read(number_of_samples_per_channel=1)
            SPL = (200 / 4) * micDATA[0]  # use output "sensitivity" for 2270 in LAF mode...
            # read Tyto stand data over UDP connection to JS
            u.sendto(b"read", (my_IP, recv_port))  # writing the "read" string to the JS requests sensor values
            message, _ = u.recvfrom(10240)  # reading the requested sensor values
            tytoDATA = json.loads(message.decode('latin1'))
            thrust = tytoDATA['thrust']['displayValue']
            torque = tytoDATA['torque']['displayValue']
            RPM = tytoDATA['motorOpticalSpeed']['displayValue']
            mech_power = tytoDATA['mechanicalPower']['displayValue']
            elec_power = tytoDATA['electricalPower']['displayValue']
            time_tyto = tytoDATA['time']['displayValue']
            t_meas = time_tyto - t0_meas
            # pause? (might be limited enough already by tyto sample rate)
        # compute values to store for this position -----------------------
        SPL_mean = np.mean(SPL)
        print('SPL_mean: ', SPL_mean, 'r/R =', roR)
        SPL_stdev = np.std(SPL)
        THRUST_mean = np.mean(thrust)
        THRUST_stdev = np.std(thrust)
        TORQUE_mean = np.mean(torque)
        TORQUE_stdev = np.std(torque)
        RPM_mean = np.mean(RPM)
        RPM_stdev = np.std(RPM)
        POWER_mean = np.mean(mech_power)
        POWER_stdev = np.std(mech_power)
        ePOWER_mean = np.mean(elec_power)
        ePOWER_stdev = np.std(elec_power)
        TIME = t0_meas
        NSAMP = itr_meas

        results_table.append({'Time, [s]': TIME, 'r/R': roR, 'Mean SPL, [dB]': SPL_mean, 'SD SPL': SPL_stdev,
                            'Mean Thrust, [lbf]': THRUST_mean, 'SD Thrust': THRUST_stdev, 'Mean Torque': TORQUE_mean,
                            'SD Torque': TORQUE_stdev, 'Mean RPM': RPM_mean, 'SD RPM': RPM_stdev,
                            'Mech. Power, [W]': POWER_mean, 'SD Power': POWER_stdev, 'Elec. Power, [W]': ePOWER_mean, 
                            'SD Elec Power': ePOWER_stdev, 'n Samples': NSAMP})

        # move to the next position ----------------------------------------
        vxm_value = f'C,I1M{nsteps},R'
        vxm.write(vxm_value.encode('utf-8'))
        time.sleep(2)  # wait for LAF to settle after motor moves and creates noise

# Shutdown Tasks
print("Traverse Complete... Shutting down...\n")
# *** step down for higher RPM? ***
# kill the Tyto-JS (shuts off motor)
throttle_down = np.linspace(tyto_data['escA']['displayValue'], 1000,10)  # make sure the ESC A vs B side is correct here!!!
for throttle in throttle_down:
    u.sendto(str(throttle).encode(), (my_IP, recv_port))
    time.sleep(0.5)
u.sendto(b"kill", (my_IP, recv_port))
# move the traverse back to the starting location (limit-zero position)
vxm.write(b'C,I1M-0,R\n')
# pause(15)% update this to be based on distance?
# clear memory and terminate connection
vxm.write(b'C,Q\n')

u.close()


# send results to a file
results_table.append({'Time, [s]': TIME, 'r/R': roR, 'Mean SPL, [dB]': SPL_mean, 'SD SPL': SPL_stdev,
                      'Mean Thrust, [lbf]': THRUST_mean, 'SD Thrust': THRUST_stdev, 'Mean Torque': TORQUE_mean,
                      'SD Torque': TORQUE_stdev, 'Mean RPM': RPM_mean, 'SD RPM': RPM_stdev,
                      'Mech. Power, [W]': POWER_mean, 'SD Power': POWER_stdev, 'Elec. Power, [W]': ePOWER_mean, 
                      'SD Elec Power': ePOWER_stdev, 'n Samples': NSAMP})
file_label = main_path + ' SPL_Traverse ' + datetime.now().strftime("%B %d %Y %H_%M_%S") + '.csv'
df = pd.DataFrame(results_table)
df.to_csv(file_label, index=False)
