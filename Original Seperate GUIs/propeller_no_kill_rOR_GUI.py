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
import csv

## THIS VERSION INCLUDES TAKING AN INITIAL BACKGROUND NOSE CHECK AND SUBTRACTING IT TOTAL SPL AT EACH POINT ##

customtkinter.set_appearance_mode("System")  # Modes: "System" (standard), "Dark", "Light"
customtkinter.set_default_color_theme("blue")  # Themes: "blue" (standard), "green", "dark-blue"

# Global variables

# Traverse distance-per-move "X_pm", [in]
X_pm = 0.1

# Acoustic measurement duration, [s]
L_sample_default = 5

# Microphone name, {string} (use to retrieve calibration data)
mic_name = 'usr_A'

# DAQ card port ID (where is it on the cDAQ module?) {string}
DAQ_ID = 'cDAQ1Mod8'

# DAQ channel number (which channel is our signal coming in?) {string}
Channel_ID = 'ai1'

# Sample frequency "f_samp", [Hz]
f_sample = 10000

# Gain on 2270 output socket (?) (I've been using 60 dB)
A = 30

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
    # no_of_moves = np.ceil((R - X0) / X_pm)

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
        self.geometry('700x580')
        self.resizable(width=True,height=True)

        # make frames
        self.blade = customtkinter.CTkFrame(master=self,
                                            fg_color='transparent')
        self.blade_radius = customtkinter.CTkFrame(self.blade,
                                                   corner_radius=20,
                                                   border_width=2,
                                                   border_color='#7EA8B5')
        self.microphone_dist = customtkinter.CTkFrame(self.blade,
                                                      corner_radius=20,
                                                      border_width=2,
                                                      border_color='#7EA8B5')
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
        
        self.blade.pack(fill='y', padx=20, pady=20, expand='True')
        self.blade_radius.pack(side='left', padx=40, pady=20, expand='True')
        self.microphone_dist.pack(side='right', padx=15, pady=20, expand='True')
        self.top_frame.pack(fill='y', padx=20, pady=10)
        self.middle_frame.pack(fill='y', padx=20, pady=20, expand='True')
        self.button_frame.pack(side='bottom', padx=20, pady=20, expand='True')

        # ----------------------------------------------------------------------------------------------------------

        # add widgets to app
        self.blade_label = customtkinter.CTkLabel(self.blade_radius, text='Enter Blade Radius [in]: ',
                        font=customtkinter.CTkFont('CustomTkinter', 18, 'bold'))
        self.blade_radius = customtkinter.CTkEntry(self.blade_radius, placeholder_text='')

        self.microphone_label = customtkinter.CTkLabel(self.microphone_dist, text='Enter Hub to Microphone Dist [in]:\n(Please set to 3.750)',
                        font=customtkinter.CTkFont('CustomTkinter', 15, 'bold'))
        self.microphone_2_hub_entry = customtkinter.CTkEntry(self.microphone_dist, placeholder_text='')

        self.label = customtkinter.CTkLabel(self.top_frame, text='Enter Target Thrust, [lbf]: ',
                        font=customtkinter.CTkFont('CustomTkinter', 18, 'bold'))
        self.target_thrust = customtkinter.CTkEntry(self.top_frame, placeholder_text='')

        self.move_distance = customtkinter.CTkLabel(self.middle_frame, text='Move Microphone to a Specified Location?',
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

        self.blade_label.pack(padx=20, pady=5)
        self.blade_radius.pack(padx=20, pady=10)

        self.microphone_label.pack(padx=20, pady=5)
        self.microphone_2_hub_entry.pack(padx=20, pady=10)

        self.label.pack(padx=20, pady=5)
        self.target_thrust.pack(padx=20, pady=10)

        self.move_distance.pack(side='top', padx=20, pady=5)
        self.radiobutton1.pack(side='left', padx=20)
        self.radiobutton2.pack(side='right', padx=20)
        # self.radiobutton1.pack(padx=20, pady=0)
        # self.radiobutton2.pack(padx=20, pady=5)

        self.button.pack(padx=20, pady=20, expand='True')
        self.reset_button.pack(padx=20, pady=20, expand='True')

    def measure_background_noise(self):
        # Take multiple readings to get a stable background noise measurement
        num_samples = 10
        noise_levels = []
        with nidaqmx.Task() as task:
            task.ai_channels.add_ai_voltage_chan(f'{DAQ_ID}/{Channel_ID}')
            for _ in range(num_samples):
                micDATA = task.read(number_of_samples_per_channel=1)
                SPL = (200 / 4) * micDATA[0]  # Assuming this is the correct conversion for your setup
                noise_levels.append(SPL)
                time.sleep(0.1)  # Short pause between readings

        # Calculate the mean SPL for background noise
        background_noise = np.mean(noise_levels)
        background_noise_stdev = np.std(noise_levels)
        print(f"Initial Background Noise: {background_noise:.2f} dB ± {background_noise_stdev:.2f}")
        results_table.append({'Initial Background Noise [dB]': background_noise})
        return background_noise, background_noise_stdev

    def button_click(self):

        # Propeller radius "R", [in]
        if self.blade_radius.get() == '':
            CTkMessagebox(title='Error', message='Please enter radius [in]')
        elif self.blade_radius.get().isnumeric() == False:
            CTkMessagebox(title='Error', message='Please enter a numerical radius value [in]')
        else:
            R = float(self.blade_radius.get())
        
        # Traverse start location "X0", [in]
        if self.microphone_2_hub_entry.get() == '':
            CTkMessagebox(title='Error', message='Please enter distance [in]')
        elif self.microphone_2_hub_entry.get().isnumeric() == False:
            CTkMessagebox(title='Error', message='Please enter a numerical radius value [in]')
        else:
            X0 = float(self.microphone_2_hub_entry.get())
        

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
                # Calling the function to measure the background noise:
                    background_noise, background_noise_stdev = self.measure_background_noise()

                # Code for moving the microphone...
                    roR_input = customtkinter.CTkInputDialog(text="Enter specific r/R to move to: (max r/R is 1.2)",
                                                            title="Specified Location")
                    # distance = customtkinter.CTkInputDialog(text="Enter the distance to move the microphone (in inches, max 15 in):",
                    #                                         title="Specified Location")

                    roR = float(roR_input.get_input())

                    X_pm = (roR * R) - X0

                    # Sets new traverse distance-per-move "X_pm" [in] if user inputted anything
                    print("r/R Distance:", roR)
                    
                    # Propeller/Motor Startup
                    throttle_init = 1120
                    u.sendto(str(throttle_init).encode(), (my_IP, recv_port))
                    # time.sleep(3)
                    # throttle = 1160  # begins to spin blades WITH THE KDE 330 KV MOTOR AND FLAME ESC INSTALLED
                    # u.sendto(str(throttle).encode(), (my_IP, recv_port))
                    time.sleep(1)  # wait to spin up
                    control2Thrust(self.target_thrust.get(), 0.1, 200, u, my_IP, recv_port, kill)

                    if X_pm != 0.1:
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
                            print('Current Iteration: ', time_hold, ' of ', len(range(1,16)))
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
                            
                            # Initialize lists to store multiple readings
                            SPLs, thrusts, torques, voltages, currents, RPMs, mech_powers, elec_powers, motor_effs, prop_Mech_effs, prop_Elec_effs, times = ([] for i in range(12))
                        

                            while t_meas <= L_sample:
                                itr_meas += 15
                                with nidaqmx.Task() as task:
                                    task.ai_channels.add_ai_voltage_chan(f'{DAQ_ID}/{Channel_ID}')
                                    micDATA = task.read(number_of_samples_per_channel=1) #micDATA is the voltage output from the microphone within DAQ chasis
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


                                # Append new readings to their respective lists
                                SPLs.append(SPL)
                                thrusts.append(thrust)
                                torques.append(torque)
                                voltages.append(voltage)
                                currents.append(current)
                                RPMs.append(RPM)
                                mech_powers.append(mech_power)
                                elec_powers.append(elec_power)
                                motor_effs.append(motor_eff)
                                prop_Mech_effs.append(prop_Mech_eff)
                                prop_Elec_effs.append(prop_Elec_eff)
                                times.append(time_tyto)

                                
                                # pause? (might be limited enough already by tyto sample rate)
                            # compute values to store for this position -----------------------
                            SPL_mean = np.mean(SPLs)
                            print('SPL_mean: ', SPL_mean, 'r/R =', roR)
                            SPL_stdev = np.std(SPLs)
                            THRUST_mean = np.mean(thrusts)
                            THRUST_stdev = np.std(thrusts)
                            TORQUE_mean = np.mean(torques)
                            TORQUE_stdev = np.std(torques)
                            VOLTAGE_mean = np.mean(voltages)
                            VOLTAGE_stdev = np.std(voltages)
                            CURRENT_mean = np.mean(currents)
                            CURRENT_stdev = np.std(currents)
                            RPM_mean = np.mean(RPMs)
                            RPM_stdev = np.std(RPMs)
                            POWER_mean = np.mean(mech_powers)
                            POWER_stdev = np.std(mech_powers)
                            ePOWER_mean = np.mean(elec_powers)
                            ePOWER_stdev = np.std(elec_powers)
                            TIME = t0_meas
                            NSAMP = itr_meas

                            # Decibel Subtraction Equation to remove background noise
                            SPLs_adjusted = [SPL_mean + np.log10(1 - 10 ** (-(SPL_mean - background_noise)/10)) for spl in SPLs]
                            SPL_no_back = np.mean(SPLs_adjusted)
                            SPL_no_back_stdev = np.std(SPLs_adjusted)

                            results_table.append({'Time, [s]': TIME, 'r/R': roR, 'SPL no background: [dB]': SPL_no_back, 'SD SPL no background': SPL_no_back_stdev, 'Mean SPL, [dB]': SPL_mean, 'SD SPL': SPL_stdev,
                                                'Mean Thrust, [lbf]': THRUST_mean, 'SD Thrust': THRUST_stdev, 'Mean Torque': TORQUE_mean,
                                                'SD Torque': TORQUE_stdev, 'Mean Voltage': VOLTAGE_mean,
                                                'SD Votlage': VOLTAGE_stdev, 'Mean RPM': RPM_mean, 'SD RPM': RPM_stdev, 'Mean Current': CURRENT_mean,
                                                'SD Current': CURRENT_stdev, 'Mech. Power, [W]': POWER_mean, 'SD Power': POWER_stdev,
                                                'Elec. Power, [W]': ePOWER_mean,'SD Elec Power': ePOWER_stdev, 'Motor Eff.': motor_eff, 
                                                'Propeller Mech. Eff.': prop_Mech_eff, 'Propeller Elec. Eff.': prop_Elec_eff, 'n Samples': NSAMP})
                            
                    # Shutdown Tasks
                    print("Traverse Complete... Shutting down...\n")
                    print(f"The initial background noise was: {background_noise:.4f} dB")
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
                    
                    file_label = main_path + ' SPL_Traverse ' + datetime.now().strftime("%B %d %Y %H_%M_%S") + '.csv'
                    df = pd.DataFrame(results_table)
                    df.to_csv(file_label, index=False)
                    
                elif self.radio_var.get() == 2:
                # Calling the function to measure the background noise:
                    background_noise, background_noise_stdev = self.measure_background_noise()

                # Code for incrementing the microphone...
                    CTkMessagebox(title='Notice', message='Mic will increment by 0.1 inches.')
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
                        print('Current Iteration: ', itr_moves, ' of ', int(no_of_moves))
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

                        # Initialize lists to store multiple readings
                        SPLs, thrusts, torques, voltages, currents, RPMs, mech_powers, elec_powers, motor_effs, prop_Mech_effs, prop_Elec_effs, times = ([] for i in range(12))

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

                            # Append new readings to their respective lists
                            SPLs.append(SPL)
                            thrusts.append(thrust)
                            torques.append(torque)
                            voltages.append(voltage)
                            currents.append(current)
                            RPMs.append(RPM)
                            mech_powers.append(mech_power)
                            elec_powers.append(elec_power)
                            motor_effs.append(motor_eff)
                            prop_Mech_effs.append(prop_Mech_eff)
                            prop_Elec_effs.append(prop_Elec_eff)
                            times.append(time_tyto)    

                            # pause? (might be limited enough already by tyto sample rate)
                        
                        # compute values to store for this position -----------------------
                        SPL_mean = np.mean(SPLs)
                        print('SPL_mean: ', SPL_mean, 'r/R =', roR)
                        SPL_stdev = np.std(SPLs)
                        THRUST_mean = np.mean(thrusts)
                        THRUST_stdev = np.std(thrusts)
                        TORQUE_mean = np.mean(torques)
                        TORQUE_stdev = np.std(torques)
                        VOLTAGE_mean = np.mean(voltages)
                        VOLTAGE_stdev = np.std(voltages)
                        CURRENT_mean = np.mean(currents)
                        CURRENT_stdev = np.std(currents)
                        RPM_mean = np.mean(RPMs)
                        RPM_stdev = np.std(RPMs)
                        POWER_mean = np.mean(mech_powers)
                        POWER_stdev = np.std(mech_powers)
                        ePOWER_mean = np.mean(elec_powers)
                        ePOWER_stdev = np.std(elec_powers)
                        TIME = t0_meas
                        NSAMP = itr_meas

                        # Decibel Subtraction Equation to remove background noise
                        SPLs_adjusted = [SPL_mean + np.log10(1 - 10 ** (-(SPL_mean - background_noise)/10)) for spl in SPLs]
                        SPL_no_back = np.mean(SPLs_adjusted)
                        SPL_no_back_stdev = np.std(SPLs_adjusted)

                        results_table.append({'Time, [s]': TIME, 'r/R': roR, ' Mean SPL no background: [dB]': SPL_no_back, 'SD SPL no background': SPL_no_back_stdev, 'Mean SPL, [dB]': SPL_mean, 'SD SPL': SPL_stdev,
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
                    print(f"The initial background noise was: {background_noise:.4f} dB")
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
                    file_label = main_path + ' SPL_Traverse ' + datetime.now().strftime("%B %d %Y %H_%M_%S") + '.csv'
                    df = pd.DataFrame(results_table)
                    df.to_csv(file_label, index=False)

    def button_reset(self):
        global file_label, app, R, X_pm, X0, L_sample_default, mic_name, DAQ_ID, Channel_ID, f_sample, A
        global hostname, my_IP, tx_port, main_path, kill, results_table, u, vxm, recv_port
        
        # Closes the existing socket before destroying the app
        if u:
            u.close()

        # Clears the result_table list so it doesn't keep appending to the same csv file if you hit reset
        results_table.clear()

        # Destroys the existing app
        app.destroy()
        
        # Reinitialize the app and other variables
        initialize_app()
        app = App()
        app.mainloop()

initialize_app()
app = App()
app.mainloop()