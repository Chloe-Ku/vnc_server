import socket
import threading
import time
import random
import math
import signal

from typing import Optional, List
from pdb import set_trace

# Hacky work-around to be able to import from a folder above this one.
import sys
import os



sys.path.insert(1, os.path.abspath("../../vnc_server/"))
from network.comm_strategy import GoodStrategy
from vehicle_util import *

sys.path.insert(1, os.path.join(sys.path[0], '../databases'))
from sqldb import SQLDB
from user_util import UserUtil

from network.vehicle_util import VehicleRideSelector, Ride, RideDBUtil

import logging
import os
logger = logging.getLogger(__name__)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(module)s - %(levelname)s - %(message)s')
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
ch.setFormatter(formatter)
logging_path = os.path.dirname(os.path.realpath(__file__)).split("src/")[0] + "src/server_log"
fh = logging.FileHandler(logging_path)
fh.setLevel(logging.DEBUG)
fh.setFormatter(formatter)
logger.addHandler(ch)
logger.addHandler(fh)
logger.setLevel(logging.DEBUG)

#
# When the user presses CTRL+C, disable all vehicles.
#
def intHandler(sig, frame):
    response = SQLDB().update('Vehicles', {'enabled': 0}, None)
    if (response.success == True):
        print('Successfully disabled all vehicles')
    else:
        print('FAILED TO DISABLE ALL VEHICLES: %s' % response.message)

    sys.exit(0)

signal.signal(signal.SIGINT, intHandler)

#
# Be able to access rides in a thread-safe way.
#
ridesLock = threading.Lock()


def withRidesLock(func):
    def wrapper(*args, **kwargs):
        ridesLock.acquire()
        try:
            return func(*args, **kwargs)
        except Exception as e:
            print('Exception: %s' % e)
        finally:
            ridesLock.release()

    return wrapper

randNum = random.randint(12001, 12999)
class VehicleServer():
    """The class handling the vehicle and ride interactions with VNC

    The 'main' method is handleClient().
    That is ran for each client connection.

    :param host: the host IP for the server to run on. (Default '')
    :type host: str
    :param port: the target server port. (Default 12345)
    :type port: int
    :param queueSize: the size of the queue of the incomming connections.
        Anything beyond this size is refused connection. (Default 100)
    :type queueSize: int
    :param _rideSelector: The private reference to the ride selector object.
        Used to later choose the :class:`vnc_server.network.vehicle_util.VehicleSelectorStrategy` strategy for a ride request.
    :type _rideSelector: :class:`vnc_server.network.vehicle_util.VehicleRideSelector`
    """

    # Listen for any IP, on the specified port
    host = ''
    port = 12345

    # How many connections to queue before refusing
    #
    # From a simple test, queueSize vs. time taken to handle 100 connections:
    # 5,   11.96
    # 50,   1.08
    # 100,  0.12
    #
    # So we may as well keep it large
    queueSize = 100

    def __init__(self, strategy: Optional[str] = None):
        """Init method for server

        :param strategy: the strategy to match rides with, defaults to None
        :type strategy: Optional[str], optional
        """
        # VehicleServer.port = port = random.randint(12001, 12999) # 12345
        # Set all vehicles to inactive (they'll become active once they connect)
        try:
            response = SQLDB().update('Vehicles', {'enabled': 0}, None)
            if (response.success != True):
                print('FAILED TO DISABLE ALL VEHICLES: %s' % response.message)
                exit()
        except Exception as e:
            print('FAILED TO DISABLE ALL VEHICLES: %s' % e)
            exit()

        self.rides = []

        self._rideSelector = VehicleRideSelector()
        self._vehicleSelectorStrat = strategy

        # dictionaries to keep track of when ride requests start and pick-up
        # inorder to calculate wait times
        self.ride_start_dict = {}  # key: rideID value: start time
        self.ride_pickup_dict = {} # key: rideID value: pickup time

        # Create the socket
        try:
            # AF_INET means IPv4,
            # SOCK_STREAM means TCP
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        except Exception as e:
            print('Failed to create socket: %s' % e)
            exit()

        # Make the socket re-usable (makes testing way easier)
        try:
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        except Exception as e:
            print('Failed to make address reusable: %s' % e)

        # Listen on the socket
        try:
            self.sock.bind((VehicleServer.host, VehicleServer.port))
        except Exception as e:
            print('Failed to bind socket: %s' % e)
            exit()

        # Listen on the socket
        try:
            self.sock.listen(VehicleServer.queueSize)
        except Exception as e:
            print('Failed to listen on socket: %s' % e)
            exit()

    #
    # This is the 'server main()'
    #

    def run(self):
        print('VehicleServer.run()')

        while True:
            try:
                (clientSock, clientAddr) = self.sock.accept()
            except Exception as e:
                print('Failed to accept client connection: %s' % e)
                continue

            # myHandler = RandomStrategy(clientSock)
            myHandler = GoodStrategy(clientSock)

            target = myHandler.__class__.startServer
            args = (myHandler, self)

            try:
                threading.Thread(target=target, args=args).start()
            except Exception as e:
                print('Failed to start client thread: %s' % e)
                continue

    @withRidesLock
    def getRide(self, vName) -> Optional[Ride]:
        """Selects and returns a ride request utilizing the best strategy

        Uses :class:`vehicle_util.VehicleRideSelector` to obtain the optimal ride
        selection strategy, and uses that strategy to choose the ride for the vehicle.
        :return: Ride instance from the queue or None
        :rtype: :class:`Ride` or None
        """
        ride = self._rideSelector.getVehicleSelector(self._vehicleSelectorStrat).selectRide(vName, queue=self.rides)
        return ride

    @withRidesLock
    def addRide(self, riderEmail, riderLat, riderLon, destLat, destLon, rtime):
        newRide = Ride(riderEmail, riderLat, riderLon, destLat, destLon, rtime)
        response = RideDBUtil.addRide(SQLDB(), newRide)
        if response:
            newRide.setRideID(SQLDB())
            self.rides.append(newRide)

            # Assign the ride id to user
            db = SQLDB()
            obj = {
                "curRideID": newRide.getRideID()
            }
            r = db.update('Users', obj, {"email": riderEmail})
            if not r.success:
                logger.error(f"Failed to assign ride id {newRide.getRideID()} to user {riderEmail}: {r.message}")
        # add ride id with start time to dictionary
        self.ride_start_dict[str(newRide.getRideID())] = time.time()
        return newRide.getRideID()

    @withRidesLock
    def findRide(self, id: str) -> dict:
        """Returns a dict representing a pending :class:`vehicle_util.Ride` with the target id

        The method returns only the ride that is active.
        The rides that are completed or cancelled will not be returned.
        The id references the ride id in the Rides table of the database.

        :param id: the id of the ride request
        :type id: str
        :return: the dict representing the target ride
        :rtype: dict
        """
        import json
        r = RideDBUtil.getRide(SQLDB(), id)
        if r:
            logger.debug(f"Found ride with id {id}: {json.dumps(r)}")
            return r
        else:
            logger.debug(f"Did not find ride with id {id}")
            return None

    @withRidesLock
    def getRides(self) -> List[dict]:
        """Returns a list of pending rides registered with the server

        This list includes the ride requests that were assigned to he vehicles and
        are in progress as well as pending requests.
        :class:`vhicle_util.Ride` is represented as dict with all fields of a class
        being the keys.

        The rides that are completed or cancelled will not be returned.

        :return: the list of the pending rides
        :rtype: List[dict]
        """
        return RideDBUtil.getRides(SQLDB())

    def getVehicles(self) -> List[dict]:
        """Returns a list of vehicles registered with the server

        This list includes the assigned vehicles as well as the unassigned vehicles.
        :class:`vehicle_util.Vehicle` is represented as dict with all fields of a class
        being the keys.

        :return: the list of the vehicles
        :rtype: List[dict]
        """
        #Might have to remove that False, this currently gets all vehicles including disabled ones.
        return VehicleDBUtil.getVehiclesLite(SQLDB())

    def findVehicle(self, id: str) -> dict:
        """Returns a dict representing a pending :class:`vehicle_util.Vehicle` with the target ride id

        The method returns only the vehicle that is related to the ride.
        The rides that are completed or cancelled will not be returned.
        The id references the ride id in the Rides table of the database,
        which is then used to find the vehicle id.

        :param id: the id of the ride request
        :type id: str
        :return: the dict representing the corresponding vehicle
        :rtype: dict
        """
        import json
        r = RideDBUtil.getVehicle(SQLDB(), id)
        if r:
            logger.debug(f"Found ride with id {id}: {json.dumps(r)}")
            return r
        else:
            logger.debug(f"Did not find ride with id {id}")
            return None

    def getLocationNodes(self) -> List[dict]:
        """Returns a list of locationNodes registered with the server

        This list includes the name, lat, and lon of the locationNode

        :return: the list of the locationNodes
        :rtype: List[dict]
        """
        return VehicleDBUtil.getLocationNodes(SQLDB())

    def confirmPickup(self, rideID):
        response = RideDBUtil.confirmPickup(SQLDB(), rideID)

        if response:
            # add ride id with pickup time to dictionary
            self.ride_pickup_dict[str(rideID)] = time.time()
            return "Confirmed Pickup"
        return "Pickup confirmation failed."

    def confirmArrival(self, rideID):
        response = RideDBUtil.confirmArrival(SQLDB(), rideID)

        if response: return "Confirmed Arrival"
        return "Arrival confirmation failed."

    def cancelRide(self, rideID):
        response = RideDBUtil.cancelRide(SQLDB(), rideID)

        if response: return "Canceled Ride"
        return "Ride cancellation failed."

    def clearStartAndPickupDicts(self):
        """
        Clears the ride start and pickup dictionaries that are used to
        measure wait time
        """
        self.ride_start_dict = {}  # key: rideID value: start time
        self.ride_pickup_dict = {} # key: rideID value: pickup time

    def signUp(self, user):
        return UserUtil().insertUser(user)

    def updateUser(self, user):
        return UserUtil().updateUser(user)

    def getUser(self, email: str) -> dict:
        """Returns a dict representing a pending :class:`User` with the target ride id

        The method returns an object containing the fields of the User.

        :param email: the email of the user
        :type email: str
        :return: the dict representing the corresponding user
        :rtype: dict
        """
        import json
        r = RideDBUtil.getUser(SQLDB(), email)
        if r:
            logger.debug(f"Found user with email {email}: {json.dumps(r, default=str)}")
            return r
        else:
            logger.debug(f"Did not find user with email {email}")
            return None

    def signIn(self, user):
        return UserUtil().validateUser(user)

    def signInGoogle(self, user):
        return UserUtil().validateGoogleUser(user)

    def getRideHistory(self, email):
        return RideDBUtil.getRideHistory(SQLDB(), email)

    def getLocationNodeByCoordinates(self, coordinates):
        return RideDBUtil.getLocationNodeByCoordinates(SQLDB(), coordinates)

    def findUserRide(self, email: str) -> dict:
        """Returns a dict representing a pending :class:`vehicle_util.Ride` correlated with a user

        The method returns only the ride that is associated with the user,
        the curRideID of the User.
        The id references the email in the Users table of the database.

        :param id: the id of the user
        :type id: str
        :return: the dict representing the target ride
        :rtype: dict
        """
        import json
        r = RideDBUtil.getUserRide(SQLDB(), email)
        if r:
            logger.debug(f"Found ride with useremail {email}: {json.dumps(r)}")
            return r
        else:
            logger.debug(f"User did not exist, or did not have a ride. Email: {email}")
            return None

def main():
    vs = VehicleServer()
    vs.run()


if __name__ == '__main__':
    main()
