import argparse
import asyncio
from multiprocessing import Queue, Process
from bleak import BleakClient, BleakScanner

# Import notification handler and main function from devel_notifications
from devel_notifications import main as notifications_main

# UUID for the write characteristic
# WRITE_CHARACTERISTIC_UUID = "2A59"

async def process_queue_and_write(client: BleakClient, queue: Queue, led_characteristic: str):
    """Read data from the queue and send write commands."""
    while True:
        try:
            # Get data from the queue
            message = queue.get()

            if "BLINK" in message:
                # If the message is a command, send it directly
                print(f"Received command from queue: {message}")
                await client.write_gatt_char(led_characteristic, message.encode("utf-8"))
                print(f"Sent command: {message}")
            else:
                # Parse IMU data
                gx, gy, gz, ax, ay, az = map(float, message.split(","))
                print(f"Parsed IMU Data - Gx: {gx}, Gy: {gy}, Gz: {gz}, Ax: {ax}, Ay: {ay}, Az: {az}")

                # Determine response
                command = "BLINK_1S" if gx > 0.50 else "BLINK_5S"

                # Write the response
                await client.write_gatt_char(led_characteristic, command.strip().encode("utf-8"))
                print(f"Sent command: {command}")


        except ValueError as e:
            print(f"Error processing queue: {e}")
        except Exception as e:
            print(f"Unexpected error: {e}")
        finally:
            await asyncio.sleep(1)  # Avoid busy-waiting on errors

async def main(queue: Queue, device_name: str,  led_characteristic: str):
    """Connect to the device and handle writing responses."""
    print("Scanning for device...")
    device = await BleakScanner.find_device_by_name(device_name)

    if not device:
        print(f"Device '{device_name}' not found.")
        return

    async with BleakClient(device) as client:
        print("Connected to Nano 33 IoT.")
        await process_queue_and_write(client, queue, led_characteristic)

def run_notifications(name, address, characteristic, led_characteristic, use_bdaddr, queue):
    """Wrapper to run the notifications_main function in an event loop."""
    asyncio.run(notifications_main(name, address, characteristic, led_characteristic, use_bdaddr, queue))

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", metavar="<name>", help="The name of the Bluetooth device to connect to", required=True)
    parser.add_argument("--address", metavar="<address>", help="The address of the Bluetooth device to connect to")
    parser.add_argument("characteristic", metavar="<notify uuid>", help="UUID of a characteristic that supports notifications")
    parser.add_argument("led_characteristic",metavar="<led uuid>",help="UUID of the LED control characteristic")
    parser.add_argument("--macos-use-bdaddr", action="store_true", help="Use Bluetooth address instead of UUID on macOS")
    args = parser.parse_args()

    queue = Queue()

    # Start notifications_main in a separate process
    # Pass specific arguments to avoid pickling issues
    notification_process = Process(target=run_notifications, args=(args.name, args.address, args.characteristic, args.led_characteristic, args.macos_use_bdaddr, queue))

    notification_process.start()

    # Run the writer
    asyncio.run(main(queue, args.name, args.led_characteristic))

    # Ensure the notification process stops on exit
    notification_process.join()
