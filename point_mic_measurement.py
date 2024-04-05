import nidaqmx
import numpy as np
from scipy.signal import iirfilter, lfilter
from scipy.fft import fft
from scipy.integrate import simpson
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
import time
import nidaqmx
from nidaqmx.constants import TerminalConfiguration, AcquisitionType
import waveform_analysis
import os
from pandas import ExcelWriter
import openpyxl
import warnings
import customtkinter
from customtkinter import *
from CTkMessagebox import CTkMessagebox
import tkinter
from tkinter import messagebox
import socket
import serial
from serial import Serial
from control2Thrust import control2Thrust
import json

customtkinter.set_appearance_mode("System")  # Modes: "System" (standard), "Dark", "Light"
customtkinter.set_default_color_theme("blue")  # Themes: "blue" (standard), "green", "dark-blue"

# Constants and Microphone Parameters
Card_ID = 'cDAQ1Mod8'
Channel_ID = 'ai1'
f_samp = 50000  # Sample frequency in Hz
L_samp = 10  # Sample duration in seconds
P_ref = 20e-6  # Reference pressure in Pascals

# Allows program to grab Host's IP Address
hostname = socket.gethostname()
my_IP = socket.gethostbyname(hostname)

u = None
vxm = None
recv_port = 55047
kill = 0
X0 = 3.75
R = 10.75

# Send port value
tx_port = 64856

# Define microphone sensitivity and gain based on Mic_Name
mic_params = {
    'usr_A': {'mic_sens': 1.56e-3, 'gain': 15},
    'usr_B': {'mic_sens': 1.575e-3, 'gain': 20},
    'GRAS': {'mic_sens': 12e-3, 'gain': 1}
}

Mic_Name = 'usr_A'  # or 'usr_B', 'GRAS', as needed
mic_sens = mic_params[Mic_Name]['mic_sens']
gain = mic_params[Mic_Name]['gain']


def initialize_app():
    global Card_ID, Channel_ID, f_samp, L_samp, P_ref, mic_params, Mic_Name, mic_sens, gain,u, vxm, recv_port
    global hostname, my_IP, tx_port, kill, X0

    u = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    u.bind((my_IP, tx_port))
    recv_port = 55047
    u.sendto(b"hello there RC Benchmark", (my_IP, recv_port))

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

        # Configure window
        self.title("Athule Point Mic Measurement")
        self.geometry('380x380')
        self.resizable(width=True,height=True)

        # make frames
        self.thrust = customtkinter.CTkFrame(master=self,
                    corner_radius=20,
                    border_width=2,
                    border_color='#7EA8B5')
        self.mic = customtkinter.CTkFrame(master=self,
                    corner_radius=20,
                    border_width=2,
                    border_color='#7EA8B5')
        self.bottom_frame = customtkinter.CTkFrame(master=self,
                                                corner_radius=10,
                                                border_width=2,
                                                border_color='#7EA8B5')
        self.button_frame = customtkinter.CTkFrame(self.bottom_frame,
                                                  fg_color='transparent')
        

        # pack the frames
        self.thrust.pack(fill='y', padx=20, pady=20, expand='True')
        self.mic.pack(fill='y', padx=20, pady=20, expand='True')
        self.button_frame.pack(side='bottom', padx=20, pady=20, expand='True')


        self.thrust_label = customtkinter.CTkLabel(self.thrust, text='Enter Thrust [lbs]',
                                font=customtkinter.CTkFont('CustomTkinter', 18, 'bold'))
        self.thrust_num = customtkinter.CTkEntry(self.thrust, placeholder_text='')

        self.mic_label = customtkinter.CTkLabel(self.mic, text='Move Microphone to Specific r/R:',
                                font=customtkinter.CTkFont('CustomTkinter', 18, 'bold'))
        self.rOR = customtkinter.CTkEntry(self.mic, placeholder_text='')

        self.reset_button = customtkinter.CTkButton(self, text='RESET', anchor='center',
                                                    font=customtkinter.CTkFont('CustomTkinter', 14, 'bold'), fg_color='#7EA8B5',
                                                    corner_radius = 20, hover_color='#F83613', command=self.button_reset)

        self.button = customtkinter.CTkButton(self, text='RUN', anchor='center', 
                                            font=customtkinter.CTkFont('CustomTkinter', 14, 'bold'), fg_color='#7EA8B5',
                                            corner_radius = 20, hover_color='#7DC445', command=self.button_click)


        self.thrust_label.pack(padx=20, pady=5)
        self.thrust_num.pack(padx=20, pady=10)

        self.mic_label.pack(padx=20, pady=5)
        self.rOR.pack(padx=20, pady=10)

        self.button.pack(padx=20, pady=5, expand='True')
        self.reset_button.pack(padx=20, pady=5, expand='True')

    def button_click(self):
        if self.thrust_num.get() == '':
            CTkMessagebox(title='Error', message='Please enter thrust [lbs]')
        elif self.thrust_num.get().isnumeric() == False:
            CTkMessagebox(title='Error', message='Please enter a numerical thrust value [lbs]')
        else:
            thrust = float(self.thrust_num.get())

            if thrust < 0 or thrust > 15:
                CTkMessagebox(title='Error', message='Thrust value must be between 0 and 15 lbs')

        if self.rOR.get() == '':
            CTkMessagebox(title='Error', message='Please enter rOR value (between 0 and 1.2)')
        elif self.rOR.get().isnumeric() == False:
            CTkMessagebox(title='Error', message='Please enter a numerical rOR value')
        else:
            rOR = float(self.rOR.get())

        X_pm = (rOR * R) - X0
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

            # Applying Frequency Weighting Filter
            weight_filt = waveform_analysis.A_weight(pressure, f_samp)
            print(weight_filt)

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

            L_avg = 10*np.log10((1/len(LAF)) * np.sum(10**(0.1*np.array(LAF))))
            print(f"The average LAF over the measurement duration is: {L_avg:.2f} dB")

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

            # Plotting the amplitude spectrum
            plt.figure(figsize=(10, 6))
            plt.semilogx(f, SPL_spec, '-b')
            plt.title('Frequency Spectrum - SPL')  # Adjusted from the MATLAB title for clarity
            plt.xlabel('Frequency [Hz]', fontsize=14)
            plt.ylabel('Amplitude [dB SPL]', fontsize=14)
            plt.xlim([1, 20000])
            plt.ylim([-40, 100])
            plt.grid(which='both', linestyle='--', linewidth=0.5)
            plt.show()

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

            # Define the output directory and file name
            output_dir = 'C:\\Users\\mykoh\\OneDrive\\Documents\\BIP\\Results\\FFT'
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)  # Ensure the directory exists
            file_label = os.path.join(output_dir, f'Point Spectrum 6ft-135deg-5lbf {datetime.now().strftime("%Y-%m-%d %H_%M_%S")}.xlsx')

            # Create DataFrames for the results
            results_table_A = pd.DataFrame({
                'Frequencies [Hz]': f,
                'Amplitudes [dB LAF]': SPL_spec
            })
            results_table_B = pd.DataFrame({
                'LAeq [dB]': [L_avg],
                'DAQ Sample Frequency [Hz]': [f_samp]
            })

            # Write the data to an Excel file
            with ExcelWriter(file_label) as writer:
                results_table_A.to_excel(writer, sheet_name='Spectrum', index=False)
                results_table_B.to_excel(writer, sheet_name='Summary', index=False)

            print(f"Results saved to {file_label}")

            

    def button_reset(self):
            global app, Card_ID, Channel_ID, f_samp, L_samp, P_ref, mic_params, Mic_Name, mic_sens, gain,u, vxm, recv_port
            global hostname, my_IP, tx_port, results_table_A, results_table_B
            
            # Closes the existing socket before destroying the app
            if u:
                u.close()

            # # Clears the result_table list so it doesn't keep appending to the same csv file if you hit reset
            # results_table_A.clear()
            # results_table_B.clear()

            # Destroys the existing app
            app.destroy()
            
            # Reinitialize the app and other variables
            initialize_app()
            app = App()
            app.mainloop()

initialize_app()
app = App()
app.mainloop()