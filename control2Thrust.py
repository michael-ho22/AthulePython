import json
import math
import time
def control2Thrust(target_thrust, tol, itr_max, udp_socket, dest_ip, dest_port, kill_button):
    kp = 1
    ki = 3
    kd = 3
    itr = 0
    err_check = None

    udp_socket.sendto(b'read', (dest_ip, dest_port))
    time.sleep(3)
    data, _ = udp_socket.recvfrom(10240)
    tyto_data = json.loads(data.decode('latin1'))
    control_thrust = tyto_data['thrust']['displayValue']
    throttle = tyto_data['escA']['displayValue']
    t_0 = tyto_data['time']['displayValue']
    err_0 = control_thrust - int(target_thrust)
    err_check = err_0

    while True:
        itr += 1
        if kill_button and kill_button.value:  # TODO: Handle kill button
            print('Loop execution killed')
            throttle = 0
            udp_socket.sendto(str(throttle).encode('utf-8'), (dest_ip, dest_port))
            udp_socket.sendto(b'kill', (dest_ip, dest_port))
            # if fig:
            #     fig.close()  # TODO: Handle fig
            break
        elif itr > itr_max:
            break
        elif abs(err_check) <= tol:
            break
        else:
            print('we continue, itr =', itr)
            udp_socket.sendto(b'read', (dest_ip, dest_port))
            # time.sleep(3)
            data, _ = udp_socket.recvfrom(10240)
            tyto_data = json.loads(data.decode('latin1'))
            control_thrust = tyto_data['thrust']['displayValue']
            t = tyto_data['time']['displayValue']
            err = control_thrust - int(target_thrust)

            if itr == 1:
                dt = t - t_0
                integral_err = (err + err_0) / 2 * dt  # trapezoid rule for numerical integration
                derivative_err = (err - err_0) / dt  # simple forward difference approx
            else:
                dt = t - t_prev
                integral_err = (err + err_prev) / 2 * dt  # error typically on O~1E1, is negative...
                derivative_err = (err - err_prev) / dt

            # determine controller output based on error
            uc = kp * err + ki * integral_err + kd * derivative_err
            print(uc)
            if uc < 0:
                change_esc = math.floor(uc)
            else:
                change_esc = math.ceil(uc)
            new_throttle = int(throttle) - change_esc
            print(f"thrust is: {control_thrust}\nESC correcting from {throttle} --> {new_throttle}")
            udp_socket.sendto(str(new_throttle).encode('utf-8'), (dest_ip, dest_port))
            throttle = new_throttle
            err_check = err
            t_prev = t
            err_prev = err
