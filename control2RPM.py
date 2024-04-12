import socket
import json
import time
import math

def control2rpmv4(target_RPM, tol, itr_max, u, my_IP, recv_port, b):
    """
    A simple PID controller to reach a target RPM.

    Parameters:
    - target_rpm: The RPM to reach.
    - tol: Tolerance for the RPM error.
    - itr_max: Maximum number of iterations.
    - udp_socket: The socket object for UDP communication.
    - my_ip: IP address to send data to.
    - recv_port: Port on which to send data.
    - kill_signal: Mock-up for an external kill signal (e.g., from a GUI button).
    """
    # PID constants
    kp = 1/1000
    ki = 3/1000
    kd = 3/1000
    
    # Initial throttle value and error
    u.sendto(b'read', (my_IP, recv_port))
    time.sleep(3)
    data, _ = u.recvfrom(4096)
    decoded_data = data.decode('latin1')

    try:
        tyto_data = json.loads(decoded_data)
        # Extract initial values
        control_RPM = tyto_data["motorOpticalSpeed"]["displayValue"]
        throttle = tyto_data["escA"]["displayValue"]
        t_0 = tyto_data['time']['displayValue']
        err_0 = control_RPM - target_RPM
        err_check = err_0
    except json.JSONDecodeError:
        print("Received non-JSON data:", decoded_data)
        return  # Exit the function or handle the error as appropriate

    # tyto_data = json.loads(data.decode('latin1'))
    # control_RPM = tyto_data["motorOpticalSpeed"]["displayValue"]
    # throttle = tyto_data["escA"]["displayValue"]
    # err_0 = control_RPM - target_RPM
    # t_0 = tyto_data['time']['displayValue']
    # err_0 = control_RPM - int(target_RPM)
    # err_check = err_0

    itr = 0

    while True:
        itr += 1
        if b and b.value:
            print('Loop execution killed')
            throttle = 0
            u.sendto(str(throttle).encode('utf-8'), (my_IP, recv_port))
            u.sendto(b'kill', (my_IP, recv_port))
            break
        elif itr > itr_max:
            break
        elif abs(err_check) <= tol:
            print("Target RPM reached within tolerance.")
            break
        else:
            print(f'we continue, itr = {itr}')
            u.sendto(b'read', (my_IP, recv_port))
            data, _ = u.recvfrom(4096)
            decoded_data = data.decode('latin1')
            try:
                tyto_data = json.loads(decoded_data)
                # Extract initial values
                control_RPM = tyto_data["motorOpticalSpeed"]["displayValue"]
                t = tyto_data['time']['displayValue']
                err = control_RPM - target_RPM
            except json.JSONDecodeError:
                print("Received non-JSON data:", decoded_data)
                return  # Exit the function or handle the error as appropriate
            
            # tyto_data = json.loads(data.decode('latin1'))
            # control_RPM = tyto_data["motorOpticalSpeed"]["displayValue"]
            # t = tyto_data['time']['displayValue']
            # err = control_RPM - int(target_RPM)

            if itr == 1:
                dt = t - t_0
                integral_err = (err + err_0) / 2 * dt # trapezoid rule for numerical integration
                derivative_err = (err - err_0) / dt # simple forward difference approx
            else:
                dt = t - t_prev
                integral_err = (err + err_prev)/ 2 * dt
                derivative_err = (err - err_prev) / dt
            
            uc = (kp * err) + (ki * integral_err) + (kd * derivative_err)
            print(uc)

            if uc < 0:
                change_esc = math.floor(uc)
            else:
                change_esc = math.ceil(uc)

            new_throttle = int(throttle) - change_esc

            print(f"RPM is {control_RPM}\nESC correcting from {throttle} --> {new_throttle}")
            u.sendto(str(new_throttle).encode('utf-8'), (my_IP, recv_port))
            throttle = new_throttle
            err_check = err
            t_prev = t
            err_prev = err

