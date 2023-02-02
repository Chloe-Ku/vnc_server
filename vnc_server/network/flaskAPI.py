import vehicle_server
from flask import Flask, Response, request
import threading
import json
from pdb import set_trace
from flask_httpauth import HTTPBasicAuth
from flask_httpauth import HTTPTokenAuth
from user_util import UserUtil
import time

import logging
import os
logger = logging.getLogger(__name__)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(module)s - %(levelname)s - %(message)s')
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
ch.setFormatter(formatter)
logging_path = os.path.dirname(os.path.realpath(__file__)).split("src/")[0] + "log"
fh = logging.FileHandler(logging_path)
fh.setLevel(logging.DEBUG)
fh.setFormatter(formatter)
logger.addHandler(ch)
logger.addHandler(fh)
logger.setLevel(logging.DEBUG)

# Create an instance of our Flask API to allow us to modify the VehicleServer via REST protocols
app = Flask(__name__)

# Create an instance of the VehicleServer that will handle socket connections from the vehicles.
# Exposing the instance globally allows our Flask methods to handle adding rides
vs = vehicle_server.VehicleServer()

"""
Auth methods below
"""
basic_auth = HTTPBasicAuth()

@basic_auth.verify_password
def verify_password(email, password):
    user = {"email": email, "password": password}
    response = UserUtil().validateUser(user)
    if user and response.success:
        return user

@basic_auth.error_handler
def basic_auth_error(status):
    return Response(status=status, response='Basic Auth API error')

@app.route('/tokens', methods=['POST', 'GET'])
@basic_auth.login_required
def get_token():
    token = UserUtil().get_token(vs.getUser(basic_auth.current_user()['email']))
    return json.dumps({'token': token})

"""
Token Auth
"""
token_auth = HTTPTokenAuth()
@token_auth.verify_token
def verify_token(token):
    return UserUtil().check_token(token) if token else None

@token_auth.error_handler
def token_auth_error(status):
    return Response(status=status, response='Token Auth API error')

"""
Add a ride to the VNC
"""
@app.route("/rides", methods=['POST'])
@token_auth.login_required
def addRides():
    user_response = token_auth.current_user()
    try:
        user_response['email']
    except TypeError:
        return token_auth_error(401)

    request_json = request.get_json()
    logger.debug("Request data:")
    logger.debug(request_json)
    try:
        riderEmail = request_json['riderEmail']
        riderLat = request_json['riderLat']
        riderLon = request_json['riderLon']
        destLat = request_json['destLat']
        destLon = request_json['destLon']
        startTime = int(time.time())

        logger.debug(f"Adding a ride: riderEmail: {riderEmail}, "\
                        f"riderLat: {riderLat}, "\
                        f"riderLon: {riderLon}, "\
                        f"destLat: {destLat}, "\
                        f"destLon: {destLon}, "\
                        f"time: {time}")
        id = vs.addRide(riderEmail, riderLat, riderLon, destLat, destLon, startTime)
        if id == -1: # Constraint violation
            return Response(status=400)
        return str(id)
    except KeyError:
        logger.exception(f"Invalid request: {request} with body >> {request_json}")
        return Response(status=400)

"""
Get information about all rides.
"""
@app.route("/rides", methods=['GET'])
@token_auth.login_required
def getRides():
    """Returns the json string with the pending rides registered with the server

    The list includes the rides that have been assigned to the vehicle and are
    in progress as well as the requests awaiting assignment.
    The rides that were completed or cancelled will not be returned.

    The sample return JSON string will look like:

    [
        {
            "id": 19,
            "tStart": 1614919948,
            "startNode": "(35.77457, -78.67173)",
            "endNode": "(35.7759581, -78.6707059)",
            "pickedUp": "\u0000",
            "arrived": "\u0000",
            "canceled": "\u0000",
            "userEmail": "rider@ncsu.edu",
            "vehicleName": null
        }
    ]

    :return: the json string with the list of :class:`vehicle_util.Ride`
    :rtype: str
    """
    user_response = token_auth.current_user()
    try:
        user_response['email']
    except TypeError:
        return token_auth_error(401)
    return Response(json.dumps(vs.getRides()), mimetype='application/json')

"""
Get information about a ride.
"""
@app.route("/rides/<rideID>", methods=['GET'])
@token_auth.login_required
def getRide(rideID):
    user_response = token_auth.current_user()
    try:
        user_response['email']
    except TypeError:
        return token_auth_error(401)
    ride = vs.findRide(rideID)
    return Response(json.dumps(ride), mimetype='application/json')

"""
Cancels a ride that a user requested
"""
@app.route("/rides/<rideID>", methods=['DELETE'])
@token_auth.login_required
def deleteRide(rideID):
    user_response = token_auth.current_user()
    try:
        user_response['email']
    except TypeError:
        return token_auth_error(401)
    return vs.cancelRide(rideID)

"""
Get information about all vehicles.
"""
@app.route("/vehicles", methods=['GET'])
def getVehicles():
    """Returns the json string with the vehicles registered with the server

    The list includes the vehicles that have been assigned and the vehicles awaiting assignment.

    The sample return JSON string will look like:

    [
        {
            "name": "vehicle1,
            "status": "WAITING",
            "lat": "35.77457",
            "lon": "-78.67173"
        }
    ]

    :return: the json string with the list of :class:`vehicle_util.Vehicle`
    :rtype: str
    """
    return Response(json.dumps(vs.getVehicles()), mimetype='application/json')

"""
Get an assigned ride's vehicle information.
"""
@app.route("/rides/<rideID>/vehicle", methods=['GET'])
@token_auth.login_required
def getRideVehicle(rideID):
    user_response = token_auth.current_user()
    try:
        user_response['email']
    except TypeError:
        return token_auth_error(401)
    ride = vs.findVehicle(rideID)
    return Response(json.dumps(ride), mimetype='application/json')

"""
Get information about all locationNodes.
"""
@app.route("/locationNodes", methods=['GET'])
def getLocationNodes():
    """Returns the json string with the locationNodes registered with the server

    The list includes the name, latitude, and longitude of the locationNodes

    The sample return JSON string will look like:

    [
        {
            "nodeName": 19,
            "lat": 35.77457,
            "lon": -78.67173
        }
    ]

    :return: the json string of the locationNodes
    :rtype: str
    """
    return Response(json.dumps(vs.getLocationNodes()), mimetype='application/json')


"""
Rider confirms their vehicle has picked them up
"""
@app.route("/confirmPickup/<rideID>", methods=['PUT'])
@token_auth.login_required
def confirmPickup(rideID):
    user_response = token_auth.current_user()
    try:
        user_response['email']
    except TypeError:
        return token_auth_error(401)
    return vs.confirmPickup(rideID)

"""
Rider confirms they have arrived at their desired location.
"""
@app.route("/confirmArrival/<rideID>", methods=['PUT'])
@token_auth.login_required
def confirmArrival(rideID):
    user_response = token_auth.current_user()
    try:
        user_response['email']
    except TypeError:
        return token_auth_error(401)
    return vs.confirmArrival(rideID)

@app.route("/signUp", methods=['POST'])
def signUp():
    request_json = request.get_json()
    logger.debug("Request data:")
    logger.debug(request_json)
    try:
        email = request_json['email']
        fname = request_json['fname']
        lname = request_json['lname']
        password = request_json['password']

        logger.debug(f"Adding a user: email: {email}, "\
            f"fname: {fname}, "\
            f"lname: {lname}, "\
            f"password: {password}")
        response = vs.signUp(request_json)
        if response.success:
            logger.debug("Successfully inserted user")
            token = UserUtil().get_token(vs.getUser(email))
            response.results['authToken'] = token
            return Response(json.dumps(response.results), mimetype='application/json')
        return Response(status=409, response=response.message)
    except KeyError:
        logger.exception(f"Invalid request: {request} with body >> {request_json}")
        return Response(status=400, response='Bad request data')

@app.route("/signIn", methods=['POST'])
def signIn():
    request_json = request.get_json()
    logger.debug("Request data:")
    logger.debug(request_json)
    try:
        email = request_json['email']
        password = request_json['password']

        logger.debug(f"Signing in: email: {email}, "\
            f"password: {password}")
        response = vs.signIn(request_json)
        if response.success:
            logger.debug("Successfully signed in")
            token = UserUtil().get_token(vs.getUser(email))
            response.results['authToken'] = token
            return Response(json.dumps(response.results), mimetype='application/json')
        return Response(status=409, response=response.message)
    except KeyError:
        logger.exception(f"Invalid request: {request} with body >> {request_json}")
        return Response(status=400, response='Bad request data')

@app.route('/signOut', methods=['DELETE'])
@token_auth.login_required
def revoke_token():
    user_response = token_auth.current_user()
    try:
        user_response['email']
    except TypeError:
        return token_auth_error(401)
    UserUtil().revoke_token(token_auth.current_user())
    return '', 204

@app.route("/signInGoogle", methods=['POST'])
def signInGoogle():
    request_json = request.get_json()
    logger.debug("Request data:")
    logger.debug(request_json)

    try:
        email = request_json['email']

        logger.debug(f"Signing in with Google: email: {email}")
        response = vs.signInGoogle(request_json)
        if response.success:
            logger.debug("Successfully signed in")
            return Response(json.dumps(response.results, default=str), mimetype='application/json')
        return Response(status=409, response=response.message)
    except KeyError:
        logger.exception(f"Invalid request: {request} with body >> {request_json}")
        return Response(status=400, response='Bad request data')

"""
Get ride history for a particular user
"""
@app.route("/rideHistory/<email>", methods=['GET'])
@token_auth.login_required
def getRideHistory(email):
    user_response = token_auth.current_user()
    try:
        user_response['email']
    except TypeError:
        return token_auth_error(401)
    rideHistory = vs.getRideHistory(email)
    for ride in rideHistory:
        ride['startNode'] = vs.getLocationNodeByCoordinates(ride['startNode'])
        ride['endNode'] = vs.getLocationNodeByCoordinates(ride['endNode'])
        ride['day'] = str(time.strftime('%-m/%-d/%Y', time.localtime(ride['tStart'])))
        ride['duration'] = round((ride['tEnd'] - ride['tStart']) / 60)
        ride['tStart'] = str(time.strftime('%I:%M %p', time.localtime(ride['tStart'])))
        ride['tEnd'] = str(time.strftime('%I:%M %p', time.localtime(ride['tEnd'])))
    return Response(json.dumps(rideHistory), mimetype='application/json')

@app.route("/updateUser", methods=['PUT'])
@token_auth.login_required
def updateUser():
    user_response = token_auth.current_user()
    try:
        user_response['email']
    except TypeError:
        return token_auth_error(401)
    request_json = request.get_json()
    logger.debug("Request data:")
    logger.debug(request_json)
    try:
        oldEmail = request_json['oldEmail']
        email = request_json['email']
        fname = request_json['fname']
        lname = request_json['lname']
        password = request_json['password']
        logger.debug(f"Updating a user: oldEmail: {oldEmail}, "\
                f"email: {email}, "\
                f"fname: {fname}, "\
                f"lname: {lname}, "\
                f"password: {password}")
        response = vs.updateUser(request_json)
        if response.success:
            logger.debug("Successfully updated user")
            return Response(json.dumps(response.results), mimetype='application/json')
        return Response(status=409, response=response.message)
    except KeyError:
        logger.exception(f"Invalid request: {request} with body >> {request_json}")
        return Response(status=400, response='Bad request data')

"""
Get information about a ride.
"""
@app.route("/users/<email>/ride", methods=['GET'])
@token_auth.login_required
def getUserRide(email):
    user_response = token_auth.current_user()
    try:
        user_response['email']
    except TypeError:
        return token_auth_error(401)
    ride = vs.findUserRide(email)
    if ride:
        ride['startNodeText'] = vs.getLocationNodeByCoordinates(ride['startNode'])
        ride['endNodeText'] = vs.getLocationNodeByCoordinates(ride['endNode'])
    return Response(json.dumps(ride), mimetype='application/json')

"""
Main method that starts up the flask API and vehicle server
"""
def main():
        # Start the Vehicle Server. This thread will handle socket connections from Vehicles
        # and the storing of a list of rides
        print("Starting vehicle server")
        vehicleServerThread = threading.Thread(target=vs.run)
        vehicleServerThread.start()

        # And start our flask API. This will handle HTTP requests in a RESTful fashion and
        # allow rides to be added to the queue from the website

        # Use this line if you want to run on the LAN
        app.run(host='0.0.0.0', threaded=True)

        # Use this line if you want to run on localhost
        # app.run(threaded=True)

if __name__ == "__main__":
    main()
