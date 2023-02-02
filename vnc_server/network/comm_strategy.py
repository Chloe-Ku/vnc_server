#
# Logic for how to actually handle a client connection is here
#

from abc import ABC, abstractmethod
import random
import time
import json
from pprint import pprint

from command import *
from network.vehicle_util import *
from vehicle import Vehicle

# Hacky work-around to be able to import from a folder above this one.
import sys
import os

sys.path.append(os.path.abspath('../databases'))
from neodb import NeoDB
from sqldb import SQLDB

import logging
logger = logging.getLogger(__name__)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(module)s - %(levelname)s - %(message)s')
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
ch.setFormatter(formatter)
logging_path = os.path.dirname(os.path.realpath(__file__)).split("src/")[0] + "/src/server_log"
fh = logging.FileHandler(logging_path)
fh.setLevel(logging.DEBUG)
fh.setFormatter(formatter)
logger.addHandler(ch)
logger.addHandler(fh)
logger.setLevel(logging.DEBUG)

#
# abstractmethod decorator reuqires the function to be implemented
# in its base classes.
#


class CommStrategy(ABC):
    """
    Servers should call startServer().
    Client should call startClient().
    """

    def __init__(self, sock):
        self.sock = sock

    @abstractmethod
    def startServer(self, theServer):
        pass


class GoodStrategy(CommStrategy):
    """
    Actually handle the client in a nice way lol
    """

    def startServer(self, theServer):
        # print('GoodStrategy.startServer()')

        # Register the vehicle
        try:
            self.theServer = theServer
            # print('%d rides' % len(list(self.theServer.rides)))

            self.db = SQLDB()
            self.to_rider_time = None
            self.to_dest_time = None

            # Make initial handshake (init request and init acknowledge)
            initRequest = Command.recv(self.sock)
            registered = VehicleDBUtil.registerVehicle(self.db, initRequest)
            if (registered == False):
                logger.error('Failed to register vehicle. Terminating this connection.')
                self.sock.close()
                return

            # Save the vehicle name for later (for disabling)
            self.vName = initRequest.name
        except Exception as e:
            logger.exception('EXCEPTION: %s' % e)
            self.sock.close()
            return

        # Now do the handshake then ping pong
        try:
            initAck = InitAck({})
            initAck.send(self.sock)

            # Assume that it's idle to being with
            self.vState = State.IDLE

            logger.debug(f"InitRequest sent")
            # Check vehicle response before retrieving a ride
            logger.debug(f"Vehicle response recieved")

            response = initRequest.toObj()
            logger.debug(f"battery life upon init: {str(response['batteryLife'])} ")
            if (response['batteryLife'] <= response['minBatteryLife']):
                lat, lon = response['lat'], response['lon']
                logger.debug(f"Node lat: {str(lat)}, Node lon:{str(lon)} ")
                #TODO: should be something like vehicle_util.getChargerLocation
                args = {
                    'lat': lat,
                    'lon': lon
                }
                request = IdleToEnrouteToCharger(args)
                request.send(self.sock)

                # Should only ever receive a chargingAck back
                response = Command.recv(self.sock)
                FSMUtil.expectClass(response, IdleToEnrouteToChargerAck)
                self.vState = State.ENROUTE_TO_CHARGER


            # Now do regular communication
            self.pingPongServer()
        except Exception as e:
            logger.exception('EXCEPTION: %s' % e)
        finally:
            self.sock.close()
            VehicleDBUtil.disableVehicle(self.db, self.vName)

    def pingPongServer(self):
        while True:
            if (self.vState == State.IDLE):
                #
                # IDLE
                #
                #print('Client is idle')
                self.ride = self.theServer.getRide(self.vName)
                if (self.ride is None or RideDBUtil.checkCanceled(self.db, self.ride.rideID)):
                    # Send the idle request
                    idleRequest = IdleRequest()
                    idleRequest.send(self.sock)

                    # Should only ever receive a idleAck back
                    response = Command.recv(self.sock)
                    FSMUtil.expectClass(response, IdleAck)

                    vehicleStateObj = response.toObj()
                    obj = {
                        "lat": vehicleStateObj["lat"],
                        "lon": vehicleStateObj["lon"],
                        "batteryLife": vehicleStateObj["batteryLife"],
                        "mileage": vehicleStateObj["mileage"],
                        # "curEdge" ?
                    }
                    r = self.db.update('Vehicles', obj, {"name": vehicleStateObj["name"]})
                    if not r.success:
                        logger.error(f"Failed to update vehicle state: {r.message}")
                        logger.debug(f"The target state: {str(vehicleStateObj)}")

                    # TODO double check that there are no issues in the DB when the ride is canceled
                    vehicleStateObj = response.toObj()

                    r = VehicleDBUtil.updateStatus(self.db, vehicleStateObj["name"], "WAITING", time.time(), vehicleStateObj["lat"],
                                                   vehicleStateObj["lon"], vehicleStateObj["batteryLife"], None)
                    if not r:
                        logger.error(f"Failed to update vehicle state when vehicle {vehicleStateObj['name']} is idle.")
                        logger.debug(f"The target state: {str(vehicleStateObj)}")

                else:
                    logger.info('Setting client to ENROUTE_TO_RIDER')
                    logger.debug(f"Got a ride: {str(self.ride)}")

                    # Get the latitude and longtitude of the Rider from the Ride we got
                    lat, lon = self.ride.getRiderLocation()

                    # Create our IdleToEnrouteToRiderRequest arguments from the rider lat and lon
                    args = {
                        'lat': lat,
                        'lon': lon
                    }

                    # Create our IdleToEnrouteToRiderRequest command and send it to the Vehicle.
                    idleToRiderRequest = IdleToEnrouteToRiderRequest(args)
                    idleToRiderRequest.send(self.sock)

                    # Wait for the message we receive back from the Vehicle. This should be an instance of
                    # IdleToEnrouteToRiderAck and should contain the internal state of the Vehicle. Update
                    # our database of Vehicles to reflect the current Vehicle state
                    response = Command.recv(self.sock)
                    FSMUtil.expectClass(response, IdleToEnrouteToRiderAck)


                    # Persist this state to DB
                    vehicleStateObj = response.toObj()

                    r = VehicleDBUtil.updateStatus(self.db, vehicleStateObj["name"], "ENROUTE_TO_RIDER", time.time(), vehicleStateObj["lat"],
                                                   vehicleStateObj["lon"], vehicleStateObj["batteryLife"], self.ride.getRideID())
                    if not r:
                        logger.error(f"Failed to update vehicle state when vehicle {vehicleStateObj['name']} is enroute to rider.")
                        logger.debug(f"The target state: {str(vehicleStateObj)}")

                    # Update the ride with the assigned vehicle name
                    logger.debug(f"Assigning a vehicle {str(response)} name to a ride {str(self.ride)}")
                    r = self.db.update('Rides', {"vehicleName": vehicleStateObj["name"], "status": "ENROUTE_TO_RIDER"},
                                       {"userEmail": self.ride.getRiderEmail()})
                    if not r.success:
                        logger.error(f"Failed to assign a vehicle name to the ride: {r.message}")
                        logger.debug(f"The target ride: {str(self.ride)}")
                        logger.debug(f"The target vehicle: {str(vehicleStateObj)}")

                    # And set our current state to ENROUTE_TO_RIDER
                    self.vState = State.ENROUTE_TO_RIDER
                    logger.info('Client is enroute to rider')
                self.batteryLife = response.toObj()['batteryLife']
            elif (self.vState == State.ENROUTE_TO_RIDER):
                # Get the latest message from the Vehicle.
                response = Command.recv(self.sock)
                if(response.__class__ == EnrouteToRiderAck):
                    # If the command received is an instance of EnrouteToRiderAck we remain in the current state.
                    # Still need to update the Vehicle database with the current state of this Vehicle

                    self.vState = State.ENROUTE_TO_RIDER

                    # Persist this state to DB
                    vehicleStateObj = response.toObj()

                    r = VehicleDBUtil.updateStatus(self.db, vehicleStateObj["name"], "ENROUTE_TO_RIDER", time.time(), vehicleStateObj["lat"],
                                                   vehicleStateObj["lon"], vehicleStateObj["batteryLife"])
                    if not r:
                        logger.error(f"Failed to update vehicle state when vehicle {vehicleStateObj['name']} is enroute to rider.")
                        logger.debug(f"The target state: {str(vehicleStateObj)}")

                elif (response.__class__ == EnrouteToRiderToToRiderAck):
                    # If the command received is an instance of EnrouteToRiderToToRiderAck we update the state to TO_RIDER
                    # Also need to update the Vehicle information in the database

                    # Persist this state to DB
                    vehicleStateObj = response.toObj()

                    r = VehicleDBUtil.updateStatus(self.db, vehicleStateObj["name"], "TO_RIDER", time.time(), vehicleStateObj["lat"],
                                                   vehicleStateObj["lon"], vehicleStateObj["batteryLife"])
                    if not r:
                        logger.error(f"Failed to update vehicle state when vehicle {vehicleStateObj['name']} is at the rider's location.")
                        logger.debug(f"The target state: {str(vehicleStateObj)}")

                    # Update the ride status
                    r = self.db.update('Rides', {"status": "TO_RIDER"}, {"userEmail": self.ride.getRiderEmail()})
                    if not r.success:
                        logger.error(f"Failed to update ride status: {r.message}")
                        logger.debug(f"The target ride: {str(self.ride)}")
                        logger.debug(f"The target vehicle: {str(vehicleStateObj)}")

                    self.vState = State.TO_RIDER
                    logger.info('Client is at the rider\'s location')

            elif (self.vState == State.TO_RIDER):
                #
                # TO_RIDER
                #
                # print('Client is to rider')

                # Check database for confirmation of pickup and cancellation
                canceled = RideDBUtil.checkCanceled(self.db, self.ride.rideID)
                pickupConfirmed = RideDBUtil.checkPickupConfirmation(self.db, self.ride.rideID)

                if (canceled):
                    lat, lon = self.ride.getRiderLocation()
                    args = {
                        'lat': lat,
                        'lon': lon
                    }

                    request = ToRiderCancel(args)
                    request.send(self.sock)

                    # Should only ever receive a ToRiderCancelAck back
                    response = Command.recv(self.sock)
                    FSMUtil.expectClass(response, ToRiderCancelAck)

                    vehicleStateObj = response.toObj()
                    r = VehicleDBUtil.updateStatus(self.db, vehicleStateObj["name"], "WAITING", time.time(), vehicleStateObj["lat"],
                                                   vehicleStateObj["lon"], vehicleStateObj["batteryLife"], None)
                    if not r:
                        logger.error(f"Failed to update vehicle state when vehicle {vehicleStateObj['name']} is at the rider's location.")
                        logger.debug(f"The target state: {str(vehicleStateObj)}")

                    ride = RideDBUtil.getRide(self.db, self.ride.getRideID())
                    riderEmail = ride["userEmail"]

                    obj = {
                        "curRideID": None
                    }
                    r = self.db.update('Users', obj, {"email": riderEmail})
                    if not r.success:
                        logger.error(f"Failed to set the ride id to NULL when ride is finished to user {riderEmail}: {r.message}")

                    r = self.db.delete('Rides', ['id'], {"id": self.ride.getRideID()})
                    if not r.success: # TODO Add alternative
                        logger.error(f"Failed to remove the ride from Rides table to move it to history: {r.message}")
                        logger.debug(f"The target ride: {str(self.ride)}")

                    tEnd = time.time()
                    obj = {
                        "userEmail": riderEmail,
                        "vehicleName": ride["vehicleName"],
                        "tStart": ride["tStart"],
                        "tEnd": int(tEnd),
                        "startNode": ride["startNode"],
                        "endNode": ride["endNode"]
                    }

                    r = self.db.create('RideHistory', list(obj.keys()), obj)
                    if not r.success: # TODO Add alternative
                        logger.error(f"Failed to add the ride from to history: {r.message}")
                        logger.debug(f"The target ride: {str(self.ride)}")
                        logger.debug(f"The target sql obj: {str(obj)}")

                    self.vState = State.IDLE
                    logger.info('Client has be canceled and will remain at current location.')

                elif (not pickupConfirmed):
                    # Rider has not yet confirmed pickup, stay in TO_RIDER state
                    self.vState = State.TO_RIDER

                    # Mark the time that this state was entered
                    """ if (not self.to_rider_time):
                        self.to_rider_time = time.time()
                        logger.debug(f"Set to_ride_time: {str(self.to_rider_time)}")
                    if (time.time() - self.to_rider_time > RideDBUtil.WAIT_TIME):
                        logger.debug(f"Progressing to next state as {str(RideDBUtil.WAIT_TIME)} seconds have passed.")
                        pickupConfirmed = True
                    logger.debug(f"Time elapsed: {str(time.time() - self.to_rider_time)}.") """

                    # Persist this state to DB
                    vehicleStateObj = response.toObj()

                    r = VehicleDBUtil.updateStatus(self.db, vehicleStateObj["name"], "TO_RIDER", time.time(), vehicleStateObj["lat"],
                                                   vehicleStateObj["lon"], vehicleStateObj["batteryLife"])
                    if not r:
                        logger.error(f"Failed to update vehicle state when vehicle {vehicleStateObj['name']} is at the rider's location.")
                        logger.debug(f"The target state: {str(vehicleStateObj)}")

                if (pickupConfirmed):
                    # Rider has confirmed pickup, transition to ENROUTE_TO_DEST
                    # If the Vehicle is at the Client we need to send it the lat/lon position of the destination
                    lat = self.ride.destLat
                    lon = self.ride.destLon

                    # Construct the arguments for our Command from the destination lat/lon
                    args = {
                        'lat': lat,
                        'lon': lon
                    }

                    # Create and send our ToRiderToEnrouteToDestRequest to the Vehicle
                    request = ToRiderToEnrouteToDestRequest(args)
                    request.send(self.sock)

                    # Should only ever receive a ToRiderToEnrouteToDestAck back
                    response = Command.recv(self.sock)
                    FSMUtil.expectClass(response, ToRiderToEnrouteToDestAck)

                    # Persist this state to DB
                    vehicleStateObj = response.toObj()

                    r = VehicleDBUtil.updateStatus(self.db, vehicleStateObj["name"], "ENROUTE_TO_DEST", time.time(), vehicleStateObj["lat"],
                                                   vehicleStateObj["lon"], vehicleStateObj["batteryLife"])
                    if not r:
                        logger.error(f"Failed to update vehicle state when vehicle {vehicleStateObj['name']} is enroute to destination.")
                        logger.debug(f"The target state: {str(vehicleStateObj)}")

                    # Update the ride status
                    r = self.db.update('Rides', {"status": "ENROUTE_TO_DEST"}, {"userEmail": self.ride.getRiderEmail()})
                    if not r.success:
                        logger.error(f"Failed to update ride status: {r.message}")
                        logger.debug(f"The target ride: {str(self.ride)}")
                        logger.debug(f"The target vehicle: {str(vehicleStateObj)}")

                    # Finally, update our state to ENROUTE_TO_DEST
                    self.vState = State.ENROUTE_TO_DEST
                    logger.info('Client is enroute to destination location with the rider')
            elif (self.vState == State.ENROUTE_TO_DEST):

                # Receive a Command from the Vehicle
                response = Command.recv(self.sock)

                if (response.__class__ == EnrouteToDestAck):
                    # If the Command is an instance of EnrouteToDestAck stay in the ENROUTE_TO_DEST state

                    # Persist this state to DB
                    vehicleStateObj = response.toObj()

                    r = VehicleDBUtil.updateStatus(self.db, vehicleStateObj["name"], "ENROUTE_TO_DEST", time.time(), vehicleStateObj["lat"],
                                                   vehicleStateObj["lon"], vehicleStateObj["batteryLife"])
                    if not r:
                        logger.error(f"Failed to update vehicle state when vehicle {vehicleStateObj['name']} is enroute to destination.")
                        logger.debug(f"The target state: {str(vehicleStateObj)}")

                    # Maintain our current state
                    self.vState = State.ENROUTE_TO_DEST

                elif (response.__class__ == EnrouteToDestToToDestAck):
                    # If the Command is an instance of EnrouteToDestToToDestAck then the Vehicle is at the destination

                    # Persist this state to DB
                    vehicleStateObj = response.toObj()

                    r = VehicleDBUtil.updateStatus(self.db, vehicleStateObj["name"], "TO_DEST", time.time(), vehicleStateObj["lat"],
                                                   vehicleStateObj["lon"], vehicleStateObj["batteryLife"])
                    if not r:
                        logger.error(f"Failed to update vehicle state when vehicle {vehicleStateObj['name']} is at the destination.")
                        logger.debug(f"The target state: {str(vehicleStateObj)}")

                    # Update the ride status
                    r = self.db.update('Rides', {"status": "TO_DEST"}, {"userEmail": self.ride.getRiderEmail()})
                    if not r.success:
                        logger.error(f"Failed to update ride status: {r.message}")
                        logger.debug(f"The target ride: {str(self.ride)}")
                        logger.debug(f"The target vehicle: {str(vehicleStateObj)}")

                    # And update our state to TO_DEST
                    self.vState = State.TO_DEST
                    logger.info('Waiting on client confirmation of arrival')

            elif (self.vState == State.TO_DEST):
                #
                # TO_DEST
                #
                # print('Client is to dest')

                # Check database for confirmation of arrival and cancellation
                arrivalConfirmed = RideDBUtil.checkArrivalConfirmation(self.db, self.ride.rideID)
                canceled = RideDBUtil.checkCanceled(self.db, self.ride.rideID)

                if (canceled):
                    lat, lon = self.ride.getRiderLocation()
                    args = {
                        'lat': lat,
                        'lon': lon
                    }

                    request = ToDestCancel(args)
                    request.send(self.sock)

                    # Should only ever receive a ToRiderCancelAck back
                    response = Command.recv(self.sock)
                    FSMUtil.expectClass(response, ToDestCancelAck)

                    vehicleStateObj = response.toObj()
                    r = VehicleDBUtil.updateStatus(self.db, vehicleStateObj["name"], "WAITING", time.time(), vehicleStateObj["lat"],
                                                   vehicleStateObj["lon"], vehicleStateObj["batteryLife"], None)
                    if not r:
                        logger.error(f"Failed to update vehicle state when vehicle {vehicleStateObj['name']} is at the rider's location.")
                        logger.debug(f"The target state: {str(vehicleStateObj)}")

                    ride = RideDBUtil.getRide(self.db, self.ride.getRideID())
                    riderEmail = ride["userEmail"]

                    obj = {
                        "curRideID": None
                    }
                    r = self.db.update('Users', obj, {"email": riderEmail})
                    if not r.success:
                        logger.error(f"Failed to set the ride id to NULL when ride is finished to user {riderEmail}: {r.message}")

                    r = self.db.delete('Rides', ['id'], {"id": self.ride.getRideID()})
                    if not r.success: # TODO Add alternative
                        logger.error(f"Failed to remove the ride from Rides table to move it to history: {r.message}")
                        logger.debug(f"The target ride: {str(self.ride)}")

                    tEnd = time.time()
                    obj = {
                        "userEmail": riderEmail,
                        "vehicleName": ride["vehicleName"],
                        "tStart": ride["tStart"],
                        "tEnd": int(tEnd),
                        "startNode": ride["startNode"],
                        "endNode": ride["endNode"]
                    }

                    r = self.db.create('RideHistory', list(obj.keys()), obj)
                    if not r.success: # TODO Add alternative
                        logger.error(f"Failed to add the ride from to history: {r.message}")
                        logger.debug(f"The target ride: {str(self.ride)}")
                        logger.debug(f"The target sql obj: {str(obj)}")

                    self.vState = State.IDLE
                    logger.info('Client has be canceled and will remain at current location.')

                elif (not arrivalConfirmed):
                    # Rider has not yet confirmed arrival, stay in TO_DEST state
                    self.vState = State.TO_DEST

                     # Mark the time that this state was entered
                    """ if (not self.to_dest_time):
                        self.to_dest_time = time.time()
                        logger.debug(f"Set to_dest_time: {str(self.to_dest_time)}")
                    if (time.time() - self.to_dest_time > RideDBUtil.WAIT_TIME):
                        logger.debug(f"Progressing to next state as {str(RideDBUtil.WAIT_TIME)} seconds have passed.")
                        arrivalConfirmed = True
                    logger.debug(f"Time elapsed: {str(time.time() - self.to_dest_time)}.") """

                    # Persist this state to DB
                    vehicleStateObj = response.toObj()

                    r = VehicleDBUtil.updateStatus(self.db, vehicleStateObj["name"], "TO_DEST", time.time(), vehicleStateObj["lat"],
                                                   vehicleStateObj["lon"], vehicleStateObj["batteryLife"])
                    if not r:
                        logger.error(f"Failed to update vehicle state when vehicle {vehicleStateObj['name']} is at the destination.")
                        logger.debug(f"The target state: {str(vehicleStateObj)}")

                if (arrivalConfirmed):
                    # Rider has confirmed arrival, transition to IDLE
                    # Send the lat/lon position of the destination
                    logger.info("Rider confirmed the arrival.")

                    lat = self.ride.riderLat
                    lon = self.ride.riderLon

                    # Construct the arguments for our Command from the destination lat/lon
                    args = {
                        'lat': lat,
                        'lon': lon
                    }

                    # Create and send our ToDestToIdle Request to the Vehicle
                    request = ToDestToIdle(args)
                    request.send(self.sock)

                    # Should only ever receive a ToDestToIdleAck back
                    response = Command.recv(self.sock)
                    FSMUtil.expectClass(response, ToDestToIdleAck)

                    # Persist this state to DB
                    vehicleStateObj = response.toObj()

                    r = VehicleDBUtil.updateStatus(self.db, vehicleStateObj["name"], "TO_DEST", time.time(), vehicleStateObj["lat"],
                                                   vehicleStateObj["lon"], vehicleStateObj["batteryLife"], None)
                    if not r:
                        logger.error(f"Failed to update vehicle state when vehicle {vehicleStateObj['name']} is at the destination.")
                        logger.debug(f"The target state: {str(vehicleStateObj)}")

                    # Update the ride status
                    # The ride is completed. Remove it from the Rides table and add it to the RidesHistory table
                    tEnd = time.time()
                    r = RideDBUtil.getRide(self.db, self.ride.getRideID())
                    if r is None: # TODO Add alternative
                        logger.error(f"Failed to get a ride to remove it from db when moving to history")
                        logger.debug(f"The target ride: {str(self.ride)}")
                        logger.debug(f"The target vehicle: {str(vehicleStateObj)}")
                    else:
                        ride = r

                        riderEmail = ride["userEmail"]
                        obj = {
                            "curRideID": None
                        }
                        r = self.db.update('Users', obj, {"email": riderEmail})
                        if not r.success:
                            logger.error(f"Failed to set the ride id to NULL when ride is finished to user {riderEmail}: {r.message}")

                        obj = {
                            "userEmail": riderEmail,
                            "vehicleName": ride["vehicleName"],
                            "tStart": ride["tStart"],
                            "tEnd": int(tEnd),
                            "startNode": ride["startNode"],
                            "endNode": ride["endNode"]
                        }
                        r = self.db.delete('Rides', ['id'], {"id": self.ride.getRideID()})
                        if not r.success: # TODO Add alternative
                            logger.error(f"Failed to remove the ride from Rides table to move it to history: {r.message}")
                            logger.debug(f"The target ride: {str(self.ride)}")

                        r = self.db.create('RideHistory', list(obj.keys()), obj)
                        if not r.success: # TODO Add alternative
                            logger.error(f"Failed to add the ride from to history: {r.message}")
                            logger.debug(f"The target ride: {str(self.ride)}")
                            logger.debug(f"The target sql obj: {str(obj)}")

                    # Finally, update our state to ENROUTE_TO_DEST
                    self.vState = State.IDLE

            elif (self.vState == State.ENROUTE_TO_CHARGER):
                #
                # Vehicle state is ENROUTE_TO_CHARGER
                #

                logger.debug("Vehicle is enroute to charger")

                # Receive a Command from the Vehicle
                response = Command.recv(self.sock)

                if (response.__class__ == EnrouteToChargerAck):
                    # If the Command is an instance of EnrouteToChargerAck stay in the ENROUTE_TO_CHARGER state

                    # Persist this state to DB
                    vehicleState = response.fields
                    vehicleStateObj = response.toObj()

                    # TODO Marked for highlighting
                    # Let's choose the things the db wants to see
                    obj = {
                        "lat": vehicleStateObj["lat"],
                        "lon": vehicleStateObj["lon"],
                        "batteryLife": vehicleStateObj["batteryLife"],
                        "mileage": vehicleStateObj["mileage"],
                        # "curEdge" ?
                    }
                    r = self.db.update('Vehicles', obj, {"name": vehicleStateObj["name"]})
                    if not r.success:
                        logger.error(f"Failed to update vehicle state: {r.message}")
                        logger.debug(f"The target state: {str(vehicleStateObj)}")

                    # Maintain our current state
                    self.vState = State.ENROUTE_TO_CHARGER

                elif (response.__class__ == EnrouteToChargerToChargingAck):
                    # If the Command is an instance of EnrouteToChargerToChargingAck then the Vehicle is at the Charger

                    # Persist this state to DB
                    vehicleState = response.fields
                    vehicleStateObj = response.toObj()

                    # TODO Marked for highlighting
                    # Let's choose the things the db wants to see
                    obj = {
                        "lat": vehicleStateObj["lat"],
                        "lon": vehicleStateObj["lon"],
                        "batteryLife": vehicleStateObj["batteryLife"],
                        "mileage": vehicleStateObj["mileage"],
                        # "curEdge" ?
                    }
                    r = self.db.update('Vehicles', obj, {"name": vehicleStateObj["name"]})
                    if not r.success:
                        logger.error(f"Failed to update vehicle state: {r.message}")
                        logger.debug(f"The target state: {str(vehicleStateObj)}")

                    # And update our state to CHARGING
                    self.vState = State.CHARGING

            elif (self.vState == State.CHARGING):
                #
                # Vehicle state is CHARGING
                #

                logger.debug("Vehicle is charging")

                # Construct the arguments for our Command from the destination lat/lon
                args = {
                    'lat': -1,
                    'lon': -1
                }

                # Create and send our ChargingToCharging Request to the Vehicle
                request = ChargingToCharging(args)
                request.send(self.sock)

                # Should only ever receive a ToDestToIdleAck back
                response = Command.recv(self.sock)
                FSMUtil.expectClass(response, ChargingAck)

                vehicleStateObj = response.toObj()

                if (vehicleStateObj['batteryLife'] >= vehicleStateObj['targetBatteryLife']):
                    # Construct the arguments for our Command from the destination lat/lon
                    args = {
                        'lat': -1,
                        'lon': -1
                    }

                    # Create and send our ChargingToIdle Request to the Vehicle
                    request = ChargingToIdle(args)
                    request.send(self.sock)

                    # Should only ever receive a CharginToIdleAck back
                    response = Command.recv(self.sock)
                    FSMUtil.expectClass(response, ChargingToIdleAck)

                    self.vState = State.IDLE
                    logger.info('Vehicle has been charged and will enter idle.')

            time.sleep(0.20)
