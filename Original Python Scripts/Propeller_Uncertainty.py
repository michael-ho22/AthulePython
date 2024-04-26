"""
CFD Validation Script
This script utilizes data from propeller_no_kill script to perform necessary calculations for CFD simulation validation.
"""

import math
import pandas as pd
from scipy import stats
import sys
import CFD_Validation as cfd_v
import propeller_no_kill_GUI
from propeller_no_kill_GUI import file_label

# Uncertainty metrics from the 1780 Datasheet
accuracy = 0.01
hysteresis = 0.016
creep = 0.016
non_linearity = 0.01

# Statistical variables based on population data
LOC = 0.95  # Level of confidence
N = 1000  # Number of samples
v = N - 1  # Degrees of freedom

# Initialize arrays
U_systematic_measured = []
U_random_m_array = []
t_value_array = []

U_simulated_torque = []
U_systematic_simulated = []

# This Seciton will read the Excel file for test
# Allow users to input Excel files
file_path_m = file_label
sheet_name = input("Please input the sheet name to be analyzed: ")
# Read the Excel Sheets
df_m = pd.read_excel(file_path_m, sheet_name=sheet_name)

# Simulated torque file information
file_path_sim = file_label
sheet_sim = input("Please input simulated torque file sheet name to be analyzed: ")
df_sim = pd.read_excel(file_path_sim, sheet_name=sheet_sim)

# extract information from nsample column
m_nsamp = int(df_m['nsample'])
sim_nsamp = int(df_sim['nsample'])

# Extract torque arrays
measured_torque_array = df_m['Mean Torque'].to_numpy()
Sd_torque_m = df_m.at[0, 'SD Torque']  # Standard deviation of measured torque
simulated_torque_array = df_sim['Mean Torque'].to_numpy()
Sd_torque_sim = df_sim.at[0, 'SD Torque']  # Standard deviation of simulated torque

# Calculate systematic uncertainty for measured torque and simulated torque
# Calculate systematic uncertainty for each torque measurement 
for torque in measured_torque_array:
    U_systematic = math.sqrt((torque * accuracy) ** 2 +
                             (torque * hysteresis) ** 2 +
                             (torque * creep) ** 2 +
                             (torque * non_linearity) ** 2)
    U_systematic_measured.append(U_systematic)

# Calculate systematic uncertainty for each simulated torque *subject to change depending on the manufacturer specification
for torque in simulated_torque_array:
    U_systematic = math.sqrt((torque * accuracy) ** 2 +
                             (torque * hysteresis) ** 2 +
                             (torque * creep) ** 2 +
                             (torque * non_linearity) ** 2)
    U_systematic_simulated.append(U_systematic)

# for torque_array, U_systematic in zip([measured_torque_array, simulated_torque_array],
#                                        [U_systematic_measured, U_systematic_simulated]):
#     for torque in torque_array:
#         U_systematic.append(math.sqrt((torque * accuracy) ** 2 +
#                                        (torque * hysteresis) ** 2 +
#                                        (torque * creep) ** 2 +
#                                        (torque * non_linearity) ** 2))

# Calculate t-value array for measured torque uncertainty
for n in range(m_nsamp):
    v = n - 1  # degrees of freedom
    t_value = stats.t.ppf((1 + LOC) / 2, v)  # Student t-value based on LOC and degrees of freedom
    t_value_array.append(t_value)

# Calculate random uncertainty for measured torque
for t_value, Sd_torque_m in zip(t_value_array, [Sd_torque_m] * N):
    U_random_m = (t_value * Sd_torque_m) / math.sqrt(N)
    U_random_m_array.append(U_random_m)

# Calculate total uncertainty for measured torque
U_measured_torque = [math.sqrt(Us ** 2 + U_random_m ** 2) for Us, U_random_m in
                     zip(U_systematic_measured, U_random_m_array)]

# Calculate random uncertainty for simulated torque
U_random_sim = (t_value * Sd_torque_sim) / math.sqrt(N)

# Calculate total uncertainty for simulated torque
U_simulated_torque = [math.sqrt(Us ** 2 + U_random_sim ** 2) for Us in U_systematic_simulated]

# Call the function from the CFD_Validation script
comparison_errors, validation_results = cfd_v.compare_torques(measured_torque_array, simulated_torque_array, U_measured_torque, U_simulated_torque)

# Print the Results
for E, validation in zip(comparison_errors, validation_results):
    print(f"Comparison Error: {E}")
    print(f"Validation: {'CFD model measurement validated.' if validation else 'CFD model measurement not validated.'}")