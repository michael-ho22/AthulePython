import math

def compare_torques(measured_torque_array, simulated_torque_array, U_measured_torque, U_simulated_torque):
    comparison_errors = []  # Validation comparison error
    validation_results = []  # Validation results

    # Calculate comparison error for each torque measurement
    for measured_torque, simulated_torque in zip(measured_torque_array, simulated_torque_array):
        E = abs(measured_torque - simulated_torque)
        comparison_errors.append(E)

    # Calculate Comparison Error Uncertainty for each pair and check model validation
    for E, U_measured, U_simulated in zip(comparison_errors, U_measured_torque, U_simulated_torque):
        U_E = math.sqrt(U_measured ** 2 + U_simulated ** 2)

        # Check if each individual CFD model measurement is validated
        if E < U_E:
            validation_results.append(True)
        else:
            validation_results.append(False)

    return comparison_errors, validation_results
