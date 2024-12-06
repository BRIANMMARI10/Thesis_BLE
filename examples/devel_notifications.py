# -*- coding: utf-8 -*-
"""
Notifications
-------------

Example showing how to add notifications to a characteristic and handle the responses,
with modifications for real-time communication using multiprocessing.Queue.

Updated on 2024-12-04 by Brian Mmari
"""

import argparse
import asyncio
import logging
from multiprocessing import Queue
from bleak import BleakClient, BleakScanner
from bleak.backends.characteristic import BleakGATTCharacteristic

logger = logging.getLogger(__name__)


def notification_handler_with_queue(queue: Queue):
    """Create a notification handler that sends data to a queue."""

    def handler(characteristic: BleakGATTCharacteristic, data: bytearray):
        """Process BLE notifications and push data to the queue."""
        try:
            decoded_data = data.decode("utf-8")
            logger.info("Received notification: %s", decoded_data)
            queue.put(decoded_data)  # Push the notification data into the queue
        except Exception as e:
            logger.error("Error handling notification: %s", e)

    return handler


async def main(name: str, address: str, characteristic: str, led_characteristic: str, use_bdaddr: bool, queue: Queue):
    """Connect to the BLE device and handle notifications and commands."""
    logger.info("Starting scan...")

    # Find the device by name or address
    if address:
        device = await BleakScanner.find_device_by_address(
            address, cb=dict(use_bdaddr=use_bdaddr)
        )
        if device is None:
            logger.error("Could not find device with address '%s'", address)
            return
    else:
        device = await BleakScanner.find_device_by_name(
            name, cb=dict(use_bdaddr=use_bdaddr)
        )
        if device is None:
            logger.error("Could not find device with name '%s'", name)
            return

    logger.info("Connecting to device...")

    async with BleakClient(device) as client:
        logger.info("Connected")

        # Set up notifications
        notification_handler = notification_handler_with_queue(queue)
        await client.start_notify(characteristic, notification_handler)

        try:
            while True:
                # Handle commands from the queue
                if not queue.empty():
                    command = queue.get()
                    logger.info("Sending command to LED characteristic: %s", command)
                    await client.write_gatt_char(led_characteristic, command.encode("utf-8"))
                await asyncio.sleep(1.0)  # Keeps the loop alive
        except asyncio.CancelledError:
            logger.info("Notification listening cancelled.")
        finally:
            await client.stop_notify(characteristic)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    device_group = parser.add_mutually_exclusive_group(required=True)

    device_group.add_argument(
        "--name",
        metavar="<name>",
        help="The name of the Bluetooth device to connect to",
    )
    device_group.add_argument(
        "--address",
        metavar="<address>",
        help="The address of the Bluetooth device to connect to",
    )

    parser.add_argument(
        "--macos-use-bdaddr",
        action="store_true",
        help="When true, use Bluetooth address instead of UUID on macOS",
    )

    parser.add_argument(
        "characteristic",
        metavar="<notify uuid>",
        help="UUID of a characteristic that supports notifications",
    )

    parser.add_argument(
        "led_characteristic",
        metavar="<led uuid>",
        help="UUID of the LED control characteristic",
    )

    parser.add_argument(
        "-d",
        "--debug",
        action="store_true",
        help="Sets the log level to debug",
    )

    args = parser.parse_args()

    # Create a Queue and pass it to asyncio.run
    queue = Queue()
    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)-15s %(name)-8s %(levelname)s: %(message)s",
    )

    asyncio.run(main(args, queue))
