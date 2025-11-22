from backend.serial_reader import get_serial_handle

def write_actuators_to_serial(cmd: dict):
    try:
        ser = get_serial_handle()
        if ser is None or not ser.is_open:
            print("[SERIAL-WRITE] serial not ready")
            return False, "serial_not_ready"

        line = f"{cmd['rackACvalve']} {cmd['rackHumidifiervalve']} {cmd['tray1fanspeed']} {cmd['tray2fanspeed']}\n"
        print("[SERIAL-WRITE]", line.strip())
        ser.write(line.encode("utf-8"))
        ser.flush()
        return True, None
    except Exception as e:
        print("[SERIAL-WRITE-ERROR]", e)
        return False, str(e)
