# -------------------------------------------------------------------------
# MICHAEL HO 03/27/2024
# -------------------------------------------------------------------------
""" This script anlyzes a microphone signal to determine a value for LAeq
    (according to ANSI S1.4 1983) over the duration of the measurement. The
    script also computes an FFT-based spectrum of the audio signal.

    -The code collects data from an NI cDAQ /NI 9223 analog voltage card.
    -The mic signal is read from the output socket of the B&K Type 2270 sound
    analyzer, which features an optional output gain. (the output gain is
    commonly set between 15-45 dB to yield good dynamic range on the DAQ
    system
    -The current code features switch-case statements including mic and gain
    parameters relevent to the Athule Lab at the BRIC. """
# -------------------------------------------------------------------------

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

# Constants and Microphone Parameters
Card_ID = 'cDAQ1Mod8'
Channel_ID = 'ai0'
f_samp = 50000  # Sample frequency in Hz
L_samp = 10  # Sample duration in seconds
P_ref = 20e-6  # Reference pressure in Pascals

# Define microphone sensitivity and gain based on Mic_Name
mic_params = {
    'usr_A': {'mic_sens': 1.56e-3, 'gain': 30},
    'usr_B': {'mic_sens': 1.575e-3, 'gain': 20},
    'GRAS': {'mic_sens': 12e-3, 'gain': 1}
}

Mic_Name = 'usr_A'  # or 'usr_B', 'GRAS', as needed
mic_sens = mic_params[Mic_Name]['mic_sens']
gain = mic_params[Mic_Name]['gain']

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