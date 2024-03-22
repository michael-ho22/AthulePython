/* //////////////// UDP Communication - MATLAB ////////////////

Script based on the Tyto example for UDP network communication.
This script communicates with PYTHON code to read sensor values and 
write throttle values to and from the Tyto 1780 hardware.

///////////// User defined variables //////////// */

var receive_port =  55047; // the listening port on this PC
var send_ip = "192.168.1.92"; // where to send the packet
var send_port = 64856; // on which port to send the packet
//var send_port = 54202; // debuging address for packet sender on my PC
var samplesAvg = 5; // how many data samples to average before sending to TCP (helps to slow down communication rate) (com rate = ?? Hz by default? Based on CPU I guess...)

///////////////// Beginning of the script //////////////////

// Setup continuous sensor read and motor control
function readSensor(){
    rcb.console.setVerbose(false);
    rcb.sensors.read(readDone, samplesAvg);
    rcb.console.setVerbose(true);
}
function readDone(result){
    // Send all the sensor data as a long JSON string
    var resultStr = JSON.stringify(result);
    var buffer = rcb.udp.str2ab(resultStr);
    rcb.udp.send(buffer);
}

/* Note the UDP functions expect arrayBuffer data type:
https://developer.mozilla.org/en-US/docs/Web/JavaScript/Typed_arrays */
rcb.udp.init(receive_port, send_ip, send_port, UDPInitialized);
rcb.udp.onReceive(UDPReceived); // Register callback event


function UDPInitialized(){
    var buffer = rcb.udp.str2ab("Hi from RCbenchmark script!");
    rcb.udp.send(buffer);
}


function UDPReceived(arrayBuffer){
    var message = rcb.udp.ab2str(arrayBuffer);
    if (message == "kill"){
        rcb.endScript(); // terminate the script (which shuts off hardware) if MATLAB message is "kill"
        
    }else if (message =="read"){
        readSensor();  // read sensors if message from MATLAB is "read"
    }else{   
        var throttle = Number(message); // otherwise, assume "message" is a throttle command
        if(isNaN(throttle)){
            rcb.console.print("Received: " + message);
        }else{
            //rcb.console.print("Setting ESC to: " + throttle);
            //rcb.output.set("esc", "throttle");
            rcb.output.set("esca",throttle);   // needed if side A-B distinction is relevant
            rcb.console.clear();
        } // if-else 2 end
    } // if-else 1 end   
} // function end