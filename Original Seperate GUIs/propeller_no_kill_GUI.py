''' This is an older version of the GUI, please refer to propeller_no_kill_rOR_GUI.py for a more updated GUI version '''

import tkinter
import tkinter.messagebox
import customtkinter
from customtkinter import *
from CTkMessagebox import CTkMessagebox
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
from serial import Serial
import nidaqmx
import os
import sys

customtkinter.set_appearance_mode("System")  # Modes: "System" (standard), "Dark", "Light"
customtkinter.set_default_color_theme("blue")  # Themes: "blue" (standard), "green", "dark-blue"

# Global variables

# Propeller radius "R", [in]
# [in] (radius for 13" nominal diameter blades)
R = 22.25 / 2

# Traverse distance-per-move "X_pm", [in]
X_pm = 0.1

# Traverse start location "X0", [in]
X0 = 3.750

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

# Path to save results
main_path = 'C:\\Users\\mykoh\\OneDrive\\Documents\\BIP\\Results\\'


kill = 0
results_table = []
u = None
vxm = None
recv_port = 55047

def initialize_app():
    global R, X_pm, X0, L_sample_default, mic_name, DAQ_ID, Channel_ID, f_sample, A
    global hostname, my_IP, tx_port, main_path, kill, results_table, u, vxm, recv_port

    # Your initialization code here...

    # Set up UDP communication with Tyto JS code
    u = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    u.bind((my_IP, tx_port))
    recv_port = 55047
    u.sendto(b"hello there RC Benchmark", (my_IP, recv_port))

    # define number of moves
    no_of_moves = np.ceil((R - X0) / X_pm)

    # VXM setup
    step_resolution = 0.0050 * (1 / 25.4)
    nsteps = np.ceil(X_pm / step_resolution)
    
    # Explicitly close the serial port if it's already open
    if vxm and vxm.is_open:
        vxm.close()

    # Try to open the serial port
    try:
        vxm = serial.Serial('COM5', 9600)
        vxm.write(b'\r')
        time.sleep(1)
        vxm.write(b'G\n')
    except serial.SerialException as e:
        print(f"Failed to open COM5: {e}")


class App(customtkinter.CTk):
    def __init__(self):
        super().__init__()

        # configure window
        self.title("Athule Test Stand Data Collector")
        self.geometry('500x380')
        self.resizable(width=True,height=True)

        # make frames
        self.top_frame = customtkinter.CTkFrame(master=self,
                                                corner_radius=20,
                                                border_width= 2,
                                                border_color='#7EA8B5')
        self.middle_frame = customtkinter.CTkFrame(master=self,
                                                corner_radius=10,
                                                border_width=2,
                                                border_color='#7EA8B5')
        self.button_frame = customtkinter.CTkFrame(self.middle_frame,
                                                  fg_color='transparent')
        
        self.top_frame.pack(fill='y', padx=20, pady=10)
        self.middle_frame.pack(fill='y', padx=20, pady=20, expand='True')
        self.button_frame.pack(side='bottom', padx=20, pady=20, expand='True')

        # ----------------------------------------------------------------------------------------------------------

        # add widgets to app
        self.label = customtkinter.CTkLabel(self.top_frame, text='Enter target thrust, [lbf]: ',
                        font=customtkinter.CTkFont('CustomTkinter', 18, 'bold'))
        self.target_thrust = customtkinter.CTkEntry(self.top_frame, placeholder_text='')

        self.move_distance = customtkinter.CTkLabel(self.middle_frame, text='Move microphone to a specified location?',
                        font=customtkinter.CTkFont('CustomTkinter', 18, 'bold'))

        # ----------------------------------------------------------------------------------------------------------

        self.radio_var = tkinter.IntVar(value=0)

        self.radiobutton1 = customtkinter.CTkRadioButton(self.button_frame, text="Yes",
                                            variable= self.radio_var, font=('CustomTkinter', 16), value=1)
        self.radiobutton2 = customtkinter.CTkRadioButton(self.button_frame, text="No",
                                            variable= self.radio_var, font=('CustomTkinter', 16), value=2)
        
        # -----------------------------------------------------------------------------------------------------------

        self.reset_button = customtkinter.CTkButton(self, text='RESET', anchor='center',
                                                    font=customtkinter.CTkFont('CustomTkinter', 14, 'bold'), fg_color='#7EA8B5',
                                                    corner_radius = 20, hover_color='#F83613', command=self.button_reset)

        self.button = customtkinter.CTkButton(self, text='RUN', anchor='center', 
                                            font=customtkinter.CTkFont('CustomTkinter', 14, 'bold'), fg_color='#7EA8B5',
                                            corner_radius = 20, hover_color='#7DC445', command=self.button_click)

        
        # ----------------------------------------------------------------------------------------------------------

        self.label.pack(padx=20, pady=5)
        self.target_thrust.pack(padx=20, pady=10)

        self.move_distance.pack(side='top', padx=20, pady=5)
        self.radiobutton1.pack(side='left', padx=20)
        self.radiobutton2.pack(side='right', padx=20)
        # self.radiobutton1.pack(padx=20, pady=0)
        # self.radiobutton2.pack(padx=20, pady=5)

        self.button.pack(padx=20, pady=20, expand='True')
        self.reset_button.pack(padx=20, pady=20, expand='True')

    # add methods to app
    def button_click(self):
        if self.target_thrust.get() == '':
            CTkMessagebox(title='Error', message='Please enter thrust [lbs]')
        elif self.target_thrust.get().isnumeric() == False:
            CTkMessagebox(title='Error', message='Please enter a numerical thrust [lbs] value')
        else:
            thrust_value = float(self.target_thrust.get())

            if thrust_value < 0 or thrust_value > 15:
                CTkMessagebox(title='Error', message='Thrust value must be between 0 and 15 lbs')
            else:
                if self.radio_var.get() == 1:
                # Code for moving the microphone...
                    distance = customtkinter.CTkInputDialog(text="Enter the distance to move the microphone (in inches, max 15 in):",
                                                            title="Specified Location")

                    move_distance = float(distance.get_input())

                    print("Distance:", move_distance)
                    
                    # Propeller/Motor Startup
                    throttle_init = 1120
                    u.sendto(str(throttle_init).encode(), (my_IP, recv_port))
                    # time.sleep(3)
                    # throttle = 1160  # begins to spin blades WITH THE KDE 330 KV MOTOR AND FLAME ESC INSTALLED
                    # u.sendto(str(throttle).encode(), (my_IP, recv_port))
                    time.sleep(1)  # wait to spin up
                    control2Thrust(self.target_thrust.get(), 0.1, 200, u, my_IP, recv_port, kill)

                    # Sets new traverse distance-per-move "X_pm" [in] if user inputted anything
                    X_pm = move_distance

                    if X_pm != 0.5:
                        # If the user selects a certain distance for the microphone to move, then this part of the statement will activate
                        no_of_moves = 1 # since user only wants to test in one location, there will only be one move
                        step_resolution = 0.0050 * (1 / 25.4)  # [mm/step] --> [in/step]
                        nsteps = np.ceil(X_pm / step_resolution) # sets new value to nsteps based on new X_pm. steps_revolution remains constant
                        # placed this here instead of end in order to allow the microphone to move to the location at the begging instead of waiting for increments
                        vxm_value = f'C,I1M{nsteps},R'
                        vxm.write(vxm_value.encode('utf-8'))
                        for time_hold in range(1,16):
                            X = X_pm + X0
                            roR = X / R
                            print('Current r/R =', roR)
                            # control thrust to target using PID script -------------------------
                            control2Thrust(self.target_thrust.get(), 0.05, 100, u, my_IP, recv_port, kill)
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
                                voltage = tytoDATA['voltage']['displayValue']
                                current = tytoDATA['current']['displayValue']
                                RPM = tytoDATA['motorOpticalSpeed']['displayValue']
                                mech_power = tytoDATA['mechanicalPower']['displayValue']
                                elec_power = tytoDATA['electricalPower']['displayValue']
                                motor_eff = tytoDATA['motorEfficiency']['displayValue']
                                prop_Mech_eff = tytoDATA['propMechEfficiency']['displayValue']
                                prop_Elec_eff = tytoDATA['propElecEfficiency']['displayValue']
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
                            VOLTAGE_mean = np.mean(voltage)
                            VOLTAGE_stdev = np.std(voltage)
                            CURRENT_mean = np.mean(current)
                            CURRENT_stdev = np.std(current)
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
                                                'SD Torque': TORQUE_stdev, 'Mean Voltage': VOLTAGE_mean,
                                                'SD Votlage': VOLTAGE_stdev, 'Mean RPM': RPM_mean, 'SD RPM': RPM_stdev, 'Mean Current': CURRENT_mean,
                                                'SD Current': CURRENT_stdev, 'Mech. Power, [W]': POWER_mean, 'SD Power': POWER_stdev,
                                                'Elec. Power, [W]': ePOWER_mean,'SD Elec Power': ePOWER_stdev, 'Motor Eff.': motor_eff, 
                                                'Propeller Mech. Eff.': prop_Mech_eff, 'Propeller Elec. Eff.': prop_Elec_eff, 'n Samples': NSAMP})
                            
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
                                        'SD Torque': TORQUE_stdev, 'Mean Voltage': VOLTAGE_mean, 'SD Votlage': VOLTAGE_stdev,
                                        'Mean RPM': RPM_mean, 'SD RPM': RPM_stdev, 'Mean Current': CURRENT_mean,
                                        'SD Current': CURRENT_stdev, 'Mech. Power, [W]': POWER_mean, 'SD Power': POWER_stdev, 
                                        'Elec. Power, [W]': ePOWER_mean, 'SD Elec Power': ePOWER_stdev,'Motor Eff.': motor_eff, 
                                        'Propeller Mech. Eff.': prop_Mech_eff, 'Propeller Elec. Eff.': prop_Elec_eff, 
                                        'n Samples': NSAMP})
                    file_label = main_path + ' SPL_Traverse ' + datetime.now().strftime("%B %d %Y %H_%M_%S") + '.csv'
                    df = pd.DataFrame(results_table)
                    df.to_csv(file_label, index=False)
                    
                elif self.radio_var.get() == 2:
                # Code for incrementing the microphone...
                    move_distance = 0.1

                    # Propeller/Motor Startup
                    throttle_init = 1120
                    u.sendto(str(throttle_init).encode(), (my_IP, recv_port))
                    # time.sleep(3)
                    # throttle = 1160  # begins to spin blades WITH THE KDE 330 KV MOTOR AND FLAME ESC INSTALLED
                    # u.sendto(str(throttle).encode(), (my_IP, recv_port))
                    time.sleep(1)  # wait to spin up
                    control2Thrust(self.target_thrust.get(), 0.1, 200, u, my_IP, recv_port, kill)

                    # Sets new traverse distance-per-move "X_pm" [in] if user inputted anything
                    X_pm = move_distance

                    no_of_moves = np.ceil((R - X0) / X_pm)

                    # Movement/Control/Data-Collection (MCDC) Loop for if user selects no
                    for itr_moves in range(1, int(no_of_moves) + 1):
                        X = ((itr_moves - 1) * X_pm) + X0
                        roR = X / R
                        print('Current r/R =', roR)
                        # control thrust to target using PID script -------------------------
                        control2Thrust(self.target_thrust.get(), 0.05, 100, u, my_IP, recv_port, kill)
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
                            voltage = tytoDATA['voltage']['displayValue']
                            current = tytoDATA['current']['displayValue']
                            RPM = tytoDATA['motorOpticalSpeed']['displayValue']
                            mech_power = tytoDATA['mechanicalPower']['displayValue']
                            elec_power = tytoDATA['electricalPower']['displayValue']
                            motor_eff = tytoDATA['motorEfficiency']['displayValue']
                            prop_Mech_eff = tytoDATA['propMechEfficiency']['displayValue']
                            prop_Elec_eff = tytoDATA['propElecEfficiency']['displayValue']
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
                        VOLTAGE_mean = np.mean(voltage)
                        VOLTAGE_stdev = np.std(voltage)
                        CURRENT_mean = np.mean(current)
                        CURRENT_stdev = np.std(current)
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
                                                'SD Torque': TORQUE_stdev, 'Mean Voltage': VOLTAGE_mean,
                                                'SD Votlage': VOLTAGE_stdev, 'Mean RPM': RPM_mean, 'SD RPM': RPM_stdev, 'Mean Current': CURRENT_mean,
                                                'SD Current': CURRENT_stdev, 'Mech. Power, [W]': POWER_mean, 'SD Power': POWER_stdev,
                                                'Elec. Power, [W]': ePOWER_mean,'SD Elec Power': ePOWER_stdev, 'Motor Eff.': motor_eff, 
                                                'Propeller Mech. Eff.': prop_Mech_eff, 'Propeller Elec. Eff.': prop_Elec_eff, 'n Samples': NSAMP})

                        # move to the next position ----------------------------------------
                        step_resolution = 0.0050 * (1 / 25.4)  # [mm/step] --> [in/step]
                        nsteps = np.ceil(X_pm / step_resolution)
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
                                        'SD Torque': TORQUE_stdev, 'Mean Voltage': VOLTAGE_mean, 'SD Votlage': VOLTAGE_stdev,
                                        'Mean RPM': RPM_mean, 'SD RPM': RPM_stdev, 'Mean Current': CURRENT_mean,
                                        'SD Current': CURRENT_stdev, 'Mech. Power, [W]': POWER_mean, 'SD Power': POWER_stdev, 
                                        'Elec. Power, [W]': ePOWER_mean, 'SD Elec Power': ePOWER_stdev,'Motor Eff.': motor_eff, 
                                        'Propeller Mech. Eff.': prop_Mech_eff, 'Propeller Elec. Eff.': prop_Elec_eff, 
                                        'n Samples': NSAMP})
                    file_label = main_path + ' SPL_Traverse ' + datetime.now().strftime("%B %d %Y %H_%M_%S") + '.csv'
                    df = pd.DataFrame(results_table)
                    df.to_csv(file_label, index=False)
            

    def button_reset(self):
        global app, R, X_pm, X0, L_sample_default, mic_name, DAQ_ID, Channel_ID, f_sample, A
        global hostname, my_IP, tx_port, main_path, kill, results_table, u, vxm, recv_port
        
        # Closes the existing socket before destroying the app
        if u:
            u.close()

        # Destroys the existing app
        app.destroy()
        
        # Reinitialize the app and other variables
        initialize_app()
        app = App()
        app.mainloop()

initialize_app()
app = App()
app.mainloop()


