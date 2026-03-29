import argparse
import signal
import sys
import time

from dual_mc33926 import Motors


STOP_REQUESTED = False


def handle_signal(signum, frame):
    del frame
    global STOP_REQUESTED
    STOP_REQUESTED = True
    print(f"Received signal {signum}, stopping motor...", flush=True)


def parse_speeds(raw_value):
    speeds = []
    for part in raw_value.split(","):
        part = part.strip()
        if not part:
            continue
        speed = float(part)
        if speed <= 0:
            raise argparse.ArgumentTypeError("speeds must be positive numbers")
        if speed > 100:
            raise argparse.ArgumentTypeError("speeds must be 100 or less")
        speeds.append(speed)
    if not speeds:
        raise argparse.ArgumentTypeError("at least one speed is required")
    return speeds


def sleep_with_stop(duration):
    deadline = time.monotonic() + duration
    while not STOP_REQUESTED and time.monotonic() < deadline:
        time.sleep(min(0.1, deadline - time.monotonic()))


def run_step(motor, signed_speed, hold_time):
    print(f"Setting speed to {signed_speed}", flush=True)
    motor.set_speed(signed_speed)
    sleep_with_stop(hold_time)


def main():
    parser = argparse.ArgumentParser(
        description="Sweep the motor forward and reverse at a range of speeds."
    )
    parser.add_argument("--host", default="localhost", help="rgpiod host")
    parser.add_argument("--port", type=int, default=8889, help="rgpiod port")
    parser.add_argument(
        "--motor",
        type=int,
        choices=(1, 2),
        default=2,
        help="motor channel to drive",
    )
    parser.add_argument(
        "--forward-sign",
        type=int,
        choices=(-1, 1),
        default=1,
        help="signed direction to treat as forward",
    )
    parser.add_argument(
        "--speeds",
        type=parse_speeds,
        default=parse_speeds("20,40,60,80"),
        help="comma-separated speed percentages",
    )
    parser.add_argument(
        "--hold-seconds",
        type=float,
        default=1.5,
        help="time to hold each speed",
    )
    parser.add_argument(
        "--stop-seconds",
        type=float,
        default=1.0,
        help="time to pause at zero between moves",
    )
    parser.add_argument(
        "--cycles",
        type=int,
        default=2,
        help="number of forward/reverse sweep cycles",
    )
    args = parser.parse_args()

    if args.hold_seconds <= 0:
        parser.error("--hold-seconds must be greater than 0")
    if args.stop_seconds < 0:
        parser.error("--stop-seconds must be 0 or greater")
    if args.cycles < 1:
        parser.error("--cycles must be at least 1")

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    with Motors(host=args.host, port=args.port) as motors:
        motors.enable()
        motor = motors.motor1 if args.motor == 1 else motors.motor2
        reverse_sign = args.forward_sign * -1

        print(
            (
                f"Starting motor{args.motor} sweep with speeds={args.speeds}, "
                f"forward_sign={args.forward_sign}, cycles={args.cycles}"
            ),
            flush=True,
        )

        try:
            for cycle in range(1, args.cycles + 1):
                if STOP_REQUESTED:
                    break

                print(f"Cycle {cycle}: forward sweep", flush=True)
                for speed in args.speeds:
                    if STOP_REQUESTED:
                        break
                    run_step(motor, args.forward_sign * speed, args.hold_seconds)
                    run_step(motor, 0, args.stop_seconds)

                if STOP_REQUESTED:
                    break

                print(f"Cycle {cycle}: reverse sweep", flush=True)
                for speed in args.speeds:
                    if STOP_REQUESTED:
                        break
                    run_step(motor, reverse_sign * speed, args.hold_seconds)
                    run_step(motor, 0, args.stop_seconds)
        finally:
            print("Stopping motor", flush=True)
            motor.set_speed(0)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
