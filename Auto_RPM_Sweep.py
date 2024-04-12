import socket
import json
import pandas as pd
import numpy as np
import time
from tkinter import Tk, Button
import customtkinter as ctk
from customtkinter import *
from datetime import datetime
from control2RPMv4 import control2rpmv4

L_samp = 5
SweepRPMs = np.linspace(1500, 3000, 25)
main_path = r'C:\Users\mykoh\OneDrive\Documents\BIP\Results\RPM_Sweep'
local_port = 64856
hostname = socket.gethostname()
my_IP = socket.gethostbyname(hostname)
recv_port = 55047
b = 0

u = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
u.bind((my_IP, local_port))
u.sendto(b"hello there RC Benchmark", (my_IP, recv_port))

# Propeller/Motor Startup
throttle_start = 1000
u.sendto(str(throttle_start).encode(), (my_IP, recv_port))
time.sleep(5)  # wait to spin up

throttle_start = 1160  # Value to start spinning the blades
u.sendto(str(throttle_start).encode(), (my_IP, recv_port))
time.sleep(3)  # Wait for the motor to spin up

# # Create the main window
# ctk.set_appearance_mode("System")  # Set the theme (System, Light, Dark)
# ctk.set_default_color_theme("blue")  # Set the color theme (blue, dark-blue, green)

# app = ctk.CTk()  # Create a CTk window
# app.geometry("307x200")  # Set the window size
# app.title("Control Window")  # Set the window title

# # Create a button
# b = ctk.CTkButton(app, text="KILL (During Thrust Manipulation)", command=control2rpmv4.on_kill_button_click)
# b.pack(pady=20, padx=10)  # Add some padding to center the button

# app.after(3000, b.pack)  # Wait for 3 seconds before showing the button

# app.mainloop()

target_RPM = 2000
control2rpmv4(target_RPM, 20, 200, u, my_IP, recv_port, b)

results = []

for rpm in SweepRPMs:
    control2rpmv4(rpm, 10, 200, u, my_IP, recv_port, b)
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

    while t_meas <= L_samp:
        # Assuming you have a similar way to repeatedly collect data
        u.sendto(read_command.encode(), (my_IP, recv_port))
        message, _ = u.recvfrom(4096)
        current_data = message.decode('latin1')
        try:
            tyto_data = json.loads(current_data)
            # Append the current data to the meas_collection list
            meas_collection.append(tyto_data)
            # Assuming 'time' is a direct value representing seconds for simplicity
            current_time = tyto_data["time"]["displayValue"]
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
        except json.JSONDecodeError:
            print("Received non-JSON data:", tyto_data)
          # Exit the function or handle the error as appropriate
        # # Append the current data to the meas_collection list
    
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
    results.append({'Time, [s]': TIME, 'Mean Thrust, [lbf]': THRUST_mean, 'SD Thrust': THRUST_stdev, 'Mean Torque': TORQUE_mean,
                    'SD Torque': TORQUE_stdev, 'Mean Voltage': VOLTAGE_mean, 'SD Votlage': VOLTAGE_stdev, 'Mean RPM': RPM_mean, 
                    'SD RPM': RPM_stdev, 'Mean Current': CURRENT_mean, 'SD Current': CURRENT_stdev, 'Mech. Power, [W]': POWER_mean, 
                    'SD Power': POWER_stdev, 'Elec. Power, [W]': ePOWER_mean,'SD Elec Power': ePOWER_stdev, 'Motor Eff.': motor_eff, 
                    'Propeller Mech. Eff.': prop_Mech_eff, 'Propeller Elec. Eff.': prop_Elec_eff, 'n Samples': NSAMP})
    
    # Saving results to a CSV file
    df = pd.DataFrame(results)
    # df.columns = ['Time', 'Mean Thrust', 'SD Thrust', 'Mean Torque', 'SD Torque', 'Mean RPM', 'SD RPM', 'Mech. Power', 'SD Mech. Power', 'Current', 'SD Current', 'Voltage', 'SD Voltage', 'Elec. Power', 'SD Elec. Power', 'Motor Efficiency', 'SD Motor Eff', 'N Samples']
    file_label = f"{main_path}/RPM_Sweep_{datetime.now().strftime('%B %d %Y %H_%M_%S')}.csv"
    df.to_csv(file_label, index=False)

print("Traverse Complete... Shutting down...\n")
u.close()