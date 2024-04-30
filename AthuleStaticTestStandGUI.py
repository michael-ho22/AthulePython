from tkinter import *
import customtkinter
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
import nidaqmx
from nidaqmx.constants import TerminalConfiguration, AcquisitionType
import waveform_analysis # To install, do: pip install git+https://github.com/endolith/waveform_analysis.git@master
from scipy.signal import iirfilter, lfilter
from scipy.fft import fft, fftfreq
from scipy.integrate import simpson
import matplotlib.pyplot as plt
from pandas import ExcelWriter
from datetime import datetime
from control2Thrust import control2Thrust
from control2RPM import control2rpm
import tkinter as tk
from tkinter import messagebox, Tk, Button
import serial
from serial import Serial
import openpyxl
import warnings
import os
import sys
import csv
import acoustics.signal
from acoustics.standards.iec_61672_1_2013 import WEIGHTING_A

customtkinter.set_appearance_mode("System")  # Modes: "System" (standard), "Dark", "Light"
customtkinter.set_default_color_theme("dark-blue")  # Themes: "blue" (standard), "green", "dark-blue"

# ----------------------------------------------------------------------------

# Global variables for Propeller no Kill

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

# ----------------------------------------------------------------------------

# Global Variables for Point Mic Measurement

# Constants and Microphone Parameters
Card_ID = DAQ_ID
f_samp = 50000  # Sample frequency in Hz
L_samp = 10  # Sample duration in seconds
P_ref = 20e-6  # Reference pressure in Pascals

X0 = 3.75

# Define microphone sensitivity and gain based on Mic_Name
mic_params = {
    'usr_A': {'mic_sens': 1.56e-3, 'gain': 15},
    'usr_B': {'mic_sens': 1.575e-3, 'gain': 20},
    'GRAS': {'mic_sens': 12e-3, 'gain': 1}
}

Mic_Name = 'usr_A'  # or 'usr_B', 'GRAS', as needed
mic_sens = mic_params[Mic_Name]['mic_sens']
gain = mic_params[Mic_Name]['gain']
output_dir = 'C:\\Users\\mykoh\\OneDrive\\Documents\\BIP\\Results\\FFT'

# ------------------------------------------------------------------------------

# Global Variables for Auto Sweep RPM
L_samp_tab3 = 5
# SweepRPMs = np.linspace(1500, 3000, 25)
main_path_tab3 = r'C:\Users\mykoh\OneDrive\Documents\BIP\Results\RPM_Sweep'
local_port = 64856
b = 0
results = []


def initialize_app():
    global R, X_pm, X0, L_sample_default, mic_name, DAQ_ID, Channel_ID, f_sample, A
    global hostname, my_IP, tx_port, main_path, kill, results_table, u, vxm, recv_port
    global Card_ID, f_samp, L_samp, P_ref, mic_params, Mic_Name, mic_sens, gain, L_samp_tab3

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

class Tooltip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip_window = None

        # Bind mouse events
        self.widget.bind("<Enter>", self.enter)
        self.widget.bind("<Leave>", self.leave)

    def enter(self, event=None):
        x, y, cx, cy = self.widget.bbox("insert")  # Get the widget's bounding box
        x += self.widget.winfo_rootx() + 25  # Position to the right of the widget
        y += self.widget.winfo_rooty() + 20  # Position below the widget

        # Create a toplevel window with no borders and not in the taskbar
        self.tooltip_window = tk.Toplevel(self.widget)
        self.tooltip_window.wm_overrideredirect(True)
        self.tooltip_window.wm_geometry("+%d+%d" % (x, y))
        
        # Add a label with the tooltip text
        background_color = "#334257"  # Dark blue background
        text_color = "#E0E1DD"  # Light text color
        label = tk.Label(self.tooltip_window, text=self.text, justify='left',
                         background=background_color, foreground=text_color,
                         relief='solid', borderwidth=1, font=("CustomTkinter", 12, "bold"))
        label.pack(ipadx=1)

    def leave(self, event=None):
        if self.tooltip_window:
            self.tooltip_window.destroy()
            self.tooltip_window = None

class MyTabView(customtkinter.CTkTabview):
    def __init__(self, master, initial_values, **kwargs):
        super().__init__(master, **kwargs)

        # Create tabs
        tab_1 = self.add("Propeller Traverse")
        tab_2 = self.add("Spectrum Collection (Point Location)")
        tab_3 = self.add("RPM Auto Sweep")

        # ---------------------------------------------------------------------------

        # Widgets in tab_1
        note1 = customtkinter.CTkFrame(tab_1)
        blade = customtkinter.CTkFrame(tab_1,
                              fg_color='transparent')
        blade_radius = customtkinter.CTkFrame(blade,
                                            corner_radius=20,
                                            border_width=2,
                                            border_color='#7EA8B5')
        microphone_dist = customtkinter.CTkFrame(blade,
                                            corner_radius=20,
                                            border_width=2,
                                            border_color='#7EA8B5')
        top_frame = customtkinter.CTkFrame(tab_1,
                                            corner_radius=20,
                                            border_width= 2,
                                            border_color='#7EA8B5')
        middle_frame = customtkinter.CTkFrame(tab_1,
                                            corner_radius=10,
                                            border_width=2,
                                            border_color='#7EA8B5')
        button_frame = customtkinter.CTkFrame(middle_frame,
                                            fg_color='transparent')
        
        note1.pack(fill='y', padx=5, pady=5)
        blade.pack(fill='y', padx=20, pady=10, expand='True')
        blade_radius.pack(side='left', padx=40, pady=10, expand='True')
        microphone_dist.pack(side='right', padx=15, pady=10, expand='True')
        top_frame.pack(fill='y', padx=20, pady=10)
        middle_frame.pack(fill='y', padx=20, pady=20, expand='True')
        button_frame.pack(side='bottom', padx=20, pady=20, expand='True')

        note_label1 = customtkinter.CTkLabel(note1, text= 'PLEASE READ DOCUMENTATION BEFORE USING PROGRAM\n\n !! Change Output Socket Signal to LAF Weighted and 30.0 dB gain in setup tab on 2270 device !!',
                                            font=customtkinter.CTkFont('CustomTkinter', 14, 'bold'), text_color='#FF2727')
        blade_label = customtkinter.CTkLabel(blade_radius, text='Enter Blade Radius [in]: ',
                        font=customtkinter.CTkFont('CustomTkinter', 18, 'bold'))
        self.blade_radius_entry = customtkinter.CTkEntry(blade_radius, placeholder_text='')
        self.blade_radius_entry.insert(0, initial_values.get('blade_radius_entry', ''))

        microphone_label = customtkinter.CTkLabel(microphone_dist, text='Enter Hub to Microphone Dist [in]:',
                        font=customtkinter.CTkFont('CustomTkinter', 15, 'bold'))
        self.microphone_2_hub_entry = customtkinter.CTkEntry(microphone_dist, placeholder_text='')
        self.microphone_2_hub_entry.insert(0, initial_values.get('microphone_2_hub_entry', ''))

        label = customtkinter.CTkLabel(top_frame, text='Enter Target Thrust, [lbf]: ',
                        font=customtkinter.CTkFont('CustomTkinter', 18, 'bold'))
        self.target_thrust = customtkinter.CTkEntry(top_frame, placeholder_text='')
        self.target_thrust.insert(0, initial_values.get('target_thrust', ''))

        move_distance = customtkinter.CTkLabel(middle_frame, text='Move Microphone to a Specified Location?',
                        font=customtkinter.CTkFont('CustomTkinter', 18, 'bold'))

        self.radio_var = tkinter.IntVar(value=0)

        radiobutton1 = customtkinter.CTkRadioButton(button_frame, text="Yes",
                                            variable= self.radio_var, font=('CustomTkinter', 16), value=1)
        radiobutton2 = customtkinter.CTkRadioButton(button_frame, text="No",
                                            variable= self.radio_var, font=('CustomTkinter', 16), value=2)
        
        reset_button = customtkinter.CTkButton(tab_1, text='RESET', anchor='center',
                                                    font=customtkinter.CTkFont('CustomTkinter', 14, 'bold'), fg_color='#7EA8B5',
                                                    corner_radius = 20, hover_color='#F83613',command=self.button_reset)

        reset_vxm = customtkinter.CTkButton(tab_1, text='RESET MIC LOCATION', anchor='center',
                                                    font=customtkinter.CTkFont('CustomTkinter', 14, 'bold'), fg_color='#7EA8B5',
                                                    corner_radius = 20, hover_color='#F83613',command=self.button_reset_vxm)

        button = customtkinter.CTkButton(tab_1, text='RUN', anchor='center', 
                                            font=customtkinter.CTkFont('CustomTkinter', 14, 'bold'), fg_color='#7EA8B5',
                                            corner_radius = 20, hover_color='#7DC445', command=self.button_click)

        note_label1.pack(padx=10, pady=2)

        blade_label.pack(padx=20, pady=5)
        self.blade_radius_entry.pack(padx=20, pady=10)

        microphone_label.pack(padx=20, pady=5)
        self.microphone_2_hub_entry.pack(padx=20, pady=10)

        label.pack(padx=20, pady=5)
        self.target_thrust.pack(padx=20, pady=10)

        move_distance.pack(side='top', padx=20, pady=5)
        radiobutton1.pack(side='left', padx=20)
        radiobutton2.pack(side='right', padx=20)

        button.pack(padx=20, pady=10, expand='True')
        reset_vxm.pack(padx=20, pady=10, expand='True')
        reset_button.pack(padx=20, pady=10, expand='True')

        tooltip1 = Tooltip(self.blade_radius_entry, "This value should be the distance from the center of the blade hub\nto the tip of the blade. Measure before testing.")
        tooltip2 = Tooltip(self.microphone_2_hub_entry, "This value should be the distance from the center of the blade hub\nto the center of the bullet mic. Measure before testing.")
        tooltip3 = Tooltip(self.target_thrust, "This value is the amonut of thrust you'd like to use to spin the blade. Default thrust value is 5 lbs.")
        tooltip4 = Tooltip(radiobutton1, "If the user would like to move the mic to a specified r/R value location on the vxm traverse, select this.\nThis value is often times determined after pressing the no button first.")
        tooltip5 = Tooltip(radiobutton2, "This would increment the microphone along the traverse over certain number of inches inputted by the user.\nEach incrementation would collect data to show users the average LAeq at each increment point.")
        tooltip6 = Tooltip(button, "This button would run the program.")
        tooltip16 = Tooltip(reset_vxm, "This button resets the vxm position to the starting location\nif it were to get stuck at any point on the traverse.")
        tooltip7 = Tooltip(reset_button, "This button would reset the entire GUI and clear any tables/arrays.\nClick after each completed test run.")
        
        # ---------------------------------------------------------------------------

        # Widgets in Point Mic Measurement
        note2 = customtkinter.CTkFrame(tab_2)
        thrust = customtkinter.CTkFrame(tab_2,
                                        corner_radius=20,
                                        border_width=2,
                                        border_color='#7EA8B5')
        radius = customtkinter.CTkFrame(tab_2,
                                        corner_radius=20,
                                        border_width=2,
                                        border_color='#7EA8B5')
        mic = customtkinter.CTkFrame(tab_2,
                                    corner_radius=20,
                                    border_width=2,
                                    border_color='#7EA8B5')
        bottom_frame = customtkinter.CTkFrame(tab_2,
                                            corner_radius=10,
                                            border_width=2,
                                            border_color='#7EA8B5')
        button_frame_tab2 = customtkinter.CTkFrame(bottom_frame,
                                            fg_color='transparent')
        
        note2.pack(fill='y', padx=5, pady=5)
        thrust.pack(fill='y', padx=20, pady=20)
        radius.pack(fill='y', padx=20, pady=20)
        mic.pack(fill='y', padx=20, pady=20)
        button_frame_tab2.pack(side='bottom', padx=20, pady=20, expand='True')

        note_label2 = customtkinter.CTkLabel(note2, text='!! Change Output Socket Signal to Input-Z Weighted and 15.0 dB gain in setup tab on 2270 device !!',
                                            font=customtkinter.CTkFont('CustomTkinter', 14, 'bold'), text_color='#FF2727')
        thrust_label = customtkinter.CTkLabel(thrust, text='Enter Thrust [lbs]',
                                font=customtkinter.CTkFont('CustomTkinter', 18, 'bold'))
        self.thrust_num = customtkinter.CTkEntry(thrust, placeholder_text='')
        self.thrust_num.insert(0, initial_values.get('thrust_num', ''))

        radius_label = customtkinter.CTkLabel(radius, text='Enter Blade Radius [in]',
                                font=customtkinter.CTkFont('CustomTkinter', 18, 'bold'))
        self.radius_num = customtkinter.CTkEntry(radius, placeholder_text='')
        self.radius_num.insert(0, initial_values.get('radius_num', ''))

        mic_label = customtkinter.CTkLabel(mic, text='Move Microphone to Specific r/R:',
                                font=customtkinter.CTkFont('CustomTkinter', 18, 'bold'))
        self.rOR = customtkinter.CTkEntry(mic, placeholder_text='')
        self.rOR.insert(0, initial_values.get('rOR', ''))

        reset_button_tab2 = customtkinter.CTkButton(tab_2, text='RESET', anchor='center',
                                                    font=customtkinter.CTkFont('CustomTkinter', 14, 'bold'), fg_color='#7EA8B5',
                                                    corner_radius = 20, hover_color='#F83613', command=self.button_reset)
        
        reset_vxm_tab2 = customtkinter.CTkButton(tab_2, text='RESET MIC LOCATION', anchor='center',
                                                    font=customtkinter.CTkFont('CustomTkinter', 14, 'bold'), fg_color='#7EA8B5',
                                                    corner_radius = 20, hover_color='#F83613',command=self.button_reset_vxm)

        button_tab2 = customtkinter.CTkButton(tab_2, text='RUN', anchor='center', 
                                            font=customtkinter.CTkFont('CustomTkinter', 14, 'bold'), fg_color='#7EA8B5',
                                            corner_radius = 20, hover_color='#7DC445', command=self.point_mic_meas)

        note_label2.pack(padx=10, pady=2)

        thrust_label.pack(padx=20, pady=5)
        self.thrust_num.pack(padx=20, pady=10)

        radius_label.pack(padx=20, pady=5)
        self.radius_num.pack(padx=20, pady=10)

        mic_label.pack(padx=20, pady=5)
        self.rOR.pack(padx=20, pady=10)

        button_tab2.pack(padx=20, pady=10)
        reset_vxm_tab2.pack(padx=20, pady=10)
        reset_button_tab2.pack(padx=20, pady=10)

        tooltip8 = Tooltip(self.thrust_num, "This value is the amonut of thrust you'd like to use to spin the blade. Default thrust value is 5 lbs.")
        tooltip9 = Tooltip(self.radius_num, "This value should be the distance from the center of the blade hub\nto the tip of the blade. Measure before testing.")
        tooltip10 = Tooltip(self.rOR, "If the user would like to move the mic to a specified r/R value location on the vxm traverse.\nThis value is often times determined after running the PROPELLER TRAVERSE program.")
        tooltip11 = Tooltip(button_tab2, "This button would run the program.")
        tooltip17 = Tooltip(reset_vxm_tab2, "This button resets the vxm position to the starting location\nif it were to get stuck at any point on the traverse.")
        tooltip12 = Tooltip(reset_button_tab2, "This button would reset the entire GUI and clear any tables/arrays.\nClick after each completed test run.")

        # ---------------------------------------------------------------------------

        # Widgets for Auto RPM Sweep
        note3 = customtkinter.CTkFrame(tab_3)
        m_rpm = customtkinter.CTkFrame(tab_3,
                                        corner_radius=20,
                                        border_width=2,
                                        border_color='#7EA8B5')
        t_rpm = customtkinter.CTkFrame(tab_3,
                                        corner_radius=20,
                                        border_width=2,
                                        border_color='#7EA8B5')
        bottom_frame_tab3 = customtkinter.CTkFrame(tab_3,
                                                corner_radius=10,
                                                border_width=2,
                                                border_color='#7EA8B5')
        button_frame_tab3 = customtkinter.CTkFrame(bottom_frame_tab3,
                                                  fg_color='transparent')
        
        note3.pack(fill='y', padx=5, pady=5)
        m_rpm.pack(fill='y', padx=20, pady=20)
        t_rpm.pack(fill='y', padx=20, pady=20)
        button_frame.pack(side='bottom', padx=20, pady=20)

        note_label3 = customtkinter.CTkLabel(note3, text='!! Change Output Socket Signal to Input-Z Weighted and 15.0 dB gain in setup tab on 2270 device !!',
                                    font=customtkinter.CTkFont('CustomTkinter', 14, 'bold'), text_color='#FF2727')

        min_RPM_label = customtkinter.CTkLabel(m_rpm, text='Enter Minimum Target RPM:',
                                font=customtkinter.CTkFont('CustomTkinter', 18, 'bold'))
        self.min_RPM_num = customtkinter.CTkEntry(m_rpm, placeholder_text='')
        self.min_RPM_num.insert(0, initial_values.get('min_RPM_num', ''))

        RPM_label = customtkinter.CTkLabel(t_rpm, text='Enter Maximum Target RPM:',
                                font=customtkinter.CTkFont('CustomTkinter', 18, 'bold'))
        self.RPM_num = customtkinter.CTkEntry(t_rpm, placeholder_text='')
        self.RPM_num.insert(0, initial_values.get('RPM_num', ''))

        button_tab3 = customtkinter.CTkButton(tab_3, text='RUN', anchor='center', 
                                            font=customtkinter.CTkFont('CustomTkinter', 14, 'bold'), fg_color='#7EA8B5',
                                            corner_radius = 20, hover_color='#7DC445', command=self.auto_rpm_sweep)
        
        reset_button_tab3 = customtkinter.CTkButton(tab_3, text='RESET', anchor='center',
                                                    font=customtkinter.CTkFont('CustomTkinter', 14, 'bold'), fg_color='#7EA8B5',
                                                    corner_radius = 20, hover_color='#F83613', command=self.button_reset)
        
        reset_vxm_tab3 = customtkinter.CTkButton(tab_3, text='RESET MIC LOCATION', anchor='center',
                                                    font=customtkinter.CTkFont('CustomTkinter', 14, 'bold'), fg_color='#7EA8B5',
                                                    corner_radius = 20, hover_color='#F83613',command=self.button_reset_vxm)


        note_label3.pack(padx=10, pady=2)
        min_RPM_label.pack(padx=20, pady=5)
        self.min_RPM_num.pack(padx=20, pady=10)
        RPM_label.pack(padx=20, pady=5)
        self.RPM_num.pack(padx=20, pady=10)

        button_tab3.pack(padx=20, pady=5)
        reset_vxm_tab3.pack(padx=20, pady=5)
        reset_button_tab3.pack(padx=20, pady=5)

        tooltip13 = Tooltip(self.RPM_num, "Set the target max RPM for program to slowly collect data from motor startup to every RPM leading up to the target.")
        tooltip14 = Tooltip(button_tab3, "This button would run the program.")
        tooltip18 = Tooltip(reset_vxm_tab3, "This button resets the vxm position to the starting location\nif it were to get stuck at any point on the traverse.")
        tooltip15 = Tooltip(reset_button_tab3, "This button would reset the entire GUI and clear any tables/arrays.\nClick after each completed test run.")

        toplevel_window = None


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
    
    def button_reset_vxm(self):
        # moves the traverse back to the starting location (limit-zero position)
        vxm.write(b'C,I1M-0,R\n')
        # clear memory and terminate connection
        vxm.write(b'C,Q\n')

    def button_click(self):
        # Propeller radius "R", [in]
        if self.blade_radius_entry.get() == '':
            CTkMessagebox(title='Error', message='Please enter radius [in]')
        elif self.blade_radius_entry.get().replace('.','',1).isnumeric() == False:
            CTkMessagebox(title='Error', message='Please enter a numerical radius value [in]')
        
        else:
            R = float(self.blade_radius_entry.get())
        
            # Traverse start location "X0", [in]
            if self.microphone_2_hub_entry.get() == '':
                CTkMessagebox(title='Error', message='Please enter distance [in]')
            elif self.microphone_2_hub_entry.get().replace('.','',1).isnumeric() == False:
                CTkMessagebox(title='Error', message='Please enter a numerical distance [in]')
            else:
                X0 = float(self.microphone_2_hub_entry.get())
        

                if self.target_thrust.get() == '':
                    CTkMessagebox(title='Error', message='Please enter thrust [lbs]')
                elif self.target_thrust.get().replace('.','',1).isnumeric() == False:
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
                            
                            roR = float(roR_input.get_input())

                            X_pm = (roR * R) - X0

                            # Sets new traverse distance-per-move "X_pm" [in] if user inputted anything
                            print("r/R Distance:", roR)
                            
                            # Propeller/Motor Startup
                            throttle_init = 1120
                            u.sendto(str(throttle_init).encode(), (my_IP, recv_port))
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
                                time.sleep(5) # puses the program for a bit before taking measurements

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

                                    results_table.append({'Time, [s]': TIME, 'r/R': roR, 'SPL no background: [dB]': SPL_no_back, 'SD SPL no background': SPL_no_back_stdev, 
                                                          'Mean SPL, [dB]': SPL_mean, 'SD SPL': SPL_stdev, 'Mean Thrust, [lbf]': THRUST_mean, 'SD Thrust': THRUST_stdev, 
                                                          'Mean Torque [N*m]': TORQUE_mean, 'SD Torque': TORQUE_stdev, 'Mean Voltage [V]': VOLTAGE_mean,
                                                          'SD Votlage': VOLTAGE_stdev, 'Mean RPM': RPM_mean, 'SD RPM': RPM_stdev, 'Mean Current [Amp]': CURRENT_mean,
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
                            # clear memory and terminate connection
                            vxm.write(b'C,Q\n')

                            u.close()
                            
                            file_label = main_path + ' SPL_Traverse ' + datetime.now().strftime("%B %d %Y %H_%M_%S") + '.csv'
                            df = pd.DataFrame(results_table)
                            df.to_csv(file_label, index=False)
                            
                        elif self.radio_var.get() == 2:
                            # Code for incrementing the microphone...
                            
                            # Calling the function to measure the background noise:
                            background_noise, background_noise_stdev = self.measure_background_noise()

                            # Asking what increments the user wants to move the mic by
                            increment_input = customtkinter.CTkInputDialog(text="Enter value to increment [in] (Please enter 0.1 for default incrementation)",
                                                                    title="Increment Value")
                            
                            increment = float(increment_input.get_input())
                            
                            messagebox.showinfo(title='Notice', message=f'Mic will increment by {increment} inches.')
                            
                            # move_distance = 0.1

                            # Propeller/Motor Startup
                            throttle_init = 1120
                            u.sendto(str(throttle_init).encode(), (my_IP, recv_port))
                            time.sleep(1)  # wait to spin up
                            control2Thrust(self.target_thrust.get(), 0.1, 200, u, my_IP, recv_port, kill)

                            # Sets new traverse distance-per-move "X_pm" [in] if user inputted anything
                            X_pm = increment

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

                                results_table.append({'Time, [s]': TIME, 'r/R': roR, ' Mean SPL no background [dB]': SPL_no_back, 'SD SPL no background': SPL_no_back_stdev, 
                                                      'Mean SPL, [dB]': SPL_mean, 'SD SPL': SPL_stdev, 'Mean Thrust, [lbf]': THRUST_mean, 'SD Thrust': THRUST_stdev, 
                                                      'Mean Torque [N*m]': TORQUE_mean, 'SD Torque': TORQUE_stdev, 'Mean Voltage [V]': VOLTAGE_mean,
                                                      'SD Votlage': VOLTAGE_stdev, 'Mean RPM': RPM_mean, 'SD RPM': RPM_stdev, 'Mean Current [Amp]': CURRENT_mean,
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
                            # clear memory and terminate connection
                            vxm.write(b'C,Q\n')

                            u.close()

                            # send results to a file
                            file_label = main_path + ' SPL_Traverse ' + datetime.now().strftime("%B %d %Y %H_%M_%S") + '.csv'
                            df = pd.DataFrame(results_table)
                            df.to_csv(file_label, index=False)

    def point_mic_meas(self):
        global output_dir
        if self.thrust_num.get() == '':
            CTkMessagebox(title='Error', message='Please enter thrust [lbs]')
        elif self.thrust_num.get().replace('.','',1).isnumeric() == False:
            CTkMessagebox(title='Error', message='Please enter a numerical thrust value [lbs]')
        else:
            thrust = float(self.thrust_num.get())

            if thrust < 0 or thrust > 15:
                CTkMessagebox(title='Error', message='Thrust value must be between 0 and 15 lbs')

            else:
                if self.radius_num.get() == '':
                    CTkMessagebox(title='Error', message='Please enter a radius [in]')
                elif self.radius_num.get().replace('.','',1).isnumeric() == False:
                    CTkMessagebox(title='Error', message='Please enter a numerical radius value [in]')
                else:
                    radius = float(self.radius_num.get())

                    if self.rOR.get() == '':
                        CTkMessagebox(title='Error', message='Please enter rOR value (between 0 and 1.2)')
                    elif self.rOR.get().replace('.','',1).isnumeric() == False:
                        CTkMessagebox(title='Error', message='Please enter a numerical rOR value')
                    else:
                        rOR = float(self.rOR.get())

                    X_pm = (rOR * radius) - X0
                    # Sets new traverse distance-per-move "X_pm" [in] if user inputted anything
                    print("r/R Distance:", rOR)

                    # Propeller/Motor Startup
                    throttle_init = 1120
                    u.sendto(str(throttle_init).encode(), (my_IP, recv_port))
                    # time.sleep(3)
                    # throttle = 1160  # begins to spin blades WITH THE KDE 330 KV MOTOR AND FLAME ESC INSTALLED
                    # u.sendto(str(throttle).encode(), (my_IP, recv_port))
                    time.sleep(1)  # wait to spin up
                    control2Thrust(self.thrust_num.get(), 0.1, 200, u, my_IP, recv_port, kill)

                    no_of_moves = 1 # since user only wants to test in one location, there will only be one move
                    step_resolution = 0.0050 * (1 / 25.4)  # [mm/step] --> [in/step]
                    nsteps = np.ceil(X_pm / step_resolution) # sets new value to nsteps based on new X_pm. steps_revolution remains constant
                    # placed this here instead of end in order to allow the microphone to move to the location at the begging instead of waiting for increments
                    vxm_value = f'C,I1M{nsteps},R'
                    vxm.write(vxm_value.encode('utf-8'))

                    for time_hold in range(1,2):
                        print('Holding for ', time_hold, ' of ', len(range(1,3)))
                        control2Thrust(self.thrust_num.get(), 0.05, 100, u, my_IP, recv_port, kill)
                        # take measurements for desired sample length -------------------------
                        u.sendto(b"read", (my_IP, recv_port))  # writing the "read" string to the JS requests sensor values
                        message, _ = u.recvfrom(10240)  # reading the requested sensor values
                        tyto_data = json.loads(message.decode('latin1'))
                        t0_meas = tyto_data['time']['displayValue']
                        # Setup and Read from the DAQ
                        with nidaqmx.Task() as task:
                            # Adjust the terminal configuration based on the microphone
                            if Mic_Name in ['usr_A', 'usr_B']:
                                terminal_config = TerminalConfiguration.DIFF
                            else:  # Assuming GRAS microphone or others using RSE configuration
                                terminal_config = TerminalConfiguration.RSE
                            
                            task.ai_channels.add_ai_voltage_chan(f"{Card_ID}/{Channel_ID}", 
                                                                terminal_config=terminal_config)
                            task.timing.cfg_samp_clk_timing(rate=f_samp, 
                                                            sample_mode=AcquisitionType.CONTINUOUS, 
                                                            samps_per_chan=L_samp * f_samp)
                            
                            # Countdown before starting the measurement
                            print("Taking measurement in:")
                            for i in range(3, 0, -1):
                                print(f"{i}...")
                                time.sleep(1)
                            print("Start")
                            time.sleep(2)
                            time.sleep(10)
                            print("Data Measurement Acquisition Completed")
                            
                            data = task.read(number_of_samples_per_channel=L_samp * f_samp)

                        # Calculating the timestamp for each sample
                        t = np.linspace(0, L_samp, num=f_samp * L_samp, endpoint=False)

                        # Assuming 'data' is a list of voltage readings
                        voltage = np.array(data) / (10 ** (gain / 20))  # Correcting the signal based on the gain
                        pressure = voltage / mic_sens  # Converting voltage to pressure

                        # Apply Z-weighting (just pressure directly)
                        z_weighted_pressure = pressure

                        # Calculate FFT for z_weighted
                        z_n = len(z_weighted_pressure)
                        yf =fft(z_weighted_pressure)
                        xf = fftfreq(z_n, 1 / f_samp)

                        # Ensure only positive half of the spectrum is taken, assuming pressure signal is real
                        xf = xf[:z_n//2]
                        yf = np.abs(yf[:z_n//2])

                        # Compute the Z-weighted amplitude spectrum in dB
                        Z_amp_spec = 20 * np.log10(yf / P_ref)
                        
                        # Storing Frequency Spectrum results
                        f_bins = xf[:len(Z_amp_spec)]

                        # Applying A Frequency Weighting Filter
                        weight_filt = waveform_analysis.A_weight(pressure, f_samp)
                        # print(weight_filt)

                        # Compute total SPL
                        tau = 0.125
                        itr = 0
                        t_settle_idx = 7 * tau * f_samp

                        # Initialize list to store LAF values and their corresponding time stamps
                        LAF = []
                        t_LAF = []

                        # Calculate position indexes based on linspace and iterate through them
                        for pos in np.ceil(np.linspace(t_settle_idx, len(t) - 1, 100)).astype(int):
                            P_4_calc = np.sqrt(np.mean(weight_filt[0:pos + 1] ** 2))  # RMS calculation
                            t_4_calc = t[0:pos + 1]

                            # ANSI S1.4 procedure
                            terms = ((P_4_calc ** 2) / (P_ref ** 2)) * (np.exp(-1 * (t[pos] - t_4_calc) / tau))
                            I_SPL = simpson(y=terms, x=t_4_calc)  # Use simps for numerical integration, similar to trapz in MATLAB
                            
                            # Ignore DeprecationWarning for simps
                            warnings.filterwarnings("ignore", category=DeprecationWarning, module="scipy.integrate")
                            
                            LAF_value = 10 * np.log10(1 / tau * I_SPL)
                            
                            # Store the computed LAF value and the corresponding time
                            LAF.append(LAF_value)
                            t_LAF.append(t[pos])
                            #LAeq & LZeq
                            
                        # The LAeq average over the duration
                        L_avg = 10*np.log10((1/len(LAF)) * np.sum(10**(0.1*np.array(LAF))))
                        print(f"The average LAF over the measurement duration is: {L_avg:.2f} dB")

                        # The LZeq average over the duration
                        LZeq = 10 * np.log10(np.mean(z_weighted_pressure ** 2) / P_ref ** 2)
                        print(f"The average LZF over the measurement duration is: {LZeq:.2f} dB")

                        # Do frequency analysis in pressure units:
                        P_fft = fft(weight_filt)

                        # Calculate the amplitude spectrum
                        P_amp_spec2 = np.sqrt(np.real(P_fft)**2 + np.imag(P_fft)**2) / len(weight_filt)

                        # Adjust the amplitude spectrum for single-sided FFT display
                        P_amp_spec1 = P_amp_spec2[:len(weight_filt)//2 + 1]
                        P_amp_spec1[1:-1] = 2*P_amp_spec1[1:-1]  # Double the amplitudes, except for the first and last points

                        # Calculate the frequency bins
                        f = np.linspace(0, f_samp/2, len(P_amp_spec1))

                        # Convert amplitude spectrum to dB SPL
                        SPL_spec = 20 * np.log10(P_amp_spec1 / P_ref)

                        # Shutdown Tasks
                        print("Spectrum Collection Complete... Shutting down...\n")
                        # kill the Tyto-JS (shuts off motor)
                        throttle_down = np.linspace(tyto_data['escA']['displayValue'], 1000,10)  # make sure the ESC A vs B side is correct here!!!
                        for throttle in throttle_down:
                            u.sendto(str(throttle).encode(), (my_IP, recv_port))
                            time.sleep(0.5)
                        u.sendto(b"kill", (my_IP, recv_port))
                        # move the traverse back to the starting location (limit-zero position)
                        vxm.write(b'C,I1M-0,R\n')
                        # clear memory and terminate connection
                        vxm.write(b'C,Q\n')

                        u.close()

                        # Define the output directory and file name
                        if not os.path.exists(output_dir):
                            os.makedirs(output_dir)  # Ensure the directory exists
                        file_label = os.path.join(output_dir, f'Point Spectrum 6ft-135deg-5lbf {datetime.now().strftime("%Y-%m-%d %H_%M_%S")}.xlsx')

                        min_length = min(len(f), len(SPL_spec), len(f_bins), len(Z_amp_spec))
                        f = f[:min_length]
                        SPL_spec = SPL_spec[:min_length]
                        f_bins = f_bins[:min_length]
                        Z_amp_spec = Z_amp_spec[:min_length]

                        # Create DataFrames for the results
                        results_table_A = pd.DataFrame({
                            'Frequencies [Hz]': f,
                            'Amplitudes [dB LAF]': SPL_spec,
                            'Frequencies [Hz]': f_bins,
                            'Amplitudes [dB LZF]': Z_amp_spec
                        })
                        results_table_B = pd.DataFrame({
                            'LAeq [dB]': [L_avg],
                            'LZeq [dB]': [LZeq],
                            'DAQ Sample Frequency [Hz]': [f_samp]
                        })

                        # Write the data to an Excel file
                        with ExcelWriter(file_label) as writer:
                            results_table_A.to_excel(writer, sheet_name='Spectrum', index=False)
                            results_table_B.to_excel(writer, sheet_name='Summary', index=False)

                        print(f"Results saved to {file_label}")

                        # Define plot save path
                        plot_output_dir = 'C:\\Users\\mykoh\\OneDrive\\Documents\\BIP\\Results\\FFT\\FFT Figures'
                        if not os.path.exists(plot_output_dir):
                            os.makedirs(plot_output_dir)

                        # Define file names for the plots
                        plot_filename_A = os.path.join(plot_output_dir, f'Frequency Spectrum A-Weighted {datetime.now().strftime("%Y-%m-%d %H_%M_%S")}.png')
                        plot_filename_Z = os.path.join(plot_output_dir, f'Frequency Spectrum Z-Weighted {datetime.now().strftime("%Y-%m-%d %H_%M_%S")}.png')

                        # Plotting the A amplitude spectrum
                        plt.figure(figsize=(10, 6))
                        plt.semilogx(f, SPL_spec, '-b')
                        plt.title('Frequency Spectrum (A-Weighted) - SPL')  # Adjusted from the MATLAB title for clarity
                        plt.xlabel('Frequency [Hz]', fontsize=14)
                        plt.ylabel('Amplitude [dB SPL]', fontsize=14)
                        plt.xlim([1, 20000])
                        plt.ylim([-40, 100])
                        plt.grid(which='both', linestyle='--', linewidth=0.5)
                        plt.text(1000, -35, f'LAeq Average: {L_avg:.2f} dB', fontsize=12, color='red', fontweight='bold')
                        plt.savefig(plot_filename_A)

                        # Plotting the Z frequency spectrum
                        plt.figure(figsize=(10, 6))
                        plt.plot(xf, 20 * np.log10(yf), '-b')  # Convert amplitude to dB
                        plt.title('Frequency Spectrum (Z-weighted) - SPL')
                        plt.xlabel('Frequency [Hz]', fontsize=14)
                        plt.ylabel('Amplitude [dB SPL]', fontsize=14)
                        plt.xscale('log')
                        plt.grid(which='both', linestyle='--', linewidth=0.5)
                        plt.text(1000, -35, f'LZeq Average: {LZeq:.2f} dB', fontsize=12, color='red', fontweight='bold')
                        plt.savefig(plot_filename_Z)
                        
                        print(f"A-weighted plot saved to {plot_filename_A} and Z-weighted plot saved to {plot_filename_Z}")

                        # Display all open plots
                        plt.show()


    def auto_rpm_sweep(self):
        if self.min_RPM_num.get() == '':
            CTkMessagebox(title='Error', message='Please enter minimum target RPM')
        elif self.min_RPM_num.get().replace('.','',1).isnumeric() == False:
            CTkMessagebox(title='Error', message='Please enter a whole numerical RPM value')
        if self.RPM_num.get() == '':
            CTkMessagebox(title='Error', message='Please enter maximum target RPM')
        elif self.RPM_num.get().replace('.','',1).isnumeric() == False:
            CTkMessagebox(title='Error', message='Please enter a whole numerical RPM value')
        else:
            target_RPM = float(self.RPM_num.get())
            min_target_RPM = float(self.min_RPM_num.get())

            if min_target_RPM <= 0 or min_target_RPM >= 2500:
                CTkMessagebox(title='Error', message='Please enter a valid minimum RPM between 1 and 2500 RPM.')
            elif min_target_RPM >= target_RPM:
                CTkMessagebox(title='Error', message='Minimum target RPM should be lower than the maximum target RPM.')

            if target_RPM <= 0 or target_RPM >= 4000:
                CTkMessagebox(title='Error', message='Thrust value must be between 1 and 4000 RPM')
            elif target_RPM <= min_target_RPM:
                CTkMessagebox(title='Error', message='Maximum target RPM should be higher than the minimum target RPM.')

            else:
                # Propeller/Motor Startup
                throttle_start = 1000
                u.sendto(str(throttle_start).encode(), (my_IP, recv_port))
                time.sleep(5)  # wait to spin up

                throttle_start = 1160  # Value to start spinning the blades
                u.sendto(str(throttle_start).encode(), (my_IP, recv_port))
                time.sleep(3)  # Wait for the motor to spin up


                control2rpm(target_RPM, 20, 200, u, my_IP, recv_port, b)

                SweepRPMs = np.linspace(min_target_RPM, target_RPM, 25)


                for rpm in SweepRPMs:
                    control2rpm(rpm, 10, 200, u, my_IP, recv_port, b)
                    # Send control command (This part should ideally be in your control function, but we're keeping it inline as per request)
                    control_command = json.dumps({"command": "set_rpm", "value": rpm})
                    u.sendto(control_command.encode(), (my_IP, recv_port))

                    # Requesting data
                    read_command = "read"
                    u.sendto(read_command.encode(), (my_IP, recv_port))
                    message, _ = u.recvfrom(4096)  # sAdjust buffer size as needed
                    decoded_data = message.decode('latin1')

                    try:
                        tytoDATA = json.loads(decoded_data)
                        t0_meas = tytoDATA["time"]["displayValue"]  # Initial measurement time
                    except json.JSONDecodeError:
                        print("Received non-JSON data:", decoded_data)

                    # Initialize measurement variables
                    t_meas = 0
                    itr_meas = 0
                    meas_collection = []  # Collect data for this RPM

                    thrusts, torques, voltages, currents, RPMs, mech_powers, elec_powers, motor_effs, prop_Mech_effs, prop_Elec_effs, times = ([] for i in range(11))

                    while t_meas <= L_samp_tab3:
                        # Assuming you have a similar way to repeatedly collect data
                        u.sendto(read_command.encode(), (my_IP, recv_port))
                        message, _ = u.recvfrom(4096)
                        current_data = message.decode('latin1')
                        try:
                            tyto_data = json.loads(current_data)
                            # Append the current data to the meas_collection list
                            meas_collection.append(tyto_data)
                        except json.JSONDecodeError:
                            print("Received non-JSON data:", tyto_data)
                        # Exit the function or handle the error as appropriate
                        # Append the current data to the meas_collection list
                        # Assuming 'time' is a direct value representing seconds for simplicity
                        
                        current_time = tyto_data["time"]["displayValue"]
                        thrust = tyto_data['thrust']['displayValue']
                        torque = tyto_data['torque']['displayValue']
                        voltage = tyto_data['voltage']['displayValue']
                        current = tyto_data['current']['displayValue']
                        RPM = tyto_data['motorOpticalSpeed']['displayValue']
                        mech_power = tyto_data['mechanicalPower']['displayValue']
                        elec_power = tyto_data['electricalPower']['displayValue']
                        motor_eff = tyto_data['motorEfficiency']['displayValue']
                        prop_Mech_eff = tyto_data['propMechEfficiency']['displayValue']
                        prop_Elec_eff = tyto_data['propElecEfficiency']['displayValue']
                        time_tyto = tyto_data['time']['displayValue']
                        t_meas = current_time - t0_meas
                        itr_meas += 1

                        # Append new readings to their respective lists
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

                        
                    
                    # compute values to store for this position -----------------------
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

                    # After collecting data for the current RPM, process and store it in DATA
                    # The processing here depends on how you want to aggregate or use the collected data
                    # For example, appending all meas_collection for this RPM
                    results.append({'Time, [s]': TIME, 'Mean Thrust, [lbf]': THRUST_mean, 'SD Thrust': THRUST_stdev, 'Mean Torque [N*m]': TORQUE_mean,
                                    'SD Torque': TORQUE_stdev, 'Mean Voltage [V]': VOLTAGE_mean, 'SD Votlage': VOLTAGE_stdev, 'Mean RPM': RPM_mean, 
                                    'SD RPM': RPM_stdev, 'Mean Current [Amp]': CURRENT_mean, 'SD Current': CURRENT_stdev, 'Mech. Power, [W]': POWER_mean, 
                                    'SD Power': POWER_stdev, 'Elec. Power, [W]': ePOWER_mean,'SD Elec Power': ePOWER_stdev, 'Motor Eff.': motor_eff, 
                                    'Propeller Mech. Eff.': prop_Mech_eff, 'Propeller Elec. Eff.': prop_Elec_eff, 'n Samples': NSAMP})

                # Saving results to a CSV file
                df = pd.DataFrame(results)
                # df.columns = ['Time', 'Mean Thrust', 'SD Thrust', 'Mean Torque', 'SD Torque', 'Mean RPM', 'SD RPM', 'Mech. Power', 'SD Mech. Power', 'Current', 'SD Current', 'Voltage', 'SD Voltage', 'Elec. Power', 'SD Elec. Power', 'Motor Efficiency', 'SD Motor Eff', 'N Samples']
                file_label = f"{main_path_tab3}/RPM_Sweep_{datetime.now().strftime('%B %d %Y %H_%M_%S')}.csv"
                df.to_csv(file_label, index=False)
                    
                # *** step down for higher RPM? ***
                # kill the Tyto-JS (shuts off motor)
                print("RPM Sweep Complete... Shutting down...\n")
                throttle_down = np.linspace(tyto_data['escA']['displayValue'], 1000,10)  # make sure the ESC A vs B side is correct here!!!
                for throttle in throttle_down:
                    u.sendto(str(throttle).encode(), (my_IP, recv_port))
                    time.sleep(0.5)
                u.sendto(b"kill", (my_IP, recv_port))
                u.close()

    def button_reset(self):
        global file_label, app, R, X_pm, X0, L_sample_default, mic_name, DAQ_ID, Channel_ID, f_sample, A
        global hostname, my_IP, tx_port, main_path, kill, results_table, u, vxm, recv_port

        current_values = {
        'blade_radius_entry': self.blade_radius_entry.get(),
        'microphone_2_hub_entry': self.microphone_2_hub_entry.get(),
        'target_thrust': self.target_thrust.get(),
        'thrust_num': self.thrust_num.get(),
        'radius_num': self.radius_num.get(),
        'rOR': self.rOR.get(),
        'min_RPM_num': self.min_RPM_num.get(),
        'RPM_num': self.RPM_num.get()
        }

        # Closes the existing socket before destroying the app
        if u:
            u.close()

        # Clears the result_table list so it doesn't keep appending to the same csv file if you hit reset
        results_table.clear()
        results.clear()

        # Destroys the existing app
        app.destroy()

        # Reinitialize the app and other variables
        initialize_app()
        app = App(initial_values=current_values)
        app.mainloop()


        # ----------------------------------------------------------------------------------------------------------


class App(customtkinter.CTk):
    def __init__(self, initial_values=None):
        super().__init__()
        self.title('Athule Static Test Stand')
        self.geometry('900x780')

        if initial_values is None:
            initial_values = {}

        self.tab_view = MyTabView(master=self, width=800, height=650, initial_values=initial_values)
        self.tab_view.pack(pady=30)


initialize_app()
app = App()
app.mainloop()